from ..prefix import Prefix
from ..graph import FnOGraph
from rdflib import RDF, RDFS, Literal

class LDESBuidlder:
  
  @staticmethod
  def fileES(g: FnOGraph, event_uri, stream_uri, file_uri, timestamp, shape=None):
    triples = [
      (stream_uri, RDF.type, Prefix.ldes().EventStream),
      (stream_uri, Prefix.ldes().timestampPath, Prefix.prov().atTime),
      (stream_uri, Prefix.ldes().versionOfPath, Prefix.prov().derivedFrom),
    ]
    
    if shape:
      triples.append((stream_uri, Prefix.tree().shape, shape))
    
    [ g.add(x) for x in triples ]
    
    LDESBuidlder.createFileEvent(g, event_uri, stream_uri, file_uri, timestamp, "File Created")
  
  @staticmethod
  def createFileEvent(g: FnOGraph, event_uri, stream_uri, file_uri, timestamp, label=None):
    triples = [
      (event_uri, RDF.type, Prefix.prov().InstantaneousEvent),
      (event_uri, Prefix.prov().atTime, Literal(timestamp)),
      (event_uri, Prefix.prov().derivedFrom, file_uri),
      (stream_uri, Prefix.tree().member, event_uri),
    ]
    
    if label:
      triples.append((event_uri, RDFS.label, Literal(label)))
    
    [ g.add(x) for x in triples ]