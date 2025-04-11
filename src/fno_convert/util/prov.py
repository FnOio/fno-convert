from datetime import datetime
from collections import deque
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import sys, time

class ProvLogger:
    
    def __init__(self):
        self.scope = deque()
        
        self.loggers = {
            "msg": MessageLogger(), 
            "file": FileLogger(),
        }
        
        self.observer = Observer()
        self.observer.schedule(self.loggers["file"], ".", recursive=True)
    
    def start(self):
        self.observer.start()
    
    def stop(self):
        self.observer.stop()
        self.observer.join()
        self.loggers["msg"].stop()
    
    def append(self, fun):
        self.scope.append(fun)
        
        for logger in self.loggers.values():
            logger.set_fun(fun)
    
    def pop(self):
        fun = self.scope.pop()
        
        for logger in self.loggers.values():
            logger.set_fun(fun)

class MessageLogger:
  
    def __init__(self):
        self.stdout = ConsoleStreamHandler(sys.stdout)
        self.stderr = ConsoleStreamHandler(sys.stderr)
        
        sys.stdout = self.stdout
        sys.stderr = self.stderr
        
        self.scope = deque()
    
    def set_fun(self, fun):
        self.stdout.fun = fun
        self.stderr.fun = fun
        
    def stop(self):
        sys.stdout = self.stdout.original_handler
        sys.stderr = self.stderr.original_handler

class ConsoleStreamHandler:
  
    def __init__(self, orignal_handler, fun = None):
        self.fun = fun
        self.original_handler = orignal_handler

    def write(self, message):
        if self.fun and message != '\n':  # Avoid capturing empty new lines
            self.fun.prov.msgs.append((message, datetime.now()))
        self.original_handler.write(message)

    def flush(self):
        self.original_handler.flush()

class FileLogger(FileSystemEventHandler):
    
    def __init__(self):
        super().__init__()
        self.debounce_time = 0.5
        self.last_event_time = 0
        self.last_event_path = None

        self.scope = deque()
        self.fun = None
    
    def set_fun(self, fun):
        self.fun = fun
    
    def on_modified(self, event):
        current_time = time.time()
        if not event.is_directory and \
            ((current_time - self.last_event_time) > self.debounce_time or \
            event.src_path != self.last_event_path):
                
            self.fun.prov.files_modified.append((event.src_path, datetime.now()))
            self.last_event_time = current_time
            self.last_event_path = event.src_path
    
    def on_created(self, event):
        current_time = time.time()
        if not event.is_directory and \
            ((current_time - self.last_event_time) > self.debounce_time or \
            event.src_path != self.last_event_path):
        
            self.fun.prov.files_created.append((event.src_path, datetime.now()))
            self.last_event_time = current_time
            self.last_event_path = event.src_path