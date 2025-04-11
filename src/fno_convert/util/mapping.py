from typing import List
from rdflib import URIRef, Literal

class Mapping:

    def __init__(self, mapfrom: "MappingNode" | List["MappingNode"], mapto: "MappingNode", priority: URIRef | None = None) -> None:
        self.mapfrom = mapfrom
        self.mapto = mapto
        self.priority = priority

class MappingNode:

    def __init__(self) -> None:
        self.context = None
        self.parameter = None
        self.output = None
        self.key = None
        self.strategy = None
        self.constant = None
        self.variable = None
    
    def set_function_par(self, context, parameter) -> "MappingNode":
        self.context = context
        self.parameter = parameter
        self.output = None
        self.constant = None

        return self
    
    def set_function_out(self, context, output) -> "MappingNode":
        self.context = context
        self.output = output
        self.parameter = None
        self.constant = None

        return self
    
    def set_constant(self, constant) -> "MappingNode":
        if not isinstance(constant, Literal):
            constant = Literal(constant)        
        self.constant = constant
        self.context = None
        self.parameter = None
        self.output = None

        return self
    
    def get_value(self):
        if self.parameter is not None:
            return self.parameter
        if self.output is not None:
            return self.output
        return self.constant
    
    def set_variable(self, var):
        self.variable = var
    
    def get_variable(self):
        return self.variable
    
    def set_strategy(self, strategy, key: int | str = None) -> "MappingNode":
        self.strategy = strategy
        self.key = key

        return self
    
    def is_output(self) -> bool:
        return self.output is not None

    def has_map_strategy(self) -> bool:
        return self.strategy is not None
    
    def from_term(self) -> bool:
        return self.parameter is None and self.output is None
    
    def from_variable(self) -> bool:
        return self.variable is not None