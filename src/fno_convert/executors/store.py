from ..graph import get_name, FnOGraph
from ..mappers import PythonMapper
from rdflib import URIRef
from enum import Enum, auto
from PyQt6.QtCore import QObject, pyqtSignal

class MappingType(Enum):
    POSITIONAL = auto()
    KEYWORD = auto()
    VARPOSITIONAL = auto()
    VARKEYWORD = auto()

class ParameterMapping:

    def __init__(self, g: FnOGraph, mapping: URIRef, par: URIRef) -> None:
        self.property = None
        self.type = None
        self.index = False
        self.keyvalue = False
        
        if g.is_varpositional(mapping, par):
            self.index = True
            self.type = MappingType.VARPOSITIONAL
        elif g.is_varkeyword(mapping, par):
            self.keyvalue = True
            self.type = MappingType.VARKEYWORD
        
        index, prop = g.get_param_mapping(mapping, par)

        if prop is not None:
            self.property = prop
            self.type = MappingType.KEYWORD
        if index is not None:
            self.property = index
            self.type = MappingType.POSITIONAL
        
        self.has_default, self.default = g.get_default_mapping(mapping, par)
        if self.has_default:
            self.default = PythonMapper.term_to_value(g, self.default)   
        
    def get_type(self):
        return self.type
    
    def get_property(self):
        return self.property

class Mapping:

    def __init__(self, sources, target: "Terminal") -> None:
        self.priority = None
        self.target = target
        self.sources = {}
        for source, priority, src_strat, src_key, tar_strat, tar_key in sources:
            if priority not in self.sources:
                self.sources[priority] = []
            self.sources[priority].append((source, src_strat, src_key, tar_strat, tar_key))
            
            # Set default term values
            if not isinstance(source, Terminal) and priority is None:
                self.target.set(source.get(src_strat, src_key), tar_strat, tar_key)
    
    def set_priority(self, priority):
        self.priority = priority
    
    def execute(self):
        self.target.prov.sources = []
        for source, src_strat, src_key, tar_strat, tar_key in self.sources[self.priority]:
            self.target.set(source.get(src_strat, src_key), tar_strat, tar_key)
            if source.prov.instance:
                self.target.prov.sources.append(source.prov.instance)
    
    def list_sources(self):
        sources = set()
        for priority in self.sources:
            for source, _, _, _, _ in self.sources[priority]:
                sources.add(source)
        return sources

class ValueStore(QObject):
    
    valueSet = pyqtSignal()
    
    def __init__(self, type=None):
        super().__init__()
        self.value = None
        self.type = type
        self.value_set = False
        self.prov = Provenance()
    
    def get(self, strat=None, key=None):
        return self.value if strat is None else self.value[key]
    
    def set(self, value):
        self.value_set = True
        self.value = value
        self.valueSet.emit()

class Terminal(ValueStore):

    def __init__(self, fun, uri: URIRef, pred: URIRef, type=None, is_output=False, param_mapping=None) -> None:
        try:
            type = PythonMapper.fno_to_obj(fun.g, type)
        except Exception as e:
            pass
        
        super().__init__(type)
        self.name = get_name(pred)
        self.fun = fun
        self.uri = uri
        self.pred = pred
        self.is_output = is_output
        self.param_mapping = param_mapping
        self.strat = None
    
    def set(self, value, strat=None, key=None):
        if strat is None:
            self.strat = None
            super().set(value)
        else:
            self.strat = strat
            if not isinstance(self.value, dict):
                super().set({})
            self.value[key] = value

    def get(self, strat=None, key=None):
        if self.is_output or self.param_mapping is None:
            return super().get(strat, key)
        
        if (self.param_mapping.get_type() == MappingType.POSITIONAL and self.strat == "toList") or \
            (self.param_mapping.get_type() == MappingType.POSITIONAL and self.param_mapping.index) or \
            self.param_mapping.get_type() == MappingType.VARPOSITIONAL:
                return self.to_list()
            
        return super().get(strat, key)
    
    def to_list(self):
        if not self.value_set:
            return []
        
        if isinstance(self.value, list):
            return self.value
        
        indexed = []
        for i, val in self.value.items():
            indexed.append((i, val))
        return [ x[1] for x in sorted(indexed, key=lambda x: x[0]) ]
    
    def id(self):
        return f"{self.fun.id()}_{get_name(self.uri)}"
                
    def json_elk(self):
        return {
            "id": self.id(),
            "uri": self.uri,
            "width": 10,
            "height":10,
            # TODO better output labels
            "labels": [{
                "text":  get_name(self.pred)
            }],
            "layoutOptions": {
                "port.side": "EAST" if self.is_output else "WEST"
            }
        }

    def __hash__(self) -> int:
        return hash(self.id())
    
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Terminal) and self.uri == other.uri and self.fun == other.fun

class Provenance():
    
    def __init__(self):
        self.sources = []
        self.instance = None