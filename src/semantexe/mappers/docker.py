import hashlib

from rdflib import Literal, RDF, URIRef
from docker.models.images import Image
from docker.models.containers import Container

from ..builders import FnOBuilder
from ..prefix import Prefix
from ..graph import ExecutableGraph

class DockerMapper:
    
    @staticmethod
    def dockerfile_uri(name, path):
        unique_hash = hashlib.sha256(path.encode()).hexdigest()[:8]
        return Prefix.ns('docker')[f"{name}{unique_hash}"]
    
    @staticmethod
    def map_image(g: ExecutableGraph, image: Image):
        image_tag = image.attrs['RepoTags'][0].replace(':', '_')
        uri = Prefix.ns('docker')[f"{image_tag}{image.short_id.removeprefix('sha256:')}"]
        g.add((uri, RDF.type, Prefix.ns('do').Image))
        g.add((uri, RDF.type, Prefix.ns('fnoi').DockerImage))
        
        # Image metadata
        # TODO Dockerpedia annotater, now simply state labels and the dockerfile
        for tag in image.tags:
            g.add((uri, Prefix.ns('rdfs').label, Literal(tag)))
        
        return uri
    
    @staticmethod
    def map_container(g: ExecutableGraph, container: Container):
        uri = Prefix.ns('docker')[f"{container.name}{container.short_id.removeprefix('sha256:')}"]
        g.add((uri, RDF.type, Prefix.ns('do').Container))
        g.add((uri, RDF.type, Prefix.ns('fnoi').DockerContainer))
        g.add((uri, Prefix.ns('rdfs').label, Literal(container.name)))
        g.add((uri, Prefix.ns('fnoi').id, Literal(container.id)))
        
        return uri