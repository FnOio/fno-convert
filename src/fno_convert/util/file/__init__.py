from rdflib import URIRef

from ...graph import FnOGraph
from ...prefix import Prefix
from ...builders import FnOBuilder
from ...mappers.python import PythonMapper
from ...mappers.file import FileMapper

NAME = Prefix.ns('rdfs').label
FILE_PRED = Prefix.ns('fnoi').file
MODULE_PRED = Prefix.ns('fnoi').module
PACKAGE_PRED = Prefix.ns('fnoi').package
DOC_PRED = Prefix.ns('dcterms').description

# TODO make move_file more general, it uses knowledge of Python Implementation too much
def move_file(g: FnOGraph, mapping, imp, src, dest):
        new_imp = None
        metadata = g.get_imp_metadata(imp)
        
        if FILE_PRED in metadata:
            new_imp = None
            src_file = str(metadata[FILE_PRED][0]).removeprefix("file://")
            dest_file = src_file.replace(src, dest)
            
            # Not needed anymore
            del metadata[FILE_PRED]
            
            if dest_file.endswith(".py"):
                name = metadata[NAME][0].value if NAME in metadata else 'unknown'
                m_name = metadata[MODULE_PRED][0].value if MODULE_PRED in metadata else None
                p_name = metadata[PACKAGE_PRED][0].value if PACKAGE_PRED in metadata else None
                
                # create new implementation
                if name.endswith(".py"):
                    new_imp = FileMapper.uri(dest_file)
                else:
                    new_imp = PythonMapper.uri(name, m_name, p_name, dest_file)
            
            if new_imp:
                # copy implementation metadata   
                for pred, values in metadata.items():
                    for value in values:
                        g.add((new_imp, pred, value))
                g.add((new_imp, Prefix.ns('fnoi').file, URIRef(f"file://{dest_file}")))
                
                # link new implementation
                FnOBuilder.implementation(g, mapping, new_imp)
                
                return new_imp