from rdflib import Namespace, URIRef

# Standard RDF prefixes
std_prefixes = {
    'rdf': "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    'rdfs': "http://www.w3.org/2000/01/rdf-schema#",
    'xsd': "http://www.w3.org/2001/XMLSchema#",
    'ex': "http://www.example.com#",
    'cf': "http://www.example.com/controlflow#",
    'py': "http://www.example.com/pythonfunction#",
    'docker': "http://www.example.com/docker#",
    'python': "http://www.example.com/python#",
    'dcterms': "http://purl.org/dc/terms/",
    'doap': "http://usefulinc.com/ns/doap#",
    'fno': "https://w3id.org/function/ontology#",
    'fnoi': "https://w3id.org/function/vocabulary/implementation#",
    'fnom': "https://w3id.org/function/vocabulary/mapping#",
    'fnoc': "https://w3id.org/function/vocabulary/composition#",
    'fnof': "http://example.com/vocabulary/flow#",
    'ptype': "http://example.com/ptype#",
    'prov': "http://www.w3.org/ns/prov#",
    'cc': "http://creativecommons.org/ns#",
    'foaf': "http://xmlns.com/foaf/0.1/",
    'void': "http://rdfs.org/ns/void#",
    'mls': "http://www.w3.org/ns/mls#",
    'mlflow': "http://www.example.com/mlflow#",
    'do': "http://linkedcontainers.org/vocab#",
    'ldes': "https://w3id.org/ldes#",
    'tree': "https://w3id.org/tree#",
}


class Prefix:
    """
    Utility class for managing RDF namespace prefixes.
    """
    NAMESPACES = {k: Namespace(v) for k, v in std_prefixes.items()}

    @staticmethod
    def ns(prefix):
        """
        Get the namespace URI for a given prefix.

        Args:
            prefix (str): The namespace prefix.

        Returns:
            Namespace: The namespace URI.
        """
        return Prefix.NAMESPACES[prefix]

    @staticmethod
    def bind_namespaces(g):
        """
        Bind namespace prefixes to an RDF graph.

        Args:
            g (Graph): The RDF graph to bind namespaces to.

        Returns:
            Graph: The RDF graph with namespaces bound.
        """
        for k, v in Prefix.NAMESPACES.items():
            g.bind(k, v)
        return g
    
    @staticmethod
    def update_namespaces(prefix, url):
        """
        Update the namespace with a new prefix and URI.

        Args:
            prefix (str): The namespace prefix.
            url (str): The namespace URI.
        """
        Prefix.NAMESPACES.update({prefix: Namespace(url)})
    
    @staticmethod
    def set_base(uri):
        """
        Set the base URI for the default namespace.

        Args:
            uri (str): The base URI.
        """
        Prefix.NAMESPACES[''] = Namespace(uri)
    
    @staticmethod
    def base():
        """
        Get the base URI for the default namespace.

        Returns:
            str: The base URI.
        """
        return Prefix.ns('ex')
    
    @staticmethod
    def cf():
        """
        Get the base URI for the controlflow functions namespace.

        Returns:
            str: The base URI.
        """
        return Prefix.ns('cf')
    
    @staticmethod
    def py():
        """
        Get the base URI for the python functions namespace.

        Returns:
            str: The base URI.
        """
        return Prefix.ns('py')
    
    @staticmethod
    def do():
        """
        Get the base URI for DockerOnto.

        Returns:
            str: The base URI.
        """
        return Prefix.ns('do')
    
    @staticmethod
    def prov():
        """
        Get the base URI for PROV-O.

        Returns:
            str: The base URI.
        """
        return Prefix.ns('prov')
    
    @staticmethod
    def ldes():
        """
        Get the base URI for LDES Ontology.

        Returns:
            str: The base URI.
        """
        return Prefix.ns('ldes')
    
    @staticmethod
    def tree():
        """
        Get the base URI for Tree Ontology.

        Returns:
            str: The base URI.
        """
        return Prefix.ns('tree')
    
    @staticmethod
    def get_name(uri: URIRef) -> str:
        """
        Extracts the local name from a URIRef based on known namespaces.
        
        Args:
            uri: The URIRef to process.
            namespaces: A mapping of prefixes -> Namespace.
            
        Returns:
            The local name (without namespace prefix). 
            If no namespace matches, returns the full URI string.
        """
        uri_str = str(uri)
        for ns in Prefix.NAMESPACES.values():
            ns_str = str(ns)
            if uri_str.startswith(ns_str):
                return uri_str[len(ns_str):]
        # Fallback: try splitting by '#' or '/' if no namespace matched
        return uri_str.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
    
    @staticmethod
    def uri_to_str(uri):
        """
        Convert a full URI to a prefixed string if possible.

        Args:
            uri (str or rdflib.URIRef): The full URI.

        Returns:
            str: The URI in prefixed form if a matching namespace is found, otherwise the full URI.
        """
        uri_str = str(uri).removeprefix("file://")
        for prefix, ns in Prefix.NAMESPACES.items():
            ns_str = str(ns)
            if uri_str.startswith(ns_str):
                local_part = uri_str[len(ns_str):]
                return f"{prefix}:{local_part}" if prefix else local_part
        return uri_str
