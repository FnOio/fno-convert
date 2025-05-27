import os

from ..graph import FnOGraph
from ..prefix import Prefix
from .fno import FnOBuilder

from rdflib import RDF, URIRef, Literal
from typing import Any


class PythonBuilder:

    @staticmethod
    def describe_imp(g, imp_uri, imp_name, m_name=None, p_name=None, f_path=None, doc=None):
        triples = []
        
        FnOBuilder.describe_implementation(g, imp_uri, imp_name)
        
        if m_name:
            triples.append((imp_uri, Prefix.ns('fnoi')['module'], Literal(m_name)))

        if p_name:
            triples.append((imp_uri, Prefix.ns('fnoi')['package'], Literal(p_name)))
        
        if f_path:
            triples.append((imp_uri,  Prefix.ns('fnoi')['file'], URIRef(f"file://{f_path}")))
        
        if doc:
            triples.append((imp_uri, Prefix.ns('dcterms')['description'], Literal(doc)))
        
        [ g.add(x) for x in triples ]
        
        return imp_uri
    
    @staticmethod
    def describe_class(g, imp_uri):
        g.add((imp_uri, RDF.type, Prefix.ns('fnoi').PythonClass))
        
    @staticmethod
    def describe_module(g, imp_uri):
        g.add((imp_uri, RDF.type, Prefix.ns('fnoi').PythonModule))
    
    @staticmethod
    def describe_method(g, imp_uri, self, static):
        g.add((imp_uri, RDF.type, Prefix.ns('fnoi').PythonMethod))
        g.add((imp_uri, Prefix.ns('fnoi').methodOf, self))
        g.add((imp_uri, Prefix.ns('fnoi').static, Literal(static)))
    
    @staticmethod
    def describe_function(g, imp_uri):
        g.add((imp_uri, RDF.type, Prefix.ns('fnoi').PythonFunction))
    
    @staticmethod
    def describe_file(g: FnOGraph, file_uri, file_path=None):
        ### FNO IMPLEMENTATION ###
        g.add((file_uri, RDF.type, Prefix.ns('fnoi').PythonFile))
        if file_path:
            g.add((file_uri, Prefix.ns('rdfs').label, Literal(os.path.basename(file_path))))
            g.add((file_uri, Prefix.ns('fnoi').file, URIRef(f"file://{file_path}")))
        
        return file_uri