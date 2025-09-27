from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsTextItem
from PyQt6.QtCore import QRectF, Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QColor, QPen, QBrush
from pyqtgraph import GraphicsObject

from ..model.store import Terminal
from .colors import *

class StoreGraphicsItem(GraphicsObject):

    storeSelected = pyqtSignal(object)

    def __init__(self, terminal: Terminal, parent=None):
        super().__init__(parent)
        self.store = terminal
        self.mappings = {}

        self.setFlags(self.GraphicsItemFlag.ItemIsSelectable | self.GraphicsItemFlag.ItemIsFocusable)
        self.setAcceptHoverEvents(True)

        # Brushes
        self.std_brush = QBrush(TERMINAL_COLOR)
        self.hover_brush = QBrush(TERMINAL_HOVER)
        self.accepted_brush = QBrush(TERMINAL_ACCEPT)

        self.is_hovered = False

        self.box = QGraphicsRectItem(0, 0, 10, 10, self)
        self.store.valueSet.connect(self.updateBrush)
        self.updateBrush()

        name = terminal.name
        self.label = QGraphicsTextItem(name, self.box)
        self.label.setScale(0.7)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

        self.setFiltersChildEvents(True)
        self.setZValue(1)

    def boundingRect(self) -> QRectF:
        return self.box.mapRectToParent(self.box.boundingRect())

    def setAnchor(self, x, y):
        pos = QPoint(x, y)
        self.anchorPos = pos
        br = self.box.mapRectToParent(self.box.boundingRect())
        lr = self.label.mapRectToParent(self.label.boundingRect())

        if not self.store.is_output:
            self.box.setPos(pos.x() - br.width(), pos.y() - br.height() / 2.)
            self.label.setPos(pos.x(), pos.y() - lr.height() / 2.)
        else:
            self.box.setPos(pos.x(), pos.y() - br.height() / 2.)
            self.label.setPos(pos.x() - lr.width(), pos.y() - lr.height() / 2.)

    def sourcePoint(self):
        return self.mapToView(self.mapFromItem(self.box, self.box.boundingRect().right(), self.box.boundingRect().center().y()))

    def targetPoint(self):
        return self.mapToView(self.mapFromItem(self.box, self.box.boundingRect().left(), self.box.boundingRect().center().y()))

    def updateBrush(self):
        if self.is_hovered or self.isSelected():
            self.box.setBrush(self.hover_brush)
        elif self.store.value_set:
            self.box.setBrush(self.accepted_brush)
        else:
            self.box.setBrush(self.std_brush)
        self.update()

    def paint(self, painter, option, widget=None):
        pass  # All visual painting handled by box

    def functionMoved(self):
        for mapping in self.mappings.values():
            mapping.updateLine()

    def mousePressEvent(self, event):
        event.ignore()

    def mousePressEvent(self, event):
        event.ignore()
    
    def mouseClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            selected = self.isSelected()
            self.setSelected(True)
            if not selected and self.isSelected():
                self.storeSelected.emit(self.store)
                self.updateBrush()
    
    def mouseDragEvent(self, event):
        event.ignore()
    
    def hoverEvent(self, event):
        if not event.isExit():
            event.acceptClicks(Qt.MouseButton.LeftButton)
            event.acceptClicks(Qt.MouseButton.RightButton)
            self.is_hovered = True
        else:
            self.is_hovered = False
        self.updateBrush()

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
        self.box.setPos(elk["x"], elk["y"])
        self.label.setPos(elk["labels"][0]["x"], elk["labels"][0]["y"])
    
    def itemChange(self, change, value):
        if change == self.GraphicsItemChange.ItemSelectedChange:
            self.updateBrush()
        return super().itemChange(change, value)