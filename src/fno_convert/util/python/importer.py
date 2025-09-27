import ast
import inspect
import importlib
import importlib.util
import builtins
import os
import sys

SKIP_MODULE = {
    "numpy",
    "sklearn",
    "tensorflow",
    "skimage",
    "scipy",
    "pandas",
    "keras",
    "nltk",
    "string",
    "pickle",
    "warnings",
}

BUILTINS = {builtins}


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

            return (
                importlib.util.find_spec(module_name) is not None
                or module_name in self._modules
            )
        except:
            return False

    def handle_rel_import(
        self, module_name: str, level: int, file_path: str, *obj_names
    ) -> str:
        """
        Handle relative imports like `from .module import obj`.

        Args:
            module_name (str): The relative module name (may be None for `from . import obj`).
            obj_names: Objects to import (ast.alias nodes).
            level (int): Relative import level (number of dots).
            file_path (str): Path to the file where the import is found.

        Returns:
            str: The resolved absolute module name.
        """

        def _path_to_module_name(base_path: str, module_name: str) -> str:
            """
            Convert a file path + module to a Python module name.
            """
            base_dir = os.path.dirname(os.path.abspath(base_path))
            rel_path = os.path.relpath(base_path, base_dir)
            package_parts = rel_path.split(os.sep)
            return ".".join([*package_parts, module_name])

        # Starting package: directory of current file
        package_dir = os.path.dirname(os.path.abspath(file_path))

        # Walk up `level - 1` directories (since 1 dot means current package)
        for _ in range(level - 1):
            package_dir = os.path.dirname(package_dir)

        # Convert path to a package-style module name
        sys.path.insert(0, os.path.dirname(package_dir))

        if module_name:
            full_module_name = _path_to_module_name(package_dir, module_name)
        else:
            full_module_name = os.path.basename(package_dir)

        # Import the module
        module = importlib.import_module(full_module_name)
        self._modules[full_module_name] = module

        # Import objects
        for obj in obj_names:
            obj_val = getattr(module, obj.name, None)
            if obj_val is not None:
                if obj.asname:
                    self._asname[obj.asname] = obj.name
                if inspect.ismodule(obj_val):
                    self._modules[obj.name] = obj_val
                else:
                    self._objects[obj.name] = obj_val
            self.user_defined.add(obj_val)
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
        source_dir = os.path.dirname(file_path)
        if source_dir not in sys.path:
            sys.path.insert(0, source_dir)

        with open(file_path, "r") as file:
            source_code = file.read()

        parsed_source = ast.parse(source_code)

        def extract_nodes(node):
            for child in ast.iter_child_nodes(node):
                if isinstance(
                    child, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef)
                ):
                    yield child
                yield from extract_nodes(child)

        nodes = list(extract_nodes(parsed_source))

        # Determine proper module name (package-aware)
        abs_file = os.path.abspath(file_path)
        module_name = None

        # Walk up until not a package
        package_path = os.path.dirname(abs_file)
        package_parts = []
        while os.path.exists(os.path.join(package_path, "__init__.py")):
            package_parts.insert(0, os.path.basename(package_path))
            package_path = os.path.dirname(package_path)

        if package_parts:
            # file is inside a package
            package_parts.append(os.path.splitext(os.path.basename(abs_file))[0])
            module_name = ".".join(package_parts)
            if module_name not in sys.modules:
                module = importlib.import_module(module_name)
            else:
                module = sys.modules[module_name]
        else:
            # fallback: standalone script
            module_name = inspect.getmodulename(obj_path or file_path)
            if module_name not in self._modules:
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
            else:
                module = self._modules[module_name]

        self._modules[module_name] = module

        # Handle AST nodes
        for node in nodes:
            try:
                if isinstance(node, ast.Import):
                    self.handle_import(*node.names)
                elif isinstance(node, ast.ImportFrom):
                    if node.level > 0:
                        self.handle_rel_import(
                            node.module, node.level, file_path, *node.names
                        )
                    else:
                        self.handle_import_from(node.module, *node.names)
                elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    obj = getattr(module, node.name, None)
                    if obj:
                        self._objects[node.name] = obj
                        self.user_defined.add(obj)
                        objects.append(obj)
            except Exception as e:
                print(f"Error importing from {file_path}: {e}")
                raise e

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
        except AttributeError:
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
