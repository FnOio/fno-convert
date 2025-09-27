import ast
from typing import List, Optional, Tuple


class ASTUtil(ast.NodeVisitor):
    """
    A utility class for visiting and extracting information from an Abstract Syntax Tree (AST).
    Extends the ast.NodeVisitor class to capture details about functions, classes, assignments,
    and other elements in the AST.

    Attributes:
        _name (str): The name of the current function being visited.
        _used_functions (list): A list of function names used in the AST.
        _classes (list): A list of class names defined in the AST.
        _inputs (ast.arguments): The arguments of the current function being visited.
        _nodes (list): A list of nodes (assignments, conditionals, loops, etc.) in the AST.
        _imports (list): A list of import statements in the AST.
    """

    def __init__(self, tree: ast.AST) -> None:
        """
        Initializes the ASTUtil instance and visits the given AST tree.

        Parameters:
            tree (ast.AST): The AST tree to be visited.
        """
        super().__init__()
        self._name = ""
        self._used_functions = []
        self._classes = []
        self._inputs = None
        self._nodes = []
        self._imports = []

        self.visit(tree)

    def used_functions(self):
        """
        Returns the list of functions used in the AST.

        Returns:
            list: A list of function names.
        """
        return self._used_functions

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """
        Visits a function definition node and captures its details.

        Parameters:
            node (ast.FunctionDef): The function definition node.
        """
        self._used_functions.append(node.name)
        self._name = node.name
        self._inputs = node.args
        self.generic_visit(node)


def analyze_statements(statements):
    """
    Given a list of AST statements, return (assigned_vars, input_vars).
    - assigned_vars: set of variables assigned in the block
    - input_vars: set of variables used before being assigned in the block
    """
    assigned_vars = set()
    input_vars = set()
    output_vars = set()

    for stmt in statements:
        # Find used vars
        used_visitor = UsedVariablesVisitor()
        used_visitor.visit(stmt)
        stmt_used = used_visitor.used

        # Any used before assignment → inputs
        for var in stmt_used:
            if var not in assigned_vars:
                input_vars.add(var)

        # Find assigned vars
        assign_visitor = AssignedVariablesVisitor()
        assign_visitor.visit(stmt)
        stmt_assigned = assign_visitor.assigned

        assigned_vars.update(stmt_assigned)

    return assigned_vars, input_vars


def for_targets(for_node: ast.For):
    """
    Given an ast.For node, return ordered list of targets.
    - targets: ordered list of variable named nodes
    """

    def extract_names(node):
        if isinstance(node, ast.Name):
            return [node]
        elif isinstance(node, (ast.Tuple, ast.List)):
            names = []
            for elt in node.elts:
                names.extend(extract_names(elt))
            return names
        else:
            return []  # ignore attributes, subscripts, etc.

    return extract_names(for_node.target)


def analyze_for_statement(for_node: ast.For):
    """
    Given an ast.For node, return (assigned_vars, input_vars).
    - assigned_vars: variables bound in the loop target
    - input_vars: variables used in the loop iterator expression
    """
    if not isinstance(for_node, ast.For):
        raise TypeError("Expected ast.For node")

    # Extract variables assigned in loop target (assigns)
    assign_visitor = AssignedVariablesVisitor()
    assign_visitor.visit(for_node)
    assigned_vars = assign_visitor.assigned

    # Extract used variables in loop iter
    used_visitor = UsedVariablesVisitor()
    used_visitor.visit(for_node.iter)
    used_vars = used_visitor.used

    return assigned_vars, used_vars


def analyze_if_statement(if_node: ast.If):
    """
    Given an ast.If node, return (input_vars).
    - input_vars: variables used in the loop iterator expression
    """
    if not isinstance(if_node, ast.If):
        raise TypeError("Expected ast.If node")

    # Extract used variables in test
    used_visitor = UsedVariablesVisitor()
    used_visitor.visit(if_node.test)
    return used_visitor.used


def extract_return_statement(statements) -> Tuple[Optional[ast.Return], List[ast.stmt]]:
    """
    Given a list of AST statements, extract the first return statement (if any)
    and return it along with the list of all other statements.

    :param statements: List of AST statements
    :return: (return_stmt, other_stmts)
    """
    return_stmt = None
    others = []

    for stmt in statements:
        if isinstance(stmt, ast.Return) and return_stmt is None:
            return_stmt = stmt
        else:
            others.append(stmt)

    return return_stmt, others


class AssignedVariablesVisitor(ast.NodeVisitor):
    def __init__(self):
        self.assigned = set()

    def visit_Assign(self, node):  # x = 5
        for target in node.targets:
            for name in _extract_targets(target):
                self.assigned.add(name)
        self.generic_visit(node)

    def visit_AnnAssign(self, node):  # x: int = 5
        for name in _extract_targets(node.target):
            self.assigned.add(name)
        self.generic_visit(node)

    def visit_AugAssign(self, node):  # x += 1
        for name in _extract_targets(node.target):
            self.assigned.add(name)
        self.generic_visit(node)

    def visit_For(self, node):  # for x, y in ...
        # Only extract the loop target
        for name in _extract_targets(node.target):
            self.assigned.add(name)

    def visit_Call(self, node):
        # If this is a method call like var.func(), mark 'var' as assigned
        if isinstance(node.func, ast.Attribute):
            value = node.func.value
            if isinstance(value, ast.Name):
                self.assigned.add(value.id)
        self.generic_visit(node)


class UsedVariablesVisitor(ast.NodeVisitor):
    def __init__(self):
        self.used = set()

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            if not self._is_function_name(node) and self._is_top_level(node):
                self.used.add(node.id)
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        for name in _extract_targets(node.target):
            self.used.add(name)
        self.generic_visit(node)

    def _is_function_name(self, node):
        """Check if this Name node is the function being called."""
        parent = getattr(node, "parent", None)
        return isinstance(parent, ast.Call) and parent.func is node

    def _is_top_level(self, node):
        """Return True if node is a top-level variable (not an attribute or only base of attribute)."""
        parent = getattr(node, "parent", None)
        # If the parent is an Attribute and this node is the value/base, it's top-level
        if isinstance(parent, ast.Attribute) and parent.value is node:
            return True
        # If the parent is not an Attribute, it's also top-level
        if not isinstance(parent, ast.Attribute):
            return True
        return False

    def generic_visit(self, node):
        # Attach parent pointers for context checks
        for child in ast.iter_child_nodes(node):
            child.parent = node
            self.visit(child)


def _extract_targets(target):
    """Recursively extract top-level variable names from assignment targets."""
    if isinstance(target, ast.Name):
        yield target.id
    elif isinstance(target, (ast.Tuple, ast.List)):
        for elt in target.elts:
            yield from _extract_targets(elt)
    elif isinstance(target, ast.Subscript):
        value = target.value
        if isinstance(value, ast.Name):
            yield value.id
    elif isinstance(target, ast.Attribute):
        value = target.value
        if isinstance(value, ast.Name):
            yield value.id
