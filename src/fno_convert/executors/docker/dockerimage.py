from ..std import Executer
from ...mappers import DockerMapper
from ...builders import ProvBuilder, FnOBuilder
from ...model.function import Function
from ...prefix import Prefix

import docker, os

class DockerImageExecutor(Executer):
  
  def uri(self):
        return Prefix.ns('fnoi').DockerImageExecutor    
  
  def accepts(self, mapping, imp):
    return self.g.is_dockerimage(imp)
  
  def execute_function(self, fun: Function, *args, **kwargs):
    client = docker.client.from_env()
    
    cmd = []
    for input in fun.positional():
      if input.param_mapping.index:
        cmd.append(' '.join([ f'"{inp}"' for inp in input.get()]))
      elif input.param_mapping.keyvalue:
        for key, value in input.get():
          cmd.append(f"{'-' if len(key) == 1 else '--'}{key}")
          cmd.append(f'"{value}"')
      else:
        cmd.append(f'"{input.get()}"')
    
    varpos = fun.varpositional()
    if varpos:
      cmd.append(' '.join([ f'"{inp}"' for inp in varpos.get()]))
    
    for key, input in fun.keyword():
      cmd.append(f"{'-' if len(key) == 1 else '--'}{key}")
      if input.param_mapping.index:
        cmd.append(' '.join([ f'"{inp}"' for inp in input.get()]))
      else:
        cmd.append(f'"{input.get()}"')
    
    varkey = fun.varpositional()
    if varkey:
      for key, value in varkey.get():
        cmd.append(f"{'-' if len(key) == 1 else '--'}{key}")
        cmd.append(f"{value}")
  
    # Execute docker run
    container = client.containers.run(fun.image, ' '.join(cmd), detach=True)
    
    # created container was derived from image
    self.container_uri = DockerMapper.map_container(self.pg, container)
    ProvBuilder.derivedFrom(self.pg, self.container_uri, fun.imp)
    
    if fun.internal:
      fun.comp.execute(self)
    
    # TODO container is a function without any inputs. It has an internal composition setting the given entrypoint cmds to the internal rep
    # FnOBuilder.map(self.pg, fun.fun_uri, fun.map, self.container_uri)
  
  def provenance(self, fun, *args, logger, **kwargs):
    pg, exe_uri = super().provenance(fun, *args, logger=logger, **kwargs)
    
    ProvBuilder.entity(self.pg, self.container_uri)
    ProvBuilder.wasGeneratedBy(self.pg, self.container_uri, exe_uri)
    
    return pg, exe_uri
  
  def map(self, fun):
    # Get the image tag from the implementation
    tag = self.g.get_tag(fun.imp)
  
    client = docker.client.from_env()
    fun.tag = tag
    fun.image = client.images.get(tag)
  
  def alt_executor(self, fun):
    # Use the python executor to capture provenance locally
    from ..python import PythonExecutor
    executor = PythonExecutor(self.pg)
    
    pg, exe_uri = executor.provenance(fun, logger=self.logger)
    self.pg += pg

    fun.prov.informed.append(exe_uri)
  
    
  