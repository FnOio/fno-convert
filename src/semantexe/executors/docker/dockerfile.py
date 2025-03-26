from rdflib import URIRef
from ...graph import ExecutableGraph
from ...prefix import Prefix
from ...builders import DockerBuilder, ProvBuilder, FnOBuilder
from ...mappers import DockerMapper
from ...util.file import move_file
from ...descriptors import FileDescriptor
from ..executeable import Function, AppliedFunction
from ..std import Executor

import os, subprocess, docker
from pathspec import PathSpec

def docker_build(dirpath, tag):
    
    # Prepare the docker build command
    build_command = ['docker', 'build', '-q', '--provenance=true', '--sbom=true', dirpath]
    
    if tag:
        build_command.extend(['-t', tag])

    try:
        # Run the docker build command and capture the output
        result = subprocess.run(
            build_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True
        )
        
        # return the image id
        return result.stdout
    
    except subprocess.CalledProcessError as e:
        print(f"Error during Docker build: {e.stderr}")
        raise

class DockerfileExecutor(Executor):
    
    def __init__(self, g: ExecutableGraph):
        super().__init__(g)
        
        self.handled = {
            Prefix.do().copy: self.execute_copy,
            Prefix.do().workdir: self.execute_workdir,
            Prefix.do().entrypoint: self.execute_entrypoint,
            Prefix.do().cmd: self.execute_cmd,
            Prefix.do().run: self.execute_run,
            Prefix.do().user: self.no_execution,
            Prefix.do().add: self.no_execution,
            Prefix.do().label: self.no_execution,
            Prefix.do().env: self.no_execution,
            Prefix.do().port: self.no_execution,
            Prefix.do().volume: self.no_execution,
            Prefix.do().maintainer: self.no_execution,
            Prefix.do()['from']: self.no_execution,
        }
    
    def accepts(self, mapping, imp):
        return self.g.is_dockerfile(imp)
    
    def map(self, fun: Function):
        # No mapping needed for Dockerfile
        pass

    def execute_function(self, fun: Function, *args, **kwargs):
        # Build the docker image
        self.build(fun)
        
        # Provide extra provenance by executing the composition
        # Make sure there is a valid composition
        if not fun.internal:
            fun.setInternal(True)
        if fun.internal:
            fun.comp.execute(self)
        
        return self.pg
    
    def build(self, fun: Function) -> ExecutableGraph:
        self.fun = fun
        self.fileDescriptor = FileDescriptor(self.pg)
        
        # Get the Dockerfile metadata
        tag = fun["tag"].get()
        filepath = self.g.get_file(fun.imp)
        self.dir = os.path.dirname(filepath)
        self.load_dockerignore()
        
        # Initiate metadata
        self.workdir = ''
        self.entrypoint_cmd = None
        self.entrypoint_params = []
        
        # Build the image
        docker_build(self.dir, tag)
        
        # Start docker client to inspect image
        client = docker.client.from_env()
        image = client.images.get(tag)
    
        # TODO Better image description
        # describe the image URI instance
        self.image_uri = DockerMapper.map_image(self.pg, image)
        fun.output.set(self.image_uri)
    
    def provenance(self, fun: Function, *args, **kwargs):
        _, exe_uri = super().provenance(fun, *args, **kwargs)
        
        ProvBuilder.derivedFrom(self.pg, self.image_uri, self.fun.imp)
        
        # Default execute provenance
        if self.entrypoint_cmd and self.entrypoint_cmd.startswith("python"):
            # Look for the correct python implementation
            # TODO Look for an implementation with a usable mapping
            try:
                # Now just take the first implementation
                file = os.path.join(self.workdir, self.entrypoint_params[0])
                imp_uri, map_uri, fun_uri = self.pg.imp_from_file(file)[0]
                # DockerBuilder.entrypoint(self.pg, self.image_uri, fun_uri, map_uri)
                ProvBuilder.alternateOf(self.pg, self.image_uri, imp_uri)
            except IndexError as e:
                print(f"[ERROR] No Python implementation found for {file}")
        
            # Map the image implementation
            FnOBuilder.map(self.pg, fun_uri, map_uri, self.image_uri)
            
            # TODO Copy mapping with new default values
            """if len(self.entrypoint_params) > 1:
                default_input = ' '.join(self.entrypoint_params[1:])
                DockerBuilder.defaultInput(self.pg, self.image_uri, default_input)"""
                
        return self.pg, exe_uri
    
    def no_execution(self, fun: Function, *args, **kwargs):
        pass
    
    def execute_run(self, fun: Function, *args, **kwargs):
        if fun.internal:
            fun.comp.execute(self)

    def execute_copy(self, fun: Function, *args, **kwargs):
        # Describe all files inside the src directory
        src_dir = fun[Prefix.do().copySrc].value.replace('.', self.dir)
        dest_dir = fun[Prefix.do().copyDest].value.replace('.', self.workdir)
        
        # recursively find all files in all subdirectories
        copied_uris = set()
        for file in self.iterate_files():
            try:
                self.fileDescriptor.describe_resource(file)
            except ValueError as e:
                pass
            
            for uri in [ uri for uri in self.pg.functions() if uri not in copied_uris]:
                copied_uris.add(uri)
                # Get the original implementation **Just one imp expected**
                for mapping, imp in self.pg.fun_to_imp(uri):
                    # Copy the implementation
                    imp_copy = move_file(self.pg, mapping, imp, src_dir, dest_dir)
                    if imp_copy:
                        # Provenance
                        ProvBuilder.alternateOf(self.pg, imp_copy, imp)
                        DockerBuilder.includes(self.pg, self.image_uri, imp_copy)

    def execute_workdir(self, fun: Function, *args, **kwargs):
        # Set workdir
        value = fun[Prefix.do().workdirInput].value
        self.workdir = '' if value == '.' else value
    
    def execute_entrypoint(self, fun: Function, *args, **kwargs):
        # self.entrypoint_cmd = fun[Prefix.do().entrypointInputCommand].get()
        # self.entrypoint_params = fun[Prefix.do().entrypointInputParamList].to_list()
        pass
    
    def execute_cmd(self, fun: Function, *args, **kwargs):
        value = fun[Prefix.do().cmdInputParamList].to_list()
        if self.entrypoint_cmd:
            self.entrypoint_params.extend(value)
        else:
            self.entrypoint_cmd = value[0]
            if len(value) > 1:
                self.entrypoint_params.extend(value[1:])
    
    def alt_executor(self, fun):
        # Use the python executor to capture provenance locally
        from ..python import PythonExecutor
        executor = PythonExecutor(self.g)
        
        pg, exe_uri = executor.provenance(fun, logger=self.logger)

        self.pg += pg
        fun.prov.informed.append(exe_uri)

    def load_dockerignore(self):
        patterns = ['Dockerfile', '.dockerignore']
        if os.path.exists('.dockerignore'):
            with open('.dockerignore', 'r') as file:
                patterns.extend(file.readlines())
            self.ignore = PathSpec.from_lines('gitwildmatch', patterns)
        else:
            self.ignore = None
        
    def iterate_files(self):
        for root, _, files in os.walk('.'):            
            for file in files:
                file_path = os.path.relpath(os.path.join(root, file), '.')
                if not self.ignore or not self.ignore.match_file(file_path):
                    yield file_path