import hashlib, os
from ..prefix import Prefix
from ..graph import FnOGraph

class FileMapper:
    
    @staticmethod
    def uri(path):
        name = os.path.basename(path).replace('.', '_')
        unique_hash = hashlib.sha256(path.encode()).hexdigest()[:8]
        return Prefix.base()[f"{name}{unique_hash}"]
    
    @staticmethod
    def alternative_files(g: FnOGraph, path):
        uri = FileMapper.uri(path)
        return [file for alt in g.alternatives(uri) if (file := g.get_file(alt))]
    
    @staticmethod
    def file_event(path, timestamp):
        name = os.path.basename(path).replace('.', '_')
        unique_hash = hashlib.sha256(f"{path}{timestamp}".encode()).hexdigest()[:8]
        return Prefix.base()[f"{name}{unique_hash}"]
    
    @staticmethod
    def file_es(path):
        name = os.path.basename(path).replace('.', '_')
        unique_hash = hashlib.sha256(path.encode()).hexdigest()[:8]
        return Prefix.base()[f"{name}{unique_hash}EventStream"]