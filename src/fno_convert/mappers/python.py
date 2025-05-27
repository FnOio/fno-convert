import inspect, importlib, importlib.util, sys, hashlib, os, argparse, ast

from typing import Any
from types import NoneType, ModuleType
from rdflib import Literal, URIRef, BNode
from rdflib.term import _toPythonMapping
from ..prefix import Prefix
from ..builders import PythonBuilder, FnOBuilder
from ..graph import FnOGraph, get_name, create_rdf_list

_toPythonMapping[Prefix.ns('xsd').string] = str
_toPythonMapping[Prefix.ns('xsd').boolean] = bool

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

def is_of_std_lit_type(instance):
    """
    Check if the instance is of a type that RDFlib recognizes as a standard literal type.
    """
    return type(instance) in _toPythonMapping.values()

def is_std_lit_type(instance):
    """
    Check if the instance is a type that RDFlib recognizes as a standard literal type.
    """
    return instance in _toPythonMapping.values()


class PythonMapper:
    
    @staticmethod
    def uri(name, m_name=None, p_name=None, f_name=None):
        combined = ''.join(str(item) for item in [m_name, p_name, f_name] if item)
        unique_hash = hashlib.sha256(combined.encode()).hexdigest()[:8]
        return Prefix.ns('python')[f"{name}{unique_hash}"]
    
    @staticmethod
    def obj_to_fno(g: FnOGraph, imp, imp_name=None, self=None, static=None):
        """
        Convert a Python function implementation to RDF.

        Args:
            imp (function): The Python function or method.
            imp_name (str, optional): The name of the implementation.
            self (URI, optional): The type of the self parameter.
            static (bool, optional): Indicates if the method is static.

        Returns:
            tuple: A tuple containing the URI of the implementation and the RDF graph.
        """
        # TODO handle multiple param annotations
        if imp is inspect._empty or isinstance(imp, str):
            imp = Any
        elif imp is None:
            imp = type(None)
            
        for type_uri, imp_type in _toPythonMapping.items():
            if imp == imp_type:
                return type_uri
        
        imp_name = getattr(imp, '__name__', getattr(type(imp), '__name__', str(imp)))
    
        m_name = p_name = f_name = doc = None
        
        ### IMPLEMENTATION METADATA ###
        
        # Module & package
        if isinstance(imp, ModuleType):
            m_name = Literal(imp.__name__)
            if hasattr(imp, '__package__'):
                p_name = Literal(imp.__package__)
        if hasattr(imp, "__module__"):
            m_name = Literal(imp.__module__)
            if '.' in imp.__module__:
                p_name = imp.__module__.split('.')[0]
        
        # File
        try:
            module_file = inspect.getfile(imp)

            # Do not add the file of externally installed modules
            if os.getcwd() in module_file:
                f_name = module_file
        except TypeError as e:
            pass
        
        # Docstring
        if hasattr(imp, '__doc__'):
            doc = imp.__doc__
        
        ### DESCRIBE IMPLEMENTATION ###
        
        imp_uri = PythonMapper.uri(imp_name, m_name, p_name, f_name)
        PythonBuilder.describe_imp(g, imp_uri, imp_name, m_name, p_name, f_name, doc)

        # Determine implementation type

        if inspect.isclass(imp) or imp is Any:
            PythonBuilder.describe_class(g, imp_uri)
        if isinstance(imp, ModuleType):
            PythonBuilder.describe_module(g, imp_uri)
        elif self is not None:
            PythonBuilder.describe_method(g, imp_uri, self, static)
        else:
            PythonBuilder.describe_function(g, imp_uri)

        return imp_uri
    
    ### MAPPINGS ###
    
    @staticmethod
    def parse_args_with_map(g: FnOGraph, map, input_parts):
        positionals = g.get_positionals(map)
        keywords = g.get_keywords(map)

        parser = argparse.ArgumentParser()

        # Track how each terminal was added
        uri_to_argname = {}

        # Add positional arguments
        for i, uri in enumerate(positionals):
            argname = f'pos_{i}'
            uri_to_argname[uri] = argname
            if g.is_list_mapping(map, uri):
                parser.add_argument(argname, nargs='*')
            else:
                parser.add_argument(argname)

        # Add keyword arguments
        for key, uri in keywords.items():
            argname = key.replace('-', '_')
            uri_to_argname[uri] = argname
            if g.is_list_mapping(map, uri):
                parser.add_argument(f'--{key}', dest=argname, nargs='*')
            else:
                parser.add_argument(f'--{key}', dest=argname)

        # Parse
        args = parser.parse_args(input_parts)

        result = {}

        # Resolve terminal values
        used = set()
        for i, uri in enumerate(positionals):
            argname = f'pos_{i}'
            val = getattr(args, argname, None)
            if val is not None:
                result[uri] = val
                used.add(uri)

        for key, uri in keywords.items():
            if uri in used:
                continue  # Skip if already used as positional
            argname = key.replace('-', '_')
            val = getattr(args, argname, None)
            if val is not None:
                result[uri] = val
                used.add(uri)
        
        return result
        
    @staticmethod
    def map_with_parse_args(g: FnOGraph, fun, imp, output, args):
        context = get_name(fun)
        
        positional = []
        keyword = []
        defaults = {}
        
        list_mapping = set()
        
        for i, arg in enumerate(args):
            name = arg['name'].lstrip('-')
            param = g.get_predicate_param(fun, name.replace('-', '_'))
            
            if not arg['name'].startswith('-'):
                # Positional
                positional.append(param)
            else:
                # Keyword
                keyword.append((param, name))
            
            if 'nargs' in arg:
                # TODO what values are possible for nargs?
                list_mapping.add(param)
            
            if 'default' in arg:
                defaults[param] = arg['default']
        
        uri = FnOBuilder.describe_mapping(g, fun, imp, context,
                                    output=output,
                                    positional=positional, keyword=keyword,
                                    args=list_mapping, defaults=defaults)
        
        return uri
    
    @staticmethod
    def map_with_sig(g: FnOGraph, f, s, imp, f_name, output, self_output): 
        sig = inspect.signature(f)
        params = sig.parameters

        # Capture the kinds
        positional = []
        keyword = []
        args = set()
        kargs = set()
        defaults = {}

        for name, param in params.items():
            # Get the parameter linked to this predicate
            par = g.get_predicate_param(s, name)
            if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                positional.append(par)
            if param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
                positional.append(par)
                keyword.append((par, name))
            elif param.kind == inspect.Parameter.KEYWORD_ONLY:
                keyword.append((par, name))
            elif param.kind == inspect.Parameter.VAR_POSITIONAL:
                args.add(par)
            elif param.kind == inspect.Parameter.VAR_KEYWORD:
                kargs.add(par)
            
            if param.default is not inspect._empty:
                defaults[par] = PythonMapper.value_to_term(g, param.default)

        FnOBuilder.describe_mapping(g, s, imp, f_name, output, positional, keyword, args, kargs, self_output, defaults)
        
    @staticmethod
    def map_with_num(g: FnOGraph, s, keywords, imp, f_name, output, self_output):
        """
        Maps function parameters and outputs to RDF representations based on the number of parameters and keywords.

        This method maps function parameters and outputs to RDF representations 
        based on the number of parameters and keywords using FnO descriptors.

        Parameters:
        -----------
        s : str
            The unique identifier (URI) representing the function in the RDF graph.
        keywords : list
            A list of keyword parameters.
        imp : str
            The unique identifier (URI) representing the implementation of the function.
        f_name : str
            The name of the function.
        output : str
            The unique identifier (URI) representing the output of the function.
        self_output : str
            The unique identifier (URI) representing the self parameter output of the function.
        """
        positional = []
        self_param = g.get_self(s)
        if self_param is not None:
            positional.append(self_param) 
        positional.extend(g.get_parameters(s))
        keyword = []
        for pred in keywords:
            par = g.get_predicate_param(s, pred.arg)
            if par is not None:
                keyword.append((par, pred.arg))

        FnOBuilder.describe_mapping(g, s, imp, f_name, output, positional=positional, keyword=keyword, self_output=self_output)
    
    @staticmethod
    def fno_to_obj(g: FnOGraph, s):
        """
        Convert RDF representing a function implementation to a Python function or method.

        Args:
            g (Graph): The RDF graph containing the implementation.
            s (str | URIRef): The URI of the implementation.

        Returns:
            function: The Python function or method.
        """
        if s is None:
            return Any
        
        if s.split('#')[-1].startswith('NoneType'):
            return NoneType
        
        if s in _toPythonMapping:
            return _toPythonMapping[s]
                
        result = [
            (x['label'].value, 
             x['module'].value if x['module'] is not None else None, 
             x['package'].value if x['package'] is not None else None,
             x['file'].value if x['file'] is not None else None,
             x['self_class'])
            for x in g.query(f'''
            SELECT ?type ?label ?module ?package ?file ?self_class WHERE {{
                VALUES ?type {{ fnoi:PythonClass fnoi:PythonFunction fnoi:PythonMethod fnoi:PythonModule }}
                <{s}> a ?type ;
                      rdfs:label ?label ;
                OPTIONAL {{ <{s}> fnoi:module ?module . }}
                OPTIONAL {{ <{s}> fnoi:package ?package . }}
                OPTIONAL {{ <{s}> fnoi:file ?file . }}
                OPTIONAL {{ <{s}> fnoi:methodOf ?self_class . }}
            }}''', initNs=Prefix.NAMESPACES)]
        
        try:
            if result:
                label, module, package, file, self_class = result[0]
                
                if g.is_pythonmodule(s):
                    return importlib.import_module(module, package)
                
                if file is not None:
                    return load_function_from_source(file, label)
                if module is not None:
                    if module == "builtins" and hasattr(__builtins__, label):
                        return getattr(__builtins__, label)   
                    module_obj = importlib.import_module(module, package)
                    if hasattr(module_obj, label):
                        return getattr(module_obj, label)
                elif self_class is not None:
                    self_obj = PythonMapper.fno_to_obj(g, self_class)
                    if hasattr(self_obj, label):
                        return getattr(self_obj, label)
        except Exception as e:
            print(f"Error while trying to get implementation from {s.split('#')[-1]}: {e}")
            return Any
            
        return Any
    
    @staticmethod
    def value_to_term(g: FnOGraph, inst):
        """
        Convert a Python literal or instance to RDF.

        Args:
            inst: The Python literal or instance.

        Returns:
            tuple: A tuple containing the RDF literal and the type description graph.
        """
        
        if isinstance(inst, URIRef):
            return inst
        if isinstance(inst, list):
            return create_rdf_list(g, [ PythonMapper.value_to_term(g, el) for el in inst ]).uri
        if inst is None:
            return Literal(None)
        if type(inst) in _toPythonMapping.values():
            return Literal(inst)
        
        try:
            return PythonMapper.obj_to_fno(g, inst)
        except:
            inst_type = PythonMapper.obj_to_fno(g, type(inst))
        
        return Literal(inst, datatype=inst_type)

    @staticmethod
    def term_to_value(g: FnOGraph, term: Literal | URIRef | BNode):
        if isinstance(term, URIRef):
            if g.is_implementation(term):
                return PythonMapper.fno_to_obj(g, term)
            return term
        if isinstance(term, BNode):
            if g.is_list(term):
                return [ PythonMapper.term_to_value(g, x) for x in g.to_list(term) ]
        if term.datatype is None and term.value == 'None':
            return None
        if term.datatype is Prefix.ns('rdf').Seq:
            return ast.literal_eval(term.value)
        return term.value
    
    @staticmethod
    def any(g: FnOGraph) -> URIRef:
        """
        Get the RDF representation of the 'Any' type.

        Returns:
            tuple: A tuple containing the URI of the 'Any' type and the RDF graph.
        """
        return PythonMapper.obj_to_fno(g, inspect._empty)