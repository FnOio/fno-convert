from rdflib import Graph, BNode, Literal, URIRef
from rdflib.container import Container
from .prefix import Prefix
from pyparsing.exceptions import ParseException
from typing import Any
from datetime import datetime

def create_rdf_list(g, elements):
    return Container(g, BNode(), seq=elements, rtype="Seq")

def get_prefix(s):
    """
    Extracts the prefix from a given URI string.
    
    The prefix is considered to be everything before the last '#' character.
    
    :param s: str
        The URI string from which to extract the prefix.
    :return: str
        The prefix of the URI.
    """
    return '#'.join(s.split('#')[:-1])

def get_name(s):
    """
    Extracts the name from a given URI string.
    
    The name is considered to be everything after the last '#' character. If no '#' is present, 
    the entire string is returned.
    
    :param s: str
        The URI string from which to extract the name.
    :return: str
        The name extracted from the URI.
    """
    if '#' in s:
        return s.split('#')[-1]
    return s

def to_uri(prefix, s):
    """
    Converts a prefix and a name into a full URI.
    
    This function takes a prefix and a name, combines them with a '#' separator, and returns a URIRef object.
    
    :param prefix: str
        The prefix part of the URI. Typically this is the base URI or namespace.
    :param s: str
        The name or identifier to be appended to the prefix.
    :return: rdflib.term.URIRef
        A URIRef object representing the full URI.
    """
    return URIRef(f"{prefix}#{s}")

class FnOGraph(Graph):
    """
    A subclass of rdflib.Graph tailored for handling pipeline graphs
    with specific functionalities for managing function descriptions.
    """
    def __init__(self, graph=None):
        """
        Initializes a PipelineGraph.
        
        :param graph: rdflib.Graph or None
            An optional RDF graph to initialize the PipelineGraph with.
        """
        super().__init__()
        Prefix.bind_namespaces(self)
        if graph:
            self += graph
        
        if isinstance(graph, FnOGraph):
            self.f_counter = graph.f_counter
        else:
            self.f_counter = {}
    
    def exists(self, uri):
        return uri in self.subjects() or uri in self.objects() or uri in self.predicates()
    
    def type(self, uri):
        return [ x['type'] for x in self.query(f'''SELECT ?type WHERE {{ {uri} a ?type . }}''', initNs=Prefix.NAMESPACES) ]
    
    def functions(self):
        return [ x['fun'] for x in self.query(f'''SELECT ?fun WHERE {{ ?fun a fno:Function . }}''', initNs=Prefix.NAMESPACES) ]
    
    def check_call(self, f):
        """
        Checks if a function call is applied in the graph and returns the function it applies.
        
        :param f: URIRef
            The function URI to check.
        :return: URIRef
            The applied function URI or the original URI if no specific function is found.
        """
        result = [x['f'] for x in self.query(
            f'''SELECT ?f WHERE {{ <{f}> fnoc:applies ?f . }}''', 
            initNs=Prefix.NAMESPACES
        )]
        if len(result) == 1:
            return result[0]
        return f
    
    def get_order(self, f):
        next = [x['next'] for x in self.query(
            f'''SELECT ?next WHERE {{ <{f}> fnoc:next ?next . }}''', 
            initNs=Prefix.NAMESPACES
        )]
        if len(next) > 1:
            raise Exception(f"Applied function {f} has ambigous next order: {next}")
        
        iterate = [x['iterate'] for x in self.query(
            f'''SELECT ?iterate WHERE {{ <{f}> fnoc:iterate ?iterate . }}''', 
            initNs=Prefix.NAMESPACES
        )]
        if len(iterate) > 1:
            raise Exception(f"Applied function has ambigous iterate order: {iterate}")
        
        iftrue = [x['iftrue'] for x in self.query(
            f'''SELECT ?iftrue WHERE {{ <{f}> fnoc:true ?iftrue . }}''', 
            initNs=Prefix.NAMESPACES
        )]
        if len(iftrue) > 1:
            raise Exception(f"Applied function has ambigous iftrue order: {iftrue}")
        
        iffalse = [x['iffalse'] for x in self.query(
            f'''SELECT ?iffalse WHERE {{ <{f}> fnoc:false ?iffalse . }}''', 
            initNs=Prefix.NAMESPACES
        )]
        if len(iffalse) > 1:
            raise Exception(f"Applied function has ambigous iftrue order: {iffalse}")
        
        return (
            next[0] if len(next) == 1 else None,
            iterate[0] if len(iterate) == 1 else None,
            iftrue[0] if len(iftrue) == 1 else None,
            iffalse[0] if len(iffalse) == 1 else None
        )

    def get_name(self, f):
        """
        Retrieves the context-free name of a function.
        
        :param f: URIRef
            The function URI to retrieve the name for.
        :return: str or None
            The function's context-free name or None if not found.
        """
        f = self.check_call(f)
        result = [x['name'].value for x in self.query(
            f'''
            SELECT ?name WHERE {{
                <{f}> rdfs:label ?name ;
            }}''', 
            initNs=Prefix.NAMESPACES
        )]
        
        """
        result = [x['name'].value for x in self.query(
            f'''
            SELECT ?name WHERE {{
                ?mapping fno:function <{f}> ;
                         fno:methodMapping ?methodmap .
                ?methodmap fnom:method-name ?name .
            }}''', 
            initNs=Prefix.NAMESPACES
        )]
        """
        
        return result[0] if len(result) > 0 else None
    
    def is_function(self, s) -> bool:
        results = self.query(
            f'''ASK WHERE {{ <{s}> a fno:Function . }}''', 
            initNs=Prefix.NAMESPACES
        )
        return True if results else False

    def is_parameter(self, s) -> bool:
        """
        Checks if a URI is a parameter.
        
        :param s: URIRef
            The URI to check.
        :return: bool
            True if the URI is a parameter, False otherwise.
        """
        s = self.check_call(s)
        results = self.query(
            f'''ASK WHERE {{ <{s}> a fno:Parameter . }}''', 
            initNs=Prefix.NAMESPACES
        )
        return True if results else False

    def is_output(self, s) -> bool:
        """
        Checks if a URI is an output.
        
        :param s: URIRef
            The URI to check.
        :return: bool
            True if the URI is an output, False otherwise.
        """
        s = self.check_call(s)
        results = self.query(
            f'''ASK WHERE {{ <{s}> a fno:Output . }}''', 
            initNs=Prefix.NAMESPACES
        )
        return True if results else False
    
    def has_function(self, uri):
        result = self.query(f"""
            ASK WHERE {{
                <{uri}> a fno:Function .
            }}""")
        return True if result else False

    def get_function(self, name):
        """
        Retrieves the function URI for a given name.

        :param name: str
            The name of the function to retrieve.
        :return: URIRef or None
            The function URI or None if not found.
        """
        try:
            result = [
                x['f'] for x in self.query(f'''
                SELECT ?f WHERE {{
                    ?f a fno:Function
                }}''', initNs=Prefix.NAMESPACES)
            ]

            for f in result:
                if get_name(f) == name:
                    return f
            raise Exception("Could not find function")
        except Exception as e:
            print(f"Error while querying function from name {name}: <{e}>")
            return

    def get_parameters(self, f, include_self=False) -> list[str]:
        """
        Retrieves the list of parameters for a function, excluding 'self' parameters.

        :param f: URIRef
            The function URI to retrieve parameters for.
        :return: list[str]
            A sorted list of parameter URIs.
        """
        result = sorted([
            x['param']
            for x in self.query(f'''
                SELECT ?param WHERE {{
                    <{f}> a fno:Function ;
                           fno:expects ?list .
                    ?list ?index ?param .
                    ?param fno:predicate ?pred .
                    FILTER(?pred != <{to_uri(get_prefix(f), 'self')}>)
                }}
            ''', initNs=Prefix.NAMESPACES)
        ])
        
        if include_self:
            self_param = self.get_self(f)
            if self_param:
                result.append(self_param)
        
        return result

    def get_parameter_at(self, f, i) -> list[str]:
        """
        Retrieves the parameter at a given position for a function.

        :param f: URIRef
            The function URI to retrieve the parameter for.
        :param i: int
            The position index of the parameter.
        :return: list[str]
            The parameter URI at the given position, or None if not found.
        """
        result = [
            x['param'] for x in self.query(f'''
                SELECT ?param WHERE {{
                    ?mapping a fno:Mapping ;
                             fno:function <{f}> ;
                             fno:parameterMapping ?parmapping .
                    ?parmapping a fnom:PositionParameterMapping ;
                                fnom:functionParameter ?param ;
                                fnom:implementationParameterPosition {Literal(i).n3()} .
                }}
            ''', initNs=Prefix.NAMESPACES)
        ]
        return result[0] if len(result) == 1 else None

    def get_parameter_index(self, f, param) -> list[str]:
        """
        Retrieves the position index of a given parameter for a function.

        :param f: URIRef
            The function URI to retrieve the parameter index for.
        :param param: str
            The parameter name.
        :return: list[str]
            The position index of the parameter, or None if not found.
        """
        prefix = get_prefix(f)
        result = [
            x['index'].value for x in self.query(f'''
                SELECT ?index WHERE {{
                    ?mapping a fnom:Mapping ;
                             fno:function <{f}> ;
                             fno:parameterMapping ?parmapping .
                    ?parmapping a fnom:PositionParameterMapping ;
                                fnom:functionParameter <{to_uri(prefix, param)}> ;
                                fnom:implementationParameterPosition ?index .
                }}
            ''', initNs=Prefix.NAMESPACES)
        ]
        return result[0] if len(result) == 1 else None

    def get_param_predicates(self, f) -> list[str]:
        """
        Retrieves the predicates for all parameters of a function.

        :param f: URIRef
            The function URI to retrieve parameter predicates for.
        :return: list[str]
            A list of tuples containing parameter URIs and their predicates.
        """
        return [
            (x['param'], x['pred'])
            for x in self.query(f'''
                SELECT ?param ?pred WHERE {{
                    <{f}> a fno:Function ;
                           fno:expects ?list .
                    ?list ?index ?param .
                    ?param fno:predicate ?pred .
                    FILTER(?pred != <{to_uri(get_prefix(f), 'self')}>)
                }}
            ''', initNs=Prefix.NAMESPACES)
        ]

    def get_predicate(self, s):
        """
        Retrieves the predicate of a given parameter or output.

        :param s: URIRef
            The parameter or output URI to retrieve the predicate for.
        :return: URIRef
            The predicate of the parameter or output.
        """
        return [
            x['pred']
            for x in self.query(f'''
                SELECT ?pred WHERE {{
                    VALUES ?type {{ fno:Parameter fno:Output }}
                    <{s}> a ?type ;
                          fno:predicate ?pred .
                }}
            ''', initNs=Prefix.NAMESPACES)
        ][0]

    def get_predicate_param(self, f, pred) -> str:
        """
        Retrieves the parameter corresponding to a given predicate for a function.

        :param f: URIRef
            The function URI to retrieve the parameter for.
        :param pred: str
            The predicate name.
        :return: str
            The parameter URI corresponding to the predicate, or None if not found.
        """
        f = self.check_call(f)
        prefix = get_prefix(f)
        result = [
            x['param']
            for x in self.query(f'''
                SELECT ?param WHERE {{
                    <{f}> a fno:Function ;
                          fno:expects ?list .
                    ?list ?index ?param .
                    ?param a fno:Parameter ;
                           fno:predicate <{to_uri(prefix, pred)}> .
                }}
            ''', initNs=Prefix.NAMESPACES)
        ]
        return result[0] if len(result) > 0 else None

    def get_param_type(self, param):
        """
        Retrieves the type of a given parameter.

        :param param: URIRef
            The parameter URI to retrieve the type for.
        :return: str
            The type of the parameter, or a default type if not found.
        """
        result = [
            x['type']
            for x in self.query(f'''
                SELECT ?type WHERE {{
                    <{param}> a fno:Parameter ;
                              fno:type ?type .
                }}
            ''', initNs=Prefix.NAMESPACES)
        ]
        
        return result[0] if len(result) > 0 else Any

    def get_self(self, f) -> str:
        """
        Retrieves the 'self' parameter of a function.

        :param f: URIRef
            The function URI to retrieve the 'self' parameter for.
        :return: str
            The 'self' parameter URI, or None if not found.
        """
        f = self.check_call(f)

        result = [
            x['param']
            for x in self.query(f'''
                SELECT ?param WHERE {{
                    <{f}> a fno:Function ;
                           fno:expects ?list .
                    ?list ?index ?param .
                    ?param fno:predicate ?pred .
                    FILTER(?pred = <{to_uri(get_prefix(f), 'self')}>)
                }}
            ''', initNs=Prefix.NAMESPACES)
        ]

        return result[0] if len(result) > 0 else None
     
    def has_self(self, f: URIRef) -> bool:
        """
        Check if a FnO Function has a `self` parameter.

        :param f: rdflib.URIRef
            The URI of the function you want to check.
        
        :return: bool
            `True` if the function has a `self` parameter, `False` otherwise
        """
        results = self.query(
            f'''ASK WHERE {{ 
                <{f}> fno:expects ?list . 
                ?list ?index ?param .
                ?param fno:predicate ?pred .
                FILTER(?pred = <{to_uri(get_prefix(f), 'self')}>)
            }}''', 
            initNs=Prefix.NAMESPACES
        )
        return True if results else False

    def get_output(self, f) -> str:
        """
        Retrieves the output of a function.

        :param f: URIRef
            The function URI to retrieve the output for.
        :return: str
            The output URI, or None if not found.
        """
        f = self.check_call(f)
        result = [
            x['output']
            for x in self.query(f'''
                SELECT ?output ?pred WHERE {{
                    <{f}> a fno:Function ;
                           fno:returns ?list .
                    ?list ?index ?output .
                    ?output a fno:Output ;
                            fno:predicate ?pred .
                    FILTER(?pred != <{to_uri(get_prefix(f), 'self_output')}>)
                }}
            ''', initNs=Prefix.NAMESPACES)
        ]

        return result[0] if len(result) > 0 else None
     
    def has_output(self, f: URIRef) -> bool:
        """
        Check if a FnO Function has an output which is not a `self` output.

        :param f: rdflib.URIRef
            The URI of the function you want to check.
        
        :return: bool
            `True` if the function has an output which is not a `self` output., `False` otherwise.
        """
        results = self.query(
            f'''ASK WHERE {{ 
                <{f}> fno:returns ?list . 
                ?list ?index ?output .
                ?output fno:predicate ?pred .
                FILTER(?pred != <{to_uri(get_prefix(f), 'self_output')}>)
            }}''', 
            initNs=Prefix.NAMESPACES
        )
        return True if results else False

    def get_self_output(self, f) -> str:
        """
        Retrieves the 'self_output' of a function.

        :param f: URIRef
            The function URI to retrieve the 'self_output' for.
        :return: str
            The 'self_output' URI, or None if not found.
        """
        f = self.check_call(f)
        result = [
            x['output']
            for x in self.query(f'''
                SELECT ?output ?pred WHERE {{
                    <{f}> a fno:Function ;
                           fno:returns ?list .
                    ?list ?index ?output .
                    ?output a fno:Output ;
                            fno:predicate ?pred .
                    FILTER(?pred = <{to_uri(get_prefix(f), 'self_output')}>)
                }}
            ''', initNs=Prefix.NAMESPACES)
        ]

        return result[0] if len(result) > 0 else None
     
    def has_self_output(self, f: URIRef) -> bool:
        """
        Check if a FnO Function has a `self` output.

        :param f: rdflib.URIRef
            The URI of the function you want to check.
        
        :return: bool
            `True` if the function has a `self` output., `False` otherwise.
        """
        results = self.query(
            f'''ASK WHERE {{ 
                <{f}> fno:returns ?list . 
                ?list ?index ?output .
                ?output fno:predicate ?pred .
                FILTER(?pred = <{to_uri(get_prefix(f), 'self_output')}>)
            }}''', 
            initNs=Prefix.NAMESPACES
        )
        return True if results else False

    def get_output_predicate(self, f) -> str:
        """
        Retrieves the predicate for the output of a function.

        :param f: URIRef
            The function URI to retrieve the output predicate for.
        :return: str
            A tuple containing the output URI and its predicate.
        """
        return [
            (x['output'], x['pred'])
            for x in self.query(f'''
                SELECT ?output ?pred WHERE {{
                    <{f}> a fno:Function ;
                           fno:returns ?list .
                    ?list ?index ?output .
                    ?output fno:predicate ?pred .
                FILTER(?pred != <{to_uri(get_prefix(f), 'self_output')}>)
                }}
            ''', initNs=Prefix.NAMESPACES)
        ][0]

    def get_output_type(self, out) -> str:
        """
        Retrieves the type of a given output.

        :param out: URIRef
            The output URI to retrieve the type for.
        :return: str
            The type of the output, or a default type if not found.
        """
        result = [
            x['type']
            for x in self.query(f'''
                SELECT ?type WHERE {{
                    <{out}> a fno:Output ;
                            fno:type ?type .
                }}
            ''', initNs=Prefix.NAMESPACES)
        ]
        return result[0] if len(result) > 0 else Any
    
    def get_outputs(self, f):
        """
        Retrieve the outputs of a function
        
        Args:
            f (URIRef): the function to get the outputs from
        
        Returns:
            return (List[URIRef]): List of outputs
        """
        return [
            x['out'] for x in self.query(f"""
                SELECT ?out WHERE {{
                    <{f}> fno:returns ?outs .
                    ?outs ?index ?out .
                }}""", initNs=Prefix.NAMESPACES)
        ]
        
    
    ### COMPOSITION ###
     
    def has_composition(self, f):
         result = self.query(f'''
                ASK WHERE {{
                    ?comp fnoc:represents <{f}> .
                }}
             ''', initNs=Prefix.NAMESPACES)

         return True if result else False
     
    def get_compositions(self, f, first=False):
         result = [
             x['comp']
             for x in self.query(f'''
                SELECT ?comp WHERE {{
                    ?comp fnoc:represents <{f}> .
                }}
             ''', initNs=Prefix.NAMESPACES)
         ]

         return result[0] if first else result
     
    def is_composition(self, c: URIRef) -> bool:
         result = self.query(f'''
            ASK WHERE {{ <{c}> a fnoc:Composition . }}
         ''', initNs=Prefix.NAMESPACES)
         return True if result else False
     
    def get_start(self, c: URIRef) -> URIRef:
        result = [
            x['start']
            for x in self.query(f'''
                SELECT ?start WHERE {{
                    <{c}> fnoc:start ?start .
                }}
            ''', initNs=Prefix.NAMESPACES)
        ]
        
        if len(result) > 1:
            raise Exception(f"Composition has multiple starts: {result}")
        if len(result) == 0:
            raise Exception(f"Composition has no start defined")
        return result[0]
        
    
    def get_representations(self, c: URIRef) -> URIRef:
        result = [
            x['f']
            for x in self.query(f'''
                SELECT ?f WHERE {{
                    <{c}> fnoc:represents ?f .
                }}
            ''', initNs=Prefix.NAMESPACES)
        ]
        return result
     
    def get_mappings(self, c):
        """
        Get all the mappings from a given composition
        
        :param c: URIRef
            The URI of the composition
        :return:
            A set of tuples where the first element is the 'mapfrom' node and the second element is the 'mapto' node
        """
        results = self.query(f'''
            SELECT ?mapfrom ?mapto ?priority WHERE {{
                <{c}> fnoc:composedOf ?mapping .
                ?mapping fnoc:mapFrom | fnoc:mapFromTerm ?mapfrom ;
                         fnoc:mapTo ?mapto .
                
                OPTIONAL {{
                    ?mapping fnoc:priority ?priority
                }}
            }}
        ''', initNs=Prefix.NAMESPACES)

        # Return the distinct set of mappings
        return set([ (m['mapfrom'], m['mapto'], m['priority']) for m in results ])
    
    def is_function_mapping(self, endpoint):
        """
        Check if a mapping endpoint is 'function mapping'. In other words it maps the parameter/output of a function.
        
        :param endpoint:
        The URI of the mapping endpoint (blank node)
        
        :return: bool
        True if the endpoint is a 'function mapping'. False otherwise.
        """
        results = self.query(f'''ASK WHERE {{ ?mapping fnoc:mapFrom | fnoc:mapTo ?endpoint }}''',
                             initNs=Prefix.NAMESPACES, initBindings={'endpoint': endpoint})
        return True if results else False
    
    def get_function_mapping(self, endpoint):
        """
        Get the URI of the function and the parameter used in a 'function mapping'.
        
        :param URIRef endpoint:
        The URI of the mapping endpoint (blank node)
        
        :return:
        A tuple where the first element is the function URI and the second element is the parameter URI.
        """
        result = [ (x['f'], x['ter']) for x in self.query(f'''
            SELECT ?f ?ter WHERE {{
               ?endpoint fnoc:constituentFunction ?f ;
                            fnoc:functionParameter | fnoc:functionOutput ?ter . 
            }}''', initNs=Prefix.NAMESPACES, initBindings={'endpoint': endpoint})][0]
        return result
    
    def is_term_mapping(self, endpoint):
        """
        Check if a mapping endpoint is 'term mapping'. In other words it maps a constant.
        
        :param URIRef endpoint:
        The URI of the mapping endpoint (blank node)
        
        :return:
        True if the endpoint is a 'term mapping'. False otherwise.
        """
        results = self.query(f'''ASK WHERE {{ ?mapping fnoc:mapFromTerm ?endpoint }}''',
                             initNs=Prefix.NAMESPACES, initBindings={'endpoint': endpoint})
        return True if results else False
    
    def has_strategy(self, endpoint):
        results = self.query(f'''ASK WHERE {{ ?endpoint fnoc:mappingStrategy ?strat }}''',
                             initNs=Prefix.NAMESPACES, initBindings={'endpoint': endpoint})
        return True if results else False

    def get_strategy(self, endpoint):
        result = [ (get_name(x['strat']), x['key'].value) for x in self.query(f'''
            SELECT ?strat ?key WHERE {{
               ?endpoint fnoc:mappingStrategy ?strat ; 
                         fnoc:key ?key .
            }}''', initNs=Prefix.NAMESPACES, initBindings={'endpoint': endpoint})]
        
        if len(result) > 1:
            raise Exception("Mapping endpoint has multiple mapping strategies.")
        elif len(result) == 1:
            return result[0]
        return None, None
    
    def unmapped_parameters(self, comp_uri, fun_uri):
        """
        Return a list of parameters for a given function that are not mapped in the composition
        """
        parameters = self.get_parameters(fun_uri, include_self=True)
        
        mapped = [
            x['par'] for x in self.query(f"""
                SELECT ?par WHERE {{
                    <{comp_uri}> fnoc:composedOf ?mapping .
                    ?mapping fnoc:mapto ?endpoint .
                    ?endpoint fnoc:consituentFunction <{fun_uri}> ;
                        fnoc:functionParameter ?par .
            }}""", initNs=Prefix.NAMESPACES)
        ]
        
        return [param for param in parameters if param not in mapped]
    
    ### TERMS ###
    
    def is_list(self, seq):
        result = self.query(f"""
            ASK WHERE {{
                ?seq a rdf:Seq .
            }}""", initNs=Prefix.NAMESPACES, initBindings={'seq': seq})
        
        return True if result else False
    
    def to_list(self, seq):
        result = [
            (x['index'], x['term']) for x in self.query(f"""
                SELECT ?index ?term WHERE {{
                    ?seq a rdf:Seq ;
                        ?index ?term .
                }}""", initNs=Prefix.NAMESPACES, initBindings={'seq': seq})
        ]
        
        return [ term[1] for term in sorted(result, key=lambda x: x[0]) if term[0] != Prefix.ns('rdf').type ]
    
    ### PARAMETER MAPPING ###
    
    def get_mapping(self, f, first=False):
        f = self.check_call(f)
        result = [
            x['mapping']
            for x in self.query(f'''
                    SELECT ?mapping WHERE {{
                        ?mapping fno:function <{f}> ;
                                a fno:Mapping .
                    }}''', initNs=Prefix.NAMESPACES)
        ]
        
        return result[0] if first else result
     
    def get_positionals(self, mapping):
          """
          Get positional parameters of a function.

          Args:
               f (str): The URI of the function.

          Returns:
               list: A list of positional parameters.
          """
          try:
               positional = sorted([
                    (x['index'].value, x['param'])
                    for x in self.query(f'''
                         SELECT ?index ?param WHERE {{
                              <{mapping}> fno:parameterMapping ?posmapping .
                              ?posmapping fnom:functionParameter ?param ;
                                        fnom:implementationParameterPosition ?index .
                              ?param fno:predicate ?pred .
                              FILTER(?pred != <{to_uri(get_prefix(mapping), 'self')}>)
                         }}''', initNs=Prefix.NAMESPACES)
               ], key=lambda x: x[0])
               return [pos[1] for pos in positional]
          except ParseException as e:
               print(f"Error while parsing query when fetching positional parameters for <{get_name(mapping)}>: <{e}>")
               return []
    
    def parameter_position(self, mapping, param):
        """
        Retrieve the mapped index for a given parameter
        
        Args:
            mapping (URIRef): The mapping that defines the index
            param (URIRef): The parameter to get the index from
            
        Returns:
            return (int | None): The mapped index or None if no PositionParameterMapping is defined
        """
        try:
            result = [
                (x['index'].value)
                for x in self.query(f'''
                    SELECT ?index WHERE {{
                        <{mapping}> fno:parameterMapping ?posmapping .
                        ?posmapping fnom:functionParameter <{param}> ;
                                fnom:implementationParameterPosition ?index .
                    }}''', initNs=Prefix.NAMESPACES)
            ]
            
            if len(result) == 1:
                return result[0]
            if len(result) == 0:
                return None
            
            raise Exception(f"Multiple indices mapped with in mapping {mapping} for parameter {param}: {result}")
        except ParseException as e:
            print(f"Error while parsing query when fetching keyword parameters for <{get_name(mapping)}>: <{e}>")
            return None

    def get_keywords(self, mapping):
        """
        Get keyword parameters of a function.

        Args:
            f (str): The URI of the function.

        Returns:
            list: A list of keyword parameters.
        """
        try:
            return {
                x['property'].value: x['param']
                for x in self.query(f'''
                        SELECT ?param ?property WHERE {{
                            <{mapping}> fno:parameterMapping ?keymapping .
                            ?keymapping fnom:functionParameter ?param ;
                                    fnom:implementationProperty ?property .
                        }}''', initNs=Prefix.NAMESPACES)
            }
        except ParseException as e:
            print(f"Error while parsing query when fetching keyword parameters for <{get_name(mapping)}>: <{e}>")
            return {}
    
    def get_keyword(self, mapping, key):
        """
        Get parameter based on a key for an FnO mapping.

        Args:
            mapping (URIRef): The FnO Mapping
            key (str): The key used in the mapping
        Returns:
            URIRef: The FnO Parameter mapped with the key
        """
        try:
            result = [ x['param'] for x in self.query(f'''
                SELECT ?param ?property WHERE {{
                    <{mapping}> fno:parameterMapping ?keymapping .
                    ?keymapping fnom:functionParameter ?param ;
                            fnom:implementationProperty {Literal(key).n3()} .
                }}''', initNs=Prefix.NAMESPACES)
            ]
            
            if len(result) == 1:
                return result[0]
            if len(result) == 0:
                raise Exception(f"No parameter mapped with key '{key}' in mapping {mapping}.")
            if len(result) > 1:
                raise Exception(f"Multiple parameters mapped with key '{key}' in mapping {mapping}: {result}")
        except ParseException as e:
            print(f"Error while parsing query when fetching keyword parameters for <{get_name(mapping)}>: <{e}>")
            return {}
    
    def parameter_keyword(self, mapping, param):
        """
        Retrieve the mapped key for a given parameter
        
        Args:
            mapping (URIRef): The mapping that defines the index
            param (URIRef): The parameter to get the index from
            
        Returns:
            return (str | None): The mapped key or None if no PropertyParameterMapping is defined
        """
        result = [
            (x['key'].value)
            for x in self.query(f'''
                SELECT ?key WHERE {{
                    <{mapping}> fno:parameterMapping ?keymapping .
                    ?keymapping fnom:functionParameter <{param}> ;
                            fnom:implementationProperty ?key .
                }}''', initNs=Prefix.NAMESPACES)
        ]
        
        if len(result) == 1:
            return result[0]
        if len(result) == 0:
            return None
        
        raise Exception(f"Multiple keys mapped in mapping {mapping} for parameter {param}: {result}")
    
    def is_list_mapping(self, mapping, param):
        try:
            result = self.query(f'''
                ASK WHERE {{
                    <{mapping}> fno:parameterMapping ?varmapping .
                    ?varmapping a fnom:ListMapping ;
                            fnom:functionParameter <{param}> .
                }}''', initNs=Prefix.NAMESPACES)
            return True if result else False
        except ParseException as e:
            print(f"Error while parsing query when fetching variable positional parameters for <{get_name(mapping)}>: <{e}>")
            return None

    def get_varpositional(self, mapping):
          """
          Get variable positional parameters of a function.

          Args:
               f (str): The URI of the function.

          Returns:
               str: The variable positional parameter.
          """
          try:
               result = [
                    x['param']
                    for x in self.query(f'''
                         SELECT ?property ?param WHERE {{
                              <{mapping}> fno:parameterMapping ?varmapping .
                              ?varmapping a fnom:ListMapping ;
                                        fnom:functionParameter ?param .
                         }}''', initNs=Prefix.NAMESPACES)
               ]
               return result
          except ParseException as e:
               print(f"Error while parsing query when fetching variable positional parameters for <{get_name(mapping)}>: <{e}>")
               return None

    def is_varpositional(self, mapping, param):
          """
          Check if a parameter of a function is a variable positional parameter.

          Args:
               f (str): The URI of the function.
               param (str): The URI of the parameter.

          Returns:
               bool: True if the parameter is a variable positional parameter, False otherwise.
          """
          try:
               result = self.query(f'''
                              ASK WHERE {{
                                   <{mapping}> fno:parameterMapping ?varmapping .
                                   ?varmapping a fnom:ListMapping ;
                                             fnom:functionParameter <{param}> .
                              }}''', initNs=Prefix.NAMESPACES)
               return True if result else False
          except ParseException as e:
               print(f"Error while parsing query when fetching variable positional parameters for <{get_name(mapping)}>: <{e}>")
               return False

    def get_varkeyword(self, mapping):
          """
          Get variable keyword parameters of a function.

          Args:
               f (str): The URI of the function.

          Returns:
               str: The variable keyword parameter.
          """
          try:
               result = [
                    x['param']
                    for x in self.query(f'''
                         SELECT ?property ?param WHERE {{
                              <{mapping}> fno:parameterMapping ?varmapping .
                              ?varmapping a fnom:KeyValueMapping ;
                                        fnom:functionParameter ?param .
                         }}''', initNs=Prefix.NAMESPACES)
               ]
               return result
          except ParseException as e:
               print(f"Error while parsing query when fetching variable keyword parameters for <{get_name(mapping)}>: <{e}>")
               return None

    def is_varkeyword(self, mapping, param):
          """
          Check if a parameter of a function is a variable keyword parameter.

          Args:
               f (str): The URI of the function.
               param (str): The URI of the parameter.

          Returns:
               bool: True if the parameter is a variable keyword parameter, False otherwise.
          """
          try:
               result = self.query(f'''
                              ASK WHERE {{
                                   <{mapping}> fno:parameterMapping ?varmapping .
                                   ?varmapping a fnom:KeyValueMapping ;
                                             fnom:functionParameter <{param}> .
                              }}''', initNs=Prefix.NAMESPACES)
               return True if result else False
          except ParseException as e:
               print(f"Error while parsing query when fetching variable keyword parameters for <{get_name(mapping)}>: <{e}>")
               return False
     
          
    def get_param_mapping(self, mapping, param):
          """
          Retrieve mapping information for a specified parameter of a function.

          Args:
               f (str): The URI of the function.
               param (str): The URI of the parameter for which mapping information is to be retrieved.

          Returns:
               tuple: A tuple containing the index and property mapping of the parameter.
                         If no mapping information is found, (None, None) is returned.

          Raises:
               ParseException: If there is an error while parsing the query.
          """
          try:
               result = [
                    (x['index'].value if x['index'] is not None else None,
                     x['property'].value if x['property'] is not None else None)
                    for x in self.query(f'''
                         SELECT ?index ?property WHERE {{
                              OPTIONAL {{ 
                                   <{mapping}> fno:parameterMapping ?posmapping .
                                   ?posmapping fnom:functionParameter <{param}> ;
                                               fnom:implementationParameterPosition ?index . 
                              }}
                              OPTIONAL {{ 
                                   <{mapping}> fno:parameterMapping ?propmapping .
                                   ?propmapping fnom:functionParameter <{param}> ;
                                                fnom:implementationProperty ?property . 
                              }}
                         }}
                    ''', initNs=Prefix.NAMESPACES) 
               ]
               return result[0] if len(result) > 0 else (None, None)
          except ParseException as e:
               print(f"Error while parsing query when fetching imp mapping for <{get_name(mapping)}>: <{e}>")
               return
    
    def get_default_mapping(self, mapping, param):
        try:
            result = [
                x['default'] if x['default'] is not None else None
                for x in self.query(f'''
                    SELECT ?default WHERE {{
                        <{mapping}> fno:parameterMapping ?defmapping .
                        ?defmapping fnom:functionParameter <{param}> ;
                                    fnom:defaultValue ?default . 
                    }}
                    ''', initNs=Prefix.NAMESPACES)
                ]
               
            if len(result) > 1:
                raise Exception(f"Parameter {param} has multiple default values: {result}")
            elif len(result) == 1:
                return True, result[0]
            return False, None
        
        except ParseException as e:
            print(f"Error while parsing query when fetching default param mapping for <{get_name(param)}>: <{e}>")
            return
     
    def get_used_functions(self, c: URIRef):
        """
        Get all used functions inside a composition

        :param c: rdflib.URIRef
            URIRef of the composition you want the used functions from.

        :return: List[rdflib.URIRef]
            A list containing the URIs of all the functions used inside the composition.
        """
        results = self.query(f'''
            SELECT ?call WHERE {{
                <{c}> fnoc:composedOf ?mapping .
                ?mapping ?map ?node .
                ?node fnoc:constituentFunction ?call .
            }}
            ''', initNs=Prefix.NAMESPACES)
        results = { x['call'] for x in results }
        results.add(self.get_start(c))
        
        return  results
    
    def depends_on(self, c: URIRef, f: URIRef):
        """
        Get all the functions on which this functions depends on
        
        :param c: rdflib.URIRef
            URIRef of the composition which the function belongs to
        
        :param f: rdflib.URIRef
            URIRef of the applied function you want to calculate the dependencies of
            
        :returns:
            A list of dependencies
        """
        
        dependencies = [x['dep'] for x in self.query(f'''
            SELECT ?dep WHERE {{
                <{c}> fnoc:composedOf ?mapping .
                ?mapping fnoc:mapto ?mapto .
                ?mapto fnoc:constituentFunction <{f}> .
                ?mapping fnoc:mapfrom ?mapfrom .
                ?mapfrom fnoc:constituentFunction ?dep .}}''')]
        
        return dependencies
     
    def get_function_description(self, f_uri) -> "FnOGraph":
          """
          Retrieve the description of a function, including its parameters, outputs, implementation, and other related information.

          Args:
               name (str): The URI of the function for which the description is to be retrieved.

          Returns:
               PipelineGraph: A PipelineGraph object containing the description of the function.

          Raises:
               ParseException: If there is an error while parsing the query.
          """
          # Get Full Function Description
          triples = [
               (f_uri, x['p'], x['o'])
               for x in self.query(f'''
                    SELECT ?p ?o WHERE {{
                         <{f_uri}> ?p ?o .
                    }}''', initNs=Prefix.NAMESPACES)
          ]

          # Get parameters
          triples.extend([
               (x['s'], x['p'], x['o'])
               for x in self.query(f'''
                    SELECT ?s ?p ?o WHERE {{
                         <{f_uri}> fno:expects ?s .
                         ?s ?p ?o .
                    }}''', initNs=Prefix.NAMESPACES)
          ])

          # Get outputs
          triples.extend([
               (x['s'], x['p'], x['o'])
               for x in self.query(f'''
                    SELECT ?s ?p ?o WHERE {{
                         <{f_uri}> fno:returns ?s .
                         ?s ?p ?o .
                    }}''', initNs=Prefix.NAMESPACES)
          ])

          # Get implementation mappings
          triples.extend([
               (x['s'], x['p'], x['o'])
               for x in self.query(f'''
                    SELECT ?s ?p ?o WHERE {{
                         ?s fno:function <{f_uri}> .
                         ?s ?p ?o .
                    }}''', initNs=Prefix.NAMESPACES)
          ])
          triples.extend([
               (x['s'], x['p'], x['o'])
               for x in self.query(f'''
                    SELECT ?s ?p ?o WHERE {{
                         ?mapping fno:function <{f_uri}> .
                         ?mapping ?type ?s .
                         ?s ?p ?o .
                    }}''', initNs=Prefix.NAMESPACES)
          ])

          # Get implementation
          triples.extend([
               (x['s'], x['p'], x['o'])
               for x in self.query(f'''
                    SELECT ?s ?p ?o WHERE {{
                         ?mapping fno:function <{f_uri}> ;
                                  fno:implementation ?s .
                         ?s ?p ?o .
                    }}''', initNs=Prefix.NAMESPACES)
          ])

          # Get Parameter Descriptions
          for param in self.get_parameters(f_uri):
               triples.extend([
                    (param, x['p'], x['o'])
                    for x in self.query(f'''
                         SELECT ?p ?o WHERE {{
                              <{param}> ?p ?o .
                         }}''', initNs=Prefix.NAMESPACES)
               ])

               # Get Parameter types
               triples.extend([
                    (x['s'], x['p'], x['o'])
                    for x in self.query(f'''
                         SELECT ?s ?p ?o WHERE {{
                              <{param}> fno:type ?s .
                         ?s ?p ?o .
                         }}''', initNs=Prefix.NAMESPACES)
               ])
          
          # Get Self Description
          param = self.get_self(f_uri)
          if param:
               triples.extend([
                    (param, x['p'], x['o'])
                    for x in self.query(f'''
                         SELECT ?p ?o WHERE {{
                              <{param}> ?p ?o .
                         }}''', initNs=Prefix.NAMESPACES)
               ])

               # Get Self type
               triples.extend([
                    (x['s'], x['p'], x['o'])
                    for x in self.query(f'''
                         SELECT ?s ?p ?o WHERE {{
                             <{param}> fno:type ?s .
                         ?s ?p ?o .
                         }}''', initNs=Prefix.NAMESPACES)
               ])
          
          # Get Output Description
          out = self.get_output(f_uri)
          if out:
               triples.extend([
                    (out, x['p'], x['o'])
                    for x in self.query(f'''
                         SELECT ?p ?o WHERE {{
                              <{out}> ?p ?o .
                         }}''', initNs=Prefix.NAMESPACES)
               ])

               # Get output type
               triples.extend([
                    (x['s'], x['p'], x['o'])
                    for x in self.query(f'''
                         SELECT ?s ?p ?o WHERE {{
                              <{out}> fno:type ?s .
                         ?s ?p ?o .
                         }}''', initNs=Prefix.NAMESPACES)
               ])
          
          # Get Self Output Description
          self_out = self.get_self_output(f_uri)
          if self_out:
               triples.extend([
                    (self_out, x['p'], x['o'])
                    for x in self.query(f'''
                         SELECT ?p ?o WHERE {{
                              <{self_out}> ?p ?o .
                         }}''', initNs=Prefix.NAMESPACES)
               ])

               # Get output type
               triples.extend([
                    (x['s'], x['p'], x['o'])
                    for x in self.query(f'''
                         SELECT ?s ?p ?o WHERE {{
                              <{self_out}> fno:type ?s .
                         ?s ?p ?o .
                         }}''', initNs=Prefix.NAMESPACES)
               ])
          
          # Get all function calls
          triples.extend([
               (x['call'], Prefix.NAMESPACES['fnoc']['applies'], f_uri)
               for x in self.query(f'''
                    SELECT ?call WHERE {{
                         ?call fnoc:applies <{f_uri}> .
                    }}
               ''', initNs=Prefix.NAMESPACES)
          ])

          desc = Prefix.bind_namespaces(FnOGraph())
          [ desc.add(x) for x in triples ]
          return desc
    
        ### IMPLEMENTATION ###
     
    def fun_to_imp(self, fun):
        """
        Retrieve all possible implementations of a function.

        Args:
            f (str): The URI of the function.

        Returns:
            Tuple[]: A list of tuples where each tuple contains the URI of a mapping and a corresponding implementation URI.
        """
        fun = self.check_call(fun)

        result = [
            (x['mapping'], x['imp'])
            for x in self.query(f'''
                    SELECT ?mapping ?imp WHERE {{
                        ?mapping fno:function <{fun}> ;
                                fno:implementation ?imp .
                    }}
            ''', initNs=Prefix.NAMESPACES) 
        ]
        return result
    
    def imp_to_fun(self, imp):
        """
        Retrieve a list of FnO Mappings with the representative FnO Function for a given implementation. 
        Return None if no mapping can be found for this implementation.
        """
        result = [
            (x['mapping'], x['fun']) for x in self.query(f'''
                                            SELECT ?mapping ?fun WHERE {{
                                                ?mapping fno:function ?fun ;
                                                         fno:implementation <{imp}> .
                                            }}''', initNs=Prefix.NAMESPACES)
        ]
        return result
    
    def mappings(self, fun, imp):
        """
        Retrieve a list of FnO Mappings for a given FnO Function and implementation pair. 
        Return None if no mapping can be found for this pair.
        """
        result = [
            x['mapping'] for x in self.query(f'''
                SELECT ?mapping WHERE {{
                    ?mapping fno:function <{fun}> ;
                             fno:implementation <{imp}> .
                }}''', initNs=Prefix.NAMESPACES)
        ]
        return result
    
    def imp_from_file(self, file):
        result = [
            (x['imp'], x['mapping'], x['fun']) for x in self.query(f'''
                SELECT ?imp ?mapping ?fun WHERE {{
                    ?imp a fnoi:PythonFile ;
                        fnoi:file <file://{file}> . 
                    ?mapping fno:implementation ?imp ;
                        fno:function ?fun .
                }}''', initNs=Prefix.NAMESPACES)
        ]
        return result
    
    def get_imp_metadata(self, imp):
        result = {}
        
        for pred, obj in self.predicate_objects(subject=imp):
            if pred not in result:
                result[pred] = []
            result[pred].append(obj)
        
        return result
     
    def represents_python(self, comp):
          """
          Check if a given composition represents a python implementation.
          """
          return self.query(f'''ASK WHERE {{ 
                <{comp}> fnoc:represnts ?file .
                ?file a fnoi:PythonFile . }}''')
          
    def get_file(self, uri: URIRef):
        result = [ x['path'].removeprefix("file://") for x in self.query(f"""
                                         SELECT ?path WHERE {{
                                            <{uri}> fnoi:file ?path .
                                        }}""", initNs=Prefix.NAMESPACES)]
        
        if len(result) > 1:
            raise Exception(f"Implementation {uri} has more than one path defined: {result}")
        return result[0] if result else None
    
    def is_implementation(self, uri: URIRef):
        return self.is_python(uri) or self.is_docker(uri)
      
    ### PYTHON ###
    
    def is_python(self, uri: URIRef):
        return self.is_pythonfunction(uri) \
            or self.is_pythonclass(uri) \
            or self.is_pythonfile(uri) \
            or self.is_pythonmethod(uri) \
            or self.is_pythonmodule(uri)
        
    def is_pythonfunction(self, uri: URIRef):
        return self.query(f"""ASK WHERE {{ <{uri}> a fnoi:PythonFunction . }}""", initNs=Prefix.NAMESPACES)
    
    def is_pythonclass(self, uri: URIRef):
        return self.query(f"""ASK WHERE {{ <{uri}> a fnoi:PythonClass . }}""", initNs=Prefix.NAMESPACES)
    
    def is_pythonmodule(self, uri: URIRef):
        return self.query(f"""ASK WHERE {{ <{uri}> a fnoi:PythonModule . }}""", initNs=Prefix.NAMESPACES)
        
    def is_pythonfile(self, uri: URIRef):
        return self.query(f"""ASK WHERE {{ <{uri}> a fnoi:PythonFile . }}""", initNs=Prefix.NAMESPACES)
    
    def is_pythonmethod(self, uri: URIRef):
        return self.query(f"""ASK WHERE {{ <{uri}> a fnoi:PythonMethod . }}""", initNs=Prefix.NAMESPACES)
    
    ### DOCKER ###
    
    def is_docker(self, uri: URIRef):
        return self.is_dockerfile(uri) or self.is_dockerimage(uri) or self.is_dockercontainer(uri)
    
    def is_dockerfile(self, uri: URIRef):
        return self.query(f"""ASK WHERE {{ <{uri}> a do:Dockerfile . }}""", initNs=Prefix.NAMESPACES)
    
    def is_dockerimage(self, uri: URIRef):
        return self.query(f"""ASK WHERE {{ <{uri}> a fnoi:DockerImage . }}""", initNs=Prefix.NAMESPACES)
    
    def is_dockercontainer(self, uri: URIRef):
        return self.query(f"""ASK WHERE {{ <{uri}> a fnoi:DockerContainer . }}""", initNs=Prefix.NAMESPACES)
    
    def get_tag(self, uri: URIRef):
        results = [ x['tag'].value for x in self.query(f"""
                SELECT ?tag WHERE {{
                    <{uri}> a fnoi:DockerImage ;
                        fnoi:tag ?tag .                                
                }}""", initNs=Prefix.NAMESPACES) ]
        
        if len(results) == 1:
            return results[0]
        
        raise Exception(f"Unable to capture valid results: {results}")
    
    def get_container_mapping(self, uri: URIRef):
        results = [ (x['con'], x['mapping']) for x in self.query(f"""
                    SELECT ?con ?mapping WHERE {{
                        <{uri}> do:container ?con .
                        ?mapping fno:function ?con .
                    }}""", initNs=Prefix.NAMESPACES)]
        return results[0] if len(results) == 1 else None
    
    def get_container_id(self, uri: URIRef):
        query = f'''
        SELECT ?id WHERE {{
            <{uri}> fnoi:id ?id .
        }}'''
        
        results = [ x['id'].value for x in self.query(query, initNs=Prefix.NAMESPACES)]
        
        if len(results) > 1:
            raise Exception(f"Container {uri} has multiple ids: {results}")
        
        return results[0] if len(results) == 1 else None
    
    ### PROVENANCE ###
    
    def derived_from(self, uri: URIRef):
        
        result = [ x['d'] for x in self.query(
            f"""SELECT ?d WHERE {{
                <{uri}> prov:wasDerivedFrom ?d .
            }}""", 
            initNs=Prefix.NAMESPACES)]
        
        return result
    
    def alternatives(self, uri: URIRef):
        
        result = [ x['d'] for x in self.query(
            f"""SELECT ?d WHERE {{
                <{uri}> prov:alternateOf ?d .
            }}""", 
            initNs=Prefix.NAMESPACES)]
        
        result.extend([ x['d'] for x in self.query(
            f"""SELECT ?d WHERE {{
                ?d prov:alternateOf <{uri}> .
            }}""", 
            initNs=Prefix.NAMESPACES)])
        
        return result
    
    def specializationOf(self, uri: URIRef):
        result = [ x['d'] for x in self.query(
            f"""SELECT ?d WHERE {{
                <{uri}> prov:specializationOf ?d .
            }}""", 
            initNs=Prefix.NAMESPACES)]
        
        return result

    def generated(self, uri: URIRef):
        result = [ x['e'] for x in self.query(
            f"""SELECT ?e WHERE {{
                ?e prov:wasGeneratedBy <{uri}> .
            }}""", 
            initNs=Prefix.NAMESPACES)]
        
        return result
    
    def get_executions(self, uri: URIRef):
        
        result = [ x['e'] for x in self.query(
            f"""SELECT ?e WHERE {{
                ?e a fno:Execution ;
                    fno:executes <{uri}> .
            }}""", 
            initNs=Prefix.NAMESPACES)]
        
        return result

    def get_value(self, uri: URIRef):
        
        result = [ x['v'] for x in self.query(
            f"""SELECT ?v WHERE {{
                <{uri}> rdf:value ?v .
            }}""", 
            initNs=Prefix.NAMESPACES)]
        
        return result
    
    def get_agent(self, uri: URIRef):
        agents = []

        # Get directly associated agents
        assoc_query = self.query(f"""
            SELECT ?agent ?qualifiedAssoc ?plan ?role WHERE {{
                <{uri}> prov:wasAssociatedWith ?agent .
                OPTIONAL {{
                    <{uri}> prov:qualifiedAssociation ?qualifiedAssoc .
                    ?qualifiedAssoc prov:agent ?agent .
                    OPTIONAL {{ ?qualifiedAssoc prov:hadPlan ?plan . }}
                    OPTIONAL {{ ?qualifiedAssoc prov:hadRole ?role . }}
                }}
            }}
        """, initNs=Prefix.NAMESPACES)

        for row in assoc_query:
            agent_info = {
                'agent': row['agent'],
                'plan': row.get('plan'),
                'role': row.get('role'),
            }
            agents.append(agent_info)

        return agents
    
    def get_execution_time(self, uri: URIRef):
        result = {
            'startedAtTime': None,
            'endedAtTime': None,
            'duration_ms': None,
        }

        time_query = self.query(f"""
            SELECT ?start ?end WHERE {{
                OPTIONAL {{ <{uri}> prov:startedAtTime ?start . }}
                OPTIONAL {{ <{uri}> prov:endedAtTime ?end . }}
            }}
        """, initNs=Prefix.NAMESPACES)

        for row in time_query:
            start_literal = row.get('start')
            end_literal = row.get('end')

            if start_literal:
                result['startedAtTime'] = datetime.fromisoformat(str(start_literal))
            if end_literal:
                result['endedAtTime'] = datetime.fromisoformat(str(end_literal))

            if result['startedAtTime'] and result['endedAtTime']:
                delta = result['endedAtTime'] - result['startedAtTime']
                result['duration_ms'] = int(delta.total_seconds() * 1000)

        return result