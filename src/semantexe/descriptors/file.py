from ..graph import ExecutableGraph
from ..mappers import FileMapper
from .resource import AbstractResourceDescriptor

from pathlib import Path
from abc import ABC, abstractmethod

import os

class IFileDescriptor(ABC):
    
    @abstractmethod
    def describe_file(self, file):
        pass
    
    @abstractmethod
    def set_next(self, descriptor: "IFileDescriptor") -> "IFileDescriptor":
        pass

class AbstractFileDescriptor(IFileDescriptor):
    
    _next_descriptor = None
    
    def set_next(self, descriptor: "IFileDescriptor") -> "IFileDescriptor":
        self._next_descriptor = descriptor
        return descriptor
    
    @abstractmethod
    def describe_file(self, file):
        if self._next_descriptor:
            return self._next_descriptor.describe_file(file)
        raise ValueError(f"Cannot describe {file} as an FnO Function")

def get_all_filepaths(directory):
    dir_path = Path(directory)
    # Use rglob('*') to recursively find all files in all subdirectories
    return [str(file) for file in dir_path.rglob('*') if file.is_file()]

class DirectoryDescriptor(AbstractResourceDescriptor):
    
    def __init__(self, g: ExecutableGraph):
        self._fileDescriptor = FileDescriptor(g)
    
    def describe_resource(self, resource):
        try:
            if os.path.isdir(resource):
                descriptions = []
                for file_path in get_all_filepaths(resource):
                    try:
                        descriptions.append(self._fileDescriptor.describe_resource(file_path))
                    except ValueError as e:
                        descriptions.append(file_path)
                return descriptions
        except:
            pass
        
        return super().describe_resource(resource)
        
class FileDescriptor(AbstractResourceDescriptor):
    
    _start: AbstractFileDescriptor = None
    
    def __init__(self, g: ExecutableGraph):
        from .python import PythonDescriptor
        from .docker import DockerfileDescriptor
        
        self._start = PythonDescriptor(g)
        self._start.set_next(DockerfileDescriptor(g))
       
    def describe_resource(self, resource):
        try:
            if os.path.isfile(resource):
                try:
                    return self._start.describe_file(resource)
                except ValueError as e:
                    return FileMapper.uri(resource)
        except:
            pass
        
        return super().describe_resource(resource)