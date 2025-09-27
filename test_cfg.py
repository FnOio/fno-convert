from scalpel.cfg import CFGBuilder
from scalpel.SSA.const import SSA
import ast

def get_source(path):
  with open(path, 'r') as file:
    return file.read()

if __name__ == "__main__":
  path = "python_examples/example_functions.py"
  name = "py_examples"
  
  src = get_source(path)
  
  cfg = CFGBuilder().build_from_file(name, path, flattened=True)
  for key in cfg:
    # Control Flow
    internal_cfg = cfg[key]
    
    # Draw diagram
    dot = cfg[key].build_visual('png')
    dot.render(f"cfg_diagrams/{name}/{key.replace('.', '_')}_cfg_diagram", view=False)