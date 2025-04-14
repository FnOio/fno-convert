import ast

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