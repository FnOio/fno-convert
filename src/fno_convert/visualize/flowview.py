import json
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtWidgets import QTextEdit, QGraphicsRectItem
from PyQt6.QtCore import QRectF

from pyqtgraph import GraphicsView, ViewBox, mkBrush, mkPen
from pyqtgraph.dockarea import DockArea, Dock
from rdflib import URIRef
import numpy as np

from ..executors.store import Mapping
from ..executors.executeable import Composition, Function
from ..graph import FnOGraph
from .function import FunctionGraphicsItem
from .store import StoreGraphicsItem
from .mapping import DataMappingGraphicsItem, ControlMappingGraphicsItem
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

class ExeViewWidget(DockArea):

    def __init__(self, ctrl):
        DockArea.__init__(self)

        self.ctrl = ctrl
        self.hoverItem = None
        self.nextZVal = 10

        # The graphics view
        self.view = ExeGraphicsView(ctrl)
        self.viewDock = Dock('view', size=(1000, 900))
        self.viewDock.addWidget(self.view)
        self.viewDock.hideTitleBar()
        self.addDock(self.viewDock)

        self.hoverText = QTextEdit()
        self.hoverText.setReadOnly(True)
        self.hoverDock = Dock('Hover Info', size=(1000, 5))
        self.hoverDock.addWidget(self.hoverText)
        self.addDock(self.hoverDock, 'bottom')

        # TODO add scrollable info
        self.selectText = QTextEdit()
        self.selectText.setReadOnly(True)
        self.selectDock = Dock('Selected Node', size=(1000, 500))
        self.selectDock.addWidget(self.selectText)
        self.addDock(self.selectDock, 'bottom')

        self._scene = self.view.scene()
        self._viewBox = self.view.viewBox()

        self._scene.selectionChanged.connect(self.selectionChanged)
        self._scene.sigMouseHover.connect(self.hoverOver)
    
    def scene(self):
        return self._scene
    
    def viewBox(self):
        return self._viewBox
    
    def setFunction(self, function: Function):
        self.function = function
        self.items = {}
        self.terminals = {}
        self.mappings = set()
        self.viewBox().clear()

        self.function = function
        function.setInternal(False)
        
        self.draw()
    
    def selectionChanged(self):
        items = self._scene.selectedItems()
        if len(items) > 0:
            item = items[0]
            self.selectText.setPlainText(f"Selected item: {item}")
    
    def hoverOver(self, items):
        store = None
        for item in items:
            if item is self.hoverItem:
                return
            self.hoverItem = item
            if isinstance(item, StoreGraphicsItem):
                store = item.store
                break
        if store is None:
            self.hoverText.setPlainText("")
        else:
            value = str(store.value)
            if len(value) > 400:
                value = value[:400] + "..."
            self.hoverText.setPlainText("%s = %s" % (store.name, value))
    
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
        self.viewBox().addItem(item)
        
        self.items[fun] = item
        for terminal_item in item.terminals.values():
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