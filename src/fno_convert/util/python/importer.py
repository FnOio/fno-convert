import ast
import inspect
import importlib
import importlib.util
import builtins
import os
import sys

SKIP_MODULE = { "numpy", "sklearn", "tensorflow", "skimage", "scipy", "pandas", "keras", "nltk", "string", "pickle", "warnings" }

BUILTINS = { builtins }

def add_submodules(module):
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if isinstance(attr, type):
            BUILTINS.add(attr)

add_submodules(builtins)

class Importer:
    """
    Utility class for dynamically importing modules and objects from Python source code.
    """

    def __init__(self) -> None:
        """
        Initialize an Importer instance.
        """
        self._objects = {}
        self._modules = {}
        self._asname = {}
        self._imported_files = set()
        self.user_defined = set()

    def objects(self):
        """
        Get a dictionary of imported objects.

        Returns:
            dict: A dictionary containing imported objects.
        """
        return self._objects

    def modules(self):
        """
        Get a dictionary of imported modules.

        Returns:
            dict: A dictionary containing imported modules.
        """
        return self._modules

    def skip(self, obj):
        """
        Check if an object should be skipped.

        Args:
            obj: The object to check.

        Returns:
            bool: True if the object should be skipped, False otherwise.
        """
        return obj not in self.user_defined

    def clear(self):
        """
        Clear all imported objects and modules.
        """
        self._objects.clear()
        self._modules.clear()
        self._asname.clear()

    def is_module(self, module_name):
        """
        Check if a name is that of a module.

        Args:
            module_name (str): The name of the module.

        Returns:
            bool: True if the name is that of a module, False otherwise.
        """
        try:
            if module_name in self._asname:
                module_name = self._asname[module_name]
            
            return importlib.util.find_spec(module_name) is not None or module_name in self._modules
        except:
            return False
    
    def get_full_module_name(file_path):
        # Start with the file path
        directory, module_name = os.path.split(file_path)
        module_name = os.path.splitext(module_name)[0]  # Remove .py extension

        # Initialize list to store module components
        module_parts = [module_name]
        
        # Walk up the directory to check for __init__.py files
        while os.path.exists(os.path.join(directory, '__init__.py')):
            directory, tail = os.path.split(directory)
            module_parts.append(tail)

        # Reverse the module parts to form the full module name
        full_module_name = '.'.join(reversed(module_parts))
        return full_module_name

    def import_from_obj(self, func):
        """
        Extract and handle all import statements from the file where a function is defined.

        Args:
            func (function): The function object.
        """
        # Get the source file of the function
        obj_path = inspect.getfile(func)
        source_file = inspect.getsourcefile(func)
        if not source_file:
            raise Exception(f"Source file for function {func.__name__} not found.")
        
        return self.import_from_file(source_file, obj_path)
    
    def import_from_file(self, file_path, obj_path=None, source_code=None):
        objects = []

        # Get the directory of the source file and add it to sys.path if needed
        source_dir = os.path.dirname(file_path)
        if source_dir not in sys.path:
            sys.path.insert(0, source_dir)  # Add directory to sys.path temporarily

        # Read the source file
        with open(file_path, 'r') as file:
            source_code = file.read()

        # Use the AST module to parse the source code
        parsed_source = ast.parse(source_code)

        # Function to recursively extract import statements or function definitions
        def extract_nodes(node):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.Import) or isinstance(child, ast.ImportFrom) or \
                   isinstance(child, ast.FunctionDef) or isinstance(child, ast.ClassDef):
                    yield child
                yield from extract_nodes(child)

        # Collect all nodes to import
        nodes = list(extract_nodes(parsed_source))

        # Handle each node
        for node in nodes:
            try:
                if isinstance(node, ast.Import):
                    self.handle_import(*node.names)
                elif isinstance(node, ast.ImportFrom):
                    self.handle_import_from(node.module, *node.names)
                elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    module_name = inspect.getmodulename(obj_path if obj_path is not None else file_path)
                    if self.is_module(module_name):
                        obj = self.handle_import_from(module_name, ast.alias(node.name), skip=False)
                        objects.append(obj)
            except Exception as e:
                print(f"Error importing for node {node}: {e}")
        
        return objects


    def handle_import(self, *module_names):
        """
        Handle import statements.

        Args:
            module_names: The names of the modules to import.
        """
        try:
            for module_name in module_names:
                module = importlib.import_module(module_name.name)

                if module_name.asname is not None:
                    self._modules[module_name.name] = module
                    self._asname[module_name.asname] = module_name.name
                else:
                    self._modules[module_name.name] = module
                
                return module
        except ModuleNotFoundError as e:
            # Module does not exist
            raise Exception(f"Module {module_name.name} does not exist.")

    def handle_import_from(self, module_name, *obj_names, skip=True):
        """
        Handle import-from statements.

        Args:
            module_name (str): The name of the module.
            obj_names: The names of the objects to import.
            skip (bool): Whether the object is defined by the user or from a library.
        """
        try:
            if module_name not in self._modules:
                self.handle_import(ast.alias(name=module_name))

            for obj_name in obj_names:
                obj = getattr(self._modules[module_name], obj_name.name, None)

                if obj is not None:
                    if obj_name.asname is not None:
                        self._asname[obj_name.asname] = obj_name.name
                        
                    if inspect.ismodule(obj):
                        self._modules[obj_name.name] = obj
                    else:
                        self._objects[obj_name.name] = obj

                    if not skip:
                        self.user_defined.add(obj)

                return obj
        except AttributeError as e:
            # Module has no such attribute
            raise Exception(f"Module {module_name} does not have the right attributes.")

    def add_object(self, name, obj):
        """
        Add an object to the Importer.

        Args:
            name (str): The name of the object.
            obj: The object to add.
        """
        self._objects[name] = obj

    def get_module(self, module_name):
        """
        Get the module with the specified name.

        Args:
            module_name (str): The name of the module.

        Returns:
            module: The module object.
        """
        if module_name in self._asname:
            module_name = self._asname[module_name]

        if module_name not in self._modules:
            try:
                self.handle_import(ast.alias(name=module_name))
            except Exception as e:
                return None

        return self._modules[module_name]

    def get_object(self, obj_name):
        """
        Get the object with the specified name.

        Args:
            obj_name (str): The name of the object.

        Returns:
            object: The object corresponding to the name.
        """
        return self._objects.get(obj_name, None)

    def object_from_module(self, module_name, obj_name):
        """
        Get an object from a module.

        Args:
            module_name (str): The name of the module.
            obj_name (str): The name of the object.

        Returns:
            object: The object from the module.
        """
        if module_name in self._asname:
            module_name = self._asname[module_name]
        if obj_name in self._asname:
            obj_name = self._asname[obj_name]

        if obj_name not in self._objects:
            self.handle_import_from(module_name, ast.alias(name=obj_name))
        return self._objects[obj_name]
    
    def object_from_builtins(self, obj_name):
        """
        Get an object from Python built-in module.

        Args:
            obj_name (str): The name of the object.

        Returns:
            object: The object from the built-in module.
        """
        for module in BUILTINS:
            if hasattr(module, obj_name):
                return getattr(module, obj_name)
            