from abc import ABC, abstractmethod
from datetime import datetime
from rdflib import URIRef
import traceback, os, hashlib

from ..graph import ExecutableGraph
from .executeable import Function, AppliedFunction, Composition
from .store import Terminal
from ..builders import ProvBuilder, FnOBuilder, LDESBuidlder
from ..mappers import PythonMapper, FileMapper
from ..util.prov import ProvLogger
from ..prefix import Prefix

class Executor(ABC):
    
    def __init__(self, g: ExecutableGraph, logger: ProvLogger = ProvLogger()):
        self.g = g
        self.depth = 0
        self.handled = []
            
        self.pg = None
        self.fun = None
        
        self.logger = logger
    
    def execute(self, fun: Function, *args, **kwargs):
        self.logger.append(fun)
        
        if self.is_handled(fun.fun_uri):
            try:
                fun.prov.startedAt = datetime.now()
                out = self.handle(fun, *args, **kwargs)
                fun.prov.endedAt = datetime.now()
                self.logger.pop()
                self.fun_provenance(fun)
                return
            except Exception as e:
                print(f"Error when executing {fun.fun_uri} with executor {self.__class__.__name__}: {e}")
                traceback.print_exc()
                pass
        # Consider all available mappings
        elif fun.imp is None:
            for mapping, imp in self.g.fun_to_imp(fun.fun_uri):
                if self.accepts(mapping, imp):
                    fun.map = mapping
                    fun.imp = imp
        
                    try:
                        fun.prov.startedAt = datetime.now()
                        out = self.execute_with_mapping(fun, *args, **kwargs)
                        fun.prov.endedAt = datetime.now()
                        self.logger.pop()
                        self.fun_provenance(fun)
                        return
                    except Exception as e:
                        print(f"Error when executing Mapping {fun.map} with executor {self.__class__.__name__}: {e}")
                        traceback.print_exc()
                        pass
        # Consider available mappings for implementation
        elif fun.map is None:
            for mapping in self.g.mappings(fun.fun_uri, fun.imp):
                if self.accepts(mapping, fun.imp):
                    fun.map = mapping
        
                    try:
                        fun.prov.startedAt = datetime.now()
                        out = self.execute_with_mapping(fun, *args, **kwargs)
                        fun.prov.endedAt = datetime.now()
                        self.logger.pop()
                        self.fun_provenance(fun)
                        return
                    except Exception as e:
                        print(f"Error when executing Mapping {fun.map} with executor {self.__class__.__name__}: {e}")
                        traceback.print_exc()
                        pass
        # Execute with given mapping and implementation
        elif fun.map and fun.imp:
            if self.accepts(fun.map, fun.imp):
                try:
                    fun.prov.startedAt = datetime.now()
                    out = self.execute_with_mapping(fun, *args, **kwargs)
                    fun.prov.endedAt = datetime.now()
                    self.logger.pop()
                    self.fun_provenance(fun)
                    return
                except Exception as e:
                    print(f"Error when executing Mapping {fun.map} with executor {self.__class__.__name__}: {e}")
                    traceback.print_exc()
                    pass
        
        # If no suitable mapping and implementation can be found, try executing a composition
        if fun.comp_uri is not None:
            internal = fun.setInternal(True)
            if internal:
                try:
                    fun.prov.startedAt = datetime.now()
                    fun.comp.execute(self)
                    fun.prov.endedAt = datetime.now()
                    self.logger.pop()
                    self.fun_provenance(fun)
                    return
                except Exception as e:
                    print(f"Error when executing Composition {fun.comp_uri} with executor {self.__class__.__name__}: {e}")
                    traceback.print_exc()
                    self.alt_executor(fun)
                    self.logger.pop()
                    return
        
        else:
            self.alt_executor(fun)
            self.logger.pop()
            self.fun_provenance(fun)
            return
    
    def execute_with_mapping(self, fun: Function, *args, **kwargs):
        # Change workdir if toplevel function
        if self.depth == 0:
            file = self.g.get_file(fun.imp)
            file_dir = os.path.dirname(file)
            current_wd = os.getcwd()
            os.chdir(file_dir)
        
        self.map(fun)

        self.depth += 1
        out = self.execute_function(fun, *args, **kwargs)
        self.depth -= 1
        
        # Change back to the previous workdir
        if self.depth == 0:
            os.chdir(current_wd)
            
        return out
    
    def is_handled(self, uri):
        return uri in self.handled
    
    def handle(self, fun: Function, *args, **kwargs):
        return self.handled[fun.fun_uri](fun, *args, **kwargs)
    
    def provenance(self, fun: Function, *args, **kwargs):
        # initialize provenance graph
        self.fun = fun
        self.pg = ExecutableGraph()
        
        # Execute the function
        self.logger.start()
        self.execute(fun, *args, **kwargs)
        self.logger.stop()
        
        # Return provenance graph
        return self.pg
    
    def fun_provenance(self, fun: Function):
        fun_uri = fun.call_uri if isinstance(fun, AppliedFunction) else fun.fun_uri
        exe_id = hashlib.sha256(f"{fun.id()}{fun.prov.startedAt}{fun.prov.endedAt}".encode()).hexdigest()[:8]
        exe_uri = URIRef(f"{fun_uri}Execution{exe_id}")
        
        # Describe execution activity
        ProvBuilder.execution(self.pg, exe_uri,
                              fun_uri, fun.imp,
                              fun.prov.startedAt, fun.prov.endedAt)
        
        terminal_values = {}
        for terminal in fun.terminals.values():
            inst_uri = self.terminal_provenance(terminal, exe_id)
            
            
            if terminal.is_output:
                ProvBuilder.wasGeneratedBy(self.pg, inst_uri, exe_uri)
            else:
                ProvBuilder.used(self.pg, exe_uri, inst_uri)
            terminal_values[terminal.pred] = inst_uri
            
        FnOBuilder.describe_execution(self.pg, exe_uri, fun_uri, fun.map, terminal_values)
        
        # Add execution to top-level execution details
        if fun.prov.informedBy:
            fun.prov.informedBy.prov.informed.append(exe_uri)
        fun.prov.informedBy = None
        
        # Describe internal provenance
        for informed in fun.prov.informed:
            ProvBuilder.wasInformedBy(self.pg, informed, exe_uri)
        fun.prov.informed = []
                
        # Describe captured messages
        self.message_provenance(exe_uri, fun.prov.msgs)
        fun.prov.msgs = []
        
        # Describe file provenance
        self.file_provenance(exe_uri, fun.prov.files_created, fun.prov.files_modified)
        fun.prov.files_created = []
        fun.prov.files_modified = []
        
        return exe_uri
    
    def terminal_provenance(self, term: Terminal, exe_id):
        if term.is_output or len(term.prov.sources) != 1:
            # Create a new RDF instance for the terminal value
            inst_uri = Prefix.base()[f"{term.name}{exe_id}"]
            term.prov.instance = inst_uri
            ProvBuilder.entity(self.pg, inst_uri)
            
            rdf_value = PythonMapper.value_to_rdf(self.pg, term.get())
            ProvBuilder.value(self.pg, inst_uri, rdf_value)
            
            if len(term.prov.sources) > 1:
                # The new instance is derived from multiple sources
                for source in term.prov.sources:
                    ProvBuilder.derivedFrom(self.pg, inst_uri, source)
            
            return inst_uri
        
        # Re-use the instance uri of the source
        return term.prov.sources[0]
            
    
    def comp_provenance(self, comp: Composition, exe_uri=None):
        for call in comp.functions.values():
            if call.prov.executedBy:
                call_exe_uri = call.prov.executedBy.fun_provenance(call)
                ProvBuilder.wasInformedBy(self.pg, call_exe_uri, exe_uri)
    
    def message_provenance(self, exe_uri, msgs):
        for msg, time in msgs:
            msg_id = hashlib.sha256(f"{msg}{time}".encode()).hexdigest()[:8]
            msg_uri = Prefix.base()[f"message{msg_id}"]
            ProvBuilder.entity(self.pg, msg_uri)
            ProvBuilder.value(self.pg, msg_uri, PythonMapper.value_to_rdf(self.pg, msg))
            ProvBuilder.wasGeneratedBy(self.pg, msg_uri, exe_uri, time)
    
    def file_provenance(self, exe_uri, created, modified):
        
        for file, timestamp in created:
            # Create a file entity
            file_uri = FileMapper.uri(file)
            ProvBuilder.entity(self.pg, file_uri)
            ProvBuilder.value(self.pg, file_uri, URIRef(f"file://{file}"))
            
            # Create a file event stream
            # TODO File SHACL shape
            event_uri = FileMapper.file_event(file, timestamp)
            stream_uri = FileMapper.file_es(file)
            LDESBuidlder.fileES(self.pg, event_uri, stream_uri, file_uri, timestamp)
        
            # Event provenance
            ProvBuilder.generationEvent(self.pg, event_uri, exe_uri, file_uri)            
        
        for file, timestamp in modified:
            # Create a file modified event
            file_uri = FileMapper.uri(file)
            event_uri = FileMapper.file_event(file, timestamp)
            stream_uri = FileMapper.file_es(file)
            LDESBuidlder.createFileEvent(self.pg, event_uri, stream_uri, file_uri, timestamp, "File Modified")
            
            # Event provenance
            ProvBuilder.usageEvent(self.pg, event_uri, exe_uri, file_uri)
    
    @abstractmethod
    def accepts(self, mapping, imp):
        pass
    
    @abstractmethod
    def map(self, fun: Function):
        pass
    
    @abstractmethod
    def execute_function(self, fun: Function, *args, **kwargs):
        pass
    
    def execute_applied(self, fun: AppliedFunction):
        # Control flow
        if fun.iterate is not None:
            self.execute(fun)
            if hasattr(fun, 'stop_iteration'):
                fun._next = fun.next
            else:
                fun._next = fun.iterate
        elif fun.iftrue is not None:
            self.execute(fun)
            fun._next = fun.iftrue if fun.output.value else fun.iffalse
        else:
            self.execute(fun)
            fun._next = fun.next    
    
    @abstractmethod
    def alt_executor(self, fun: Function):
        pass