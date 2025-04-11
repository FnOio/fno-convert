import traceback
import json

from fno_convert.descriptors import ResourceDescriptor
from fno_convert.graph import FnOGraph
from fno_convert.executors.docker import DockerfileExecutor
from fno_convert.executors.executeable import Function
from fno_convert.elk import elk_layout

DD_DOCKERFILE = "docker_examples/data-driven/Dockerfile"
DD_PY_FILE = "docker_examples/data-driven/job/run.py"
SIMPLE_DOCKERFILE = "docker_examples/simple/Dockerfile"
SIMPLE_PY_FILE = "docker_examples/simple/run.py"

if __name__ == "__main__":
  g = FnOGraph()
  descriptor = ResourceDescriptor(g)
  print("Describing resource...")
  fun_uri = descriptor.describe(SIMPLE_DOCKERFILE)
  g.serialize("graphs/docker/Dockerfile_simple.ttl", format="turtle")
  print("Done!")
  
  # try to create executable model
  try:
    print(f"Trying to create executable model...")
    fun = Function(g, fun_uri, internal=True)
  except Exception as e:
    print(f"Error while creating executable model of {fun_uri}")
    print(traceback.format_exc())
  
  # try to execute the function
  print("Executing FnO Function with DockerfileExecutor...")
  executor = DockerfileExecutor(g)
  prov = executor.execute(fun, tag="simple")
  prov.serialize("graphs/prov/docker/Dockerfile_simple.ttl", format="turtle")
  print("Done!") 