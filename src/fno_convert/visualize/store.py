from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsTextItem, QGraphicsEllipseItem
from PyQt6.QtCore import QRectF, Qt, QPoint
from PyQt6.QtGui import QColor, QPen, QBrush
from pyqtgraph import GraphicsObject

from ..executors.store import Terminal, ValueStore
from .colors import *

from abc import abstractmethod

class StoreGraphicsItem(GraphicsObject):

    def __init__(self, store: ValueStore, parent=None):
        GraphicsObject.__init__(self, parent)
        self.store = store
        self.mappings = {}
    
    @abstractmethod
    def sourcePoint(self):
        pass

    @abstractmethod
    def targetPoint(self):
        pass

class TerminalGraphicsItem(StoreGraphicsItem):

    def __init__(self, terminal: Terminal, parent=None):
        StoreGraphicsItem.__init__(self, terminal, parent)

        self.std_brush = QBrush(TERMINAL_COLOR)    # Standard brush is black
        self.hover_brush = QBrush(TERMINAL_HOVER)      # Hover brush is blue
        self.accepted_brush = QBrush(TERMINAL_ACCEPT)   # Accepted brush is green
        self.error_brush = QBrush(TERMINAL_ERROR)      # Error brush is red
        self.brush = self.std_brush

        self.box = QGraphicsRectItem(0, 0, 10, 10, self)
        self.box.setBrush(self.brush)
        
        if terminal.is_output:
            name = terminal.name if terminal.name == "self_output" else "out"
        else:
            name = terminal.name
        self.label = QGraphicsTextItem(name, self.box)
        self.label.setScale(0.7)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        
        self.setFiltersChildEvents(True) # pick up mouse events on rectitem
        self.setZValue(1)

        # terminal.valueChange.connect(self.valueChange)

    def boundingRect(self) -> QRectF:
        # Return the smallest rectangle that contains both the label and the box
        br = self.box.mapRectToParent(self.box.boundingRect())
        # lr = self.label.mapRectToParent(self.label.boundingRect())
        return br
    
    def setAnchor(self, x, y):
        pos = QPoint(x, y)
        self.anchorPos = pos
        br = self.box.mapRectToParent(self.box.boundingRect())
        lr = self.label.mapRectToParent(self.label.boundingRect())

        if not self.store.is_output:
        # Input: Box is to the left, Label is to the right
            self.box.setPos(pos.x() - br.width(), pos.y() - br.height() / 2.)
            self.label.setPos(pos.x(), pos.y() - lr.height() / 2.)
        else:
            # Output: Box is to the right, Label is to the left
            self.box.setPos(pos.x(), pos.y() - br.height() / 2.)
            self.label.setPos(pos.x() - lr.width(), pos.y() - lr.height() / 2.)
        # self.updateConnections()
    
    def sourcePoint(self):
        return self.mapToView(self.mapFromItem(self.box, self.box.boundingRect().right(), self.box.boundingRect().center().y()))
    
    def targetPoint(self):
        return self.mapToView(self.mapFromItem(self.box, self.box.boundingRect().left(), self.box.boundingRect().center().y()))
    
    def valueChange(self, accepted):
        if accepted:
            self.brush = self.accepted_brush
        else:
            self.brush = self.error_brush
            
        self.box.setBrush(self.brush)
        self.update()
    
    def paint(self, p, *args):
        pass
    
    def functionMoved(self):
        for mapping in self.mappings.values():
            mapping.updateLine()
    
    def mousePressEvent(self, event):
        event.ignore()
    
    def mouseClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            self.label.setFocus(Qt.FocusReason.MouseFocusReason)
    
    def mouseDragEvent(self, event):
        event.ignore()
    
    def hoverEvent(self, event):
        if not event.isExit() and event.acceptDrags(Qt.MouseButton.LeftButton):
            event.acceptClicks(Qt.MouseButton.LeftButton)
            event.acceptClicks(Qt.MouseButton.RightButton)
            self.box.setBrush(self.hover_brush)
        else:
            self.box.setBrush(self.brush)
        self.update()
    
    def elk(self):
        return {
            "id": self.store.id(),
            "uri": self.store.uri,
            "width": self.box.boundingRect().width(),
            "height": self.box.boundingRect().height(),
            "layoutOptions": {
                "port.side": "EAST" if self.store.is_output else "WEST"
            },
            "labels": [{
                "text": self.label.toPlainText(),
                "width": self.label.boundingRect().width(),
                "height": self.label.boundingRect().height(),
            }]
        }
    
    def layer(self, elk):
        # set box
        self.box.setPos(elk["x"], elk["y"])
        
        # set label
        self.label.setPos(elk["labels"][0]["x"], elk["labels"][0]["y"])