from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QTextEdit,
                             QHBoxLayout, QTreeWidget, QTreeWidgetItem, QHeaderView, QSplitter,
                             QLabel, QGroupBox, QFormLayout, QListWidget, QListWidgetItem, QDialog)
from PyQt6.QtCore import Qt
from ...prefix import Prefix
from ...graph import FnOGraph
from rdflib import URIRef, Literal

import pandas as pd
import pprint

class URIWidget(QWidget):

    def __init__(self, g: FnOGraph, uri, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        if g.is_implementation(uri):
            splitter.addWidget(ImplementationWidget(g, uri))
        else:
            values = g.get_value(uri)
            if len(values) == 1:
                splitter.addWidget(InstanceWidget(g, values[0]))
            splitter.addWidget(ProvenanceTreeWidget(g, uri))
    
class ImplementationWidget(QWidget):

    def __init__(self, g: FnOGraph, uri, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        table_widget = ImplementationTableWidget(g, uri)
        provenance_widget = ProvenanceTreeWidget(g, uri)

        splitter.addWidget(table_widget)
        splitter.addWidget(provenance_widget)

class ImplementationTableWidget(QWidget):
  
    def __init__(self, g: FnOGraph, uri, parent=None):
        super().__init__(parent)
        self.table = QTableWidget(self)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Key", "Value", "Type"])
        
        rows = []
        for key, value in g.get_imp_metadata(uri).items():
            if isinstance(value, list):
                for item in value:
                    rows.append((key, item))
            else:
                rows.append((key, value))

        self.table.clearContents()
        self.table.setRowCount(len(rows))

        for row, (key, value) in enumerate(rows):
            key_item = QTableWidgetItem(Prefix.uri_to_str(key))
            if isinstance(value, URIRef):
              value_item = QTableWidgetItem(Prefix.uri_to_str(value))
              value_type = QTableWidgetItem('uri')
            elif isinstance(value, Literal):
              value_item = QTableWidgetItem(value.value)
              value_type = QTableWidgetItem(Prefix.uri_to_str(value.datatype))
            self.table.setItem(row, 0, key_item)
            self.table.setItem(row, 1, value_item)
            self.table.setItem(row, 2, value_type)

        self.table.resizeColumnsToContents()

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        self.setLayout(layout)

class ExecutionWidget(QWidget):
    def __init__(self, g: FnOGraph, execution_uri, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        table_widget = ExecutionDetailsWidget(g, execution_uri)
        provenance_widget = ProvenanceTreeWidget(g, execution_uri)

        splitter.addWidget(table_widget)
        splitter.addWidget(provenance_widget)


class ExecutionDetailsWidget(QWidget):
    def __init__(self, g: FnOGraph, exe_uri: URIRef, parent=None):
        super().__init__(parent)
        self.graph = g
        self.exe_uri = exe_uri

        main_layout = QVBoxLayout(self)

        # --- Execution Metadata ---
        meta_box = QGroupBox("Execution Metadata")
        meta_layout = QFormLayout()

        execution_data = g.get_execution_time(exe_uri)
        started = execution_data.get('startedAtTime')
        ended = execution_data.get('endedAtTime')
        duration = execution_data.get('duration_ms')

        if started:
            meta_layout.addRow("Started at:", QLabel(str(started)))
        if ended:
            meta_layout.addRow("Ended at:", QLabel(str(ended)))
        if duration is not None:
            meta_layout.addRow("Duration (ms):", QLabel(str(duration)))

        meta_box.setLayout(meta_layout)
        main_layout.addWidget(meta_box)

        # --- Associated Agents ---
        agent_box = QGroupBox("Associated Agents")
        agent_layout = QVBoxLayout()

        self.agent_list = QListWidget()
        self.agent_list.itemDoubleClicked.connect(self.open_agent_uri)

        for assoc in g.get_agent(exe_uri):
            agent_uri = assoc.get("agent")
            plan_uri = assoc.get("plan")
            role_uri = assoc.get("role")

            text = Prefix.uri_to_str(agent_uri)
            if plan_uri:
                text += f"\n\tPlan: {Prefix.uri_to_str(plan_uri)}"
            if role_uri:
                text += f"\n\tRole: {Prefix.uri_to_str(role_uri)}"

            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, agent_uri)
            self.agent_list.addItem(item)

        agent_layout.addWidget(self.agent_list)
        agent_box.setLayout(agent_layout)
        main_layout.addWidget(agent_box)

        self.setLayout(main_layout)

    def open_agent_uri(self, item: QListWidgetItem):
        agent_uri = item.data(Qt.ItemDataRole.UserRole)
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Agent: {agent_uri}")
        layout = QVBoxLayout(dialog)
        layout.addWidget(URIWidget(self.graph, agent_uri))
        dialog.setLayout(layout)
        dialog.resize(600, 400)
        dialog.exec()
        
class ProvenanceTreeWidget(QWidget):
    def __init__(self, g: FnOGraph, uri, parent=None):
        super().__init__(parent)
          
        self.tree = URITreeWidget(g)
        self.tree.setHeaderLabels(["Relation", "Target"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)

        # Create the top-level items
        self.derived_item = QTreeWidgetItem(["derivedFrom"])
        self.alternative_item = QTreeWidgetItem(["alternativeOf"])
        self.specialization_item = QTreeWidgetItem(["specializationOf"])
        self.generated_item = QTreeWidgetItem(["generated"])

        # Add top-level items to the tree
        self.tree.addTopLevelItems([
            self.derived_item,
            self.alternative_item,
            self.specialization_item,
            self.generated_item
        ])
        
        # Populate children
        for d in g.derived_from(uri):
          child = QTreeWidgetItem(["", Prefix.uri_to_str(d)])
          child.setData(0, 1, d)
          self.derived_item.addChild(child)
        
        for a in g.alternatives(uri):
          child = QTreeWidgetItem(["", Prefix.uri_to_str(a)])
          child.setData(0, 1, a)
          self.alternative_item.addChild(child)
        
        for s in g.specializationOf(uri):
          child = QTreeWidgetItem(["", Prefix.uri_to_str(s)])
          child.setData(0, 1, s)
          self.specialization_item.addChild(child)
        
        for g in g.generated(uri):
          child = QTreeWidgetItem(["", Prefix.uri_to_str(g)])
          child.setData(0, 1, g)
          self.generated_item.addChild(child)

        layout = QVBoxLayout()
        layout.addWidget(self.tree)
        self.setLayout(layout)

class URITreeWidget(QTreeWidget):
    def __init__(self, g: FnOGraph, parent=None):
        super().__init__(parent)
        self.g = g
        self.setMouseTracking(True)  # Optional, for other hover-based behavior

    def mouseDoubleClickEvent(self, event):
        item = self.itemAt(event.pos())
        if item and item.data(0, 1):
            uri = item.data(0, 1)
            self.open_uri_window(uri)
        super().mouseDoubleClickEvent(event)

    def open_uri_window(self, uri):
        # Create a standalone URIWidget window
        window = URIWidget(self.g, uri)
        window.setWindowTitle(str(uri))
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)  # Auto cleanup on close
        window.setWindowFlags(Qt.WindowType.Window)  # Standard resizable window with close button
        window.resize(600, 400)
        window.show()

class InstanceWidget(QWidget):
  
  def __init__(self, g: FnOGraph, value, parent = None):
    super().__init__(parent)
    self.setLayout(QHBoxLayout(self))
    
    if isinstance(value, Literal):
      value = value.value
    
    if isinstance(value, URIRef):
      if g:
        widget = URIWidget(g, value)
        self.layout().addWidget(widget)
        return
      else:
        value = Prefix.uri_to_str(value)
    
    if isinstance(value, pd.DataFrame):
      # Create a widget for the DataFrame
      preview = value.head(100)
      widget = QTableWidget()
      widget.setRowCount(len(preview))
      widget.setColumnCount(len(preview.columns))
      widget.setHorizontalHeaderLabels([str(col) for col in preview.columns])

      for i, row in preview.iterrows():
        for j, col in enumerate(preview.columns):
          widget.setItem(i, j, QTableWidgetItem(str(row[col])))

      widget.resizeColumnsToContents()
    else:
      # Pretty-print non-DataFrame values
      text = pprint.pformat(value)
      widget = QTextEdit()
      widget.setReadOnly(True)
      widget.setPlainText(text)
    
    self.layout().addWidget(widget)