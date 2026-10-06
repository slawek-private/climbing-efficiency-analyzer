"""Shared route, attempt and checkpoint selection for every comparison view."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget,QHBoxLayout,QLabel,QComboBox,QPushButton,QMenu


def identity(doc):
    return doc.get('attempt_id') or '|'.join((doc['source']['sha256'],doc['climber'],doc['attempt']))


class CompareScope(QWidget):
    changed=Signal()
    def __init__(self):
        super().__init__();self.documents=[];self.selected=None;layout=QHBoxLayout(self)
        self.route=QComboBox();self.reference=QComboBox();self.point=QComboBox();self.subjects=QPushButton('Attempts…')
        for name,control in [('Route',self.route),('Reference',self.reference),('Checkpoint',self.point)]:layout.addWidget(QLabel(name));layout.addWidget(control,1)
        layout.addWidget(self.subjects);self.menu=QMenu(self);self.subjects.setMenu(self.menu)
        self.route.currentIndexChanged.connect(self.route_changed);self.reference.currentIndexChanged.connect(self.changed);self.point.currentIndexChanged.connect(self.changed)
    def set_documents(self,documents):
        self.documents=documents;previous=self.route.currentText();self.route.blockSignals(True);self.route.clear();self.route.addItems(sorted({d['route'] for d in documents}));self.route.setCurrentIndex(max(0,self.route.findText(previous)));self.route.blockSignals(False);self.rebuild()
    def route_changed(self):self.selected=None;self.rebuild();self.changed.emit()
    def rebuild(self):
        docs=[d for d in self.documents if d['route']==self.route.currentText()]
        old=self.reference.currentData();self.reference.blockSignals(True);self.reference.clear();self.menu.clear()
        for d in docs:
            key=identity(d);name=f"{d['climber']} · {d['attempt']}"
            self.reference.addItem(name,key);action=self.menu.addAction(name);action.setCheckable(True);action.setChecked(self.selected is None or key in self.selected);action.setData(key)
            action.toggled.connect(self.selection_changed)
        self.reference.setCurrentIndex(max(0,self.reference.findData(old)));self.reference.blockSignals(False)
        old=self.point.currentText();self.point.blockSignals(True);self.point.clear();self.point.addItem('Climb start');self.point.addItems(sorted({p['name'] for d in docs for p in d.get('checkpoints',[])}));self.point.setCurrentIndex(max(0,self.point.findText(old)));self.point.blockSignals(False)
    def selection_changed(self):
        self.selected={a.data() for a in self.menu.actions() if a.isChecked()};self.changed.emit()
    def chosen(self):
        ref=self.reference.currentData()
        docs=[d for d in self.documents if d['route']==self.route.currentText() and (self.selected is None or identity(d) in self.selected or identity(d)==ref)]
        return sorted(docs,key=lambda d:identity(d)!=ref)
