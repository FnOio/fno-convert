from PyQt6.QtWidgets import (QWidget,  QHBoxLayout, QSplitter)
from PyQt6.QtCore import Qt
from ...graph import FnOGraph
from ...executors.store import Terminal
from .entity import ProvenanceTreeWidget
from .entity import InstanceWidget

class TerminalWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.setLayout(QHBoxLayout(self))
        self.layout().addWidget(self.splitter)

        self.instance_widget = None
        self.provenance_widget = None
        self.g = None

    def clear_content(self):
        # Remove all widgets from splitter
        while self.splitter.count():
            widget = self.splitter.widget(0)
            self.splitter.widget(0).setParent(None)
            widget.deleteLater()

        self.instance_widget = None
        self.provenance_widget = None

    def set_graph(self, g: FnOGraph):
        self.g = g

    def set_data(self, terminal: Terminal):
        self.clear_content()

        if not terminal.value_set:
            return

        value = terminal.value
        self.instance_widget = InstanceWidget(self.g, value)
        self.splitter.addWidget(self.instance_widget)

        if terminal.prov.instance and self.g:
            self.provenance_widget = ProvenanceTreeWidget(self.g, terminal.prov.instance)
            self.splitter.addWidget(self.provenance_widget)