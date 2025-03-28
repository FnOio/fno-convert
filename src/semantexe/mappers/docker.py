import hashlib

from rdflib import Literal, RDF, URIRef
from docker.models.images import Image
from docker.models.containers import Container

from ..builders import FnOBuilder
from ..prefix import Prefix
from ..graph import ExecutableGraph
from .python import PythonMapper

class DockerMapper:
    
    @staticmethod
    def dockerfile_uri(name, path):
        unique_hash = hashlib.sha256(path.encode()).hexdigest()[:8]
        return Prefix.ns('docker')[f"{name}{unique_hash}"]
    
    @staticmethod
    def map_image(g: ExecutableGraph, image: Image):
        image_tag = image.attrs['RepoTags'][0].replace(':', '_')
        
        ### FUNCTION ###
        
        fun_uri = Prefix.base()[f"docker_image"]
        
        args = URIRef(f"{fun_uri}Arguments")
        FnOBuilder.describe_parameter(g, args, PythonMapper.any(g), "args")
        kargs = URIRef(f"{fun_uri}Keywords")
        FnOBuilder.describe_parameter(g, kargs, PythonMapper.any(g), "kargs")
        out = URIRef(f"{fun_uri}Output")
        FnOBuilder.describe_output(g, out, PythonMapper.any(g), "container")
        
        FnOBuilder.describe_function(g, fun_uri, "docker create", [args, kargs], [out])
        
        ### IMPLEMENTATION ###
        
        imp_uri = Prefix.ns('docker')[f"{image_tag}Image{image.short_id.removeprefix('sha256:')}"]
        g.add((imp_uri, RDF.type, Prefix.ns('do').Image))
        g.add((imp_uri, RDF.type, Prefix.ns('fnoi').DockerImage))
        
        # Image metadata
        # TODO Dockerpedia annotater, now simply state labels
        for tag in image.tags:
            g.add((imp_uri, Prefix.ns('rdfs').label, Literal(tag)))
            
        ### MAPPING ###
        
        FnOBuilder.describe_mapping(g, fun_uri, imp_uri, "docker create",
                                    args={args}, kargs={kargs}, output=out)
        
        return imp_uri, image_tag
    
    @staticmethod
    def map_container(g: ExecutableGraph, container: Container):
        uri = Prefix.ns('docker')[f"{container.name}{container.short_id.removeprefix('sha256:')}"]
        g.add((uri, RDF.type, Prefix.ns('do').Container))
        g.add((uri, RDF.type, Prefix.ns('fnoi').DockerContainer))
        g.add((uri, Prefix.ns('rdfs').label, Literal(container.name)))
        g.add((uri, Prefix.ns('fnoi').id, Literal(container.id)))
        
        return uri