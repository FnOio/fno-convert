import subprocess

class CallableScript:
  
  def __init__(self, file):
    self.file = file
  
  def __call__(self, *args, **kwds):
    # TODO *args & **kwargs
    subprocess.run(['python3', self.file])
    return