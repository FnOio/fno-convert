from rdflib import URIRef
from ...graph import FnOGraph
from ...prefix import Prefix
from ...builders import DockerBuilder, ProvBuilder, FnOBuilder
from ...mappers import DockerMapper, PythonMapper
from ...util.file import move_file
from ...util.mapping import Mapping, MappingNode
from ...descriptors import FileDescriptor
from ..executeable import Function
from ..std import Executer

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

class DockerfileExecutor(Executer):
    
    def __init__(self, g: FnOGraph):
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
        
    def uri(self):
        return Prefix.ns('fnoi').DockerfileExecutor    
    
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
    
    def build(self, fun: Function) -> FnOGraph:
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
        
        # Start docker client
        client = docker.client.from_env()
        
        # Build the image
        # docker_build(self.dir, tag)
        image, _ = client.images.build(path=self.dir, tag=tag, rm=True)
    
        # describe the image
        self.imp_uri, image_tag = DockerMapper.map_image(self.pg, image)
        fun.output.set(self.imp_uri)
        
        # create function uri
        self.fun_uri = Prefix.base()[f"{image_tag}{image.short_id.removeprefix('sha256:')}"]
        self.image_name = tag
    
    def provenance(self, fun: Function, *args, **kwargs):
        _, exe_uri = super().provenance(fun, *args, **kwargs)
        
        # Image was derived from Dockerfile
        ProvBuilder.derivedFrom(self.pg, self.imp_uri, fun.imp)
        
        # TODO implement command descriptor
        if self.entrypoint_cmd and self.entrypoint_cmd.startswith("python"):
            # Look for the correct python implementation
            try:
                # Now just take the first implementation
                file = os.path.join(self.workdir, self.entrypoint_params[0])
                
                imps = self.pg.imp_from_file(file)
                for imp_uri, map_uri, fun_uri in imps:
                    ProvBuilder.specialiazitionOf(self.pg, self.imp_uri, imp_uri)
            
                # Now just take the first implementation
                imp_uri, map_uri, fun_uri = imps[0]
                
                # Describe the image function
                rep = Function(self.pg, fun_uri, map_uri, imp_uri)
                
                
                mappings = []
                
                inputs = []
                positional = []
                keywords = {}
                varpos = set()
                varkey = set()
                
                rep_positional = rep.positional()
                for i, term in enumerate(rep_positional):
                    param_uri = URIRef(f"{self.fun_uri}Parameter{i}")
                    FnOBuilder.describe_parameter(self.pg, param_uri, 
                                                    PythonMapper.obj_to_fno(self.pg, term.type), 
                                                    term.pred)
                    positional.append(param_uri)
                    inputs.append(param_uri)
                    if term.param_mapping.index:
                        varpos.add(param_uri)
                    
                    mapfrom = MappingNode().set_function_par(self.fun_uri, param_uri)
                    mapto = MappingNode().set_function_par(rep.fun_uri, term.uri)
                    mappings.append(Mapping(mapfrom, mapto))
                
                rep_keywords = rep.keyword()
                for key, term in rep_keywords.items():
                    param_uri = URIRef(f"{self.fun_uri}Parameter{key}")
                    FnOBuilder.describe_parameter(self.pg, param_uri, 
                                                    PythonMapper.obj_to_fno(self.pg, term.type), 
                                                    term.pred)
                    keywords[key] = param_uri
                    inputs.append(param_uri)
                    
                    mapfrom = MappingNode().set_function_par(self.fun_uri, param_uri)
                    mapto = MappingNode().set_function_par(rep.fun_uri, term.uri)
                    mappings.append(Mapping(mapfrom, mapto))
                
                rep_varpos = rep.varpositional()
                if rep_varpos:
                    param_uri = URIRef(f"{self.fun_uri}Args")
                    FnOBuilder.describe_parameter(self.pg, param_uri, 
                                                    PythonMapper.obj_to_fno(self.pg, rep_varpos.type), 
                                                    rep_varpos.pred)
                    varpos.add(param_uri)
                    inputs.append(param_uri)
                    
                    mapfrom = MappingNode().set_function_par(self.fun_uri, param_uri)
                    mapto = MappingNode().set_function_par(rep.fun_uri, rep_varpos.uri)
                    mappings.append(Mapping(mapfrom, mapto))
                
                rep_varkey = rep.varkeyword()
                if rep_varkey:
                    param_uri = URIRef(f"{self.fun_uri}Kargs")
                    FnOBuilder.describe_parameter(self.pg, param_uri, 
                                                    PythonMapper.obj_to_fno(self.pg, rep_varkey.type), 
                                                    rep_varkey.pred)
                    varkey.add(param_uri)
                    inputs.append(param_uri)
                    
                    mapfrom = MappingNode().set_function_par(fun_uri, param_uri)
                    mapto = MappingNode().set_function_par(rep.fun_uri, rep_varkey.uri)
                    mappings.append(Mapping(mapfrom, mapto))
                    
                FnOBuilder.describe_function(self.pg, self.fun_uri, self.image_name, parameters=inputs)
                map_uri = FnOBuilder.describe_mapping(self.pg, self.fun_uri, self.imp_uri,
                                            f_name=f"docker run {self.image_name}",
                                            positional=positional, keyword=keywords,
                                            args=varpos, kargs=varkey)
                comp_uri = URIRef(f"{self.fun_uri}Composition")
                FnOBuilder.describe_composition(self.pg, comp_uri, mappings, represents=self.fun_uri)
                FnOBuilder.start(self.pg, comp_uri, rep.fun_uri)
                
            except IndexError as e:
                print(f"[ERROR] No Python implementation found for {file}")
                
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
                self.fileDescriptor.describe_resource(os.path.join(os.getcwd(), file))
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
                        fun.prov.generated.append(imp_copy)
                        ProvBuilder.alternateOf(self.pg, imp_copy, imp)
                        DockerBuilder.includes(self.pg, self.imp_uri, imp_copy)

    def execute_workdir(self, fun: Function, *args, **kwargs):
        # Set workdir
        value = fun[Prefix.do().workdirInput].value
        self.workdir = '' if value == '.' else value
    
    def execute_entrypoint(self, fun: Function, *args, **kwargs):
        self.entrypoint_cmd = fun[Prefix.do().entrypointInputCommand].get()
        self.entrypoint_params = fun[Prefix.do().entrypointInputParamList].to_list()
        self.entrypoint_params = [word for string in self.entrypoint_params for word in string.split(' ')]
    
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
        executor = PythonExecutor(self.pg)
        
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
    
    """if len(self.entrypoint_params) > 1:
                    i = 1
                    while i < len(self.entrypoint_params):
                        param = self.entrypoint_params[i]
                        if param.startswith('-'):
                            key = param.lstrip('-')
                            if key in rep_keywords:
                                terminal = rep_keywords[key]
                                if terminal.param_mapping.index:
                                    k = i
                                    while k < len(self.entrypoint_params) and not self.entrypoint_params[k+1].startwith('-'):
                                        value = self.entrypoint_params[k+1]
                                        mapfrom = MappingNode().set_constant(self.entrypoint_params[k])
                                        mapto = MappingNode().set_function_par(rep.fun_uri, terminal.uri).set_strategy('toList', k-i-1)
                                        mappings.append(Mapping(mapfrom, mapto))
                                        k += 1
                                    i = k
                                else:
                                    mapfrom = MappingNode().set_constant(self.entrypoint_params[i+1])
                                    mapto = MappingNode().set_function_par(rep.fun_uri, terminal.uri)
                                    mappings.append(Mapping(mapfrom, mapto))
                                    i += 1
                                
                                # Container function does not need this parameter
                                del keywords[key]
                            else:
                                # TODO variable keyword
                                pass
                        else:
                            try:
                                terminal = next(positional)
                                if terminal.param_mapping.index:
                                    k = i+1
                                    value = self.entrypoint_params[k]
                                    while k < len(self.entrypoint_params) and not value.startwith('-'):
                                        mapfrom = MappingNode().set_constant(self.entrypoint_params[k])
                                        mapto = MappingNode().set_function_par(rep.fun_uri, terminal.uri).set_strategy('toList', k-i-1)
                                        mappings.append(Mapping(mapfrom, mapto))
                                        k += 1
                                    i = k
                                else:
                                    mapfrom = MappingNode().set_constant(self.entrypoint_params[i+1])
                                    mapto = MappingNode().set_function_par(rep.fun_uri, terminal.uri)
                                    mappings.append(Mapping(mapfrom, mapto))
                                    i += 1
                            except StopIteration as e:
                                k = i+1
                                value = self.entrypoint_params[k]
                                while k < len(self.entrypoint_params) and not value.startwith('-'):
                                    mapfrom = MappingNode().set_constant(self.entrypoint_params[k])
                                    mapto = MappingNode().set_function_par(rep.fun_uri, rep_varpos.uri).set_strategy('toList', k-i-1)
                                    mappings.append(Mapping(mapfrom, mapto))
                                    k += 1
                                i = k
                        i += 1"""