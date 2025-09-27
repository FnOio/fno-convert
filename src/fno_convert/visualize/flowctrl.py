from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSizePolicy,
    QHeaderView,
    QTreeWidgetItem,
    QVBoxLayout,
    QLineEdit,
    QPushButton,
    QGridLayout,
    QComboBox,
    QMessageBox,
    QFileDialog,
)
from PyQt6.QtGui import QIntValidator, QDoubleValidator
from rdflib import URIRef
from pyqtgraph import TreeWidget
import os

from ..model.function import Function
from ..model.store import Terminal
from ..executors import (
    PythonExecutor,
    DockerfileExecutor,
    DockerImageExecutor,
    DockerContainerExecuter,
)
from ..util.prov import ProvLogger
from ..graph import FnOGraph
from .flowview import ExeViewWidget


class ExeCtrlWidget(QWidget):

    def __init__(self) -> None:
        QWidget.__init__(self)

        self.grid = QGridLayout(self)

        self.viewWidget = ExeViewWidget(self)
        self.inputWidget = InputWidget(self.viewWidget)
        self.functionList = FunctionList(self.viewWidget)

        self.grid.addWidget(self.inputWidget, 0, 0)
        self.grid.addWidget(self.viewWidget, 0, 1, 2, 1)
        self.grid.addWidget(self.functionList, 1, 0)

        self.grid.setRowStretch(0, 1)
        self.grid.setRowStretch(1, 2)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 3)

        # Make the widgets fill available space
        self.inputWidget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.viewWidget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self.executor = None

    def setFunction(self, g: FnOGraph, fun_uri):
        """if imp_uri:
        if g.is_python(imp_uri):
            self.inputWidget.executor.setCurrentText("python")
        if g.is_dockerfile(imp_uri):
            self.inputWidget.executor.setCurrentText("dockerfile")
        if g.is_dockerimage(imp_uri):
            self.inputWidget.executor.setCurrentText("dockerimage")
        if g.is_dockercontainer(imp_uri):
            self.inputWidget.executor.setCurrentText("dockercontainer")"""

        self.function = Function(g, fun_uri, g.get_mapping(fun_uri, first=True))

        self.viewWidget.setFunction(g, self.function)
        self.inputWidget.setFunction(g, self.function)
        self.functionList.setFunction(self.function)


class InputWidget(QWidget):

    # TODO Allow more executors
    # TODO Accept input

    def __init__(self, view: ExeViewWidget) -> None:
        QWidget.__init__(self)
        self.view = view
        self.items = {}

        self.inputList = TreeWidget()
        self.inputList.headerItem().setText(0, "Name")
        self.inputList.headerItem().setText(1, "Type")
        self.inputList.headerItem().setText(2, "Input")
        self.inputList.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )

        self.executors = {
            "python": PythonExecutor,
            "dockerfile": DockerfileExecutor,
            "dockerimage": DockerImageExecutor,
            "dockercontainer": DockerContainerExecuter,
        }
        self.executor = QComboBox(self)
        self.executor.addItems(self.executors.keys())

        execute = QPushButton("Execute", self)
        execute.clicked.connect(self.execute)

        self.save_btn = QPushButton("Save Provenance", self)
        self.save_btn.setEnabled(False)  # Initially disabled
        self.save_btn.clicked.connect(self.save_provenance)

        layout = QVBoxLayout()
        layout.addWidget(self.inputList)
        layout.addWidget(self.executor)
        layout.addWidget(execute)
        layout.addWidget(self.save_btn)
        self.setLayout(layout)

    def setFunction(self, g, function: Function):
        self.inputList.clear()
        self.function = function
        inputs = function.inputs()
        for inp in inputs:
            inp_type = getattr(inp.type, "__name__", str(inp.type))
            item = QTreeWidgetItem([inp.name, inp_type, ""])
            self.inputList.addTopLevelItem(item)
            convertItem = ConvertWidget(inp, item, self.inputList)
            self.inputList.setItemWidget(item, 2, convertItem)
            self.items[inp] = convertItem

    def execute(self):
        # Set the inputs
        for inp, item in self.items.items():
            inp.set(item.getInput())

        if self.executor is None:
            self.show_message(
                "Please load a turtle file first.", QMessageBox.Icon.Warning
            )
            return

        exe = self.executors[self.executor.currentText()](self.function.g)

        logger = ProvLogger()
        logger.start()
        pg, _ = exe.provenance(self.function, logger=logger)
        logger.stop()

        # set the provenance graph as new graph
        self.view.terminalWidget.set_graph(pg)
        self.view.functionWidget.set_graph(pg)

        self.prov_graph = pg
        self.save_btn.setEnabled(True)

    def save_provenance(self):
        if not self.prov_graph:
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Provenance File",
            "provenance.ttl",
            "Turtle Files (*.ttl);;All Files (*)",
        )
        if filename:
            try:
                self.prov_graph.serialize(destination=filename, format="turtle")
                self.show_message(
                    f"Provenance saved to:\n{filename}", QMessageBox.Icon.Information
                )
            except Exception as e:
                self.show_message(
                    f"Failed to save provenance:\n{str(e)}", QMessageBox.Icon.Critical
                )

    def show_message(self, message, icon):
        msg_box = QMessageBox()
        msg_box.setIcon(icon)
        msg_box.setText(message)
        msg_box.exec()


class ConvertWidget(QWidget):

    def __init__(
        self, inp: Terminal, item: QTreeWidgetItem, inputList: TreeWidget
    ) -> None:
        super().__init__()
        self.inp = inp
        self.item = item
        self.inputList = inputList
        self.input_fields = []

        layout = QVBoxLayout(self)

        if self.inp.param_mapping.index:
            button_layout = QHBoxLayout()

            add_button = QPushButton("+", self)
            add_button.clicked.connect(lambda: self.add_input_field(True))
            button_layout.addWidget(add_button)

            remove_button = QPushButton("-", self)
            remove_button.clicked.connect(self.remove_input_field)
            button_layout.addWidget(remove_button)

            layout.addLayout(button_layout)
        elif self.inp.param_mapping.keyvalue:
            button_layout = QHBoxLayout()

            add_button = QPushButton("+", self)
            add_button.clicked.connect(lambda: self.add_input_field(False))
            button_layout.addWidget(add_button)

            remove_button = QPushButton("-", self)
            remove_button.clicked.connect(self.remove_input_field)
            button_layout.addWidget(remove_button)

            layout.addLayout(button_layout)
        elif self.inp.type in [str, int, float]:
            self.input_field = QLineEdit(self)
            if self.inp.type == int:
                self.input_field.setValidator(QIntValidator())
            elif self.inp.type == float:
                self.input_field.setValidator(QDoubleValidator())

            layout.addWidget(self.input_field)

        self.setLayout(layout)

    def add_input_field(self, index_mapping):
        new_input_field = QLineEdit(self)
        self.input_fields.append(new_input_field)
        index = self.item.childCount()

        if index_mapping:
            self.item.addChild(QTreeWidgetItem([str(index), "", ""]))
        else:
            self.item.addChild(QTreeWidgetItem(["", "", ""]))
            new_input_field.key = QLineEdit(self)
            self.inputList.setItemWidget(self.item.child(index), 0, new_input_field.key)

        self.inputList.setItemWidget(self.item.child(index), 2, new_input_field)

    def remove_input_field(self):
        if len(self.input_fields) > 0:
            last_input_field = self.item.child(len(self.input_fields) - 1)
            self.item.removeChild(last_input_field)
            self.input_fields.pop()

    def getInput(self):
        if self.inp.type == int:
            return int(self.input_field.text())
        elif self.inp.type == float:
            return float(self.input_field.text())
        elif self.inp.param_mapping.index:
            input = []
            for input_field in self.input_fields:
                input.append(input_field.text())
            return input
        elif self.inp.param_mapping.keyvalue:
            input = {}
            for input_field in self.input_fields:
                input[input_field.key.text()] = input_field.text()
            return input

        return self.input_field.text()


class FunctionList(QWidget):

    def __init__(self, view) -> None:
        super().__init__()
        self.view = view

        self.list = TreeWidget(self)
        self.list.setColumnCount(2)
        self.list.setHeaderLabels(["Functions", ""])
        self.list.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.list.setUniformRowHeights(True)

        layout = QVBoxLayout()
        layout.addWidget(self.list)
        self.setLayout(layout)

    def setFunction(self, function: Function):
        self.function = function
        self.makeList()

    def makeList(self):
        self.list.clear()
        self.add_function_item(self.function)

    def add_function_item(self, fun: Function, parent=None):
        item = QTreeWidgetItem([fun.name, ""])

        if parent:
            parent.addChild(item)
        else:
            self.list.addTopLevelItem(item)

        if fun.comp_uri:
            if fun.internal:
                toggleBtn = QPushButton("Hide")
                if fun.comp:
                    for call in fun.comp.functions.values():
                        self.add_function_item(call, item)
                elif fun.branches:
                    for branch in fun.branches.values():
                        for call in branch.functions.values():
                            call.append(call)
                            self.add_function_item(call, item)
            else:
                toggleBtn = QPushButton("Expand")

            toggleBtn.setFixedWidth(50)
            toggleBtn.fun = fun
            toggleBtn.item = item
            toggleBtn.clicked.connect(self.toggleChildren)
            self.list.setItemWidget(item, 1, toggleBtn)

    def toggleChildren(self):
        btn = QObject.sender(self)

        if btn.text() == "Expand":
            btn.fun.setInternal(True)
            if btn.fun.comp:
                for call in btn.fun.comp.functions.values():
                    self.add_function_item(call, btn.item)
            elif btn.fun.branches:
                for branch in btn.fun.branches.values():
                    for call in branch.functions.values():
                        self.add_function_item(call, btn.item)
            btn.item.setExpanded(True)
            btn.setText("Hide")
        else:
            btn.fun.setInternal(False)
            btn.item.takeChildren()
            btn.setText("Expand")

        self.view.draw()
