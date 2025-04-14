import math
from pyqtgraph import GraphicsObject, Point
import pyqtgraph.functions as fn
from PyQt6.QtGui import QPainterPath, QPainterPathStroker
from PyQt6.QtWidgets import QGraphicsTextItem
from PyQt6.QtCore import Qt

from .store import TerminalGraphicsItem

STD_COLOR = (100, 100, 250)
LINK_COLOR = (250, 50, 50)

class MappingGraphicsItem(GraphicsObject):

    def __init__(self):
        GraphicsObject.__init__(self)

        self.length = 0
        self.path = None
        self.shapePath = None
        self.style = {}
    
    def layer(self, elk):        
        # TODO multiple sections?
        sections = elk.get("sections", [])
        if len(sections) == 0:
            return
        if len(sections) > 1:
            print("Multiple sections not handled!!!")
            
        start = Point(sections[0]["startPoint"]["x"], sections[0]["startPoint"]["y"])
        stop = Point(sections[0]["endPoint"]["x"], sections[0]["endPoint"]["y"])
        bendPoints = sections[0].get("bendPoints", [])
        
        self.path = QPainterPath()
        self.path.moveTo(start)
        for point in bendPoints:
            self.path.lineTo(Point(point["x"], point["y"]))
        self.path.lineTo(stop)
        
        self.shapePath = None
        self.update()
    
    def keyPressEvent(self, ev):
        ev.ignore()
        return

    def mousePressEvent(self, ev):
        ev.ignore()
        return

    def mouseClickEvent(self, ev):
        ev.ignore()
        return
    
    def boundingRect(self):
        return self.shape().boundingRect()
    
    def viewRangeChanged(self):
        self.shapePath = None
        self.prepareGeometryChange()

    def shape(self):
        if self.shapePath is None:
            if self.path is None:
                return QPainterPath()
            stroker = QPainterPathStroker()
            px = self.pixelWidth()
            stroker.setWidth(px * 8)
            self.shapePath = stroker.createStroke(self.path)
        return self.shapePath
    
    def paint(self, p, *args):
        if self.path is None:
            return
        
        p.setPen(fn.mkPen(self.style['color'], width=self.style['width']))
        p.drawPath(self.path)

class ControlMappingGraphicsItem(MappingGraphicsItem):
    
    def __init__(self, source, target, type):
        super().__init__()
        
        color = LINK_COLOR
        self.style = {
            'shape': 'line',
            'color': color,
            'width': 2.0
        }
        
        self.label = QGraphicsTextItem(type, self)
        self.label.setScale(0.7)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        
        self.source = source
        source.control_mappings.add(self)
        self.target = target
        target.control_mappings.add(self)
        
    def id(self):
        return f"{self.source.function.id()}_{self.target.function.id()}_{self.label.toPlainText()}"
    
    def elk(self):
        return {
            "id": self.id(),
            "target": self.target.function.id(),
            # "targetPort": f"{self.source.function.id()}_{self.label.toPlainText()}_in",
            "source": self.source.function.id(),
            # "sourcePort": f"{self.source.function.id()}_{self.label.toPlainText()}_out",
            "labels": [{
                "text": self.label.toPlainText(),
                "width": self.label.boundingRect().width(),
                "height": self.label.boundingRect().height(),
                "layoutOptions": {
                    "edgeLabels.placement": "TAIL"
                }
            }]
        }
    
    def port(self, call):
        return {
            "id": f"{self.source.function.id()}_{self.label.toPlainText()}_{"in" if call == self.target else "out"}",
            "width": 0,
            "height": 0,
            "layoutOptions": {
                "allowNonFlowPortsToSwitchSides": "true",
                "port.side": "SOUTH"
            }
        }
    
    def layer(self, elk):
        super().layer(elk)
        
        # Set label
        self.label.setPos(elk["labels"][0]["x"], elk["labels"][0]["y"])
        
        self.add_arrowhead()
    
    def add_arrowhead(self):
        # Get last two points of the path
        end = self.path.currentPosition()  # Get last point
        if self.path.elementCount() > 1:
            lastElement = self.path.elementAt(self.path.elementCount() - 2)
            start = Point(lastElement.x, lastElement.y)
        
            arrow_size = 10  # Arrowhead length

            # Compute direction vector
            dx = end.x() - start.x()
            dy = end.y() - start.y()
            angle = math.atan2(dy, dx)

            # Compute arrowhead points
            left = Point(end.x() - arrow_size * math.cos(angle - math.pi / 6), 
                        end.y() - arrow_size * math.sin(angle - math.pi / 6))
            right = Point(end.x() - arrow_size * math.cos(angle + math.pi / 6), 
                            end.y() - arrow_size * math.sin(angle + math.pi / 6))

            # Append arrow lines to the path
            self.path.lineTo(left)
            self.path.moveTo(end)
            self.path.lineTo(right)
            
            self.update()

class DataMappingGraphicsItem(MappingGraphicsItem):
    
    def __init__(self, source: TerminalGraphicsItem, target: TerminalGraphicsItem):
        super().__init__()
        
        color = STD_COLOR
        self.style = {
            'shape': 'line',
            'color': color,
            'width': 2.0
        }
        
        self.source = source
        self.target = target
        
        if self.source.getViewBox():
            self.source.getViewBox().addItem(self)
        else:
            self.target.getViewBox().addItem(self)
            self.target.getViewBox().addItem(self.source)
        
        self.source.mappings[target] = self
        self.target.mappings[source] = self
        
        self.setZValue(1)
    
    def id(self):
        return f"{self.source.store.id()}_{self.target.store.id()}"
    
    def elk(self):
        return {
            "id": f"{self.source.store.id()}_{self.target.store.id()}",
            "target": self.target.store.fun.id(),
            "targetPort": self.target.store.id(),
            "source": self.source.store.fun.id(),
            "sourcePort": self.source.store.id()
        }