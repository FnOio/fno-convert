import traceback
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

        raise ValueError(f"No descriptor could describe the {method_suffix}.")

    @abstractmethod
    def _get_method_suffix(self) -> str:
        """Each subclass must return the suffix used in method names (e.g., 'file')."""
        pass


# High-level descriptor that tries every available generic descriptor
class Descriptor:
    @staticmethod
    def describe(g: FnOGraph, resource: Any) -> Any:
        descriptors: List[GenericDescriptor] = [
            FileDescriptor(g),
            CLIDescriptor(g),
            ObjectDescriptor(g),
        ]

        for descriptor in descriptors:
            try:
                return descriptor.describe(resource)
            except Exception as e:
                print(f"Error in {descriptor.__class__.__name__}: {e}")
                traceback.print_exc()
                continue  # Try next descriptor

        raise ValueError("No available descriptors could describe the resource.")


class FileDescriptor(GenericDescriptor):
    def __init__(self, g, workdir):
        super().__init__(workdir)

        from .python import PythonDescriptor
        from .docker import DockerfileDescriptor
        self.subscribed = [
            PythonDescriptor(g),
            DockerfileDescriptor(g)
        ]

    def _get_method_suffix(self) -> str:
        return 'file'


class CLIDescriptor(GenericDescriptor):
    def __init__(self, g: FnOGraph, workdir):
        super().__init__(workdir)

        from .python import PythonDescriptor
        self.subscribed = [
            PythonDescriptor(g),
        ]

    def _get_method_suffix(self) -> str:
        return 'cli'


class ObjectDescriptor(GenericDescriptor):
    def __init__(self, g: FnOGraph, workdir):
        super().__init__(workdir)

        from .python import PythonDescriptor
        self.subscribed = [
            PythonDescriptor(g),
        ]

    def _get_method_suffix(self) -> str:
        return 'object'