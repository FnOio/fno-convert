from ..std import Executor
from ...mappers import DockerMapper
from ...builders import ProvBuilder, FnOBuilder
from ..executeable import Function

import docker, os

class DockerImageExecutor(Executor):
  
  def accepts(self, mapping, imp):
    return self.g.is_dockerimage(imp)
  
  def execute_function(self, fun: Function, *args, **kwargs):
    
    # Get the image tag from the implementation
    tag = self.g.get_tag(fun.imp)
    
    client = docker.client.from_env()
    image = client.images.get(tag)
    
    container = client.containers.create(image, detach=True)
    
    self.container_uri = DockerMapper.map_container(self.pg, container)
    fun.output.set(self.container_uri)
  
  def provenance(self, fun: Function, *args, **kwargs):
    _, exe_uri = super().provenance(fun, *args, *kwargs)
    
    # Container was derived from the image
    ProvBuilder.derivedFrom(self.pg, self.container_uri, fun.imp)
    
    # Map container implementation to the function
    fun_uri, map_uri = self.g.get_container_mapping(fun.imp)
    FnOBuilder.map(self.pg, fun_uri, map_uri, self.container_uri)
    
    return self.pg, exe_uri
  
  def execute_applied(self, fun):
    pass
  
  def map(self, fun):
    pass
  
  def alt_executor(self, fun):
    pass
    
  