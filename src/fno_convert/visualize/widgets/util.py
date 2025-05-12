from PyQt6.QtWidgets import QWidget, QHBoxLayout, QSizePolicy
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPainter, QFont, QPen, QPaintEvent

from ...graph import FnOGraph
from .entity import URIWidget

class VerticalTextWidget(QWidget):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._text = text
        self.setMinimumWidth(20)  # Ensure some visible width

    def setText(self, text):
        self._text = text
        self.update()  # Trigger repaint

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Rotate -90 degrees for bottom-to-top text
        painter.translate(0, self.height())  # Move origin to bottom-left
        painter.rotate(-90)

        painter.setPen(QPen(Qt.GlobalColor.blue))
        painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))

        # After rotation, height becomes width and vice versa
        painter.drawText(0, 0, self.height(), self.width(), Qt.AlignmentFlag.AlignCenter, self._text)

    def sizeHint(self):
        return QSize(20, 100)

class LabeledDockWidget(QWidget):
    def __init__(self, label_text: str, content_widget: QWidget, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create the rotated label
        label = VerticalTextWidget(label_text)
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)  # Keep the label fixed in width
        layout.addWidget(label)

        # Add the content widget which will take remaining space
        content_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(content_widget)

        self.setLayout(layout)