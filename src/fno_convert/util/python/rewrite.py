import ast
import traceback

import ast
import traceback

class ASTRewriter(ast.NodeTransformer):
    def __init__(self, parse_arg=False):
        super().__init__()
        self.parse_arg = parse_arg
        self.parser = None
        self.arguments = []
        self.arg_var = None
    
    def rewrite(self, source_code):
        tree = ast.parse(source_code)
        transformed_tree = self.visit(tree)
        ast.fix_missing_locations(transformed_tree)
        updated_code = ast.unparse(transformed_tree)
        return updated_code, self.arguments

    def visit_Assign(self, node):
        try:
            # Check if this assignment defines a generator
            if isinstance(node.value, (ast.ListComp, ast.DictComp, ast.SetComp)):
                return self.rewrite_comprehension(node.targets, node.value)
            
            if self.parse_arg:
                # Check if this assignment defines the ArgumentParser
                if self.parser is None:
                    self.parser = self.find_argparser_variable(node)
                    if self.parser:
                        return None  # Remove this node from the AST

                # Check if this assignment defines the parse_args variable
                if self.arg_var is None:
                    self.arg_var = self.find_argument_variable(node)
                    if self.arg_var:
                        return None  # Remove this node from the AST
        except Exception as e:
            print(f"[ERROR] Error in visit_Assign: {e}")
            print(traceback.format_exc())
        return self.generic_visit(node)

    def visit_Expr(self, node):
        try:
            # Check if this expression is an add_argument call
            if self.parser:
                arg = self.parse_argument(node)
                if arg:
                    self.arguments.append(arg)
                    return None  # Remove this node from the AST
        except Exception as e:
            print(f"[ERROR] Error in visit_Expr: {e}")
            print(traceback.format_exc())
        return self.generic_visit(node)

    def visit_Attribute(self, node):
        try:
            # Replace attribute access on the args variable with a Name node
            if (
                isinstance(node, ast.Attribute) and
                isinstance(node.value, ast.Name) and
                node.value.id == self.arg_var
            ):
                return ast.Name(id=node.attr, ctx=ast.Load())
        except Exception as e:
            print(f"[ERROR] Error in visit_Attribute: {e}")
            print(traceback.format_exc())
        return self.generic_visit(node)
    
    def visit_If(self, node):
        # Check if the condition is `if __name__ == "__main__"`
        if (
            self.parse_arg and
            isinstance(node.test, ast.Compare) and
            isinstance(node.test.left, ast.Name) and
            node.test.left.id == "__name__" and
            len(node.test.ops) == 1 and
            isinstance(node.test.ops[0], ast.Eq) and
            isinstance(node.test.comparators[0], ast.Str) and
            node.test.comparators[0].s == "__main__"
        ):
            # Visit the body of the if statement first
            ret = self.generic_visit(node)
            
            args=[]
            for arg in self.arguments:
                name = arg["name"].lstrip('-').replace('-', '_')
                arg_node = ast.arg(arg=name)
                args.append(arg_node)

            # Replace with a function definition
            return ast.FunctionDef(
                name="_",
                args=ast.arguments(posonlyargs=[], args=args, vararg=None, 
                                   kwonlyargs=[], kw_defaults=[], defaults=[]),
                body=ret.body,
                decorator_list=[]
            )
            
        return self.generic_visit(node)
    
    def rewrite_comprehension(self, target, comp_node):
        """
        Rewrite a comprehension (list or dict) as a loop with explicit appending.
        """
        # Create a new list (or dict for DictComp)
        if isinstance(comp_node, ast.ListComp):
            init_value = ast.List(elts=[], ctx=ast.Load())
            append_method = 'append'
        elif isinstance(comp_node, ast.DictComp):
            init_value = ast.Dict(keys=[], values=[])
            append_method = None  # No append method; use key-value assignment
        elif isinstance(comp_node, ast.SetComp):
            init_value = ast.Set(elts=[])
            append_method = 'add'
        else:
            raise ValueError("Unsupported comprehension type")

        # Create the assignment: `target = []` or `target = {}`
        assign_init = ast.Assign(
            targets=target,
            value=init_value
        )

        # Create the loop body
        if isinstance(comp_node, ast.ListComp):
            loop_body = [
                ast.Expr(
                    value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id=target[0].id, ctx=ast.Load()),
                            attr=append_method,
                            ctx=ast.Load()
                        ),
                        args=[comp_node.elt],
                        keywords=[]
                    )
                )
            ]
        elif isinstance(comp_node, ast.DictComp):
            loop_body = [
                ast.Assign(
                    targets=[
                        ast.Subscript(
                            value=ast.Name(id=target[0].id, ctx=ast.Load()),
                            slice=ast.Index(value=comp_node.key),
                            ctx=ast.Store()
                        )
                    ],
                    value=comp_node.value
                )
            ]

        # Create the loop: `for ... in ...`
        for_stmt = ast.For(
            target=comp_node.generators[0].target,
            iter=comp_node.generators[0].iter,
            body=loop_body,
            orelse=[]
        )

        # Return the rewritten nodes
        return [assign_init, for_stmt]

    def find_argparser_variable(self, node):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            func = node.value.func
            if (
                isinstance(func, ast.Name) and func.id == "ArgumentParser"
            ) or (
                isinstance(func, ast.Attribute) and func.attr == "ArgumentParser"
            ):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        return target.id
        return None

    def parse_argument(self, node):
        argument = {}
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call_node = node.value
            if (
                isinstance(call_node.func, ast.Attribute) and
                call_node.func.attr == "add_argument" and
                isinstance(call_node.func.value, ast.Name)
            ):
                if call_node.func.value.id == self.parser:
                    argument['name'] = call_node.args[0].value
                    for option in call_node.keywords:
                        argument[option.arg] = option.value.s if isinstance(option.value, ast.Constant) else option.value.id
        return argument

    def find_argument_variable(self, node):
        if isinstance(node, ast.Assign):
            var = node.targets[0].id if isinstance(node.targets[0], ast.Name) else None
            call_node = node.value
            if (
                isinstance(call_node, ast.Call) and
                isinstance(call_node.func, ast.Attribute) and
                call_node.func.attr == "parse_args" and
                isinstance(call_node.func.value, ast.Name)
            ):
                if call_node.func.value.id == self.parser:
                    return var
        return None