from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QScrollArea, QTextEdit, QVBoxLayout, QPushButton, 
                             QFileDialog, QMessageBox, QComboBox, QLineEdit, QSizePolicy,
                             QLabel, QFrame)
from PyQt6.QtGui import QTextCursor, QColor, QTextCharFormat
from ..mappers import PythonMapper
from ..graph import FnOGraph
from ..descriptors import FileDescriptor
from rdflib import URIRef

import os, sys, inspect, time

class Descriptor(QWidget):

    file_loaded = pyqtSignal(str)
    resource_described = pyqtSignal(FnOGraph, URIRef)

    def __init__(self) -> None:
        super().__init__()

        self.layout = QVBoxLayout(self)

        self.file_button = QPushButton("Select File")
        self.file_button.clicked.connect(self.select_file)
        self.layout.addWidget(self.file_button)

        self.layout.addWidget(self._horizontal_line())

        self.triplet_label = QLabel("Select Function Triplet")
        self.layout.addWidget(self.triplet_label)

        self.triplet_select = QComboBox()
        self.layout.addWidget(self.triplet_select)

        self.layout.addWidget(self._horizontal_line())

        self.select_button = QPushButton("Select Function")
        self.select_button.clicked.connect(self.select_function)
        self.layout.addWidget(self.select_button)

        self.layout.addStretch()

        self.file_path = None
        self.graph = None
        self.triplets = []  # Stores (function_uri, mapping_uri, implementation_uri)

    def _horizontal_line(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        return line

    def select_file(self):
        self.file_path, _ = QFileDialog.getOpenFileName(
            self, "Select File", "", "Python Files (*.py);;Dockerfile;;Turtle Files (*.ttl)"
        )

        if not self.file_path:
            return
        
        with open(self.file_path, "r") as file:
            self.file_loaded.emit(file.read())

        self.graph = FnOGraph()
        self.triplet_select.clear()
        self.triplets.clear()

        if self.file_path.endswith(".ttl"):
            self.graph.parse(self.file_path)

        else:
            cwd = os.getcwd()
            fno_rep = FileDescriptor(self.graph, cwd).describe(self.file_path)
            if not fno_rep:
                self.show_message("No functions found in the file.", QMessageBox.Warning)
                return

        # Aggregate all function-mapping-implementation triplets
        for fun_uri in self.graph.functions():
            fun_name = self.graph.label(fun_uri)
            self.triplet_select.addItem(fun_name, fun_uri)
            
        """for fun_uri in self.graph.functions():
            for map_uri, imp_uri in self.graph.fun_to_imp(fun_uri):
                self.triplets.append((fun_uri, map_uri, imp_uri))

        for fun_uri, map_uri, imp_uri in self.triplets:
            fun_name = self.graph.label(fun_uri)
            map_name = self.graph.method_name(map_uri)
            imp_name = self.graph.label(imp_uri)

            parts = [f"Function: {fun_name}"]
            if map_name:
                parts.append(f"Mapping: {map_name}")
            if imp_name:
                parts.append(f"Implementation: {imp_name}")

            label = " | ".join(parts)
            self.triplet_select.addItem(label, (fun_uri, map_uri, imp_uri))"""

    def select_function(self):
        if not self.file_path:
            self.show_message("Please select a file first.", QMessageBox.Icon.Warning)
            return

        if not self.graph or not self.triplet_select.currentData():
            self.show_message("Please select a valid function triplet.", QMessageBox.Icon.Warning)
            return

        fun_uri = self.triplet_select.currentData()
        self.resource_described.emit(self.graph, fun_uri)

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

    def setGraph(self, g: FnOGraph):
        self.text.setPlainText(g.serialize(format='turtle'))
    
    def setSource(self, g: FnOGraph, fun_uri: URIRef):
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