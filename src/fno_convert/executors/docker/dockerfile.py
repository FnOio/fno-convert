from rdflib import URIRef
from ...graph import FnOGraph
from ...prefix import Prefix
from ...builders import DockerBuilder, ProvBuilder, FnOBuilder
from ...mappers import DockerMapper, PythonMapper
from ...util.file import move_file
from ...util.mapping import Mapping, MappingNode
from ...descriptors import FileDescriptor, CLIDescriptor
from ...model.function import Function
from ..std import Executer

import os, subprocess, docker
from pathspec import PathSpec

def build_image_clean(dirpath, tag):
    """
    Build a Docker image from a directory, tag it, and clean up dangling images.
    
    Args:
        dirpath (str): Path to the Docker build context (e.g., directory with Dockerfile)
        tag (str): Image tag to use (e.g., 'myimage:latest')
    
    Returns:
        str: ID of the built Docker image
    """
    client = docker.from_env()

    try:
        # Build the image with specified tag
        print(f"Building image with tag: {tag}")
        image, logs = client.images.build(path=dirpath, tag=tag, rm=True)

        # Print build logs (optional)
        for chunk in logs:
            if 'stream' in chunk:
                print(chunk['stream'], end='')

        # Remove dangling images (intermediate, untagged ones)
        print("\nCleaning up dangling images...")
        dangling_images = client.images.list(filters={"dangling": True})
        for img in dangling_images:
            try:
                client.images.remove(img.id, force=True)
                print(f"Removed dangling image: {img.short_id}")
            except Exception as e:
                print(f"Failed to remove image {img.id}: {e}")

        return image

    except docker.errors.BuildError as e:
        print("Build failed:", e)
        for line in e.build_log:
            print(line.get('stream', ''), end='')
        raise
    except docker.errors.APIError as e:
        print("Docker API error:", e)
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
        self.workdir = ''
        
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
        # Get the Dockerfile metadata
        self.tag = fun["tag"].get()
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
        # image, _ = client.images.build(path=self.dir, tag=tag, rm=True)
        image = build_image_clean(self.dir, self.tag)
    
        # describe the image
        self.imp_uri, self.image_tag = DockerMapper.map_image(self.pg, image)
        fun.output.set(self.imp_uri)
        
        # create function uri
        self.fun_uri = Prefix.base()[f"{self.image_tag}DockerImage"]
    
    def provenance(self, fun: Function, *args, **kwargs):
        _, exe_uri = super().provenance(fun, *args, **kwargs)
        
        # Image was derived from Dockerfile
        ProvBuilder.derivedFrom(self.pg, self.imp_uri, fun.imp)
        
        cmdstr = self.entrypoint_cmd + ' ' + ' '.join(self.entrypoint_params)
        fno_rep = CLIDescriptor(self.pg, self.workdir).describe(cmdstr)
        
        if fno_rep:
            fun_uri, comp_uri = fno_rep
            FnOBuilder.represents(self.pg, comp_uri, self.fun_uri)
        
            # Create a new function based on the entrypoint cmd
            # Copy the unmapped parameters
            param_uris = {}
            params = self.pg.get_parameters(fun_uri, include_self=True)
            for i, param in enumerate(params):
                uri = Prefix.base()[f'{self.image_tag}Parameter{i}']
                FnOBuilder.describe_parameter(self.pg, uri, 
                                                Prefix.ns('xsd').string, 
                                                self.pg.get_predicate(param))
                param_uris[param] = (uri)
                
                mapping = Mapping(MappingNode().set_function_out(self.fun_uri, uri), MappingNode().set_function_out(fun_uri, param))
                FnOBuilder.add_mapping(self.pg, comp_uri, mapping)
            
            # Copy the outputs and map them accordingly
            output_uris = []
            output = self.pg.get_output(fun_uri)
            uri = Prefix.base()[f'{self.image_tag}Output']
            FnOBuilder.describe_output(self.pg, uri, self.pg.get_output_type(output), self.pg.get_predicate(output))
            output_uris.append(uri)
            
            mapping = Mapping(MappingNode().set_function_out(fun_uri, output), MappingNode().set_function_out(self.fun_uri, uri))
            FnOBuilder.add_mapping(self.pg, comp_uri, mapping)
            
            if self.pg.has_self_output(fun_uri):
                output = self.pg.get_self_output(fun_uri)
                uri = Prefix.base()[f'{self.image_tag}SelfOutput']
                FnOBuilder.describe_output(self.pg, uri, self.pg.get_output_type(output), self.pg.get_predicate(output))
                output_uris.append(uri)
                
                mapping = Mapping(MappingNode().set_function_out(fun_uri, output), MappingNode().set_function_out(self.fun_uri, uri))
                FnOBuilder.add_mapping(self.pg, comp_uri, mapping)
            
            # Create FnO Function
            FnOBuilder.describe_function(self.pg, self.fun_uri, self.tag, param_uris.values(), output_uris)
            
            # Copy the mapping 
            # TODO with new default values based on cmd
            for map_uri in self.pg.get_mapping(fun_uri):
                positional = []
                keywords = []
                lists = set()
                dicts = set()
                
                for param in params:
                    index = self.pg.parameter_position(map_uri, param)
                    if index is not None:
                        positional.append((index, param_uris[param]))
                    
                    key = self.pg.parameter_keyword(map_uri, param)
                    if key:
                        keywords.append((param_uris[param], key))
                    
                    if self.pg.is_list_mapping(map_uri, param):
                        lists.add(param_uris[param])
                    
                    if self.pg.is_keyvalue_mapping(map_uri, param):
                        dicts.add(param_uris[param])
                
                positional = [ param[1] for param in sorted(positional, key=lambda x: x[0]) ]
                        
                FnOBuilder.describe_mapping(self.pg, self.fun_uri, self.imp_uri, "docker run", 
                                            output_uris[0], positional, keywords, lists, dicts,
                                            self_output=output_uris[1] if len(output_uris) > 1 else None)
            
            # Docker image is a specialization of its entrypoint
            for _, imp_uri in self.pg.fun_to_imp(fun_uri):
                ProvBuilder.specialiazitionOf(self.pg, self.imp_uri, imp_uri)
        
        """if self.entrypoint_cmd and self.entrypoint_cmd.startswith("python"):
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
                    
                FnOBuilder.describe_function(self.pg, self.fun_uri, self.image_tag, parameters=inputs)
                map_uri = FnOBuilder.describe_mapping(self.pg, self.fun_uri, self.imp_uri,
                                            f_name=f"docker run {self.image_tag}",
                                            positional=positional, keyword=keywords,
                                            args=varpos, kargs=varkey)
                comp_uri = URIRef(f"{self.fun_uri}Composition")
                FnOBuilder.describe_composition(self.pg, comp_uri, mappings, represents=self.fun_uri)
                FnOBuilder.start(self.pg, comp_uri, rep.fun_uri)
                
            except IndexError as e:
                print(f"[ERROR] No Python implementation found for {file}")"""
                
        return self.pg, exe_uri
    
    def no_execution(self, fun: Function, *args, **kwargs):
        pass
    
    def execute_run(self, fun: Function, *args, **kwargs):
        if fun.internal:
            fun.comp.execute(self)

    def execute_copy(self, fun: Function, *args, **kwargs):
        # Describe all files inside the src directory
        pass

    def execute_workdir(self, fun: Function, *args, **kwargs):
        # Set workdir
        value = fun[Prefix.do().workdirInput].value
        self.workdir = '' if value == '.' else value
    
    def execute_entrypoint(self, fun: Function, *args, **kwargs):
        self.entrypoint_cmd = fun[Prefix.do().entrypointInputCommand].get()
        self.entrypoint_params = fun[Prefix.do().entrypointInputParamList].to_list()
    
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