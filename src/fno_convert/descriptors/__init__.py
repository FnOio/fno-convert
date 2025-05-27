import traceback, os
from abc import ABC, abstractmethod
from typing import List, Any
from ..graph import FnOGraph

class GenericDescriptor(ABC):
    def __init__(self, workdir):
        self.subscribed: List[Any] = []
        self.workdir = workdir

    def describe(self, resource: Any) -> Any:
        method_suffix = self._get_method_suffix()

        can_method = f'can_describe_{method_suffix}'
        describe_method = f'describe_{method_suffix}'
        
        for descriptor in self.subscribed:
            can_fn = getattr(descriptor, can_method, None)
            describe_fn = getattr(descriptor, describe_method, None)

            if callable(can_fn) and can_fn(resource):
                if callable(describe_fn):
                    return describe_fn(resource)

        return None

    @abstractmethod
    def _get_method_suffix(self) -> str:
        """Each subclass must return the suffix used in method names (e.g., 'file')."""
        pass


# High-level descriptor that tries every available generic descriptor
class Descriptor:
    @staticmethod
    def describe(g: FnOGraph, resource: Any) -> Any:
        workdir = os.getcwd()
        
        descriptors: List[GenericDescriptor] = [
            FileDescriptor(g, workdir),
            CLIDescriptor(g, workdir),
            ObjectDescriptor(g, workdir),
        ]

        for descriptor in descriptors:
            try:
                return descriptor.describe(resource)
            except Exception as e:
                print(f"Error in {descriptor.__class__.__name__}: {e}")
                traceback.print_exc()
                continue  # Try next descriptor

        return None


class FileDescriptor(GenericDescriptor):
    def __init__(self, g, workdir):
        super().__init__(workdir)

        from .python import PythonDescriptor
        from .docker import DockerfileDescriptor
        self.subscribed = [
            PythonDescriptor(g, workdir),
            DockerfileDescriptor(g, workdir)
        ]
    
    def describe(self, file):
        file = os.path.join(self.workdir, file)
        return super().describe(file)

    def _get_method_suffix(self) -> str:
        return 'file'


class CLIDescriptor(GenericDescriptor):
    def __init__(self, g: FnOGraph, workdir):
        super().__init__(workdir)

        from .python import PythonDescriptor
        self.subscribed = [
            PythonDescriptor(g, workdir),
        ]

    def _get_method_suffix(self) -> str:
        return 'cli'


class ObjectDescriptor(GenericDescriptor):
    def __init__(self, g: FnOGraph, workdir):
        super().__init__(workdir)

        from .python import PythonDescriptor
        self.subscribed = [
            PythonDescriptor(g, workdir),
        ]

    def _get_method_suffix(self) -> str:
        return 'object'