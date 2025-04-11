from PyQt6.QtWidgets import QMainWindow, QWidget, QGridLayout, QTabWidget

from .flowctrl import ExeCtrlWidget
from .load import ScrollWidget, Descripter

class PY2RDFWindow(QMainWindow):

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("Flow Visualizer")
        self.setGeometry(100, 100, 600, 400)

        # Tab to describe a flow
        loadTab = QWidget()
        layout1 = QGridLayout()
        loadTab.setLayout(layout1)

        # TODO Expand visualizer input with simple file
        codeViewer = ScrollWidget()
        rdfViewer = ScrollWidget()
        descripter = Descripter()

        layout1.addWidget(descripter, 0, 0, 1, 1)
        layout1.addWidget(codeViewer, 0, 1, 1, 4)
        layout1.addWidget(rdfViewer, 0, 5, 1, 4)

        # Tab to view flow
        viewTab = ExeCtrlWidget()

        # Event handling
        descripter.file_loaded.connect(codeViewer.setText)
        # funPicker.function_loaded.connect(codeViewer.setSource)
        descripter.resource_described.connect(rdfViewer.setGraph)
        descripter.resource_described.connect(viewTab.setFunction)
        # funPicker.function_loaded.connect(rdfViewer.setGraph)
        # funPicker.function_loaded.connect(viewTab.setExe)

        # Add Tabs
        tabWidget = QTabWidget()
        tabWidget.addTab(loadTab, "Load")
        tabWidget.addTab(viewTab, "View")
        self.setCentralWidget(tabWidget)