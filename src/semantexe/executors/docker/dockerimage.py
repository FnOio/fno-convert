from ..std import Executor
from ...mappers import DockerMapper
from ...builders import ProvBuilder, FnOBuilder

import docker, os

class DockerImageExecutor(Executor):
  
  def accepts(self, mapping, imp):
    return self.g.is_dockerimage(imp)
  
  def execute_function(self, fun, *args, **kwargs):
    
    # Get the image tag from the implementation
    tag = self.g.get_tag(fun.imp)
    
    client = docker.client.from_env()
    image = client.images.get(tag)
    
    container = client.containers.create(image, detach=True)
    
    self.container_uri = DockerMapper.map_container(self.pg, container)
  
  def execute_applied(self, fun):
    pass
  
  def provenance(self):
        _, exe_uri = super().provenance()
        
        ProvBuilder.wasGeneratedBy(self.pg, self.container_uri, exe_uri)
        ProvBuilder.derivedFrom(self.pg, self.container_uri, self.fun.imp)
        
        # The image has an FnO entrypoint
        entrypoint = self.g.is_dockerfile()
        
        if self.entrypoint_cmd.startswith("python"):
            # Look for the correct python implementation
            # TODO Look for an implementation with a usable mapping
            try:
                # Now just take the first implementation
                file = os.path.join(self.workdir, self.entrypoint_params[0])
                imp_uri, map_uri, fun_uri = self.pg.imp_from_file(file)[0]
                ProvBuilder.alternateOf(self.pg, self.image_uri, imp_uri)
            except IndexError as e:
                print(f"[ERROR] No Python implementation found for {file}")
        
            # Map the image implementation
            FnOBuilder.map(self.pg, fun_uri, map_uri, self.image_uri)
            
            # TODO Copy mapping with new default values
            """if len(self.entrypoint_params) > 1:
                default_input = ' '.join(self.entrypoint_params[1:])
                DockerBuilder.defaultInput(self.pg, self.image_uri, default_input)"""
                
        return self.pg, exe_uri
    
  