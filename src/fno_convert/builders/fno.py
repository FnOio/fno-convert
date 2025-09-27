from rdflib import RDF, BNode, Literal, URIRef

from ..prefix import Prefix
from ..graph import FnOGraph, create_rdf_list, get_name
from ..util.mapping import Mapping, ValueMapping, BranchMapping, MappingNode


class FnOBuilder:
    """
    Provides methods to describe functions, implementations, mappings, parameters, and outputs
    in the context of the Function Ontology (FNO).
    """

    @staticmethod
    def map(g: FnOGraph, fun, map, imp):
        g.add((map, Prefix.ns("fno").function, fun))
        g.add((map, Prefix.ns("fno").implementation, imp))

    @staticmethod
    def apply(g: FnOGraph, call, f):
        """
        Apply a call to a function.

        Args:
            call (URIRef): The call URI.
            f (URIRef): The function URI.

        Returns:
            PipelineGraph: The resulting graph.
        """
        g.add((call, Prefix.ns("fnoc")["applies"], f))

    @staticmethod
    def represents(g: FnOGraph, comp, fun):
        g.add((comp, Prefix.ns("fnoc").represents, fun))

    @staticmethod
    def link(g: FnOGraph, call1, pred, call2):
        if call1 is not None and call2 is not None:
            g.add((call1, Prefix.ns("fnoc")[pred], call2))

    @staticmethod
    def start(g: FnOGraph, comp, call, condition=None):
        if condition is None:
            g.add((comp, Prefix.ns("fnoc")["start"], call))
        elif condition:
            g.add((comp, Prefix.ns("fnoc")["if"], call))
        else:
            g.add((comp, Prefix.ns("fnoc")["ifNot"], call))

    @staticmethod
    def describe_composition(
        g: FnOGraph, comp: URIRef, mappings: list[Mapping], represents=None
    ):
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

        g.add((comp_uri, RDF.type, Prefix.ns("fno")["Composition"]))
        if represents:
            FnOBuilder.represents(g, comp_uri, represents)

        for mapping in mappings:
            try:
                FnOBuilder.add_mapping(g, comp_uri, mapping)
            except Exception as e:
                print("MAP FROM: ", mapping.mapfrom)
                print("MAP TO", mapping.mapto)
                raise e

        return comp_uri

    @staticmethod
    def add_mapping(g: FnOGraph, comp_uri: URIRef, mapping: Mapping):
        if isinstance(mapping, ValueMapping):
            FnOBuilder.add_value_mapping(g, comp_uri, mapping)
        else:
            FnOBuilder.add_branch_mapping(g, comp_uri, mapping)

    @staticmethod
    def add_branch_mapping(g: FnOGraph, comp_uri: URIRef, mapping: BranchMapping):
        mapping_node = BNode()

        mappings = mapping.mappings
        start = mapping.start
        test = mapping.test

        g.add((comp_uri, Prefix.ns("fnoc").composedOf, mapping_node))
        branch_node = BNode()
        if mapping.test_value:
            g.add((mapping_node, Prefix.ns("fnoc").mapIf, branch_node))
        else:
            g.add((mapping_node, Prefix.ns("fnoc").mapIfNot, branch_node))
        g.add((branch_node, Prefix.ns("fnoc").constituentFunction, test.context))
        g.add((branch_node, Prefix.ns("fnoc").functionParameter, test.parameter))

        composition_node = BNode()
        g.add((branch_node, Prefix.ns("fnoc").composition, composition_node))
        g.add((composition_node, RDF.type, Prefix.ns("fno").Composition))
        for mapping in mappings:
            FnOBuilder.add_mapping(g, composition_node, mapping)
        if start:
            FnOBuilder.start(g, composition_node, start)

    @staticmethod
    def add_value_mapping(g: FnOGraph, comp_uri: URIRef, mapping: ValueMapping):
        mapping_node = BNode()

        mapfrom = mapping.mapfrom
        mapto = mapping.mapto

        g.add((comp_uri, Prefix.ns("fnoc")["composedOf"], mapping_node))

        # priority
        if mapping.priority:
            g.add((mapping_node, Prefix.ns("fnoc")["priority"], mapping.priority))

        if mapfrom.from_term():
            # map from term
            term = mapfrom.get_value()
            g.add((mapping_node, Prefix.ns("fnoc")["mapFromTerm"], term))
        else:
            # map from function
            bnode = BNode()

            triples = [
                (
                    mapping_node,
                    Prefix.ns("fnoc")["mapFor" if mapfrom.from_for() else "mapFrom"],
                    bnode,
                ),
                (bnode, Prefix.ns("fnoc")["constituentFunction"], mapfrom.context),
                (
                    bnode,
                    Prefix.ns("fnoc")[
                        "functionOutput" if mapfrom.is_output() else "functionParameter"
                    ],
                    mapfrom.get_value(),
                ),
            ]

            # map from strategy
            if mapfrom.has_map_strategy():
                triples.append(
                    (
                        bnode,
                        Prefix.ns("fnoc")["mappingStrategy"],
                        Prefix.ns("fnoc")[mapfrom.strategy],
                    )
                )
                triples.append((bnode, Prefix.ns("fnoc")["key"], Literal(mapfrom.key)))

            [g.add(x) for x in triples]

        # map to function
        bnode = BNode()

        triples = [
            (mapping_node, Prefix.ns("fnoc")["mapTo"], bnode),
            (bnode, Prefix.ns("fnoc")["constituentFunction"], mapto.context),
            (
                bnode,
                Prefix.ns("fnoc")[
                    "functionOutput" if mapto.is_output() else "functionParameter"
                ],
                mapto.get_value(),
            ),
        ]

        # map to strategy
        if mapto.has_map_strategy():
            triples.append(
                (
                    bnode,
                    Prefix.ns("fnoc")["mappingStrategy"],
                    Prefix.ns("fnoc")[mapto.strategy],
                )
            )
            triples.append((bnode, Prefix.ns("fnoc")["key"], Literal(mapto.key)))

        [g.add(x) for x in triples]

    @staticmethod
    def describe_function(g: FnOGraph, uri, name=None, parameters=[], outputs=[]):
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

        # create fno:returns container
        c_returns = create_rdf_list(g, outputs)

        g.add((uri, RDF.type, Prefix.ns("fno")["Function"]))
        g.add((uri, RDF.type, Prefix.ns("prov")["Entity"]))
        g.add((uri, Prefix.ns("fno")["expects"], c_expects.uri))
        g.add((uri, Prefix.ns("fno")["returns"], c_returns.uri))
        if name is not None:
            g.add((uri, Prefix.ns("rdfs")["label"], Literal(name)))

        g.log()

        return uri

    @staticmethod
    def describe_loop(g: FnOGraph, uri, name=None, parameters=[], outputs=[]):
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
        FnOBuilder.describe_function(g, uri, name, parameters, outputs)
        g.add((uri, RDF.type, Prefix.ns("fno").Loop))

    @staticmethod
    def describe_branch(g: FnOGraph, uri, name=None, parameters=[], outputs=[]):
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
        FnOBuilder.describe_function(g, uri, name, parameters, outputs)
        g.add((uri, RDF.type, Prefix.ns("fno").Branch))
        test_uri = URIRef(f"{uri}Test")
        FnOBuilder.describe_parameter(
            g, test_uri, Prefix.ns("xsd").boolean, Prefix.ns("fno").test, req=True
        )
        g.add((uri, Prefix.ns("fno").tests, test_uri))

    @staticmethod
    def describe_parameter(g: FnOGraph, uri, type, pred, req=None):
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
            (uri, RDF.type, Prefix.ns("fno")["Parameter"]),
            (
                uri,
                Prefix.ns("fno")["predicate"],
                pred if isinstance(pred, URIRef) else Prefix.base()[pred],
            ),
            (uri, Prefix.ns("fno")["type"], type),
        ]

        if req is not None:
            triples.append((uri, Prefix.ns("fno").required, Literal(req)))

        [g.add(x) for x in triples]

        return uri

    @staticmethod
    def describe_output(g: FnOGraph, uri, type, pred):
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
            (uri, RDF.type, Prefix.ns("fno")["Output"]),
            (uri, Prefix.ns("fno")["predicate"], Prefix.base()[pred]),
            (uri, Prefix.ns("fno")["type"], type),
        ]

        [g.add(x) for x in triples]

        return uri

    @staticmethod
    def describe_implementation(g: FnOGraph, imp_uri, imp_name):
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
            (imp_uri, RDF.type, Prefix.ns("fnoi")["Implementation"]),
            (imp_uri, Prefix.ns("doap")["name"], Literal(imp_name)),
        ]

        [g.add(x) for x in triples]

        return imp_uri

    ### IMPLEMENTATION MAPPING ###

    @staticmethod
    def describe_mapping(
        g: FnOGraph,
        f,
        imp=None,
        f_name=None,
        positional=[],
        keyword={},
        args=set(),
        kargs=set(),
        output=None,
        unpack=[],
        context=None,
        defaults={},
    ) -> URIRef:
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

        s = Prefix.base()[f"{Prefix.get_name(f)}Mapping"]

        triples = [
            (s, RDF.type, Prefix.ns("fno")["Mapping"]),
            (s, Prefix.ns("fno")["function"], f),
        ]

        if imp:
            triples.append((s, Prefix.ns("fno")["implementation"], imp))

        if f_name is not None:
            triples.extend(
                [
                    (s, Prefix.ns("fno")["methodMapping"], methodNode),
                    (methodNode, RDF.type, Prefix.ns("fnom")["StringMethodMapping"]),
                    (methodNode, Prefix.ns("fnom")["method-name"], Literal(f_name)),
                ]
            )

        ### DEFAULT OUTPUTS ###

        if output:
            returnNode = BNode()
            triples.extend(
                [
                    (s, Prefix.ns("fno")["returnMapping"], returnNode),
                    (returnNode, RDF.type, Prefix.ns("fnom")["DefaultReturnMapping"]),
                    (returnNode, Prefix.ns("fnom")["functionOutput"], output),
                ]
            )

        ### UNPACKED OUTPUTS ###

        for i, output in enumerate(unpack):
            returnNode = BNode()
            triples.extend(
                [
                    (s, Prefix.ns("fno")["returnMapping"], returnNode),
                    (returnNode, RDF.type, Prefix.ns("fnom")["UnpackReturnMapping"]),
                    (returnNode, Prefix.ns("fnom")["functionOutput"], output),
                    (
                        returnNode,
                        Prefix.ns("fnom")["implementationUnpackPosition"],
                        Literal(i),
                    ),
                ]
            )

        ### CONTEXT ###

        if context:
            context_input, context_output = context

            contextOutputNode = BNode()
            contextInputNode = BNode()

            triples.extend(
                [
                    (s, Prefix.ns("fno")["parameterMapping"], contextInputNode),
                    (
                        contextInputNode,
                        RDF.type,
                        Prefix.ns("fnom")["ContextParameterMapping"],
                    ),
                    (
                        contextInputNode,
                        Prefix.ns("fnom")["functionParameter"],
                        context_input,
                    ),
                    (s, Prefix.ns("fno")["returnMapping"], contextOutputNode),
                    (
                        contextOutputNode,
                        RDF.type,
                        Prefix.ns("fnom")["ContextReturnMapping"],
                    ),
                    (
                        contextOutputNode,
                        Prefix.ns("fnom")["functionOutput"],
                        context_output,
                    ),
                ]
            )

        ### POSITIONAL PARAMETER MAPPING ###

        for i, param in enumerate(positional):
            paramNode = BNode()

            triples.extend(
                [
                    (s, Prefix.ns("fno")["parameterMapping"], paramNode),
                    (
                        paramNode,
                        RDF.type,
                        Prefix.ns("fnom")["PositionParameterMapping"],
                    ),
                    (paramNode, Prefix.ns("fnom")["functionParameter"], param),
                    (
                        paramNode,
                        Prefix.ns("fnom")["implementationParameterPosition"],
                        Literal(i),
                    ),
                ]
            )

            if param in args:
                triples.append((paramNode, RDF.type, Prefix.ns("fnom")["ListMapping"]))
                args.remove(param)
            if param in kargs:
                triples.append(
                    (paramNode, RDF.type, Prefix.ns("fnom")["KeyValueMapping"])
                )
                kargs.remove(param)

            if param in defaults:
                triples.append((param, Prefix.ns("fno")["required"], Literal(False)))
            else:
                triples.append((param, Prefix.ns("fno")["required"], Literal(True)))

        ### PROPERTY PARAMETER MAPPING ###

        for param, key in keyword:
            paramNode = BNode()

            triples.extend(
                [
                    (s, Prefix.ns("fno")["parameterMapping"], paramNode),
                    (
                        paramNode,
                        RDF.type,
                        Prefix.ns("fnom")["PropertyParameterMapping"],
                    ),
                    (paramNode, Prefix.ns("fnom")["functionParameter"], param),
                    (
                        paramNode,
                        Prefix.ns("fnom")["implementationProperty"],
                        Literal(key),
                    ),
                ]
            )

            if g.is_required(param) is None and param in defaults:
                triples.append((param, Prefix.ns("fno")["required"], Literal(False)))
            else:
                triples.append((param, Prefix.ns("fno")["required"], Literal(True)))

        ### DEFAULT PARAMETER MAPPING ###

        for param, default in defaults.items():
            defaultNode = BNode()

            triples.extend(
                [
                    (s, Prefix.ns("fno")["parameterMapping"], defaultNode),
                    (
                        defaultNode,
                        RDF.type,
                        Prefix.ns("fnom")["DefaultParameterMapping"],
                    ),
                    (defaultNode, Prefix.ns("fnom")["functionParameter"], param),
                    (defaultNode, Prefix.ns("fnom")["defaultValue"], default),
                ]
            )

        ### LIST PARAMETER MAPPING ###

        if len(args) == 1:
            arg = args.pop()
            argNode = BNode()
            triples.extend(
                [
                    (s, Prefix.ns("fno")["parameterMapping"], argNode),
                    (argNode, RDF.type, Prefix.ns("fnom")["ListMapping"]),
                    (argNode, Prefix.ns("fnom")["functionParameter"], arg),
                ]
            )
        elif len(args) > 1:
            raise Exception("There can only be one non-positional index mapping")

        ### KEY VALUE PARAMETER MAPPING ###

        if len(kargs) == 1:
            karg = kargs.pop()
            kargNode = BNode()
            triples.extend(
                [
                    (s, Prefix.ns("fno")["parameterMapping"], kargNode),
                    (kargNode, RDF.type, Prefix.ns("fnom")["KeyValueMapping"]),
                    (kargNode, Prefix.ns("fnom")["functionParameter"], karg),
                ]
            )
        elif len(kargs) > 1:
            raise Exception("There can only be one non-positional key value mapping")

        [g.add(x) for x in triples]

        return s

    @staticmethod
    def implementation(g: FnOGraph, mapping, imp):
        g.add((mapping, Prefix.ns("fno").implementation, imp))

    @staticmethod
    def describe_execution(g: FnOGraph, exe, fun, mapping, inputs):
        g.add((exe, RDF.type, Prefix.ns("fno").Execution))
        g.add((exe, Prefix.ns("fno").executes, fun))

        if mapping:
            g.add((exe, Prefix.ns("fno").uses, mapping))

        for pred, input in inputs.items():
            g.add((exe, pred, input))
