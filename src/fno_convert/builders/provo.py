from ..graph import FnOGraph
from ..prefix import Prefix
from rdflib import RDF, BNode, Literal

class ProvBuilder:
    
    @staticmethod
    def entity(g, uri):
        g.add((uri, RDF.type, Prefix.prov().Entity))
    
    @staticmethod
    def activity(g, uri):
        g.add((uri, RDF.type, Prefix.prov().Activity))
    
    @staticmethod
    def agent(g, uri):
        g.add((uri, RDF.type, Prefix.prov().Agent))
        
    @staticmethod
    def alternateOf(g, alt, src):
        g.add((alt, Prefix.prov().alternateOf, src))
        
    @staticmethod
    def derivedFrom(g, der, src):
        g.add((der, Prefix.prov().wasDerivedFrom, src))
        
    @staticmethod
    def specialiazitionOf(g, spec, src):
        g.add((spec, Prefix.prov().specializationOf, src))
    
    @staticmethod
    def used(g, act, ent):
        g.add((act, Prefix.prov().used, ent))
        
    @staticmethod
    def usageEvent(g, event_uri, exe_uri, file_uri):
        g.add((event_uri, RDF.type, Prefix.prov().Usage))
        g.add((event_uri, Prefix.prov().entity, file_uri))
        g.add((exe_uri, Prefix.prov().qualifiedUsage, event_uri))
        ProvBuilder.used(g, exe_uri, file_uri)
    
    @staticmethod
    def wasGeneratedBy(g, ent, act, time=None):
        g.add((ent, Prefix.prov().wasGeneratedBy, act))
        if time is not None:
            g.add((ent, Prefix.prov().generatedAtTime, Literal(time)))
    
    @staticmethod
    def generationEvent(g, event_uri, exe_uri, file_uri):
        g.add((event_uri, RDF.type, Prefix.prov().Generation))
        g.add((event_uri, Prefix.prov().activity, exe_uri))
        g.add((file_uri, Prefix.prov().qualifiedGeneration, event_uri))
        ProvBuilder.wasGeneratedBy(g, file_uri, exe_uri)
    
    @staticmethod
    def wasInformedBy(g, act1, act2):
        g.add((act1, Prefix.prov().wasInformedBy, act2))
    
    @staticmethod
    def value(g, ent, value):
        g.add((ent, RDF.value, value))
    
    @staticmethod
    def execution(g: FnOGraph, exe, fun, imp, startedAt, endendAt):
        
        # Set PROV-O types
        ProvBuilder.activity(g, exe)
        ProvBuilder.entity(g, fun)
        
        # Function execution
        triples = [
            (exe, Prefix.prov().startedAtTime, Literal(startedAt)),
            (exe, Prefix.prov().endedAtTime, Literal(endendAt)),
            (exe, Prefix.prov().used, fun)
        ]
        
        # Associate implementation
        if imp:
            ProvBuilder.associate(g, exe, imp, Prefix.base().implementation)
        
        [ g.add(x) for x in triples ]
    
    @staticmethod
    def associate(g: FnOGraph, exe, agent, role = None, plan = None):
        
        ProvBuilder.agent(g, agent)
        triples = [
            (exe, Prefix.prov().wasAssociatedWith, agent),
        ]
        
        # Qualified association
        if role or plan:
            association = BNode()
            triples.extend([
                (association, RDF.type, Prefix.prov().Association),
                (exe, Prefix.prov().qualifiedAssociation, association),
                (association, Prefix.prov().agent, agent),
            ])
            
            if role:
                triples.append((association, Prefix.prov().hadRole, role))
            if plan:
                triples.append((association, Prefix.prov().hadPlan, plan))
        
        [ g.add(x) for x in triples ]