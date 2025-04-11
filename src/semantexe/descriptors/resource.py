from ..graph import FnOGraph

from abc import ABC, abstractmethod

class IDescriptor(ABC):
    
    @abstractmethod
    def describe_resource(self, g: FnOGraph, resource):
        pass
    
    @abstractmethod
    def set_next(self, descriptor: "IDescriptor") -> "IDescriptor":
        pass

class AbstractResourceDescriptor(IDescriptor):
    
    _next_descriptor = None
    
    def set_next(self, descriptor: "IDescriptor") -> "IDescriptor":
        self._next_descriptor = descriptor
        return descriptor
    
    @abstractmethod
    def describe_resource(self, resource):
        if self._next_descriptor:
            return self._next_descriptor.describe_resource(resource)
        raise ValueError(f"Cannot describe {resource} as an FnO Function")

class ResourceDescriptor:
    
    _start: AbstractResourceDescriptor = None
    
    def __init__(self, g: FnOGraph):
        from .file import FileDescriptor, DirectoryDescriptor
        from .python import PythonDescriptor
        
        self._start = FileDescriptor(g)
        self._start.set_next(DirectoryDescriptor(g)).set_next(PythonDescriptor(g))
    
    def describe(self, resource):
        try:
            return self._start.describe_resource(resource)
        except TypeError as e:
            print(e)
            return None