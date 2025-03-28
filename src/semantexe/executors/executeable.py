from ..graph import ExecutableGraph, get_name
from .store import Mapping, Terminal, ValueStore, ParameterMapping, MappingType
from rdflib import URIRef
from typing import Dict, List, Set

class Composition:

    def __init__(self, g: ExecutableGraph, comp: URIRef, rep: "Function | AppliedFunction" = None) -> None:
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
                source = ValueStore(mapfrom.datatype)
                source.set(mapfrom.value)
            
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

class Function:

    def __init__(self, g: ExecutableGraph, fun: URIRef, map: URIRef = None, imp: URIRef = None, internal=False) -> None:
        self.fun_uri = fun
        self.name = g.get_name(fun)
        self.imp = imp
        self._map = None
        self.g = g

        ### TERMINALS ###

        self.terminals = {}
        self.self_input = None
        self.self_output = None
        self.output = None
        
        self.terminals.update({ par: Terminal(self, par, g.get_predicate(par), 
                                              type=g.get_param_type(par)) for par in g.get_parameters(fun) })
        
        if g.has_self(fun):
            uri = g.get_self(fun)
            self.self_input = Terminal(self, uri, g.get_predicate(uri), 
                                       type=g.get_param_type(uri))
            self.terminals[self.self_input.uri] = self.self_input
        if g.has_output(fun):
            uri = g.get_output(fun)
            self.output = Terminal(self, uri, g.get_predicate(uri), type=g.get_output_type(uri), is_output=True)
            self.terminals[self.output.uri] = self.output
        if g.has_self_output(fun):
            uri = g.get_self_output(fun)
            self.self_output = Terminal(self, uri, g.get_predicate(uri), type=g.get_output_type(uri), is_output=True)
            self.terminals[self.self_output.uri] = self.self_output
        
        self.map = map
        
        ### COMPOSITION ###
        
        self.comp = None
        if g.has_composition(fun):
            # TODO Function is represented by multiple compositions
            self.comp_uri = g.get_compositions(fun)[0]
        else:
            self.comp_uri = None
        self.setInternal(internal)
        
        ### PROVENANCE ###
        self.prov = Provenance()
    
    def setInternal(self, internal: bool):
        # Wether or not to capture the internal flow of the function
        if internal:
            if self.comp_uri is not None:
                self.internal = True
                if self.internal and self.comp is None:
                    self.comp = Composition(self.g, self.comp_uri, self)
            else:
                self.internal = False
        else:
            self.internal = False
        
        return self.internal
    
    @property
    def map(self):
        return self._map
    
    @map.setter
    def map(self, uri):
        if uri != self._map:
            self._map = uri
            
            # TODO support Mappings for outputs?
            for terminal in self.inputs():
                terminal.param_mapping = ParameterMapping(self.g, uri, terminal.uri)
    
    def inputs(self) -> Set[Terminal]:
        return { self.terminals[id] for id in self.terminals if not self.terminals[id].is_output }
    
    def positional(self) -> List[Terminal]:
        inputs = self.inputs()
        length = max(input.param_mapping.property 
                           for input in inputs 
                           if input.param_mapping.get_type() == MappingType.POSITIONAL)
        positional = [None] * (length + 1)
        for input in inputs:
            if input.param_mapping.get_type() == MappingType.POSITIONAL:
                positional[input.param_mapping.property] = input
        return positional
    
    def varpositional(self) -> Terminal:
        next((input for input in self.inputs() if input.param_mapping.get_type() == MappingType.VARPOSITIONAL), None)
    
    def keyword(self) -> Dict[str, Terminal]:
        return {
            input.param_mapping.property: input 
            for input in self.inputs() 
            if input.param_mapping.get_type() == MappingType.KEYWORD
        }
    
    def varkeyword(self) -> Terminal:
        next((input for input in self.inputs() if input.param_mapping.get_type() == MappingType.VARKEYWORD), None)

    def outputs(self) -> Set[Terminal]:
        return { self.terminals[id] for id in self.terminals if self.terminals[id].is_output }
    
    def __getitem__(self, key) -> Terminal:
        # Based on parameter URI
        if isinstance(key, URIRef):
            return self.terminals[key]
        
        # Based on parameter predicate
        for ter in self.terminals.values():
            if ter.name == key:
                return ter
        
        raise KeyError(f"No terminal found with key '{key}'")
    
    def id(self):
        # TODO Format prefix
        return get_name(self.fun_uri)
    
    def __hash__(self) -> int:
        return hash(self.id())
    
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Function) and self.fun_uri == other.fun_uri

    
class AppliedFunction(Function):
    
    def __init__(self, g: ExecutableGraph, call: URIRef, scope: "URIRef | Function | AppliedFunction") -> None:
        fun = g.check_call(call)
        self.call_uri = call
        self.scope = scope
        
        super().__init__(g, fun)
        
        if g.has_composition(call):
            self.comp_uri = g.get_compositions(call, True)
        
        self._next = None
        self.next, self.iterate, self.iftrue, self.iffalse = g.get_order(call)
    
    def next_executeable(self):
        return self._next
    
    def id(self):
        if isinstance(self.scope, (Function, AppliedFunction)):
            return f"{self.scope.id()}_{get_name(self.call_uri)}"
        return f"{get_name(self.scope)}_{get_name(self.call_uri)}"
    
    def __hash__(self) -> int:
        return hash(self.id())
    
    def __eq__(self, other: object) -> bool:
        return isinstance(other, AppliedFunction) and self.call_uri == other.call_uri and self.scope == other.scope

class Provenance:
    
    def __init__(self):
        self.informedBy = None
        self.informed = []
        self.startedAt = None
        self.endedAt = None
        self.msgs = []
        self.files_created = []
        self.files_modified = []