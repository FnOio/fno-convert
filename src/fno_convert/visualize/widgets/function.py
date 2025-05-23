from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QSizePolicy, QSplitter
)
from PyQt6.QtCore import pyqtSignal, Qt
from ...prefix import Prefix
from ...graph import FnOGraph
from ...model.function import Function, AppliedFunction
from .entity import ImplementationWidget, ExecutionWidget

class ImplementationListWidget(QTreeWidget):
    implementationSelected = pyqtSignal(object)  # URI of selected implementation

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["Implementations"])
        self.itemExpanded.connect(self.on_item_expanded)
        self.itemSelectionChanged.connect(self.on_selection_changed)
        self.function = None
        self.g = None

    def set_graph(self, g: FnOGraph):
        self.g = g

    def set_function(self, function: Function):
        self.clear()
        self.function = function

        for _, imp in self.g.fun_to_imp(function.fun_uri):
            item = QTreeWidgetItem([Prefix.uri_to_str(imp)])
            item.setData(0, 1, imp)
            item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
            self.addTopLevelItem(item)

        # Update selection if needed
        if function.imp:
            self.select_implementation(function.imp)

    def select_implementation(self, imp):
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if item.data(0, 1) == imp:
                self.setCurrentItem(item)
                self.scrollToItem(item)
                break

    def on_item_expanded(self, item):
        if item.childCount() > 0:
            return

        imp = item.data(0, 1)
        container = QWidget()
        container.setLayout(QVBoxLayout(container))
        container.setContentsMargins(0, 0, 0, 0)

        imp_widget = ImplementationWidget(self.g, imp)
        container.layout().addWidget(imp_widget)

        child_item = QTreeWidgetItem()
        item.addChild(child_item)
        self.setItemWidget(child_item, 0, container)

    def on_selection_changed(self):
        item = self.currentItem()
        if item:
            self.implementationSelected.emit(item.data(0, 1))

class ExecutionListWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Executions"])
        
        # Ensure the internal tree expands
        self.tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout()
        layout.addWidget(self.tree)
        self.setLayout(layout)

        self.g = None
        self.function = None

        self.tree.itemExpanded.connect(self.on_item_expanded)

    def set_graph(self, g: FnOGraph):
        self.g = g

    def set_function(self, function: AppliedFunction | Function):
        self.function = function
        self.tree.clear()

        if isinstance(function, AppliedFunction):
            executions = self.g.get_executions(function.call_uri)
        else:
            executions = self.g.get_executions(function.fun_uri)

        for exec_uri in executions:
            item = QTreeWidgetItem([Prefix.uri_to_str(exec_uri)])
            item.setData(0, 1, exec_uri)
            item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
            self.tree.addTopLevelItem(item)

    def on_item_expanded(self, item):
        if item.childCount() > 0:
            return  # Already populated

        exec_uri = item.data(0, 1)
        container = QWidget()
        container.setLayout(QVBoxLayout(container))
        container.setContentsMargins(0, 0, 0, 0)

        widget = ExecutionWidget(self.g, exec_uri)
        container.layout().addWidget(widget)

        child_item = QTreeWidgetItem()
        item.addChild(child_item)
        self.tree.setItemWidget(child_item, 0, container)
        
class FunctionWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.function = None
        self.g = None

        self.implementation_list = ImplementationListWidget()
        self.execution_list = ExecutionListWidget()

        # Set size policies
        self.implementation_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.execution_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Create splitter and add widgets
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.implementation_list)
        splitter.addWidget(self.execution_list)

        # Optional: set initial sizes (stretch factors)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        # Main layout
        layout = QVBoxLayout()
        layout.addWidget(splitter)
        self.setLayout(layout)

        self.implementation_list.implementationSelected.connect(self.on_implementation_selected)

    def set_graph(self, g: FnOGraph):
        self.g = g
        self.implementation_list.set_graph(g)
        self.execution_list.set_graph(g)

    def set_data(self, function: Function):
        if self.function:
            self.function.implementationChanged.disconnect(self.on_imp_changed)

        self.function = function

        # IMPLEMENTATION
        self.function.implementationChanged.connect(self.on_imp_changed)
        self.implementation_list.set_function(function)
        if function.imp:
            self.on_imp_changed(function.imp)

        # EXECUTION
        self.execution_list.set_function(function)

    def on_imp_changed(self, imp):
        self.implementation_list.select_implementation(imp)

    def on_implementation_selected(self, imp):
        self.function.imp = imp  # This triggers on_imp_changed indirectly
