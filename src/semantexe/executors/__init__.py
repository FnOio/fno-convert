from .executeable import Composition, Function, AppliedFunction
from .python import PythonExecutor
from .docker import DockerfileExecutor, DockerImageExecutor
from ..graph import ExecutableGraph

class Executor:
    
    def __init__(self, g: ExecutableGraph):
        self.g = g
        self.pg = ExecutableGraph()
        self.executor = None
    
    def execute(self, exe):
        if self.g.is_dockerfile(exe):
            exe = Composition(self.g, self.g.get_compositions(exe, first=True))
            self.executor = DockerfileExecutor()
        elif self.g.is_pythonfile(exe):
            exe = Composition(self.g, self.g.get_compositions(exe, first=True))
            self.executor = PythonExecutor
        else:
            exe = Function(self.g, exe)
            self.executor = PythonExecutor
        
        if isinstance(exe, Composition):
            self.execute_comp(exe)
        elif isinstance(exe, Function):
            self.execute_fun(exe)
        elif isinstance(exe, AppliedFunction):
            self.execute_applied(exe)
    
    def execute_comp(self, comp: Composition):
        # Execute each function and follow the control flow until no new function can be selected
        call = comp.start
        while call is not None:
            # Get the FnO Function Executeable
            fun = comp.functions[call]
            # Fetch inputs from mappings
            comp.ingest(fun)
            # Execute
            self.execute_applied(fun)
            # Signify execution to relevant mappings
            if call in comp.priorities:
                for mapping in comp.priorities[call]:
                    mapping.set_priority(call)
            # Get the URI of the next executeable
            call = fun.next_executable()
        
        # If this composition represents the internal flow of a function, set the output
        if comp.rep:
            comp.ingest(comp.scope)
    
    def execute_fun(self, fun: Function):
        if fun.comp:
            self.executor.execute_comp(fun)
        else:            
            self.executor.execute_fun(fun)
    
    def execute_applied(self, fun: AppliedFunction):
        self.executor.execute_applied(fun)