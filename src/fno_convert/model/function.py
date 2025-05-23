from ..graph import FnOGraph, get_name
from .store import Terminal, ParameterMapping, MappingType
from rdflib import URIRef
from typing import Dict, List, Set
from PyQt6.QtCore import pyqtSignal, QObject

class Function(QObject):
    
    implementationChanged = pyqtSignal(object)

    def __init__(self, g: FnOGraph, fun: URIRef, map: URIRef = None, imp: URIRef = None, internal=False) -> None:
        super().__init__()
        
        self.fun_uri = fun
        self.name = g.get_name(fun)
        self._imp = imp
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
                    from .composition import Composition
                    self.comp = Composition(self.g, self.comp_uri, self)
            else:
                self.internal = False
        else:
            self.internal = False
        
        return self.internal
    
    @property
    def imp(self):
        return self._imp
    
    @imp.setter
    def imp(self, uri):
        if uri != self._imp:
            self._imp = uri
            self.implementationChanged.emit(uri)
        
        
    
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
                           if input.param_mapping.is_type(MappingType.POSITIONAL))
        positional = [None] * (length + 1)
        for input in inputs:
            if input.param_mapping.is_type(MappingType.POSITIONAL):
                positional[input.param_mapping.property] = input
        return positional
    
    def varpositional(self) -> Terminal | None:
        next((input for input in self.inputs() if input.param_mapping.is_type(MappingType.LIST, distinct=True) 
              and not input.param_mapping.is_type(MappingType.POSITIONAL)), None)
    
    def keyword(self) -> Dict[str, Terminal]:
        return {
            input.param_mapping.property: input 
            for input in self.inputs() 
            if input.param_mapping.is_type(MappingType.KEYWORD)
        }
    
    def varkeyword(self) -> Terminal | None:
        next((input for input in self.inputs() if input.param_mapping.is_type(MappingType.KEYVALUE, distinct=True)), None)

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
    
    def __init__(self, g: FnOGraph, call: URIRef, scope: "URIRef | Function | AppliedFunction") -> None:
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
        self.generated = []