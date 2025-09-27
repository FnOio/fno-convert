import copy
import inspect
import random
import traceback
import ast
import os, sys, shlex, hashlib

from operator import (
    __add__,
    __and__,
    __call__,
    __contains__,
    __eq__,
    __floordiv__,
    __ge__,
    __getitem__,
    __gt__,
    __iadd__,
    __iand__,
    __ifloordiv__,
    __ilshift__,
    __imatmul__,
    __imod__,
    __imul__,
    __invert__,
    __ior__,
    __ipow__,
    __irshift__,
    __isub__,
    __itruediv__,
    __ixor__,
    __le__,
    __lshift__,
    __lt__,
    __matmul__,
    __mod__,
    __mul__,
    __ne__,
    __neg__,
    __not__,
    __or__,
    __pos__,
    __pow__,
    __rshift__,
    __setitem__,
    __sub__,
    __truediv__,
    __xor__,
)

from scalpel.cfg.builder import CFGBuilder

from rdflib import URIRef
from collections import deque

from ..util.mapping import ValueMapping, BranchMapping, MappingNode, MappingStrategy
from ..util.python.importer import Importer
from ..util.python.rewrite import ASTRewriter
from ..builders import PythonBuilder, FnOBuilder
from ..util.python.scope import ScopeState
from ..util.std_kg import STD_KG
from ..util.python.controlflow import PythonSequenceFactory
from ..util.python.ast import for_targets
from ..graph import FnOGraph, get_name
from ..prefix import Prefix
from ..mappers import PythonMapper, FileMapper
from ..executors import PythonExecutor
from ..descriptors import FileDescriptor
from ..util.controlflow import Sequence, Signature, SignatureType


class PythonDescriptor:

    @staticmethod
    def name_node(name: str):
        return ast.Name(id=name, ctx=ast.Load())

    def __init__(self, g: FnOGraph, workdir, max_depth=3) -> None:
        self.g = g
        self.workdir = workdir
        self.executor = PythonExecutor(g)
        self.importer = Importer()
        self.rewriter = ASTRewriter(parse_arg=True)
        self.max_depth = max_depth
        self.fun_cfgs = {}
        self.state = deque()
        self.init_scope()

        self.depth = 0

    def init_scope(self, scope=None, path=None):
        self.scope = ScopeState(scope=scope, path=path)
        if path is not None:
            sys.path.append(os.path.dirname(path))

    def new_scope(self, new_scope, new_path=None):
        # Save current state
        self.state.append(self.scope)
        # Reset to a new blank state
        self.init_scope(new_scope, new_path)

    def restore_scope(self):
        if self.scope.path is not None:
            sys.path.remove(os.path.dirname(self.scope.path))
        if not self.state:
            raise RuntimeError("No saved state to restore.")
        self.scope = self.state.pop()

    def can_describe_cli(self, cmd: str):
        return cmd.startswith("python")

    def describe_cli(self, cmd: str):
        parts = shlex.split(cmd)

        if len(parts) < 2:
            raise Exception("No File stated after 'python' command.")

        fno_rep = FileDescriptor(self.g, self.workdir).describe(parts[1])
        encoded = hashlib.sha256(cmd.encode()).hexdigest()[:8]
        comp_uri = Prefix.base()[f"command{encoded}Composition"]

        # TODO create composition for all fno representations
        for fun_uri, map_uri, _ in fno_rep:
            try:
                argparse_mappings = PythonMapper.parse_args_with_map(
                    self.g, map_uri, parts[2:] if len(parts) >= 2 else []
                )

                mappings = []
                for param, value in argparse_mappings.items():
                    mapfrom = MappingNode().set_constant(value)
                    mapto = MappingNode().set_function_par(fun_uri, param)
                    mappings.append(ValueMapping(mapfrom, mapto))

                FnOBuilder.describe_composition(self.g, comp_uri, mappings)
                FnOBuilder.start(self.g, comp_uri, fun_uri)

                return fun_uri, comp_uri
            except:
                print(
                    f"Unable to create composition for input {parts} with mapping {map_uri}"
                )
                traceback.print_exc()

        raise Exception(f"Unable to create composition of command '{cmd}'")

    def can_describe_object(self, obj):
        return callable(obj)

    def describe_object(self, obj):
        return self.from_function(obj.__name__, obj.__name__, obj)

    def can_describe_file(self, file_path):
        return file_path.endswith(".py")

    def describe_file(self, file_path):
        file_uri = FileMapper.uri(file_path)
        file_name, suff = os.path.splitext(os.path.basename(file_path))
        fun_uri = Prefix.base()[f"{file_name}_main"]
        if not self.g.exists(file_uri):
            ### IMPORT ###
            try:
                self.importer.import_from_file(file_path)
            except Exception as e:
                print(f"Error importing from {file_path}: {e}")
                print(traceback.format_exc())

            ### PARSE SOURCE CODE ###
            with open(file_path, "r") as file:
                source_code = file.read()
            source_code, args = self.rewriter.rewrite(source_code)
            # URI
            comp_uri = URIRef(f"{fun_uri}Composition")

            # FnO Parameters
            parameters = []
            for i, arg in enumerate(args):
                uri = URIRef(f"{fun_uri}Parameter{i}")
                pred = arg["name"].lstrip("-").replace("-", "_")
                type = Prefix.ns("xsd").string
                if "nargs" in arg and arg["nargs"] == "*":
                    FnOBuilder.describe_parameter(self.g, uri, type, pred, False)
                else:
                    FnOBuilder.describe_parameter(self.g, uri, type, pred)
                parameters.append(uri)

            # FnO Output
            output_uri = URIRef(f"{fun_uri}Output")
            output_pred = "output"
            output_type = PythonMapper.any(self.g)
            FnOBuilder.describe_output(self.g, output_uri, output_type, output_pred)

            # FnO Function
            FnOBuilder.describe_function(
                self.g, fun_uri, f"{file_name}{suff}", parameters, [output_uri]
            )

            # FnO Implementation
            PythonBuilder.describe_file(self.g, file_uri, file_path)

            # FnO Mapping
            map_uri = PythonMapper.map_with_parse_args(
                self.g, fun_uri, file_uri, output_uri, args
            )

            # FnO Composition
            self.describe_composition(
                "_", file_path, fun_uri, comp_uri, source_code, alt_name=file_name
            )

            return [(fun_uri, map_uri, file_uri)]

        return [
            (fun_uri, map_uri, file_uri)
            for (map_uri, fun_uri) in self.g.imp_to_fun(file_uri)
        ]

    def from_function(self, name, context, obj, num=0, keywords=[]):

        ### IMPORT ###

        try:
            self.importer.import_from_obj(obj)
        except Exception as e:
            print(f"Error importing from {name}: {e}")
            print(traceback.format_exc())

        ### PARSE SOURCE CODE ###

        path = inspect.getsourcefile(obj)
        src = inspect.getsource(obj)

        # Uri
        fun_uri = self.function_to_rdf(name, context, num, keywords, obj)
        comp_uri = URIRef(f"{fun_uri}Composition")

        # FnO Composition
        self.describe_composition(name, path, fun_uri, comp_uri, src)

        return fun_uri

    def describe_composition(
        self, name, path, fun_uri, comp_uri, source, alt_name=None
    ):

        ### NEW SCOPE ###

        self.new_scope(fun_uri, path)

        ### PARSE SOURCE CODE ###

        try:
            def_cfg = CFGBuilder().build_from_src(name, source)

            for (_, fun_name), fun_cfg in def_cfg.functioncfgs.items():
                if fun_name == name:
                    self.fun_cfgs[fun_uri] = fun_cfg
                    dot = fun_cfg.build_visual("png")
                    dot.render(
                        f"cfg_diagrams/{alt_name if alt_name else fun_name}_cfg_diagram",
                        view=False,
                    )

                    # CFG to Sequence
                    seq = PythonSequenceFactory.from_cfg(fun_cfg)
                    self.describe_sequence(seq, fun_uri, comp_uri)
        except Exception as e:
            print(f"Error: Unable to describe composition of function: {name}")
            traceback.print_exc()

        ### RESTORE SCOPE ###

        self.restore_scope()

    # ---------- Sequence ----------

    def describe_loop(self, loop: Sequence, loop_uri, comp_uri):
        # Collect sequence inputs
        inputs = {
            Prefix.get_name(var): param
            for (param, var) in self.g.get_parameters(loop_uri, include_pred=True)
        }

        # New scope
        self.new_scope(loop_uri)

        # Assign inputs
        self._assign_inputs(loop_uri, inputs)

        # Process signatures
        self._describe_sigs(loop, loop_uri, inputs)

        # Handle loop outputs
        self._map_outputs(loop_uri)

        # Build composition
        FnOBuilder.describe_composition(
            self.g, comp_uri, self.scope.mappings, represents=loop_uri
        )
        if self.scope.start is not None:
            FnOBuilder.start(self.g, comp_uri, self.scope.start)

        self.restore_scope()
        return loop_uri

    def describe_branch(self, seq: Sequence, branch_uri):
        # Branch inputs
        inputs = {
            Prefix.get_name(var): param
            for (param, var) in self.g.get_parameters(branch_uri, include_pred=True)
        }

        # New scope
        self.new_scope(branch_uri)

        # Assign inputs
        self._assign_inputs(branch_uri, inputs)

        # Process signature
        self._describe_sigs(seq, branch_uri, inputs)

        # Map branch outputs
        self._map_outputs(branch_uri)

        mappings = self.scope.mappings
        start = self.scope.start

        self.restore_scope()

        return mappings, start

    def describe_sequence(self, seq: Sequence, seq_uri, comp_uri):
        # Sequence function inputs
        inputs = {
            Prefix.get_name(var): param
            for (param, var) in self.g.get_parameters(seq_uri, include_pred=True)
        }

        # New scope
        self.new_scope(seq_uri)

        # Assign inputs
        self._assign_inputs(seq_uri, inputs)

        # Process signatures
        self._describe_sigs(seq, seq_uri, inputs)

        # Map sequence outputs
        self._map_outputs(seq_uri)

        # Build composition
        FnOBuilder.describe_composition(
            self.g, comp_uri, self.scope.mappings, represents=seq_uri
        )
        if self.scope.start is not None:
            FnOBuilder.start(self.g, comp_uri, self.scope.start)

        self.restore_scope()
        return seq_uri

    # ---------- Sequence Helpers ----------

    def _assign_inputs(self, seq_uri, inputs):
        for var, param in inputs.items():
            var = self.name_node(var)
            mapfrom = MappingNode().set_function_par(seq_uri, param)
            self.handle_assignment(mapfrom, [var])

    def _describe_sigs(self, seq: Sequence, uri, inputs: dict):
        tests = {}
        for sig in seq.sigs:
            if sig.type == SignatureType.FUNCTION:
                for stmt in sig.stmts:
                    self.handle_stmt(stmt)
            elif sig.type == SignatureType.TEST:
                test_output = self.handle_stmt(sig.stmts[0].test)
                tests[sig.id] = test_output
            elif sig.type == SignatureType.ITER:
                iter_output = self.handle_stmt(sig.stmts[0].iter)
                iter_output.set_iteration()
                for i, target in enumerate(for_targets(sig.stmts[0])):
                    iter_output = iter_output.set_strategy(MappingStrategy.GET_ITEM, i)
                    self.handle_assignment(iter_output, [target])
            else:
                sig_uri = self.describe_signature(sig)
                self._map_signature_inputs(sig, sig_uri, uri, inputs, tests=tests)

                self._assign_signature_outputs(sig_uri)
                if sig.type == SignatureType.LOOP:
                    self._handle_loop_feedback(sig, sig_uri)
                self.handle_order(sig_uri)

    def _map_signature_inputs(
        self,
        sig: Signature,
        sig_uri: URIRef,
        input_uri: URIRef,
        inputs: dict[str, URIRef],
        tests: dict[str, MappingNode] = dict(),
    ):
        for var, source in sig.inputs.items():
            if source == "IN":
                # Map from sequence input
                mapfrom = MappingNode().set_function_par(input_uri, inputs[var])
            else:
                # Map from assigned output
                mapfrom = self.handle_stmt(self.name_node(var))

            param = self.g.get_param(sig_uri, var)
            mapto = MappingNode().set_function_par(sig_uri, param)
            self.handle_mapping(mapfrom, mapto)

        if sig.type == SignatureType.BRANCH:
            if sig.test not in tests:
                raise ValueError(f"Function for test signature not found: {sig.test}")
            mapfrom = tests[sig.test]
            test_input = self.g.get_test(sig_uri)
            mapto = MappingNode().set_function_par(sig_uri, test_input)
            self.handle_mapping(mapfrom, mapto)

    def _assign_signature_outputs(self, sig_uri):
        for output, pred in self.g.get_outputs(sig_uri, include_pred=True):
            var = self.name_node(Prefix.get_name(pred))
            mapfrom = MappingNode().set_function_out(sig_uri, output)
            self.handle_assignment(mapfrom, [var])

    def _handle_loop_feedback(self, sig, sig_uri):
        for var in sig.outputs.intersection(sig.inputs.keys()):
            output = self.g.get_output(sig_uri, var)
            mapfrom = MappingNode().set_function_out(sig_uri, output)
            param = self.g.get_param(sig_uri, var)
            mapto = MappingNode().set_function_par(sig_uri, param)
            self.handle_mapping(mapfrom, mapto)

    def _map_outputs(self, uri):
        for output, var in self.g.get_outputs(uri, include_pred=True):
            var_output = self.scope.assignments.get(Prefix.get_name(var))
            if not var_output:
                continue
            mapto = MappingNode().set_function_out(uri, output)
            self.handle_mapping(var_output, mapto)

    # ---------- Signature ----------

    def describe_signature(self, sig: Signature):
        uri = Prefix.base()[sig.id]

        positional = []
        keywords = []

        # Remove module refernces from signature
        sig.inputs = {
            k: v for k, v in sig.inputs.items() if not self.importer.is_module(k)
        }

        for i, input in enumerate(sig.inputs):
            input_uri = URIRef(f"{uri}Parameter{i}")
            FnOBuilder.describe_parameter(
                self.g, input_uri, Prefix.base()["any"], input, True
            )
            positional.append(input_uri)
            keywords.append((input_uri, input))

        outputs = []
        for i, output in enumerate(sig.outputs):
            output_uri = URIRef(f"{uri}Output{i}")
            FnOBuilder.describe_output(self.g, output_uri, Prefix.base()["any"], output)
            outputs.append(output_uri)
        if len(outputs) == 0:
            output_uri = URIRef(f"{uri}Output")
            FnOBuilder.describe_output(
                self.g, output_uri, Prefix.base()["any"], f"{sig.id}Result"
            )
            outputs.append(output_uri)

        if sig.type == SignatureType.FUNCTION or sig.type == SignatureType.ITER:
            FnOBuilder.describe_function(self.g, uri, sig.id, positional, outputs)
        elif sig.type == SignatureType.BRANCH:
            FnOBuilder.describe_branch(self.g, uri, sig.id, positional, outputs)
        elif sig.type == SignatureType.LOOP:
            FnOBuilder.describe_loop(self.g, uri, sig.id, positional, outputs)

        ### MAPPING ###

        FnOBuilder.describe_mapping(
            self.g,
            uri,
            f_name=sig.id,
            positional=positional,
            keyword=keywords,
            output=outputs[0] if len(outputs) == 1 else None,
            unpack=outputs if len(outputs) > 1 else [],
        )

        ### FUNCTION ###
        if sig.type == SignatureType.FUNCTION:
            comp_uri = URIRef(f"{uri}Composition")
            if sig.seq:
                self.describe_sequence(sig.seq, uri, comp_uri)
            elif sig.stmts:
                self.new_scope(uri)
                self.describe_body(sig.stmts, uri)
                FnOBuilder.describe_composition(
                    self.g, comp_uri, self.scope.mappings, uri
                )
                if self.scope.start is not None:
                    FnOBuilder.start(self.g, comp_uri, self.scope.start)
                self.restore_scope()

        ### BRANCH ###
        if sig.type == SignatureType.BRANCH:
            test = MappingNode().set_function_par(uri, self.g.get_test(uri))
            comp_uri = URIRef(f"{uri}Composition")
            mappings, start = self.describe_branch(sig.branch.true_seq, uri)
            branches = [BranchMapping(mappings, test, True, start)]
            if sig.branch.false_seq:
                mappings, start = self.describe_branch(sig.branch.false_seq, uri)
                branches.append(BranchMapping(mappings, test, False, start))
            FnOBuilder.describe_composition(self.g, comp_uri, branches, represents=uri)

        ### LOOP ###
        if sig.type == SignatureType.LOOP and sig.seq:
            comp_uri = URIRef(f"{uri}Composition")
            self.describe_loop(sig.seq, uri, comp_uri)

        return uri

    def describe_body(self, stmts: list[ast.stmt], fun_uri):

        # assign inputs
        for param, pred in self.g.get_parameters(fun_uri, include_pred=True):
            mapfrom = MappingNode().set_function_par(fun_uri, param)
            var = self.name_node(Prefix.get_name(pred))
            self.handle_assignment(mapfrom, [var])

        for stmt in stmts:
            self.handle_stmt(stmt)

        # map outputs
        for output, pred in self.g.get_outputs(fun_uri, include_pred=True):
            var = self.name_node(Prefix.get_name(pred))
            mapfrom = self.handle_stmt(var)
            mapto = MappingNode().set_function_out(fun_uri, output)
            self.handle_mapping(mapfrom, mapto)

    def get_type(self, var):
        """
        Retrieves the stored type of a given variable, if available.

        This method attempts to find and return the type of a variable that has been propagated
        through the system. It first checks if the type is directly stored in `self.scope.var_types`.
        If the type is not found, it checks if the variable is assigned to the output of a function
        that has a stored type.

        Parameters:
        -----------
        var : Any
            The variable for which the type is to be retrieved.

        Returns:
        --------
        type or None
            The stored type of the variable if available; otherwise, None.
        """

        # Check if the type of the variable is directly stored
        if var in self.scope.var_types:
            # Return None if no type annotation was found (inspect._empty)
            if self.scope.var_types[var] is inspect._empty:
                return None
            return self.scope.var_types[var]

        # Check if the variable is assigned to the output of a function with a stored type
        if var in self.scope.assignments:
            return self.get_type(self.scope.assignments[var].get_value())

        # Return None if no type information is found
        return None

    def handle_mapping(self, mapfrom, mapto):
        self.scope.mappings.append(ValueMapping(mapfrom, mapto))

    def handle_order(self, call):
        if self.scope.prev_function[0] is None:
            self.scope.start = call
        else:
            FnOBuilder.link(self.g, *self.scope.prev_function, call)
        self.scope.prev_function = (call, "next")

    def handle_stmt(self, stmt):
        if isinstance(stmt, ast.Expr):
            return self.handle_stmt(stmt.value)
        if isinstance(stmt, ast.Constant):
            return self.handle_constant(stmt.value)
        elif isinstance(stmt, ast.Name):
            return self.handle_name(stmt.id)
        elif isinstance(stmt, ast.Attribute):
            return self.handle_attr(stmt.attr, stmt.value)
        elif isinstance(stmt, ast.List):
            return self.handle_list(stmt.elts)
        elif isinstance(stmt, ast.ListComp):
            return self.handle_listcomp(stmt)
        elif isinstance(stmt, ast.Dict):
            return self.handle_dict(stmt.keys, stmt.values)
        elif isinstance(stmt, ast.DictComp):
            return self.handle_dictcomp(stmt)
        elif isinstance(stmt, ast.Tuple):
            return self.handle_tuple(stmt.elts)
        elif isinstance(stmt, ast.JoinedStr):
            return self.handle_strjoin(stmt.values)
        elif isinstance(stmt, ast.FormattedValue):
            return self.handle_format(stmt.value, stmt.conversion, stmt.format_spec)
        elif isinstance(stmt, ast.Assign):
            return self.handle_assignment(stmt.value, stmt.targets)
        elif isinstance(stmt, ast.AugAssign):
            return self.handle_augassignment(stmt.target, stmt.op, stmt.value)
        elif isinstance(stmt, ast.Call):
            return self.handle_call(stmt.func, stmt.args, stmt.keywords)
        elif isinstance(stmt, ast.UnaryOp):
            return self.handle_unop(stmt.op, stmt.operand)
        elif isinstance(stmt, ast.BinOp):
            return self.handle_binop(stmt.op, stmt.left, stmt.right)
        elif isinstance(stmt, ast.BoolOp):
            return self.handle_boolop(stmt.op, stmt.values)
        elif isinstance(stmt, ast.Compare):
            return self.handle_compare(stmt.left, stmt.ops, stmt.comparators)
        elif isinstance(stmt, ast.IfExp):
            return self.handle_ifexpr(stmt.test, stmt.body, stmt.orelse)
        elif isinstance(stmt, ast.Slice):
            return self.handle_slice(stmt.lower, stmt.upper, stmt.step)
        elif isinstance(stmt, ast.Subscript):
            return self.handle_subscript(stmt.value, stmt.slice)
        elif isinstance(stmt, ast.Return):
            return self.handle_return(stmt.value)
        elif isinstance(stmt, ast.Import):
            self.importer.handle_import(*stmt.names)
            return
        elif isinstance(stmt, ast.ImportFrom):
            self.importer.handle_import_from(stmt.module, *stmt.names)
            return
        elif isinstance(stmt, (ast.FunctionDef, ast.ClassDef)):
            module_name = inspect.getmodulename(self.scope.path)
            if self.importer.is_module(module_name):
                self.importer.handle_import_from(
                    module_name, ast.alias(stmt.name), skip=False
                )
            return
        elif isinstance(stmt, MappingNode):
            return stmt
        raise Exception(f"Cannot handle node of type {type(stmt)}")

    def handle_constant(self, value) -> MappingNode:
        """
        Handles an AST constant node.

        This method simply returns the constant value without any additional context or transformation.

        Parameters:
        -----------
        value : Any
            The constant value to be handled.

        Returns:
        --------
        MappingNode
            A MappingNode containing the constant
        """
        return MappingNode().set_constant(PythonMapper.value_to_term(self.g, value))

    def handle_name(self, id):
        """
        Handles a AST name node by resolving the identifier to its meaning within the system.

        This method attempts to resolve a variable name by checking if it is assigned to a function output,
        an imported function, class, or module. It provides meaning to the string value contained within
        by looking at assigned values or imported objects.

        Parameters:
        -----------
        id : str
            The identifier of the variable to be handled.

        Returns:
        --------
        MappingNode
            A mapping node containing:
            - None or the node name (if applicable)
            - The assigned value/output

        Workflow:
        ---------
        1. Checks if the identifier is assigned to a function output.
        2. Checks if the identifier references an imported object.
        3. Adds full description if the object is callable.
        4. Returns the object or identifier without context.
        """
        # Check if the variable is assigned to a function output
        if id in self.scope.assignments:
            mapfrom = self.scope.assignments[id]
            return mapfrom.from_variable(id)

        # Check if it references an imported object
        obj = self.importer.get_object(id)
        if callable(obj):
            # Add full description for extra provenance
            if obj.__name__ not in self.g.f_counter:
                self.describe_resource(obj)
            # Return the object without context
            return MappingNode().set_constant(PythonMapper.value_to_term(self.g, obj))

        # Check if it references a module
        mod = self.importer.get_module(id)
        if mod:
            return MappingNode().set_constant(PythonMapper.value_to_term(self.g, mod))

        # Return the identifier without context if no resolution is found
        return MappingNode().set_constant(PythonMapper.value_to_term(self.g, id))

    def handle_augassignment(self, target, op, value):
        self.handle_assignment(ast.BinOp(target, op, value), [target])

    def handle_assignment(self, value, targets):
        """
        Handles an AST assignment node which assigns a value to one or multiple targets.

        This method correctly handles various assignment scenarios including augmented assigns disguised as normal assigns,
        merges assignments made in different conditional bodies using if-expr, and supports indexing and unpacking.

        Parameters:
        -----------
        value : ast.AST
            The value node to be assigned to the targets.

        targets : list of ast.AST
            The target nodes to which the value is assigned. This can be a list of variables, subscript nodes, or tuples.

        Workflow:
        ---------
        1. Handle binary operations within the value if the target is used in the operation.
        2. Handle the value node to generate its RDF representation.
        3. For each target:
            - If it is a variable name:
                - Handle conditional assignments within if-then-else bodies if present.
                - Map the variable name to the value output and propagate the type if available.
            - If it is a subscript, handle the subscript assignment appropriately.
            - If it is a tuple, handle unpacking by assigning each element of the tuple.
        """

        # TODO Handle binary operations within the value
        for target in targets:
            if isinstance(target, ast.Name):
                # Handle assignment to variable
                target = get_name(target.id)
                value_output = self.handle_stmt(value)
                self.scope.assignments[target] = value_output

                # Copy the type if the assigned value has a type
                val_type = self.get_type(value_output.get_value())
                if val_type:
                    self.scope.var_types[target] = val_type

            elif isinstance(target, ast.Subscript):
                # Handle assignment to subscript nodes
                value_output = self.handle_stmt(value)
                subscript_output = self.handle_subscript(
                    target.value, target.slice, value_output
                )
                self.handle_assignment(subscript_output, [target.value])

            elif isinstance(target, ast.Tuple):
                # Handle unpacking assignments
                value_output = self.handle_stmt(value)
                for i, el in enumerate(target.elts):
                    subscript_output = self.handle_subscript(
                        value_output, ast.Constant(value=i)
                    )
                    self.handle_assignment(subscript_output, [el])

    def handle_return(self, value):
        if value:
            value_output = self.handle_stmt(value)
        else:
            value_output = MappingNode().set_constant(None)

        try:
            scope = self.scope.scope
            default_output = self.g.get_output(self.scope.scope)
        except Exception as e:
            print(
                f"Encountered return statement when no default return mapping defined for {scope}"
            )
            raise e

        mapto = MappingNode().set_function_out(scope, default_output)
        self.handle_mapping(value_output, mapto)

    def handle_call(self, func, args, kargs):
        """
        Handles an AST Call node to obtain the corresponding function object and process the call.

        This method identifies the function object being called, including methods, attributes, or built-in functions.
        It then invokes the handle_func method to process the call and generate the RDF representation.

        Parameters:
        -----------
        func : ast.AST
            The AST node representing the function being called.
        args : list
            The arguments passed to the function call.
        kargs : list
            The keyword arguments passed to the function call.

        Returns:
        --------
        Any
            The result of the handle_func method call, which processes the function call.

        Workflow:
        ---------
        1. Initialize variables to store information about the function object, such as name, context, and type.
        2. Identify the type of function call:
            - Attribute call: If the function is called as an attribute of an object.
            - Name call: If the function is a simple name.
            - Nested call: If the function call is nested within another call.
        3. Determine the function object based on the type of call:
            - For attribute calls: Get the function object from the attribute or method.
            - For name calls: Retrieve the function object from the importer or built-ins.
            - For nested calls: Obtain the function object from the type of the output of the nested call.
        4. Invoke the handle_func method with the appropriate parameters to process the function call and generate the RDF representation.
        5. Return the result of the handle_func method call.
        """

        ### FUNCTION OBJECT ###

        name = None
        context = None
        func_object = None
        value_output = None
        value_type = None
        static = None

        # attribute call
        if isinstance(func, ast.Attribute):
            attr = str(func.attr)
            name = str.strip(attr, "_")
            context = name

            value_output = self.handle_stmt(func.value)
            if value_output.from_term():
                raw_value = PythonMapper.term_to_value(self.g, value_output.get_value())
                value_type = type(raw_value)
            else:
                raw_value = value_output.get_value()
                value_type = self.get_type(raw_value)

            # The value is an imported object
            if callable(raw_value):
                func_object = getattr(raw_value, attr, None)
                if hasattr(raw_value, "__name__"):
                    context = f"{getattr(raw_value, '__name__')}_{name}"
                else:
                    context = name

            # If the value is called on an instance, try to get the object from that type
            elif not isinstance(value_type, str) and value_type is not None:
                func_object = getattr(value_type, attr, None)
                if hasattr(value_type, "__name__"):
                    context = f"{getattr(value_type, '__name__')}_{name}"
                else:
                    context = name
                static = False

            # If the value is called on a module, get the object from that module
            elif self.importer.is_module(raw_value):
                func_object = self.importer.object_from_module(raw_value, attr)
                context = f"{raw_value.__name__}_{name}"
                value_type = False

            # If the value is called on a class, get the object from that class
            elif get_name(value_output.get_value()) in self.importer.objects():
                attr_object = self.importer.get_object(
                    get_name(value_output.get_value())
                )
                func_object = getattr(attr_object, attr, None)
                if hasattr(attr_object, "__name__"):
                    context = f"{getattr(attr_object, '__name__')}_{name}"
                else:
                    context = name
                value_type = False
                static = True

            # Create an applied function with internal body
            if func_object is None:
                call_output = self.handle_func(
                    name,
                    context,
                    None,
                    args,
                    kargs,
                    value_output,
                    value_type,
                    False,
                )
                applied = call_output.context

                """self.new_scope(applied)
                
                try:
                    # getattr call
                    fun_uri = self.g.check_call(applied)
                    value_input = MappingNode().set_function_par(fun_uri, self.g.get_param(fun_uri, 'self'))
                    attr_output = self.handle_func("getattr", "getattr", getattr, [value_input, self.name_node(attr)])
                    
                    # call on attr
                    mapping = self.g.get_mapping(fun_uri, first=True)
                    positional = self.g.get_positionals(mapping)
                    varpos = self.g.get_list_mappings(mapping)
                    varkey = self.g.get_varkeyword(mapping)
                    
                    ## map arguments to correct applied inputs
                    new_args = [attr_output]
                    new_kargs = []
                    
                    for i, _ in enumerate(args):
                        if i < len(positional):
                            par = positional[i]
                            new_args.append(MappingNode().set_function_par(fun_uri, par))
                        else:
                            break
                            
                    if len(varpos) == 1:
                        new_args.append(MappingNode().set_function_par(fun_uri, varpos[0]))
                        
                    for karg in kargs:
                        par = self.g.get_param(fun_uri, karg.arg)
                        if par is not None:
                            new_karg = ast.keyword(arg=karg.arg, value=MappingNode().set_function_par(fun_uri, par))
                            new_kargs.append(new_karg)
                            
                    if len(varkey) == 1:
                        new_args.append(MappingNode().set_function_par(fun_uri, varkey[0]))
                        
                    attrcall_output = self.handle_func("call", "call", __call__, new_args, new_kargs)
                    
                    ## map output
                    fun_output = MappingNode().set_function_out(fun_uri, self.g.get_output(fun_uri))
                    self.handle_mapping(attrcall_output, fun_output)
                    
                    fun_selfoutput = MappingNode().set_function_out(fun_uri, self.g.get_output(fun_uri, 'self'))
                    self.handle_mapping(value_input, fun_selfoutput)
                    
                    # create composition
                    comp_uri =  URIRef(f"{applied}Composition")
                    FnOBuilder.describe_composition(self.g, comp_uri, self.scope.mappings, represents=applied)
                    FnOBuilder.start(self.g, comp_uri, attr_output.context)
                except Exception as e:
                    self.g.log()
                    self.restore_scope()
                    raise e
                
                self.restore_scope()"""

                return call_output

        # the function is called on the output of another function
        elif isinstance(func, ast.Call):
            value_output = self.handle_stmt(func)
            value_type = self.get_type(value_output.get_value())
            name = "call"
            if value_type is not None:
                context = f"{value_type.__name__}_call"
            else:
                context = f"{Prefix.get_name(value_output.context)}_call"
            func_object = getattr(
                value_type, "call", getattr(value_type, "__call__", None)
            )

        if isinstance(func, ast.Name):
            name = func.id
            context = name
            func_object = self.importer.objects().get(name)

            if func_object is None:
                func_object = self.importer.object_from_builtins(name)

        return self.handle_func(
            name,
            context,
            func_object,
            args,
            kargs,
            value_output,
            value_type,
            static,
        )

    def handle_func(
        self,
        name,
        context,
        func_object=None,
        args=[],
        kargs=[],
        value_output=None,
        value_type=None,
        static=None,
    ):
        """
        Handles the processing of a function call, including generating its RDF representation and composing function descriptions.

        This method manages the creation of function descriptions, handling of function composition,
        and mapping of function arguments to RDF nodes.
        It also updates the RDF graph with the function composition and ensures that function outputs are properly mapped.

        Parameters:
        -----------
        name : str
            The name of the function.
        context : str
            The context in which the function is called.
        func_object : callable or None
            The function object corresponding to the function being called.
        args : list, optional
            The positional arguments passed to the function call. Default is an empty list.
        kargs : list, optional
            The keyword arguments passed to the function call. Default is an empty list.
        value_name : tuple or None, optional
            A tuple containing the context and output URIs on which the function is called, if applicable. Default is None.
        value_type : type or None, optional
            The type of the object on which the function is called, if applicable. Default is None.
        static : bool or None, optional
            Indicates whether the function call is static (True), dynamic (False), or not applicable (None). Default is None.
        func : ast.AST or None, optional
            The AST node representing the function call, if available. Default is None.

        Returns:
        --------
        tuple
            A tuple containing the URI of the function call and the URI for the function output.

        Workflow:
        ---------
        1. Check if a function description already exists in the RDF graph. If not, create a new one.
        2. Determine if the function call is recursive or defined by the user. If not, create its RDF representation.
        3. Determine the function composition by mapping arguments to RDF nodes and update the RDF graph accordingly.
        4. Handle function outputs and potential variable changes resulting from the function call.
        5. Return the URI of the function call and its output.
        """

        ### FUNCTION DESCRIPTION ###

        # Don't create function description twice
        if context not in self.g.f_counter:
            self.g.f_counter[context] = 1

            # Not a recursive call
            if not context == get_name(self.scope.scope):
                # Do not describe composition of functions that were not defined by the user
                if func_object is None or self.importer.skip(func_object):
                    self.function_to_rdf(
                        name, context, len(args), kargs, func_object, value_type, static
                    )
                # Do not go deeper then necesary
                elif self.depth < self.max_depth:
                    self.depth += 1
                    self.from_function(name, context, func_object, len(args), kargs)
                    self.depth -= 1
                else:
                    self.function_to_rdf(
                        name, context, len(args), kargs, func_object, value_type, static
                    )
        else:
            self.g.f_counter[context] += 1

        ### FUNCTION COMPOSITION ###

        f = self.g.get_function(context)
        call = URIRef(f"{f}_{self.g.f_counter[context]}")
        FnOBuilder.apply(self.g, call, f)

        # Get usefull information from description
        try:
            self_par = self.g.get_param(f, "self")
        except:
            self_par = None
        output = self.g.get_output(f)
        f_output = MappingNode().set_function_out(call, output)

        # Create mappings for composition
        # TODO what if multiple mappings are present?
        # TODO store the created mapping and imp if a function is made to avoid ambiguity
        mapping = self.g.get_mapping(f, first=True)
        positional = self.g.get_positionals(mapping)
        varpos = self.g.get_list_mappings(mapping)
        varkey = self.g.get_varkeyword(mapping)

        # Assign self if called upon a value
        if self_par:
            mapto = MappingNode().set_function_par(call, self_par)
            self.handle_mapping(value_output, mapto)

            if value_output.var:
                self.handle_assignment(f_output, [self.name_node(value_output.var)])

        # first map all positional arguments
        # If no more positional arguments, add to variable positional argument
        for i, arg in enumerate(args):
            mapfrom = self.handle_stmt(arg)
            if i < len(positional):
                par = positional[i]
                mapto = MappingNode().set_function_par(call, par)
                self.handle_mapping(mapfrom, mapto)
            elif len(varpos) == 1:
                mapto = (
                    MappingNode()
                    .set_function_par(call, varpos[0])
                    .set_strategy("toList", i - len(positional))
                )
                self.handle_mapping(mapfrom, mapto)

        # Then map all keywords arguments to the parameter with the same predicate
        # If no such parameter exists add it to the variable keyword parameter
        for karg in kargs:
            mapfrom = self.handle_stmt(karg.value)
            par = self.g.get_param(f, karg.arg)
            if par is not None:
                mapto = MappingNode().set_function_par(call, par)
                self.handle_mapping(mapfrom, mapto)
            elif len(varkey) == 1:
                mapto = (
                    MappingNode()
                    .set_function_par(call, varkey[0])
                    .set_strategy("toDictionary", karg.arg)
                )
                self.handle_mapping(mapfrom, mapto)

        self.handle_order(call)

        return f_output

    def handle_attr(self, attr, value):
        """
        Handles an AST attribute node using a standard description format.

        This method processes an attribute node by creating a function description if it does not exist,
        generating an RDF representation of the attribute access, and handling the attribute and value
        nodes appropriately.

        Parameters:
        -----------
        attr : ast.AST or str
            The attribute node or a string representing the attribute to be handled.

        value : ast.AST
            The value node to which the attribute belongs.

        Returns:
        --------
        tuple
            A tuple containing:
            - The URIRef of the function call representing the attribute access.
            - The URI of the attribute output in the RDF graph.

        Workflow:
        ---------
        1. Create a function description for the attribute if it does not exist.
        2. Generate a unique URI for the attribute access call.
        3. Handle the value node to determine if it comes from an imported module.
        4. Convert simple string attributes to AST Name nodes if necessary.
        5. Handle the attribute and value nodes to generate their RDF representations.
        6. Describe the composition of the attribute access in the RDF graph.
        """
        name = str.strip(attr, "_")
        context = name

        value_output = self.handle_stmt(value)

        call_output = self.handle_func(name, context, None, [value_output])
        applied = call_output.context

        self.new_scope(applied)

        try:
            # getattr call
            fun_uri = self.g.check_call(applied)
            value_input = MappingNode().set_function_par(
                fun_uri, self.g.get_parameter_at(fun_uri, 0)
            )
            attr_output = self.handle_func(
                "getattr", "getattr", getattr, [value_input, self.name_node(attr)]
            )

            ## map output
            fun_output = MappingNode().set_function_out(
                fun_uri, self.g.get_output(fun_uri)
            )
            self.handle_mapping(attr_output, fun_output)

            # create composition
            comp_uri = URIRef(f"{applied}Composition")
            FnOBuilder.describe_composition(
                self.g, comp_uri, self.scope.mappings, represents=applied
            )
            FnOBuilder.start(self.g, comp_uri, attr_output.context)
        except Exception as e:
            self.restore_scope()
            raise e

        self.restore_scope()

        return call_output

    def handle_slice(self, lower, upper, step):
        """
        Handles an AST slice node using a standard function description.

        This method processes a slice node by creating a function description for the slice,
        generating an RDF representation of the slice operation, and handling the lower, upper,
        and step components of the slice appropriately.

        Parameters:
        -----------
        lower : ast.AST or None
            The lower bound of the slice. Can be None if no lower bound is specified.

        upper : ast.AST or None
            The upper bound of the slice. Can be None if no upper bound is specified.

        step : ast.AST or None
            The step of the slice. Can be None if no step is specified.

        Returns:
        --------
        tuple
            A tuple containing:
            - The URIRef of the function call representing the slice operation.
            - The URI of the slice output in the RDF graph.

        Workflow:
        ---------
        1. Create a function description for the slice if it does not exist.
        2. Generate a unique URI for the slice operation call.
        3. Handle the lower, upper, and step nodes to generate their RDF representations.
        4. Describe the composition of the slice operation in the RDF graph.
        """
        """context = "slice"
        s = Prefix.cf()[context]
        if context not in self.g.f_counter:
            self.g.f_counter[context] = 1
            self.g += STD_KG[s]
        else:
            self.g.f_counter[context] += 1

        f = Prefix.cf()[context]
        call = URIRef(f"{f}_{self.g.f_counter[context]}")
        FnOBuilder.apply(self.g, call, f)"""

        # Handle the lower, upper, and step components of the slice
        lower_output = (
            self.handle_stmt(lower)
            if lower
            else MappingNode().set_constant(PythonMapper.value_to_term(self.g, None))
        )
        upper_output = (
            self.handle_stmt(upper)
            if upper
            else MappingNode().set_constant(PythonMapper.value_to_term(self.g, None))
        )
        step_output = (
            self.handle_stmt(step)
            if step
            else MappingNode().set_constant(PythonMapper.value_to_term(self.g, None))
        )

        return self.handle_func(
            "slice", "slice", slice, [lower_output, upper_output, step_output]
        )

        mapto = MappingNode().set_function_par(call, Prefix.cf()["LowerIndexParameter"])
        self.handle_mapping(lower_output, mapto)

        mapto = MappingNode().set_function_par(call, Prefix.cf()["UpperIndexParameter"])
        self.handle_mapping(upper_output, mapto)

        mapto = MappingNode().set_function_par(call, Prefix.cf()["StepParameter"])
        self.handle_mapping(step_output, mapto)

        self.handle_order(call)

        return MappingNode().set_function_out(call, Prefix.cf()["SliceOutput"])

    def handle_subscript(self, value, index, assign=None):
        """
        Handles an AST subscript node, representing indexing using the __getitem__ and __setitem__ functions.

        This method processes a subscript node by determining whether it represents a get or set operation,
        handling the index node, and then calling the appropriate function with the correct arguments.

        Parameters:
        -----------
        value : ast.AST
            The value node that is being indexed.

        index : ast.AST
            The index node that specifies the position or range within the value.

        assign : ast.AST or None, optional
            The value to be assigned if this is a set operation. If None, the operation is assumed to be a get operation.

        Returns:
        --------
        Any
            The result of the handle_func method call, which processes the subscript operation.

        Workflow:
        ---------
        1. Handle the index node to generate its RDF representation.
        2. Determine if the operation is a get or set operation based on the presence of the assign parameter.
        3. Prepare the function name, context, and arguments for the corresponding indexing function.
        4. Call the handle_func method with the appropriate parameters to process the subscript operation.
        """

        # Determine the function and context based on whether this is a get or set operation
        f = __setitem__ if assign else __getitem__
        name = f.__name__
        context = f.__name__

        args = [value, index]

        if assign:
            args.append(assign)

        # Call the handle_func method with the appropriate parameters
        return self.handle_func(name, context, f, args)

    def handle_list(self, elts):
        """
        Handles an AST node representing a list, generating its RDF representation and managing element assignments.

        This method creates a description for a list, assigns elements to it, and updates the RDF graph accordingly.
        It also ensures that the list type is properly propagated.

        Parameters:
        -----------
        elements : list of ast.AST
            The elements to be included in the list. Each element is processed to generate its RDF representation.

        Returns:
        --------
        tuple
            A tuple containing the URI of the list call and the URI for the list output.

        Workflow:
        ---------
        1. Check if the "list" function has been encountered before and update its counter.
        2. Create a URI for the list function and apply it to the RDF graph.
        3. Handle each element in the list to generate its RDF representation and map it to the list.
        4. Describe the composition of the list in the RDF graph using `FnODescriptor`.
        5. Set the type of the list output to `list`.
        6. Return the URI of the list call and the list output.
        """
        # Check if the "list" function has been encountered before and update its counter
        elements = Prefix.py()["Elements"]
        output = Prefix.py()["ListOutput"]

        if "list" not in self.g.f_counter:
            # Create FnO Function
            self.g.f_counter["list"] = 1
            s = Prefix.py()["list"]
            self.g += STD_KG[s]

            # Python implementation
            imp_uri = PythonMapper.obj_to_fno(self.g, list)

            # Mapping
            FnOBuilder.describe_mapping(
                self.g,
                s,
                imp_uri,
                "list",
                positional=[elements],
                args={elements},
                output=output,
            )
        else:
            self.g.f_counter["list"] += 1

        # Create a URI for the list function and apply it to the RDF graph
        f = Prefix.py()["list"]
        call = Prefix.base()[f"list_{self.g.f_counter['list']}"]
        FnOBuilder.apply(self.g, call, f)

        # Handle each element in the list to generate its RDF representation and map it to the list
        for i, el in enumerate(elts):
            el_output = self.handle_stmt(el)
            mapto = (
                MappingNode()
                .set_function_par(call, Prefix.py()["Elements"])
                .set_strategy("toList", i)
            )
            self.handle_mapping(el_output, mapto)

        # Set the type of the list output to `list`
        self.scope.var_types[Prefix.py()["ListOutput"]] = list

        # Return the URI of the list call and the list output
        self.handle_order(call)

        return MappingNode().set_function_out(call, Prefix.py()["ListOutput"])

    def handle_listcomp(self, comp: ast.ListComp):
        if "listcomp" not in self.g.f_counter:
            self.g.f_counter["listcomp"] = 1
        name = f"listcomp_{self.g.f_counter["listcomp"]}"
        self.g.f_counter["listcomp"] += 1
        seq = PythonSequenceFactory.from_comp(comp, name)
        sig = Signature.from_sequence(seq)
        sig.outputs.add("list")
        call = self.describe_signature(sig)

        # Map the inputs from variables
        for param, var in self.g.get_parameters(call, include_pred=True):
            var = self.name_node(Prefix.get_name(var))
            var_output = self.handle_stmt(var)
            mapto = MappingNode().set_function_par(call, param)
            self.handle_mapping(var_output, mapto)

        self.handle_order(call)

        return MappingNode().set_function_out(call, self.g.get_output(call))

    def handle_tuple(self, elts):
        """
        Handles an AST node representing a tuple, generating its RDF representation and managing element assignments.

        This method creates a description for a tuple, assigns elements to it, and updates the RDF graph accordingly.
        It also ensures that the tuple type is properly propagated.

        Parameters:
        -----------
        elts : list of ast.AST
            The elements to be included in the tuple. Each element is processed to generate its RDF representation.

        Returns:
        --------
        tuple
            A tuple containing the URI of the tuple call and the URI for the tuple output.

        Workflow:
        ---------
        1. Check if the "tuple" function has been encountered before and update its counter.
        2. Create a URI for the tuple function and apply it to the RDF graph.
        3. Handle each element in the tuple to generate its RDF representation and map it to the tuple.
        4. Describe the composition of the tuple in the RDF graph using `FnODescriptor`.
        5. Set the type of the tuple output to `tuple`.
        6. Return the URI of the tuple call and the tuple output.

        Assumptions:
        ------------
        This method assumes that `self.g.f_counter`, `self.f_generator`, `to_uri`, `PrefixMap.pf()`, `URIRef`, `FnODescriptor`,
        `self.g`, `self.handle_node`, `self._scope`, and `self.scope.var_types` are properly defined and accessible within the class or module.
        """

        context = "tuple"
        s = Prefix.py()[context]
        output = Prefix.py()["TupleOutput"]
        elements = Prefix.py()["Elements"]

        if context not in self.g.f_counter:
            self.g.f_counter[context] = 1
            self.g += STD_KG[s]

            # Map to 'tuple' implementation
            imp = PythonMapper.obj_to_fno(self.g, tuple, "tuple")
            FnOBuilder.describe_mapping(
                self.g,
                s,
                imp,
                "tuple",
                positional=[elements],
                args={elements},
                output=output,
            )
        else:
            self.g.f_counter[context] += 1

        f = Prefix.py()[context]
        call = URIRef(f"{f}_{self.g.f_counter[context]}")
        FnOBuilder.apply(self.g, call, f)

        for i, el in enumerate(elts):
            el_output = self.handle_stmt(el)
            mapto = (
                MappingNode().set_function_par(call, elements).set_strategy("toList", i)
            )
            self.handle_mapping(el_output, mapto)

        # TupleOutput has type tuple
        self.scope.var_types[output] = tuple

        self.handle_order(call)

        return MappingNode().set_function_out(call, output)

    def handle_dict(self, keys, values):
        """
        Handles an AST node representing a dictionary, generating its RDF representation and managing key-value assignments.

        This method creates a description for a dictionary, assigns key-value pairs to it, and updates the RDF graph accordingly.
        It also ensures that the dictionary type is properly propagated.

        Parameters:
        -----------
        keys : list of ast.AST
            The key nodes of the dictionary.
        values : list of ast.AST
            The value nodes corresponding to the keys.

        Returns:
        --------
        tuple
            A tuple containing the URI of the dictionary call and the URI for the dictionary output.

        Workflow:
        ---------
        1. Check if the "dict" function has been encountered before and update its counter.
        2. Create a URI for the dict function and apply it to the RDF graph.
        3. Handle each key-value pair in the dictionary to generate its RDF representation and map it to the dictionary.
        4. Describe the composition of the dictionary in the RDF graph using `FnODescriptor`.
        5. Set the type of the dictionary output to `dict`.
        6. Return the URI of the dict call and the dict output.

        Assumptions:
        ------------
        This method assumes that `self.g.f_counter`, `self.f_generator`, `to_uri`, `PrefixMap.pf()`, `URIRef`, `FnODescriptor`,
        `self.g`, `self.handle_tuple`, `self._scope`, and `self.scope.var_types` are properly defined and accessible within the class or module.
        """
        context = "dict"
        s = Prefix.py()[context]
        pairs = Prefix.py()["Pairs"]
        output = Prefix.py()["DictOutput"]

        if context not in self.g.f_counter:
            self.g.f_counter[context] = 1
            self.g += STD_KG[s]

            # Map to 'dict' implementation
            imp = PythonMapper.obj_to_fno(self.g, dict, "dict")
            FnOBuilder.describe_mapping(
                self.g, s, imp, "dict", positional=[pairs], args={pairs}, output=output
            )
        else:
            self.g.f_counter[context] += 1

        f = Prefix.py()["dict"]
        call = URIRef(f"{f}_{self.g.f_counter['dict']}")
        FnOBuilder.apply(self.g, call, f)

        for i, (key, val) in enumerate(zip(keys, values)):
            pair_output = self.handle_tuple([key, val])
            mapto = (
                MappingNode().set_function_par(call, pairs).set_strategy("toList", i)
            )
            self.handle_mapping(pair_output, mapto)

        # DictOutput has type dict
        self.scope.var_types[Prefix.py()["DictOutput"]] = dict

        self.handle_order(call)

        return MappingNode().set_function_out(call, Prefix.py()["DictOutput"])

    def handle_dictcomp(self, comp: ast.DictComp):
        if "dictcomp" not in self.g.f_counter:
            self.g.f_counter["dictcomp"] = 1
        name = f"dictcomp_{self.g.f_counter["dictcomp"]}"
        self.g.f_counter["dictcomp"] += 1
        seq = PythonSequenceFactory.from_comp(comp, name)
        sig = Signature.from_sequence(seq)
        sig.outputs.add("dict")
        call = self.describe_signature(sig)

        # Map the inputs from variables
        for param, var in self.g.get_parameters(call, include_pred=True):
            var = self.name_node(Prefix.get_name(var))
            var_output = self.handle_stmt(var)
            mapto = MappingNode().set_function_par(call, param)
            self.handle_mapping(var_output, mapto)

        self.handle_order(call)

        return MappingNode().set_function_out(call, self.g.get_output(call))

    def handle_strjoin(self, values):
        """
        Handles an AST node representing a string join operation, generating its RDF representation and managing string parameter assignments.

        This method creates a description for a string join operation, assigns string parameters to it, and updates the RDF graph accordingly.
        It also ensures that the output type is properly propagated.

        Parameters:
        -----------
        values : list of ast.AST
            The string nodes to be joined.

        Returns:
        --------
        tuple
            A tuple containing the URI of the strjoin call and the URI for the strjoin output.

        Workflow:
        ---------
        1. Check if the "strjoin" function has been encountered before and update its counter.
        2. Create a URI for the strjoin function and apply it to the RDF graph.
        3. Handle each string parameter in the operation to generate its RDF representation and map it to the strjoin.
        4. Describe the composition of the strjoin operation in the RDF graph using `FnODescriptor`.
        5. Set the type of the strjoin output to `str`.
        6. Return the URI of the strjoin call and the strjoin output.
        """

        # Check if the "list" function has been encountered before and update its counter
        context = "joinstr"
        delimiter = Prefix.py()["Delimiter"]
        strings = Prefix.py()["Strings"]
        output = Prefix.py()["JoinStringOutput"]

        if context not in self.g.f_counter:
            # Create FnO Function
            self.g.f_counter[context] = 1
            s = Prefix.py()[context]
            self.g += STD_KG[s]

            # Python implementation
            str_uri = PythonMapper.obj_to_fno(self.g, str)
            imp_uri = PythonMapper.obj_to_fno(
                self.g, str.join, "joinstr", self=str_uri, static=False
            )

            # Mapping
            FnOBuilder.describe_mapping(
                self.g,
                s,
                imp_uri,
                "join",
                positional=[delimiter, strings],
                outputs=output,
            )
        else:
            self.g.f_counter["joinstr"] += 1

        # Create a URI for the join function and apply it to the RDF graph
        f = Prefix.py()["joinstr"]
        call = Prefix.base()[f"joinstr_{self.g.f_counter['joinstr']}"]
        FnOBuilder.apply(self.g, call, f)

        # Set the delimiter to an empty string
        empty_string = self.handle_constant("")
        mapto = MappingNode().set_function_par(call, delimiter)
        self.handle_mapping(empty_string, mapto)

        # Handle each value and map it to the strings parameter
        for i, value in enumerate(values):
            value_output = self.handle_stmt(value)
            mapto = (
                MappingNode().set_function_par(call, strings).set_strategy("toList", i)
            )
            self.handle_mapping(value_output, mapto)

        # Set the type of the join output to `str`
        self.scope.var_types[output] = str

        # Return the URI of the list call and the list output
        self.handle_order(call)

        return MappingNode().set_function_out(call, output)

    def handle_format(self, value, conversion, spec):
        """
        Handles an AST node representing a string formatting operation.

        This method creates a description for a string formatting operation and calls the handle_func method to handle the operation.

        Parameters:
        -----------
        value : ast.AST
            The value node to be formatted.
        conversion : ast.AST
            The conversion node (not currently used in the implementation).
        spec : ast.AST
            The specification node for formatting.

        Returns:
        --------
        Any
            The result of the handle_func method call, which processes the format operation.

        Workflow:
        ---------
        1. Set the name and context for the format function.
        2. Call the handle_func method with the appropriate parameters to process the format operation.
        """
        # TODO what with conversion ?

        name = "format"
        context = "format"
        args = [value, spec] if spec is not None else [value]

        return self.handle_func(name, context, format, args)

    def handle_unop(self, op, operand):
        """
        Handles an AST Unary Operation node, processing the unary operation and generating its RDF representation.

        This method identifies the type of unary operation and adds the corresponding FnO Description if not already implemented.
        It then invokes the handle_func method to process the unary operation and generate the RDF representation.

        Parameters:
        -----------
        op : ast.AST
            The AST node representing the unary operator.
        operand : ast.AST
            The AST node representing the operand of the unary operation.

        Returns:
        --------
        tuple
            A tuple containing the URI of the unary operation and the URI for the function output.

        Workflow:
        ---------
        1. Determine the type of unary operator based on the AST node.
        2. Create a context for the unary operation based on the operator type.
        3. Invoke the handle_func method with the appropriate parameters to process the unary operation and generate the RDF representation.
        4. Return the URI of the unary operation and its output.
        """
        # Get the type of operator and add the FnO Description if it has not been implemented
        if isinstance(op, ast.UAdd):
            op_type = __pos__
        elif isinstance(op, ast.USub):
            op_type = __neg__
        elif isinstance(op, ast.Not):
            op_type = __not__
        elif isinstance(op, ast.Invert):
            op_type = __invert__

        name = op_type.__name__
        context = f"op_{name}"

        return self.handle_func(name, context, op_type, [operand])

    def handle_binop(self, op, left, right, assign=False):
        # Get the type of operator and add the FnO Description if it has not been implemented
        if isinstance(op, ast.Add):
            op_type = __iadd__ if assign else __add__
        elif isinstance(op, ast.Sub):
            op_type = __isub__ if assign else __sub__
        elif isinstance(op, ast.Mult):
            op_type = __imul__ if assign else __mul__
        elif isinstance(op, ast.Div):
            op_type = __itruediv__ if assign else __truediv__
        elif isinstance(op, ast.FloorDiv):
            op_type = __ifloordiv__ if assign else __floordiv__
        elif isinstance(op, ast.Mod):
            op_type = __imod__ if assign else __mod__
        elif isinstance(op, ast.Pow):
            op_type = __ipow__ if assign else __pow__
        elif isinstance(op, ast.LShift):
            op_type = __ilshift__ if assign else __lshift__
        elif isinstance(op, ast.RShift):
            op_type = __irshift__ if assign else __rshift__
        elif isinstance(op, ast.BitOr):
            op_type = __ior__ if assign else __or__
        elif isinstance(op, ast.BitXor):
            op_type = __ixor__ if assign else __xor__
        elif isinstance(op, ast.BitAnd):
            op_type = __iand__ if assign else __and__
        elif isinstance(op, ast.MatMult):
            op_type = __imatmul__ if assign else __matmul__

        name = op_type.__name__
        context = f"op_{name}"

        return self.handle_func(name, context, op_type, [left, right])

    def handle_boolop(self, op, values):
        """
        Handles an AST Binary Operation node, processing the binary operation and generating its RDF representation.

        This method identifies the type of binary operation and adds the corresponding FnO Description if not already implemented.
        It then invokes the handle_func method to process the binary operation and generate the RDF representation.

        Parameters:
        -----------
        op : ast.AST
            The AST node representing the binary operator.
        left : ast.AST
            The AST node representing the left operand of the binary operation.
        right : ast.AST
            The AST node representing the right operand of the binary operation.
        assign : bool, optional
            Indicates whether the binary operation is an assignment (True) or not (False). Default is False.

        Returns:
        --------
        tuple
            A tuple containing the URI of the binary operation and the URI for the function output.

        Workflow:
        ---------
        1. Determine the type of binary operator based on the AST node.
        2. Create a context for the binary operation based on the operator type.
        3. Invoke the handle_func method with the appropriate parameters to process the binary operation and generate the RDF representation.
        4. Return the URI of the binary operation and its output.
        """
        # Capture the values recursively for the boolop-function
        left = values[0]
        if len(values) > 2:
            right = ast.BoolOp(op=op, values=values[1:])
        else:
            right = values[1]

        # Get the type of operator
        op_type = __and__ if isinstance(op, ast.And) else __or__
        name = op_type.__name__
        context = f"op_{name}"

        return self.handle_func(name, context, op_type, [left, right])

    def handle_compare(self, left, ops, comparators):
        """
        Handles an AST Compare node, processing the comparison operation and generating its RDF representation.

        This method identifies the type of comparison operation and adds the corresponding FnO Description if not already implemented.
        It then invokes the appropriate method to process the comparison operation and generate the RDF representation.

        Parameters:
        -----------
        left : ast.AST
            The AST node representing the left operand of the comparison.
        ops : list
            A list of AST nodes representing comparison operators.
        comparators : list
            A list of AST nodes representing comparators (right operands) for the comparison.

        Returns:
        --------
        tuple
            A tuple containing the URI of the comparison operation and the URI for the function output.

        Workflow:
        ---------
        1. If the node holds multiple comparators, treat it as an AND operation consisting of multiple compare operations.
        2. Determine the type of comparison operator and handle it accordingly:
            - For 'is' and 'is not', invoke handle_memcompare method.
            - For other comparison operators, handle them using the corresponding function.
        3. Return the URI of the comparison operation and its output.
        """
        # ops is a function that takes 2 arguments (left and comparator)
        # If the node holds multiple comparators treat it as an And consisting of multiple compares
        if len(comparators) > 1:
            nodes = []
            for op, comparator in zip(ops, comparators):
                nodes.append(ast.Compare(left=left, ops=[op], comparators=[comparator]))
                left = comparator
            return self.handle_boolop(ast.And(), nodes)
        else:
            comparator = comparators[0]
            op = ops[0]

            if isinstance(op, ast.Is):
                return self.handle_memcompare("Is", left, comparator)
            if isinstance(op, ast.IsNot):
                return self.handle_memcompare("IsNot", left, comparator)

            if isinstance(op, ast.Eq):
                op_type = __eq__
            elif isinstance(op, ast.NotEq):
                op_type = __ne__
            elif isinstance(op, ast.Lt):
                op_type = __lt__
            elif isinstance(op, ast.LtE):
                op_type = __le__
            elif isinstance(op, ast.Gt):
                op_type = __gt__
            elif isinstance(op, ast.GtE):
                op_type = __ge__
            elif isinstance(op, ast.In):
                op_type = __contains__
            elif isinstance(op, ast.NotIn):
                name = __contains__.__name__
                context = f"op_{name}"
                return self.handle_unop(
                    ast.Not(),
                    self.handle_func(name, context, __contains__, [left, comparator]),
                )

            name = op_type.__name__
            context = f"op_{name}"
            return self.handle_func(name, context, op_type, [left, comparator])

    def handle_memcompare(self, name, left, right):
        """
        Handles an AST Compare node for 'is' and 'is not' comparisons, generating their RDF representation.

        This method adds the FnO Description for the 'is' and 'is not' comparisons if not already implemented.
        It then processes the comparison operation and generates the RDF representation.

        Parameters:
        -----------
        name : str
            The name of the comparison operation ('Is' for 'is', 'IsNot' for 'is not').
        left : ast.AST
            The AST node representing the left operand of the comparison.
        right : ast.AST
            The AST node representing the right operand of the comparison.

        Returns:
        --------
        tuple
            A tuple containing the URI of the comparison operation and the URI for the function output.

        Workflow:
        ---------
        1. Add the FnO Description for the 'is' and 'is not' comparisons if not already implemented.
        2. Create a call to the corresponding function using FnO Descriptor.
        3. Process the left and right operands using the handle_node method.
        4. Map the left and right operands to the function parameters.
        5. Return the URI of the comparison operation and its output.
        """
        if name not in self.g.f_counter:
            self.g.f_counter[name] = 1
            s = Prefix.py()[name]
            self.g += STD_KG[s]
        else:
            self.g.f_counter[name] += 1

        f = Prefix.py()[name]
        call = URIRef(f"{f}_{self.g.f_counter[name]}")
        FnOBuilder.apply(self.g, call, f)

        mapfrom = self.handle_stmt(left)
        mapto = MappingNode().set_function_par(call, Prefix.py()["ObjectParameter1"])
        self.handle_mapping(mapfrom, mapto)

        mapfrom = self.handle_stmt(right)
        mapto = MappingNode().set_function_par(call, Prefix.py()["ObjectParameter2"])
        self.handle_mapping(mapfrom, mapto)

        self.handle_order(call)

        return MappingNode().set_function_out(call, Prefix.py()["BoolOutput"])

    def handle_ifexpr(self, test, true, false):
        """
        Handles an AST IfExp node, generating its RDF representation.

        This method processes the IfExp node, which represents a ternary conditional expression (test ? true : false),
        and generates its RDF representation using FnO descriptors.

        Parameters:
        -----------
        test : ast.AST
            The AST node representing the condition of the conditional expression.
        true : ast.AST or None
            The AST node representing the expression to be evaluated if the condition is true.
        false : ast.AST or None
            The AST node representing the expression to be evaluated if the condition is false.
        expr_name : str or None, optional
            The name of the expression. If None, a new name will be generated.

        Returns:
        --------
        tuple
            A tuple containing the URI of the IfExpr function call and the URI for the function output.

        Workflow:
        ---------
        1. Process the condition, true expression, and false expression using the handle_node method.
        2. If expr_name is None, generate a new name for the IfExpr function call and add its FnO Description.
        Otherwise, use the provided expr_name.
        3. Map the condition, true expression, and false expression to the corresponding parameters of the IfExpr function.
        4. Describe the composition using FnO Descriptor.
        5. Return the URI of the IfExpr function call and its output.
        """
        context = "ifexpr"
        s = Prefix.py()[context]
        if context not in self.g.f_counter:
            self.g.f_counter[context] = 1
            self.g += STD_KG[s]
        else:
            self.g.f_counter["ifexpr"] += 1

        s = Prefix.py()["ifexpr"]
        call = URIRef(f"{s}_{self.g.f_counter['ifexpr']}")
        FnOBuilder.apply(self.g, call, s)

        mapfrom = self.handle_stmt(test)
        mapto = MappingNode().set_function_par(call, Prefix.py()["TestParameter"])
        self.handle_mapping(mapfrom, mapto)

        if true is not None:
            mapfrom = self.handle_stmt(true)
            mapto = MappingNode().set_function_par(call, Prefix.py()["IfTrueParameter"])
            self.handle_mapping(mapfrom, mapto)

        if false is not None:
            mapfrom = self.handle_stmt(false)
            mapto = MappingNode().set_function_par(
                call, Prefix.py()["IfFalseParameter"]
            )
            self.handle_mapping(mapfrom, mapto)

        self.handle_order(call)

        return MappingNode().set_function_out(call, Prefix.py()["IfExprOutput"])

    def function_to_rdf(
        self, fun_name, context, num, keywords, fun=None, self_class=None, static=None
    ):
        """
        Converts a Python function definition into its RDF representation.

        This method generates an RDF representation of a Python function definition
        using FnO descriptors based on the provided function name, context, and function object.

        Parameters:
        -----------
        f_name : str
            The name of the function.
        context : str
            The context or namespace in which the function is defined.
        f : callable
            The function object.
        num : int
            The number of parameters.
        keywords : list
            A list of keyword parameters.
        self_class : type, optional
            The class type for the self parameter, if applicable (default is None).
        static : bool, optional
            Indicates whether the method is a static method (default is None).

        Returns:
        --------
        s : str
            The unique identifier (URI) representing the function in the RDF graph.
        """

        if fun is not None:
            # Get the function object if it is a method
            fun = getattr(fun, "__func__", fun)

        ### FUNCTION DESCRIPTION ###

        try:
            s, output, fun_context, self_type = self.desc_with_sig(
                fun_name, context, fun, self_class
            )
        except:
            s, output, fun_context, self_type = self.desc_with_amount(
                fun_name, context, num, keywords, static
            )

        ### FUNCTION IMPLEMENTATION ###

        try:
            if fun is not None:
                imp = PythonMapper.obj_to_fno(self.g, fun, context, self_type, static)
            else:
                imp = PythonMapper.uri(fun_name)
                PythonBuilder.describe_imp(self.g, imp, context)
        except:
            module = getattr(fun, "__module__")
            imp = PythonBuilder.describe_imp(
                self.g, context, module, getattr(fun, "__package__", None)
            )

        ### FUNCTION MAPPING ###

        try:
            PythonMapper.map_with_sig(
                self.g, fun, s, imp, fun_name, output, fun_context
            )
        except:
            PythonMapper.map_with_num(
                self.g, s, keywords, imp, fun_name, output, fun_context
            )

        return s

    def desc_with_sig(self, f_name, context, f, self_class):
        """
        Creates a function description based on the function signature.

        This method generates a function description based on the function signature
        using FnO descriptors.

        Parameters:
        -----------
        f_name : str
            The name of the function.
        context : str
            The context or namespace in which the function is defined.
        f : callable
            The function object.
        self_class : type
            The class type for the self parameter.

        Returns:
        --------
        s : str
            The unique identifier (URI) representing the function in the RDF graph.
        output : str
            The unique identifier (URI) representing the output of the function.
        self_output : str
            The unique identifier (URI) representing the self parameter output of the function.
        self_type : type
            The type of the self parameter.
        """
        sig = inspect.signature(f)
        params = sig.parameters
        self_type = None
        return_type = sig.return_annotation

        ### PARAMETERS ###

        # Create function description from signature
        parameters = []
        context_input = None

        # Create parameter description
        for i, (name, param) in enumerate(params.items()):
            if name == "self":
                if self_class == False:
                    continue
                self_type = PythonMapper.obj_to_fno(self.g, self_class)

                context_input = Prefix.base()[f"{context}ParameterSelf"]
                FnOBuilder.describe_parameter(
                    self.g, uri=context_input, type=self_type, pred="self"
                )
                parameters.append(context_input)
            else:
                # Get rdf representation of type
                param_type = PythonMapper.obj_to_fno(self.g, param.annotation)

                # Create input description
                par_name = f"{context}Parameter{i}"
                uri = Prefix.base()[par_name]
                FnOBuilder.describe_parameter(
                    self.g, uri=uri, type=param_type, pred=name
                )
                parameters.append(uri)
                self.scope.var_types[uri] = param.annotation

        ### OUTPUTS ###

        outputs = []

        #### DEFAULT OUTPUT #####

        output_pred = f"{context}Result"
        output = Prefix.base()[f"{context}Output"]

        if f is not None and type(f) is type:
            # If the function is a class constructor, the output wil have the class type
            output_type = PythonMapper.obj_to_fno(self.g, f)
            self.scope.var_types[output] = f
        else:
            # Convert return annotation
            output_type = PythonMapper.obj_to_fno(self.g, return_type)
            self.scope.var_types[output] = return_type

        # Create default output description
        FnOBuilder.describe_output(
            self.g, uri=output, type=output_type, pred=output_pred
        )
        outputs.append(output)

        #### SELF OUTPUT ####

        if context_input:
            context_output = Prefix.base()[f"{context}SelfOutput"]
            FnOBuilder.describe_output(
                self.g, uri=context_output, type=self_type, pred="self_output"
            )
            outputs.append(context_output)

        ### FUNCTION DESCRIPTION ###

        # Add function description
        s = FnOBuilder.describe_function(
            self.g,
            uri=Prefix.base()[context],
            name=f_name,
            parameters=parameters,
            outputs=outputs,
        )

        return (
            s,
            output,
            (context_input, context_output) if context_input else None,
            self_type,
        )

    def desc_with_amount(self, f_name, context, num_of_params, keywords, has_self):
        """
        Creates a function description based on the number of parameters and keywords.

        This method generates a function description based on the number of parameters
        and keywords using FnO descriptors.

        Parameters:
        -----------
        f_name : str
            The name of the function.
        context : str
            The context or namespace in which the function is defined.
        num_of_params : int
            The number of parameters.
        keywords : list
            A list of keyword parameters.
        self_class : type
            The class type for the self parameter.

        Returns:
        --------
        s : str
            The unique identifier (URI) representing the function in the RDF graph.
        output : str
            The unique identifier (URI) representing the output of the function.
        self_output : str
            The unique identifier (URI) representing the self parameter output of the function.
        self_type : type
            The type of the self parameter.
        """
        # Create the python any type
        any_type = PythonMapper.any(self.g)

        parameters = []
        outputs = []

        #### SELF OUTPUT AND INPUT ####

        if has_self is not None:
            self_type = any_type

            context_input = Prefix.base()[f"{context}ParameterSelf"]
            FnOBuilder.describe_parameter(
                self.g, uri=context_input, type=context_input, pred="self"
            )
            parameters.append(context_input)

            context_output = Prefix.base()[f"{context}SelfOutput"]
            FnOBuilder.describe_output(
                self.g, uri=context_output, type=context_output, pred="self_output"
            )
            outputs.append(context_output)
        else:
            self_type = None

        ### PARAMETERS ###

        for i in range(num_of_params):
            uri = Prefix.base()[f"{context}Parameter{i}"]
            pred = f"param{i}"
            FnOBuilder.describe_parameter(self.g, uri=uri, type=any_type, pred=pred)
            parameters.append(uri)

        for i, keyword in enumerate(keywords):
            uri = Prefix.base()[f"{context}Parameter{i+num_of_params}"]
            pred = keyword.arg
            FnOBuilder.describe_parameter(self.g, uri=uri, type=any_type, pred=pred)
            parameters.append(uri)

        ### OUTPUTS ###

        #### DEFAULT OUTPUT ####

        output = Prefix.base()[f"{context}Output"]
        output_type = any_type
        output_pred = f"{context}Result"
        FnOBuilder.describe_output(
            self.g, uri=output, type=output_type, pred=output_pred
        )
        outputs.append(output)

        ### FUNCTION ###

        s = FnOBuilder.describe_function(
            self.g,
            uri=Prefix.base()[context],
            name=f_name,
            parameters=parameters,
            outputs=outputs,
        )

        return (
            s,
            output,
            (context_input, context_output) if has_self else None,
            self_type,
        )
