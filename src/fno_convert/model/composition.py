from ..graph import FnOGraph, get_name
from .store import Mapping, ValueStore
from .function import Function, AppliedFunction
from ..mappers import PythonMapper
from rdflib import URIRef, Literal

class Composition:

    def __init__(self, g: FnOGraph, comp: URIRef, rep: "Function | AppliedFunction" = None) -> None:
        self.uri = comp
        self.name = get_name(comp)
        self.rep = rep
        
        if rep is None:
            reps = g.get_representations(comp)
            if len(reps) > 1:
                raise Exception(f"Composition has multiple representaitons {reps}")
            elif len(reps) == 1:
                self.rep = reps[0]
            else:
                self.rep = comp

        ### USED FUNCTIONS ###
        self.functions = {}

        # Get all the used functions
        for call in g.get_used_functions(self.uri):
            if call != self.rep.fun_uri and call not in self.functions:
                self.functions[call] = AppliedFunction(g, call, rep)

        ### MAPPINGS ###

        self.mappings = {}
        self.priorities = {}
        
        for mapfrom, mapto, priority in g.get_mappings(comp):          
            # Handle mapfrom
            if g.is_function_mapping(mapfrom):
                call, ter = g.get_function_mapping(mapfrom)
                source = self.get_terminal(call, ter)
            elif g.is_term_mapping(mapfrom):
                if isinstance(mapfrom, Literal):
                    source = ValueStore(mapfrom.datatype)
                else:
                    source = ValueStore()
                source.set(PythonMapper.term_to_value(g, mapfrom))
            
            # Handle mapto
            call, ter = g.get_function_mapping(mapto)
            target = self.get_terminal(call, ter)
            
            # Group mappings by target
            if target not in self.mappings:
                self.mappings[target] = []
            src_strat, src_key = g.get_strategy(mapfrom)
            tar_strat, tar_key = g.get_strategy(mapto)
            self.mappings[target].append((source, priority, src_strat, src_key, tar_strat, tar_key))
        
        # Create mapping for each target    
        for target, sources in self.mappings.items():
            self.mappings[target] = Mapping(sources, target)
            for source in sources:
                priority = source[1]
                if priority not in self.priorities:
                    self.priorities[priority] = set()     
                self.priorities[priority].add(self.mappings[target])
        
        ### EXECUTION START ###
        self.start = g.get_start(comp)
    
    def execute(self, executor):
        # Execute each function and follow the control flow until no new function can be selected
        call = self.start
        while call is not None:
            # Get the FnO Function Executeable
            fun = self.functions[call]
            fun.prov.informedBy = self.rep
            # Fetch inputs from mappings
            self.ingest(fun)
            # Execute
            executor.execute_applied(fun)
            # Signify execution to relevant mappings
            if call in self.priorities:
                for mapping in self.priorities[call]:
                    mapping.set_priority(call)
            # Get the URI of the next executeable
            call = fun.next_executeable()
        
        # If this composition represents the internal flow of a function, set the output
        if self.rep:
            if self.rep.output in self.mappings:
                self.mappings[self.rep.output].execute()
            if self.rep.self_output is not None:
                self.rep.self_output.set(self.rep.self_input.get())
        
    
    def ingest(self, fun):
        for input in fun.inputs():
            if input in self.mappings:
                self.mappings[input].execute()            
    
    def get_terminal(self, call, ter):
        return  self.functions[call][ter] if call != self.rep.fun_uri else self.rep[ter]
    
    def __hash__(self) -> int:
        return hash(self.uri)
    
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Composition) and self.uri == other.uri