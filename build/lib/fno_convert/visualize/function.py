from PyQt6.QtGui import QColor, QPen, QBrush
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtWidgets import QGraphicsTextItem
from pyqtgraph import GraphicsObject

from ..executors.executeable import Function
from .store import TerminalGraphicsItem
from .mapping import MappingGraphicsItem, ControlMappingGraphicsItem
from .colors import STD_COLOR

class FunctionGraphicsItem(GraphicsObject):

    def __init__(self, function: Function, view):
        GraphicsObject.__init__(self)
        self.view = view

        self.hovered = False
        self.pen = None
        self.brush = None
        self.hoverBrush = None
        self.selectPen = None
        self.selectBrush = None
        self.setColor(STD_COLOR)

        self.function = function
        
        self.terminals = {}
        self.control_mappings = set()
        self.internal_functions = {}
        self.internal_mappings = {}
        self.internal_ctrl_mappings = {}
        

        self.titleOffset = 25
        self.terminalOffset = 15

        flags = self.GraphicsItemFlag.ItemIsSelectable | self.GraphicsItemFlag.ItemIsFocusable | self.GraphicsItemFlag.ItemSendsGeometryChanges
        self.setFlags(flags)
        
        # Create label
        self.nameItem = QGraphicsTextItem(function.name, self)
        self.nameItem.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.nameItem.setDefaultTextColor(QColor(50, 50, 50))
        
        # Create terminals
        for term in self.function.terminals.values():
            item = TerminalGraphicsItem(term, self)
            item.setZValue(self.zValue())
            self.terminals[term.id()] = item

        # Placeholder bounds
        self.bounds = QRectF(0, 0, 0, 0)
    
    def addFunction(self, item: "FunctionGraphicsItem"):
        # Add internal function
        self.internal_functions[item.function.id()] = item
        item.setParentItem(self)
    
    def addMapping(self, item: "MappingGraphicsItem"):
        # Add internal mapping
        self.internal_mappings[item.id()] = item
        item.setParentItem(self)
    
    def addControlMapping(self, item: "ControlMappingGraphicsItem"):
        # Add internal control mapping
        self.internal_ctrl_mappings[item.id()] = item
        item.setParentItem(self)
    
    def setColor(self, color: QColor):
        pen_color = color.darker(105)
        brush_color = color.lighter(105)
        brush_color.setAlpha(5)
        hover_color = color.lighter(110)

        self.setPenColor(pen_color)
        self.setBrushColor(brush_color)
        self.setHoverColor(hover_color)
    
    def setPenColor(self, color: QColor):
        self.pen = QPen(color, 2)
        self.selectPen = QPen(color, 4)
        self.update()

    def setBrushColor(self, color: QColor):
        self.brush = QBrush(color)
        select_color = color.lighter(115)
        select_color.setAlpha(200)
        self.selectBrush = QBrush(select_color)
        self.update()
    
    def setHoverColor(self, color: QColor):
        self.hoverBrush = QBrush(color)
        self.update()
    
    def boundingRect(self) -> QRectF:
        return self.bounds.adjusted(-5, -5, 5, 5)
    
    def paint(self, p, *args):
        if self.isSelected():
            p.setPen(self.selectPen)
            p.setBrush(self.selectBrush)
        else:
            p.setPen(self.pen)
            if self.hovered:
                p.setBrush(self.hoverBrush)
            else:
                p.setBrush(self.brush)
        p.drawRect(self.bounds)

    def mousePressEvent(self, event):
        event.ignore()
        
    def mouseDragEvent(self, event):
        event.ignore()

    def mouseClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            """selected = self.isSelected()
            self.setSelected(True)
            if not selected and self.isSelected():
                self.update()"""
    
    def hoverEvent(self, event):
        if not event.isExit() and event.acceptClicks(Qt.MouseButton.LeftButton):
            event.acceptDrags(Qt.MouseButton.LeftButton)
            self.hovered = True
        else:
            self.hovered = False
        self.update()
    
    def keyPressEvent(self, event) -> None:
        event.ignore()
    
    def internalMappings(self):
        mappings = set()
        
        for internal in self.internal_functions.values():
            for terminal in internal.terminals.values():
                mappings.update(terminal.mappings.values())
        
        return mappings
        
    def elk(self):
        elk = {
            "id": self.function.id(),
            "uri": self.function.fun_uri,
            "ports": [ ter.elk() for ter in self.terminals.values() ],
            "children": [ fun.elk() for fun in self.internal_functions.values() ],
            "edges": [ mapping.elk() for mapping in self.internal_mappings.values() ],
            "layoutOptions": {
                "nodeSize.constraints": "[PORTS, PORT_LABELS, NODE_LABELS]",
                "portConstraints": "FIXED_SIDE",
                "portLabels.placement": "[INSIDE]",
                "nodeLabels.placement": "[H_CENTER, V_TOP, INSIDE]",
                "elk.spacing.portPort": self.terminalOffset,
                "elk.padding": f"[top=10.0,left=20.0,bottom=10.0,right=20.0]" if self.function.internal else f"[top=0.0,left=0.0,bottom=0.0,right=0.0]",
            },
            "labels": [{
                "text": self.nameItem.toPlainText(),
                "width": self.nameItem.boundingRect().width(),
                "height": self.nameItem.boundingRect().height(),
            }]
        }
        
        # Add control flow ports
        # for control in self.control_mappings:
        #    elk["ports"].append(control.port(self))
        
        # Add control flow mappings
        for edge in self.internal_ctrl_mappings.values():
            elk["edges"].append(edge.elk())

        return elk
    
    def layer(self, elk):
        # Create bounds
        self.bounds = QRectF(0, 0, elk["width"], elk["height"])
        self.setPos(elk["x"], elk["y"])
        
        # Set label
        self.nameItem.setPos(elk["labels"][0]["x"], elk["labels"][0]["y"])
        
        # Set terminal positions
        for port in elk["ports"]:
            if port["id"] in self.terminals:
                # Input or output
                self.terminals[port["id"]].layer(port)
        
        # Layer internal nodes
        for child in elk["children"]:
            self.internal_functions[child["id"]].layer(child)
            
        # Layer mappings
        for edge in elk["edges"]:
            if edge["id"] in self.internal_mappings:
                # Data flow mapping
                self.internal_mappings[edge["id"]].layer(edge)
            else:
                # Control flow mapping
                self.internal_ctrl_mappings[edge["id"]].layer(edge)

    def itemChange(self, change, value):
        if change == self.GraphicsItemChange.ItemPositionHasChanged:
            pass
        return GraphicsObject.itemChange(self, change, value)