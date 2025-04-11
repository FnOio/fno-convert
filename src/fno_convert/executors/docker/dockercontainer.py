from ..std import Executer
from ..executeable import Function

import docker

class DockerContainerExecuter(Executer):
  
  def accepts(self, mapping, imp):
    return self.g.is_dockercontainer(imp)
  
  def execute_function(self, fun: Function, *args, **kwargs):
    # start the container
    fun.container.start()
    
    cmd = []
    for input in fun.positional():
      if input.param_mapping.index:
        cmd.append(' '.join(input.get()))
      elif input.param_mapping.keyvalue:
        for key, value in input.get():
          cmd.append(f"{'-' if len(key) == 1 else '--'}{key}")
          cmd.append(value)
      else:
        cmd.append(input.get())
    
    varpos = fun.varpositional()
    if varpos:
      cmd.append(' '.join(varpos.get()))
    
    for key, input in fun.keyword():
      cmd.append(f"{'-' if len(key) == 1 else '--'}{key}")
      if input.param_mapping.index:
        cmd.append(' '.join(input.get()))
      else:
        cmd.append(input.get())
    
    varkey = fun.varpositional()
    if varkey:
      for key, value in varkey.get():
        cmd.append(f"{'-' if len(key) == 1 else '--'}{key}")
        cmd.append(value)
    
    # run the container
    fun.container.exec_run(' '.join(cmd))
    
    # Capture local provenance to simulate provenance capture in container
    if fun.internal:
      fun.comp.execute(self)
  
  def execute_applied(self, fun):
    pass
  
  def map(self, fun):
    # Get the image tag from the implementation
    id = self.g.get_container_id(fun.imp)
    
    # Start the container
    client = docker.client.from_env()
    fun.container = client.containers.get(id)
  
  def alt_executor(self, fun):
    pass