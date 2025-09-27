from ..model.function import Function
from .std import Executer
from ..model.store import MappingType
from ..graph import FnOGraph
from ..prefix import Prefix
from ..util.python.script import CallableScript

import importlib
import importlib.util
import sys
import os

from urllib.parse import urlparse
from datetime import datetime
from typing import Any
from types import NoneType

def load_function_from_source(file_path, function_name):
    """
    Load a function from a Python source file.

    Args:
        file_path (str): The path to the Python source file.
        function_name (str): The name of the function to load.

    Returns:
        function: The loaded function object.
    """
    module_name = file_path.split('/')[-1][:-len('.py')]
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None:
        raise ImportError(f"Cannot find module spec for {file_path}")
    
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    try:
        func = getattr(module, function_name)
        return func
    except AttributeError as e:
        return

class PythonExecutor(Executer):
    
    @staticmethod
    def python_object(g: FnOGraph, uri):
        if uri is None:
            return Any
        
        if uri.split('#')[-1] == 'NoneType':
            return NoneType
                
        result = [
            (x['label'].value, 
             x['module'].value if x['module'] is not None else None, 
             x['package'].value if x['package'] is not None else None,
             urlparse(x['file']).path if x['file'] is not None else None,
             x['self_class'])
            for x in g.query(f'''
            SELECT ?type ?label ?module ?package ?file ?self_class WHERE {{
                VALUES ?type {{ fnoi:PythonClass fnoi:PythonFunction fnoi:PythonMethod }}
                <{uri}> a ?type ;
                      doap:name ?label ;
                OPTIONAL {{ <{uri}> fnoi:module ?module . }}
                OPTIONAL {{ <{uri}> fnoi:package ?package . }}
                OPTIONAL {{ <{uri}> fnoi:file ?file . }}
                OPTIONAL {{ <{uri}> fnoi:methodOf ?self_class . }}
            }}''', initNs=Prefix.NAMESPACES)]
        
        try:
            if result:
                label, module, package, file, self_class = result[0]
                if file is not None:
                    return load_function_from_source(file, label)
                if module is not None:
                    if module == "builtins" and hasattr(__builtins__, label):
                        return getattr(__builtins__, label)   
                    module_obj = importlib.import_module(module, package)
                    if hasattr(module_obj, label):
                        return getattr(module_obj, label)
                elif self_class is not None:
                    self_obj = PythonExecutor.python_object(g, self_class)
                    if hasattr(self_obj, label):
                        return getattr(self_obj, label)
        except Exception as e:
            print(f"Error while trying to get implementation from {uri.split('#')[-1]}: {e}")
            return Any
            
        return Any
    
    def __init__(self, g):
        super().__init__(g)
        
        self.handled = { Prefix.base().setitem: self.handle_setitem }
    
    def handle_setitem(self, fun: Function, *args, **kwargs):
        value = fun['a'].get()
        key = fun['b'].get()
        assign = fun['c'].get()
        
        value[key] = assign
        
        fun.output.set(value)
    
    def uri(self):
        return Prefix.ns('fnoi').PythonExecutor    
 
    def accepts(self, mapping, imp):
        file = self.g.get_file(imp)
        if file:
            return os.path.exists(file) and self.g.is_python(imp)
        return self.g.is_python(imp)
    
    def map(self, fun: Function):
        # TODO use PythonMapper
        try:
            if self.g.is_pythonfile(fun.imp):
                file = self.g.get_file(fun.imp)
                fun.f_object = CallableScript(file)
            else:
                fun.f_object = PythonExecutor.python_object(self.g, fun.imp)
        except Exception as e:
            print(f"Error while trying to get implementation from {fun.imp.split('#')[-1]}: {e}")
            fun.f_object = None
    
    def execute_function(self, fun: Function, *_args, **_keyargs):
        # Set input and output based on arguments
        for param in fun.inputs():
            mapping = param.param_mapping
            if mapping.is_type(MappingType.KEYWORD):
                if mapping.get_property() in _keyargs:
                    param.set(_keyargs[mapping.get_property()])
            elif mapping.is_type(MappingType.POSITIONAL):
                if mapping.get_property() < len(_args):
                    param.set(_args[mapping.get_property()])
        
        # If internal provenance is captured, you do not need to execute the function
        if fun.internal:
            try:
                fun.comp.execute(self)
                fun.imp = None
                return
            except:
                # An error occured when trying to execute the composition, try to execute the implementation
                pass
                  
        # If there is a fun input, use the function object from that terminal's uri value
        if fun.context_input is not None:
            fun.f_object = getattr(fun.context_input.value, fun.name, None)
        
        # Only execute when there is a function object
        if fun.f_object is not None:
            args = []
            vargs = []
            keyargs = {}
            vkeyargs = {}

            for param in fun.inputs():
                mapping = param.param_mapping
                if not param.value_set:
                    if mapping.has_default:
                        param.set(mapping.default)
                value = param.get()                    

                if mapping.is_type(MappingType.LIST):
                    vargs = value
                elif mapping.is_type(MappingType.KEYVALUE):
                    if isinstance(value, dict):
                        vkeyargs = value
                elif mapping.is_type(MappingType.KEYWORD):
                    keyargs[mapping.get_property()] = value
                elif mapping.is_type(MappingType.POSITIONAL):
                    args.append((mapping.get_property(), value))
            
            # correctly sort the positional arguments
            args = [ x[1] for x in sorted(args, key=lambda x: x[0])]

            # Remove the fun parameter as we already have the method object
            if fun.context_input is not None:
                if 'fun' in keyargs:
                    del keyargs['fun']
                else:
                    args = args[1:]
            
            try:
                fun.prov.startedAt = datetime.now()
                ret = fun.f_object(*args, *vargs, **keyargs, **vkeyargs)
                fun.prov.endedAt = datetime.now()
                
                fun.output.set(ret)
                if fun.context_output is not None:
                    fun.context_output.set(fun.context_input.get())
            except StopIteration as e:
                fun.stop_iteration = True
            except Exception as e:
                print(f"Error while executing {fun.name} with")
                print(f"\targs: {args}")
                print(f"\tvargs: {vargs}")
                print(f"\tkeyargs: {",".join([f"{key}={arg}" for key, arg in keyargs.items()])}")
                print(f"\tvkeyargs: {",".join([f"{key}={arg}" for key, arg in vkeyargs.items()])}")
                raise e        
    
    def alt_executor(self, fun: Function):
        raise Exception("No alternative executors")