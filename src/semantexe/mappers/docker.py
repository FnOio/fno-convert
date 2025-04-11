import hashlib

from rdflib import Literal, RDF, URIRef
from docker.models.images import Image
from docker.models.containers import Container

from ..builders import FnOBuilder
from ..prefix import Prefix
from ..graph import FnOGraph
from .python import PythonMapper

class DockerMapper:
    
    @staticmethod
    def dockerfile_uri(name, path):
        unique_hash = hashlib.sha256(path.encode()).hexdigest()[:8]
        return Prefix.ns('docker')[f"{name}{unique_hash}"]
    
    @staticmethod
    def map_image(g: FnOGraph, image: Image):
        image_tag = image.attrs['RepoTags'][0].replace(':', '_')
        
        ### IMPLEMENTATION ###
        
        imp_uri = Prefix.ns('docker')[f"{image_tag}Image{image.short_id.removeprefix('sha256:')}"]
        g.add((imp_uri, RDF.type, Prefix.ns('do').Image))
        g.add((imp_uri, RDF.type, Prefix.ns('fnoi').DockerImage))
        
        # Image metadata
        # TODO Dockerpedia annotater, now simply state labels
        g.add((imp_uri, Prefix.ns('fnoi').tag, Literal(image.attrs['RepoTags'][0])))
        g.add((imp_uri, Prefix.ns('rdfs').label, Literal(image.attrs['RepoTags'][0])))
        
        return imp_uri, image_tag
    
    @staticmethod
    def map_container(g: FnOGraph, container: Container):
        uri = Prefix.ns('docker')[f"{container.name}{container.short_id.removeprefix('sha256:')}"]
        g.add((uri, RDF.type, Prefix.ns('do').Container))
        g.add((uri, RDF.type, Prefix.ns('fnoi').DockerContainer))
        g.add((uri, Prefix.ns('rdfs').label, Literal(container.name)))
        g.add((uri, Prefix.ns('fnoi').id, Literal(container.id)))
        
        return uri