from PyQt6.QtGui import QPainter, QResizeEvent
from PyQt6.QtWidgets import QWidget, QSplitter, QVBoxLayout, QSlider, QSizePolicy
from PyQt6.QtCore import Qt

from pyqtgraph import GraphicsView, ViewBox

from ..executors.store import Mapping, ValueStore
from ..executors.executeable import Function
from ..graph import FnOGraph
from .function import FunctionGraphicsItem
from .store import StoreGraphicsItem
from .mapping import DataMappingGraphicsItem, ControlMappingGraphicsItem
from .widgets import FunctionWidget, TerminalWidget, LabeledDockWidget
from ..elk import elk_layout

class ExeGraphicsView(GraphicsView):

    def __init__(self, widget, *args):
        GraphicsView.__init__(self, *args, useOpenGL=False)

        # lockAspect ensures aspect ratio between X and Y axis is consistent during zooming
        self._viewbox = ExeViewBox(widget, lockAspect=True, invertY=True)
        self.setCentralItem(self._viewbox)
        # Enables smooth lines or edges
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    
    def viewBox(self):
        return self._viewbox

class ExeViewBox(ViewBox):
    def __init__(self, widget, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.widget = widget

        # Set the background of the viewbox
        self.setBackgroundColor('white')

    def items(self):
        return self.addedItems

class ExeViewWidget(QWidget):
    def __init__(self, ctrl):
        super().__init__()

        self.ctrl = ctrl
        self.view = ExeGraphicsView(ctrl)
        self.terminalWidget = TerminalWidget()
        self.functionWidget = FunctionWidget()
        
        # Scene and viewBox references
        self._scene = self.view.scene()
        self._viewBox = self.view.viewBox()

        # Main splitter (only terminal + function will be resizable by user)
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.view_container = QWidget()
        self.view_container.setLayout(QVBoxLayout())
        self.view_container.layout().setContentsMargins(0, 0, 0, 0)
        self.view_container.layout().addWidget(self.view)
        self.view_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.splitter.addWidget(self.view_container)
        self.splitter.addWidget(LabeledDockWidget("Instance", self.terminalWidget))
        self.splitter.addWidget(LabeledDockWidget("Function", self.functionWidget))

        # Slider to control view height only
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(100)
        self.slider.valueChanged.connect(self.update_view_height)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.slider)
        layout.addWidget(self.splitter)
        self.setLayout(layout)
        
        # Connect hover
        self._scene.sigMouseHover.connect(self.hoverOver)
        self.selected_store = None
        self.hover_store = None
        
        self.update_view_height()

    def update_view_height(self):
        max_height = 600
        percent = self.slider.value() / 100.0
        new_height = int(percent * max_height)

        self.view_container.setMaximumHeight(new_height)
        self.view_container.setMinimumHeight(new_height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_view_height()
    
    def scene(self):
        return self._scene
    
    def viewBox(self):
        return self._viewBox
    
    def setFunction(self, g: FnOGraph, function: Function):
        self.g = g
        self.functionWidget.set_graph(g)
        
        self.function = function
        self.items = {}
        self.terminals = {}
        self.mappings = set()
        self.viewBox().clear()

        self.function = function
        function.setInternal(False)
        
        self.draw()
    
    def onFunctionSelected(self, function: Function):
        # Implementation details
        self.functionWidget.set_data(function)
    
    def onStoreSelected(self, store: ValueStore):
        self.selected_store = store
        self.terminalWidget.set_data(store)
    
    def hoverOver(self, items):
        hovered_store = None

        for item in items:
            if isinstance(item, StoreGraphicsItem):  # Assuming this is your terminal graphics item
                hovered_store = item.store
                break

        if hovered_store == self.hover_store:
            return  # Nothing changed

        self.hover_store = hovered_store

        if self.hover_store:
            self.terminalWidget.set_data(self.hover_store)
        elif self.selected_store:
            self.terminalWidget.set_data(self.selected_store)
        else:
            self.terminalWidget.clear_content()
    
    def draw(self):
        # reset the viewbox
        self.viewBox().clear()
        self.nextZVal = 10
              
        root = self.draw_function(self.function)
        
        elk = {
            "id": "root",
            "layoutOptions": {
                "algorithm": "layered",
                "elk.direction": "RIGHT",
                "edgeRouting": "ORTHOGONAL",
                "hierarchyHandling": "SEPERATE_CHILDREN",
                "elk.spacing.edgeNode": 50, 
                "elk.spacing.nodeNode": 30,
                "elk.layered.feedbackEdges": True
            },
            "children": [root.elk()]
        }
        
        # with open("no_layout.json", "w") as f:
        #     json.dump(elk, f, indent=2)
        
        elk = elk_layout(elk)
        
        # with open("with_layout.json", "w") as f:
        #     json.dump(elk, f, indent=2)
        
        root.layer(elk["children"][0])
    
    def draw_function(self, fun: Function, parent=None):
        item = FunctionGraphicsItem(fun, self)
        item.setZValue(self.nextZVal*2)
        self.nextZVal += 1
        item.functionSelected.connect(self.onFunctionSelected)
        self.viewBox().addItem(item)
        
        self.items[fun] = item
        for terminal_item in item.terminals.values():
            terminal_item.storeSelected.connect(self.onStoreSelected)
            self.terminals[terminal_item.store] = terminal_item
        
        if parent:
            parent.addFunction(item)
        
        if fun.internal and fun.comp:
            for call in fun.comp.functions.values():
                self.draw_function(call, item)
                
            for mapping in fun.comp.mappings.values():
                self.draw_mapping(mapping, item)
            
            for call in fun.comp.functions.values():
                self.draw_controlflow(
                    call, 
                    fun.comp.functions.get(call.next, None),
                    fun.comp.functions.get(call.iterate, None),
                    fun.comp.functions.get(call.iftrue, None),
                    fun.comp.functions.get(call.iffalse, None),
                    item
                )
            
        return item
    
    def draw_controlflow(self, call, next, iterate, iftrue, iffalse, parent):
        # Only visualize control flow for nodes with non-linear control flow
        # if iftrue or iffalse or iterate:
        if next:
            mapping_item = ControlMappingGraphicsItem(self.items[call], self.items[next], "next")
            self.viewBox().addItem(mapping_item)
            mapping_item.setZValue(1)
            parent.addControlMapping(mapping_item)
        if iterate:
            mapping_item = ControlMappingGraphicsItem(self.items[call], self.items[iterate], "iterate")
            self.viewBox().addItem(mapping_item)
            mapping_item.setZValue(1)
            parent.addControlMapping(mapping_item)
        if iftrue:
            mapping_item = ControlMappingGraphicsItem(self.items[call], self.items[iftrue], "iftrue")
            self.viewBox().addItem(mapping_item)
            mapping_item.setZValue(1)
            parent.addControlMapping(mapping_item)
        if iffalse:
            mapping_item = ControlMappingGraphicsItem(self.items[call], self.items[iffalse], "iffalse")
            self.viewBox().addItem(mapping_item)
            mapping_item.setZValue(1)
            parent.addControlMapping(mapping_item)
            
        # Or nodes at the end of a for-loop
        """elif next and next.iterate:
            mapping_item = ControlMappingGraphicsItem(self.items[call], self.items[next], "next")
            self.viewBox().addItem(mapping_item)
            mapping_item.setZValue(1)
            parent.addControlMapping(mapping_item)"""
    
    def draw_mapping(self, mapping: Mapping, parent):
        if mapping.target in self.terminals:
            for source in mapping.list_sources():
                if source in self.terminals:
                    source_item = self.terminals[source]
                    target_item = self.terminals[mapping.target]
                    mapping_item = DataMappingGraphicsItem(source_item, target_item)
                    self.viewBox().addItem(mapping_item)
                    parent.addMapping(mapping_item)