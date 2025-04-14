from ..graph import FnOGraph
from importlib.resources import files

from rdflib import Graph

class StandardKG:
    """
    Utility class for managing and accessing RDF dictionaries of function descriptions.
    """
    def __init__(self):
        self.g = FnOGraph()
        self.g += Graph().parse(files("fno_convert.functions").joinpath("control_flow.ttl"), format='turtle')
        self.g += Graph().parse(files("fno_convert.functions").joinpath("python.ttl"), format='turtle')
        self.g += Graph().parse(files("fno_convert.functions").joinpath("dockeronto.ttl"), format='turtle')
    
    def __contains__(self, uri):
        return self.g.has_function(uri)
    
    def __getitem__(self, uri):
        return self.g.get_function_description(uri)

STD_KG = StandardKG()