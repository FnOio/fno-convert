from rdflib import RDF, BNode, Literal, URIRef

from ..prefix import Prefix
from ..graph import ExecutableGraph, create_rdf_list, get_name

class FnOBuilder():
    """
    Provides methods to describe functions, implementations, mappings, parameters, and outputs
    in the context of the Function Ontology (FNO).
    """
    
    @staticmethod
    def map(g: ExecutableGraph, fun, map, imp):
        g.add((map, Prefix.ns('fno').function, fun))
        g.add((map, Prefix.ns('fno').implementation, imp))

    @staticmethod
    def apply(g: ExecutableGraph, call, f):
        """
        Apply a call to a function.

        Args:
            call (URIRef): The call URI.
            f (URIRef): The function URI.

        Returns:
            PipelineGraph: The resulting graph.
        """
        g.add((call, Prefix.ns('fnoc')["applies"], f))
    
    @staticmethod
    def link(g: ExecutableGraph, call1, pred, call2):
        if call1 is not None and call2 is not None:
            g.add((call1, Prefix.ns('fnoc')[pred], call2))
    
    @staticmethod
    def start(g: ExecutableGraph, comp, call):
        g.add((comp, Prefix.ns('fnoc')["start"], call))

    @staticmethod
    def describe_composition(g: ExecutableGraph, comp, mappings, represents=None):
        """
        Describe a composition.

        Args:
            g (Graph): The graph to describe.
            comp_uri (URIRef): The composition URI.
            mappings (list): List of mappings.
        """

        # create the composition
        if not isinstance(comp, URIRef):
            comp_uri = Prefix.base()[comp]
        else:
            comp_uri = comp
        
        g.add((comp_uri, RDF.type, Prefix.ns('fno')["Composition"]))
        if represents:
            g.add((comp_uri, Prefix.ns('fnoc')["represents"], represents))

        # initiate the mapping nodes
        mapping_nodes = [BNode() for i in range(len(mappings))]

        for mapping, mapping_node in zip(mappings, mapping_nodes):
            mapfrom = mapping.mapfrom
            mapto = mapping.mapto

            g.add((comp_uri, Prefix.ns('fnoc')["composedOf"], mapping_node))
            if mapping.priority:
                g.add((mapping_node, Prefix.ns('fnoc')["priority"], mapping.priority))
                
            if mapfrom.from_term():
                # map from term
                term = mapfrom.get_value()
                g.add((mapping_node, Prefix.ns('fnoc')["mapFromTerm"], term))
            else:
                # map from function
                bnode = BNode()

                triples = [
                    (mapping_node, Prefix.ns('fnoc')["mapFrom"], bnode),
                    (bnode, Prefix.ns('fnoc')["constituentFunction"], mapfrom.context),
                    (bnode, Prefix.ns('fnoc')["functionOutput" if mapfrom.is_output() else "functionParameter"], mapfrom.get_value())
                ]
                        
                # map from strategy
                if mapfrom.has_map_strategy():
                    triples.append((bnode, Prefix.ns('fnoc')["mappingStrategy"], Prefix.ns('fnoc')[mapfrom.strategy]))
                    triples.append((bnode, Prefix.ns('fnoc')["key"], Literal(mapfrom.key)))

                [ g.add(x) for x in triples ]
                    
            # map to function
            bnode = BNode()

            triples = [
                (mapping_node, Prefix.ns('fnoc')["mapTo"], bnode),
                (bnode, Prefix.ns('fnoc')["constituentFunction"], mapto.context),
                (bnode, Prefix.ns('fnoc')["functionOutput" if mapto.is_output() else "functionParameter"], mapto.get_value())
            ]

            # map to strategy
            if mapto.has_map_strategy():
                triples.append((bnode, Prefix.ns('fnoc')["mappingStrategy"], Prefix.ns('fnoc')[mapto.strategy]))
                triples.append((bnode, Prefix.ns('fnoc')["key"], Literal(mapto.key)))

            [ g.add(x) for x in triples ]
            
        return comp_uri
        
    @staticmethod
    def describe_function(g: ExecutableGraph, 
                          uri=None, name=None,
                          parameters = [], 
                          outputs = []):
        """
        Describe a function.

        Args:
            f_name (str): The name of the function.
            context (str): The context of the function.
            inputs (list, optional): List of input parameters. Defaults to [].
            input_types (list, optional): List of input parameter types. Defaults to [].
            input_defaults (list, optional): List of default values for input parameters. Defaults to None.
            output (str, optional): Output parameter name. Defaults to None.
            output_type (str, optional): Output parameter type. Defaults to None.
            self_type (str, optional): Type of the self parameter. Defaults to None.

        Returns:
            Tuple: URI of the function and the resulting graph.
        """    
        # create fno:expects container
        c_expects = create_rdf_list(g, parameters)   

        # create fno:returns list
        c_returns = create_rdf_list(g, outputs)

        g.add((uri, RDF.type, Prefix.ns('fno')["Function"]))
        g.add((uri, RDF.type, Prefix.ns('prov')["Entity"]))
        g.add((uri, Prefix.ns('fno')['expects'], c_expects.uri))
        g.add((uri, Prefix.ns('fno')['returns'], c_returns.uri))
        if name is not None:
            g.add((uri, Prefix.ns('rdfs')['label'], Literal(name)))

        return uri

    @staticmethod
    def describe_parameter(g: ExecutableGraph, uri, type, pred):
        """
        Describe a parameter.

        Args:
            f_name (str): The name of the function.
            type (str): The parameter type.
            pred (str, optional): The predicate. Defaults to 'self'.
            default (any, optional): The default value. Defaults to None.
            i (int, optional): The index. Defaults to -1.

        Returns:
            PipelineGraph: The resulting graph.
        """

        triples = [
            (uri, RDF.type, Prefix.ns('fno')["Parameter"]),
            (uri, Prefix.ns('fno')["predicate"], Prefix.base()[pred]),
            (uri, Prefix.ns('fno')["type"], type)
        ]

        [ g.add(x) for x in triples ]
        
        return uri
    
    @staticmethod
    def describe_output(g: ExecutableGraph, uri, type, pred):
        """
        Describe an output.

        Args:
            f_name (str): The name of the function.
            type (str): The output type.
            pred (str, optional): The predicate. Defaults to 'selfResult'.
            name (str, optional): The output name. Defaults to None.

        Returns:
            PipelineGraph: The resulting graph.
        """
        triples = [
            (uri, RDF.type, Prefix.ns('fno')["Output"]),
            (uri, Prefix.ns('fno')["predicate"], Prefix.base()[pred]),
            (uri, Prefix.ns('fno')["type"], type)
        ]
        
        [ g.add(x) for x in triples ]
        
        return uri
    
    @staticmethod
    def describe_implementation(g: ExecutableGraph, imp_uri, imp_name):
        """
        Describe the implementation of a function.

        Args:
            f_name (str): The name of the function.
            m_name (str, optional): The module name. Defaults to None.
            p_name (str, optional): The package name. Defaults to None.

        Returns:
            PipelineGraph: The resulting graph.
        """
        triples = [
            (imp_uri, RDF.type, Prefix.ns('fnoi')['Implementation']),
            (imp_uri, Prefix.ns('doap')['name'], Literal(imp_name))
        ]

        [ g.add(x) for x in triples ]
        
        return imp_uri
    
    ### IMPLEMENTATION MAPPING ###
    
    @staticmethod
    def describe_mapping(g, f, imp, f_name=None, output=None,
                         positional=[], keyword={}, 
                         args=set(), kargs=set(), 
                         self_output=None, 
                         defaults={}) -> URIRef:
        """
        Describe a mapping.

        Args:
            f: The function.
            imp: The implementation.
            f_name (str): The name of the function.
            positional (list): List of positional arguments.
            keyword (list): List of keyword arguments.
            args: Variable positional argument.
            kargs: Variable keyword argument.
            output: Output parameter.
            self_output: Self output parameter.

        Returns:
            PipelineGraph: The resulting graph.
        """
        methodNode = BNode()
        returnNode = BNode()
        selfNode = BNode()

        context = get_name(f)
        s = Prefix.base()[f"{context}Mapping"]

        triples = [
            (s, RDF.type, Prefix.ns('fno')['Mapping']),
            (s, Prefix.ns('fno')['function'], f),
            (s, Prefix.ns('fno')['implementation'], imp),
            (s, Prefix.ns('fnom')['mappingMethod'], Literal("default"))  
        ]
        
        if f_name is not None:
            triples.extend([
                (s, Prefix.ns('fno')['methodMapping'], methodNode),
                (methodNode, RDF.type, Prefix.ns('fnom')['StringMethodMapping']),
                (methodNode, Prefix.ns('fnom')['method-name'], Literal(f_name))
            ])
        
        if output is not None:
            triples.extend([
                (s, Prefix.ns('fno')['returnMapping'], returnNode),
                (returnNode, RDF.type, Prefix.ns('fnom')['DefaultReturnMapping']),
                (returnNode, Prefix.ns('fnom')['functionOutput'], output),
            ])

        if self_output is not None:
            triples.extend([
                (s, Prefix.ns('fno')['returnMapping'], selfNode),
                (selfNode, RDF.type, Prefix.ns('fnom')['ValueReturnMapping']),
                (selfNode, Prefix.ns('fnom')['functionOutput'], self_output)
            ])

        ### POSITIONAL PARAMETER MAPPING ###

        for i, param in enumerate(positional):
            paramNode = BNode()

            triples.extend([
                (s, Prefix.ns('fno')['parameterMapping'], paramNode),
                (paramNode, RDF.type, Prefix.ns('fnom')['PositionParameterMapping']),
                (paramNode, Prefix.ns('fnom')['functionParameter'], param),
                (paramNode, Prefix.ns('fnom')['implementationParameterPosition'], Literal(i))
            ])
            
            if param in args:
                triples.append((paramNode, RDF.type, Prefix.ns('fnom')['IndexMapping']))
                args.remove(param)
            if param in kargs:
                triples.append((paramNode, RDF.type, Prefix.ns('fnom')['KeyValueMapping']))
                kargs.remove(param)

            if param in defaults:
                triples.append((param, Prefix.ns('fno')["required"], Literal(False)))
            else:
                triples.append((param, Prefix.ns('fno')["required"], Literal(True)))

        ### PROPERTY PARAMETER MAPPING ###
        
        for (param, key) in keyword:
            paramNode = BNode()

            triples.extend([
                (s, Prefix.ns('fno')['parameterMapping'], paramNode),
                (paramNode, RDF.type, Prefix.ns('fnom')['PropertyParameterMapping']),
                (paramNode, Prefix.ns('fnom')['functionParameter'], param),
                (paramNode, Prefix.ns('fnom')['implementationProperty'], Literal(key))

            ])

            if param in defaults:
                triples.append((param, Prefix.ns('fno')["required"], Literal(False)))
            else:
                triples.append((param, Prefix.ns('fno')["required"], Literal(True)))
        
        ### DEFAULT PARAMETER MAPPING ###

        for (param, default) in defaults.items():
            defaultNode = BNode()
                
            triples.extend([
                (s, Prefix.ns('fno')['parameterMapping'], defaultNode),
                (defaultNode, RDF.type, Prefix.ns('fnom')['DefaultParameterMapping']),
                (defaultNode, Prefix.ns('fnom')['functionParameter'], param),
                (defaultNode, Prefix.ns('fnom')['defaultValue'], default),
            ])
        
        ### INDEX PARAMETER MAPPING ###
        
        if len(args) == 1:
            arg = args.pop()
            argNode = BNode()
            triples.extend([
                (s, Prefix.ns('fno')['parameterMapping'], argNode),
                (argNode, RDF.type, Prefix.ns('fnom')['IndexMapping']),
                (argNode, Prefix.ns('fnom')['functionParameter'], arg)
            ])
        elif len(args) > 1:
            raise Exception("There can only be one non-positional index mapping")

        ### KEY VALUE PARAMETER MAPPING ###
        
        if len(kargs) == 1:
            karg = kargs.pop()
            kargNode = BNode()
            triples.extend([
                (s, Prefix.ns('fno')['parameterMapping'], kargNode),
                (kargNode, RDF.type, Prefix.ns('fnom')['KeyValueMapping']),
                (kargNode, Prefix.ns('fnom')['functionParameter'], karg)
            ])
        elif len(kargs) > 1:
            raise Exception("There can only be one non-positional key value mapping")
        
        [ g.add(x) for x in triples ]

        return s
    
    @staticmethod
    def implementation(g: ExecutableGraph, mapping, imp):
        g.add((mapping, Prefix.ns('fno').implementation, imp))
    
    @staticmethod
    def describe_execution(g: ExecutableGraph, exe, fun, mapping, inputs):
        g.add((exe, RDF.type, Prefix.ns('fno').Execution))
        g.add((exe, Prefix.ns('fno').executes, fun))
        
        if mapping:
            g.add((exe, Prefix.ns('fno').uses, mapping))
        
        for pred, input in inputs.items():
            g.add((exe, pred, input))