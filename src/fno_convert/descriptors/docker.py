from dockerfile_parse import DockerfileParser
from rdflib import URIRef
from pathspec import PathSpec

import ast, os
from . import CLIDescriptor, FileDescriptor
from ..prefix import Prefix
from ..graph import FnOGraph
from ..builders import FnOBuilder, DockerBuilder, ProvBuilder
from ..mappers import FileMapper, PythonMapper
from ..util.std_kg import STD_KG
from ..util.mapping import Mapping, MappingNode
from ..util.file import move_file

INPUT_IMAGE = Prefix.do()["imageInputParam"]
OUTPUT_IMAGE = Prefix.do()["imageOutputParam"]

# TODO multiple build stages

class DockerfileDescriptor:
    
    def __init__(self, g: FnOGraph, workdir) -> None:
        self.parser = DockerfileParser()
        self.g = g
        
        self.host_wd = workdir
        self.file_wd = workdir
        self.con_wd = ''
        self.files = {}
    
    def can_describe_file(self, path):
        return path.endswith("Dockerfile")
    
    def describe_file(self, path):
        self.file_wd = os.path.join(self.host_wd, os.path.dirname(path))
        name = os.path.basename(self.file_wd)
        file_uri = FileMapper.uri(path)
        if not self.g.exists(file_uri):
            
            self.load_dockerignore()
            
            ### DOCKERFILE ###
            fun_uri = Prefix.base()[f"{name}Dockerfile"]
            map_uri = DockerBuilder.describe_dockerfile(self.g, path, fun_uri, file_uri)
        
            ### URI ###
            
            comp_uri = URIRef(f"{fun_uri}Composition")
            
            self.parser.dockerfile_path = path
            
            self.prev_instruction = None
            self.mappings = []
            
            for inst in self.parser.structure:
                self.handle_inst(inst)
            
            FnOBuilder.describe_composition(self.g, comp_uri, self.mappings, represents=fun_uri)
            
            # Indicate start
            FnOBuilder.start(self.g, comp_uri, self.start)
                
            return [(fun_uri, map_uri, file_uri)]
        
        return [(fun_uri, map_uri, file_uri) for (map_uri, fun_uri) in self.g.imp_to_fun(file_uri)]

    def load_dockerignore(self):
        patterns = ['Dockerfile', '.dockerignore']
        if os.path.exists('.dockerignore'):
            with open('.dockerignore', 'r') as file:
                patterns.extend(file.readlines())
        self.ignore = PathSpec.from_lines('gitwildmatch', patterns)
    
    def handle_mapping(self, mapfrom, mapto):
        self.mappings.append(Mapping(mapfrom, mapto))
    
    def handle_order(self, call):
        if self.prev_instruction == None:
            # Instruction is the sart of the composition
            self.start = call
        else:
            # Use the image output is image input
            output = MappingNode().set_function_out(self.prev_instruction, OUTPUT_IMAGE)
            input = MappingNode().set_function_par(call, INPUT_IMAGE)
            self.handle_mapping(output, input)
            # Explicit execution order
            FnOBuilder.link(self.g, self.prev_instruction, "next", call)
        self.prev_instruction = call
    
    def get_call(self, inst):
        inst_uri = Prefix.do()[inst]
        if inst not in self.g.f_counter:
            self.g.f_counter[inst] = 1
            self.g += STD_KG[inst_uri]
        else:
            self.g.f_counter[inst] += 1
        
        call_uri = Prefix.base()[f"{inst}_{self.g.f_counter[inst]}"]
        FnOBuilder.apply(self.g, call_uri, inst_uri)
        
        return call_uri
    
    def handle_inst(self, inst):
        if inst['instruction'] == 'FROM':
            self.handle_from(inst['value'])
        elif inst['instruction'] == 'ENTRYPOINT':
            self.handle_entrypoint(inst['value'])
        elif inst['instruction'] == 'CMD':
            self.handle_cmd(inst['value'])
        elif inst['instruction'] == 'RUN':
            self.handle_run(inst['value'])
        elif inst['instruction'] == 'COPY':
            self.handle_copy(inst['value'])
        elif inst['instruction'] == 'WORKDIR':
            self.handle_workdir(inst['value'])
    
    def handle_from(self, value):
        inst = 'from'
        call_uri = self.get_call(inst)
        
        # Set input parameter
        image = MappingNode().set_constant(value)
        input = MappingNode().set_function_par(call_uri, INPUT_IMAGE)
        self.handle_mapping(image, input)
        
        self.handle_order(call_uri)
    
    def handle_entrypoint(self, values):
        inst = 'entrypoint'
        call_uri = self.get_call(inst)
        
        # Convert input parameter to list
        values = ast.literal_eval(values)
        
        # Set entrypoint command
        cmd = MappingNode().set_constant(values[0])
        entrypoint_cmd = MappingNode().set_function_par(call_uri, Prefix.do()['entrypointInputCommand'])
        self.handle_mapping(cmd, entrypoint_cmd)
        
        # Set entrypoint command parameters
        if len(values) > 1:
            entrypoint_cmd_params = MappingNode().set_function_par(call_uri, Prefix.do()['entrypointInputParamList'])
            values = MappingNode().set_constant(PythonMapper.value_to_term(self.g, values[1:]))
            self.handle_mapping(values, entrypoint_cmd_params)
        
        self.handle_order(call_uri)
    
    def handle_cmd(self, values):
        inst = 'cmd'
        call_uri = self.get_call(inst)
        
        # Convert input parameter to list
        values = ast.literal_eval(values)
        
        # Set command parameters
        if len(values) > 1:
            cmd_params = MappingNode().set_function_par(call_uri, Prefix.do()['cmdInputParamList'])
            values = MappingNode().set_constant(PythonMapper.value_to_term(self.g, values[1:]))
            self.handle_mapping(values, cmd_params)
        
        self.handle_order(call_uri)
    
    def handle_run(self, value):
        inst = 'run'
        call_uri = self.get_call(inst)
        
        # Set run command
        cmd = MappingNode().set_constant(value)
        run_cmd = MappingNode().set_function_par(call_uri, Prefix.do()['runInputCommand'])
        self.handle_mapping(cmd, run_cmd)
        
        self.handle_order(call_uri)
        
        # Check if the run cmd can be written as an FnO Function
        fno_rep = CLIDescriptor(self.g, self.con_wd).describe(value)
        if fno_rep:
            fun_uri, comp_uri = fno_rep
            FnOBuilder.represents(self.g, comp_uri, call_uri)
            ProvBuilder.specialiazitionOf(self.g, call_uri, fun_uri)
    
    def handle_copy(self, value):
        inst = 'copy'
        call_uri = self.get_call(inst)
        
        # Split input string into components
        parts = value.split()
        if len(parts) != 2:
            return  # Ignore malformed COPY commands

        src, dest = parts

        # Set src parameter
        src_node = MappingNode().set_constant(src)
        src_input = MappingNode().set_function_par(call_uri, Prefix.do()['copySrc'])
        self.handle_mapping(src_node, src_input)

        # Set dest parameter
        dest_node = MappingNode().set_constant(dest)
        dest_input = MappingNode().set_function_par(call_uri, Prefix.do()['copyDest'])
        self.handle_mapping(dest_node, dest_input)
        
        # Describe all files inside the host src directory
        src_dir = src.replace('.', self.file_wd)
        fileDescriptor = FileDescriptor(self.g, src_dir)
        for file in self.iterate_files():
            fileDescriptor.describe(file)
        
        # Copy the implementations to the container dest directory
        dest_dir = dest.replace('.', self.con_wd)
        for uri in self.g.functions():
            # Get the original implementation **Just one imp expected**
            for mapping, imp in self.g.fun_to_imp(uri):
                # Copy the implementation
                imp_copy = move_file(self.g, mapping, imp, src_dir, dest_dir)
                if imp_copy:
                    ProvBuilder.alternateOf(self.g, imp_copy, uri)
        
        self.handle_order(call_uri)
    
    def iterate_files(self):
        for _, _, files in os.walk(self.file_wd):
            for file in files:
                if not self.ignore.match_file(file):
                    yield file
        
    def handle_workdir(self, value):
        inst = 'workdir'
        call_uri = self.get_call(inst)
        
        # Set src parameter
        dir = MappingNode().set_constant(value)
        dir_input = MappingNode().set_function_par(call_uri, Prefix.do()['workdirInput'])
        self.handle_mapping(dir, dir_input)
        
        self.handle_order(call_uri)
        
        self.con_wd = value