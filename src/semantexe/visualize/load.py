from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QScrollArea, QTextEdit, QVBoxLayout, QPushButton, 
                             QFileDialog, QMessageBox, QComboBox, QLineEdit, QSizePolicy)
from PyQt6.QtGui import QTextCursor, QColor, QTextCharFormat
from ..mappers import PythonMapper
from ..graph import ExecutableGraph
from ..util.python.ast import ASTUtil
from ..descriptors import PythonDescriptor, DockerfileDescriptor
from rdflib import URIRef

import os, sys, ast, inspect, time

class Descripter(QWidget):

    file_loaded = pyqtSignal(str) # signal that a file is loaded
    resource_described = pyqtSignal(ExecutableGraph, URIRef, list, URIRef, str) # signal that a resource has been described
    # function_loaded = pyqtSignal(ExecutableGraph, URIRef, list, URIRef) # signal that a new function is loaded
    
    def __init__(self) -> None:
        super().__init__()

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.file_button = QPushButton("Select File")
        self.file_button.clicked.connect(self.select_file)
        self.layout.addWidget(self.file_button)

        self.function_select = QComboBox()
        self.layout.addWidget(self.function_select)

        self.load_button = QPushButton("Load Function")
        self.load_button.clicked.connect(self.load_function)
        self.layout.addWidget(self.load_button)

        self.layout.addStretch()

        self.file_path = None

    # TODO Allow turtle files
    def select_file(self):
        self.file_path, _ = QFileDialog.getOpenFileName(self, "Select File", "", "Python Files (*.py);;Dockerfile;;Turtle Files (*.ttl)")
        if self.file_path:
            file_dir = os.path.dirname(self.file_path)
            sys.path.append(file_dir)  # Add the file directory to the Python path
            
            if self.file_path.endswith(".py"):
                with open(self.file_path, "r") as file:
                    source = file.read()
                    self.file_loaded.emit(source)
                    """tree = ast.parse(source)

                used_functions = ASTUtil(tree).used_functions()
                self.function_select.clear()
                self.function_select.addItems(used_functions)"""
                
                g = ExecutableGraph()
                fun_uri, map_uris, imp_uri = PythonDescriptor(g).describe_file(self.file_path)
                self.resource_described.emit(g, fun_uri, map_uris, imp_uri, "python")
            
            if self.file_path.endswith("Dockerfile"):
                with open(self.file_path, "r") as file:
                    source = file.read()
                    self.file_loaded.emit(source)
                g = ExecutableGraph()
                fun_uri, map_uris, imp_uri = DockerfileDescriptor(g).describe_file(self.file_path)
                self.resource_described.emit(g, fun_uri, map_uris, imp_uri, "dockerfile")

    def load_function(self):
        function_name = self.function_select.currentText()

        if not self.file_path:
            self.show_message("Please select a file first.", QMessageBox.Icon.Warning)
            return
        
        if not function_name:
            self.show_message("Please select a pipeline first.", QMessageBox.Icon.Warning)
            return

        try:
            file_dir = os.path.dirname(self.file_path)
            sys.path.append(file_dir)  # Add the file directory to the Python path

            with open(self.file_path, "r") as file:
                code = compile(file.read(), self.file_path, 'exec')
            exec(code)
            selected_function = locals().get(function_name)
            if selected_function and callable(selected_function):
                start = time.time()
                graph = ExecutableGraph()
                uri = PythonDescriptor(graph).describe_resource(selected_function)
                stop = time.time()
                print(f"gen time: {(stop-start)*1000}")
                print(f"num of triples: {len(graph)}")
                self.function_loaded.emit(graph, uri)
            else:
                self.show_message(f"Function '{function_name}' not found or not callable.", QMessageBox.Icon.Warning)
        except Exception as e:
            self.show_message(f"Error loading function: {e}", QMessageBox.Icon.Critical)
        finally:
            sys.path.remove(file_dir)  # Remove the file directory from the Python path after execution
    
    def show_message(self, message, icon):
        msg_box = QMessageBox()
        msg_box.setIcon(icon)
        msg_box.setText(message)
        msg_box.exec()

class ScrollWidget(QWidget):

    def __init__(self):
        super().__init__()

        # Main layout
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # Create search bar, buttons for navigation, and search button
        self.search_line = QLineEdit()
        self.prev_button = QPushButton("<")
        self.prev_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.next_button = QPushButton(">")
        self.next_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.search_button = QPushButton("Search")

        # Connect button signals to slots
        self.prev_button.clicked.connect(self.move_to_previous_result)
        self.next_button.clicked.connect(self.move_to_next_result)
        self.search_button.clicked.connect(self.search_text)

        # Adding search components to layout
        search_layout = QHBoxLayout()
        search_layout.addWidget(self.search_line)
        search_layout.addWidget(self.search_button)
        search_layout.addWidget(self.prev_button)
        search_layout.addWidget(self.next_button)
        main_layout.addLayout(search_layout)

        # Create a scrollable text area
        self.text_area = QScrollArea()
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text_area.setWidgetResizable(True)
        self.text_area.setWidget(self.text)
        main_layout.addWidget(self.text_area)

        self.search_results = []
        self.current_result_index = -1
    
    def setText(self, text: str):
        self.text.setPlainText(text)

    def setGraph(self, g: ExecutableGraph):
        self.text.setPlainText(g.serialize(format='turtle'))
    
    def setSource(self, g: ExecutableGraph, fun_uri: URIRef):
        # TODO What if there are multiple imps?
        _, imp_uri = g.fun_to_imp(fun_uri)[0]
        if imp_uri is not None:
            # TODO DockerMapper
            obj = PythonMapper.fno_to_obj(g, imp_uri)
            text = inspect.getsource(obj)
            self.text.setPlainText(text)

    def search_text(self):
        # Clear existing formatting and search results
        cursor = self.text.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.setCharFormat(QTextCharFormat())
        cursor.clearSelection()
        self.search_results.clear()
        self.current_result_index = -1

        # Get the search term
        search_term = self.search_line.text()
        if not search_term:
            return

        # Setup the format for matches
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("yellow"))

        # Search and highlight
        pos = 0
        while True:
            index = self.text.toPlainText().find(search_term, pos)
            if index == -1:
                break
            cursor.setPosition(index)
            cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, len(search_term))
            cursor.setCharFormat(fmt)
            pos = index + len(search_term)

            # Store the match position for navigation
            self.search_results.append(index)

        if self.search_results:
            self.current_result_index = 0
            self.show_current_search_result()

    def show_current_search_result(self):
        if 0 <= self.current_result_index < len(self.search_results):
            cursor = self.text.textCursor()
            cursor.setPosition(self.search_results[self.current_result_index])
            self.text.setTextCursor(cursor)
            self.text.ensureCursorVisible()

    def move_to_next_result(self):
        if self.search_results:
            self.current_result_index = (self.current_result_index + 1) % len(self.search_results)
            self.show_current_search_result()

    def move_to_previous_result(self):
        if self.search_results:
            self.current_result_index = (self.current_result_index - 1) % len(self.search_results)
            self.show_current_search_result()