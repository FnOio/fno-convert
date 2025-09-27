from abc import ABC, abstractmethod
from datetime import datetime
from rdflib import URIRef
import traceback, os, hashlib

from ..graph import FnOGraph
from ..model.function import Function, AppliedFunction, Composition
from ..model.store import Terminal
from ..builders import ProvBuilder, FnOBuilder, LDESBuidlder
from ..mappers import PythonMapper, FileMapper
from ..util.prov import ProvLogger
from ..prefix import Prefix


class Executer(ABC):

    def __init__(self, g: FnOGraph):
        self.g = g
        self.handled = []

        self.pg = None
        self.logger = None

    def execute(self, fun: Function, *args, **kwargs):
        self.logger.append(fun)

        if self.is_handled(fun.fun_uri):
            try:
                fun.prov.startedAt = datetime.now()
                out = self.handle(fun, *args, **kwargs)
                fun.prov.endedAt = datetime.now()
                self.logger.pop()
                return self.fun_provenance(fun)
            except Exception as e:
                print(
                    f"Error when executing {fun.fun_uri} with executor {self.__class__.__name__}: {e}"
                )
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
                        return self.fun_provenance(fun)
                    except Exception as e:
                        print(
                            f"Error when executing Mapping {fun.map} with executor {self.__class__.__name__}: {e}"
                        )
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
                        return self.fun_provenance(fun)
                    except Exception as e:
                        print(
                            f"Error when executing Mapping {fun.map} with executor {self.__class__.__name__}: {e}"
                        )
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
                    return self.fun_provenance(fun)
                except Exception as e:
                    print(
                        f"Error when executing Mapping {fun.map} with executor {self.__class__.__name__}: {e}"
                    )
                    traceback.print_exc()
                    pass

        # Try an alternative executor
        try:
            self.alt_executor(fun)
            self.logger.pop()
            return self.fun_provenance(fun)
        except Exception as e:
            pass

        # If no suitable mapping and implementation can be found, try executing a composition
        if fun.comp_uri is not None:
            internal = fun.setInternal(True)
            if internal:
                fun.prov.startedAt = datetime.now()
                fun.comp.execute(self)
                fun.prov.endedAt = datetime.now()
                self.logger.pop()
                return self.fun_provenance(fun)

        raise Exception(
            f"{self.__class__.__name__} is unable to execute {fun.name} ({fun.fun_uri})."
        )

    def execute_with_mapping(self, fun: Function, *args, **kwargs):
        self.map(fun)

        # Change workdir if executing a file
        file = self.g.get_file(fun.imp)
        current_wd = os.getcwd()
        if file and os.path.dirname(file):
            os.chdir(os.path.dirname(file))

        out = self.execute_function(fun, *args, **kwargs)

        # Change back to previous workdir
        os.chdir(current_wd)

        return out

    def is_handled(self, uri):
        return uri in self.handled

    def handle(self, fun: Function, *args, **kwargs):
        return self.handled[fun.fun_uri](fun, *args, **kwargs)

    def provenance(self, fun: Function, *args, logger: ProvLogger, **kwargs):
        # initialize provenance graph
        self.pg = FnOGraph(self.g)

        # Execute the function
        self.logger = logger
        exe_uri = self.execute(fun, *args, **kwargs)

        # Return provenance graph
        return self.pg, exe_uri

    def fun_provenance(self, fun: Function):
        fun_uri = fun.call_uri if isinstance(fun, AppliedFunction) else fun.fun_uri
        exe_id = hashlib.sha256(
            f"{fun.id()}{fun.prov.startedAt}{fun.prov.endedAt}".encode()
        ).hexdigest()[:8]
        exe_uri = URIRef(f"{fun_uri}Execution{exe_id}")

        # Describe execution activity
        ProvBuilder.execution(
            self.pg, exe_uri, fun_uri, fun.imp, fun.prov.startedAt, fun.prov.endedAt
        )

        # Associate executor as agent
        if fun.internal:
            ProvBuilder.associate(
                self.pg, exe_uri, self.uri(), Prefix.base().composition, fun.comp_uri
            )

        terminal_values = {}
        for terminal in fun.terminals.values():
            inst_uri = self.terminal_provenance(terminal, exe_id)

            if terminal.is_output:
                ProvBuilder.wasGeneratedBy(self.pg, inst_uri, exe_uri)
            else:
                ProvBuilder.used(self.pg, exe_uri, inst_uri)
            terminal_values[terminal.pred] = inst_uri

        # Outputs are derived from inputs
        for output in fun.outputs():
            for input in fun.inputs():
                ProvBuilder.derivedFrom(
                    self.pg, output.prov.instance, input.prov.instance
                )

                # TODO implement context mapping and use this instead of self predicate
                if output.name == "self_output" and input.name == "self":
                    ProvBuilder.specialiazitionOf(
                        self.pg, output.prov.instance, input.prov.instance
                    )

        FnOBuilder.describe_execution(
            self.pg, exe_uri, fun_uri, fun.map, terminal_values
        )

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

        # Describe generated uris
        for uri in fun.prov.generated:
            ProvBuilder.wasGeneratedBy(self.pg, uri, exe_uri)

        return exe_uri

    def terminal_provenance(self, term: Terminal, exe_id):
        if not term.is_output and len(term.prov.sources) == 1:
            # Re-use the instance uri of the source
            term.prov.instance = term.prov.sources[0]
        else:
            # Create a new RDF instance for the terminal value
            inst_uri = Prefix.base()[f"{term.name}{exe_id}"]
            term.prov.instance = inst_uri
            ProvBuilder.entity(self.pg, inst_uri)

            rdf_value = PythonMapper.value_to_term(self.pg, term.get())
            ProvBuilder.value(self.pg, inst_uri, rdf_value)

            for src in term.prov.sources:
                ProvBuilder.derivedFrom(self.pg, inst_uri, src)

        return term.prov.instance

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
            ProvBuilder.value(
                self.pg, msg_uri, PythonMapper.value_to_term(self.pg, msg)
            )
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
            LDESBuidlder.createFileEvent(
                self.pg, event_uri, stream_uri, file_uri, timestamp, "File Modified"
            )

            # Event provenance
            ProvBuilder.usageEvent(self.pg, event_uri, exe_uri, file_uri)

    @abstractmethod
    def uri(self):
        pass

    @abstractmethod
    def accepts(self, mapping, imp):
        pass

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
            if hasattr(fun, "stop_iteration"):
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
