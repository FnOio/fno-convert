import subprocess

class CallableScript:
  
  def __init__(self, file):
    self.file = file
  
  def __call__(self, *args, **kwds):
    cmd = ['python3', self.file, *args ]
    
    for key, value in kwds.items():
      cmd.append(f'--{key}' if len(key) > 1 else f'-{key}')
      cmd.append(value)
    
    subprocess.run(cmd)
    return