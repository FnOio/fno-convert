import traceback

from semantexe.descriptors import ResourceDescriptor
from semantexe.graph import FnOGraph
from semantexe.executors.python import PythonExecutor
from semantexe.executors.executeable import Function

from docker_examples.diagnose.train import train

DD_PY_FILE = "docker_examples/data-driven/job/run.py"
SIMPLE_PY_FILE = "docker_examples/simple/run.py"

if __name__ == "__main__":
  g = FnOGraph()
  descriptor = ResourceDescriptor(g)
  print("Describing resource...")
  fun_uri = descriptor.describe(train)
  g.serialize("graphs/python/diagnose_run.ttl", format="turtle")
  print("Done!")
  
  # try to create executable model
  try:
    print(f"Trying to create executable model...")
    fun = Function(g, fun_uri, internal=True)
  except Exception as e:
    print(f"Error while creating executable model of {fun_uri}")
    print(traceback.format_exc())
  
  # try to execute the function
  print("Executing FnO Function with PythonExecutor...")
  executor = PythonExecutor(g)
  prov = executor.execute(fun)
  # prov.serialize("graphs/prov/python/binarycount.ttl", format="turtle")
  print("Done!")
  print(f"Got output: {fun.output.get()}")