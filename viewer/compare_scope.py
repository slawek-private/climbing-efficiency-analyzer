"""Shared route, attempt and checkpoint selection for every comparison view."""
from PySide6.QtCore import Signal,Qt
from PySide6.QtWidgets import QWidget,QHBoxLayout,QLabel,QComboBox,QPushButton,QDialog,QVBoxLayout,QListWidget,QListWidgetItem,QDialogButtonBox


def identity(doc):
    return doc.get('attempt_id') or '|'.join((doc['source']['sha256'],doc['climber'],doc['attempt']))


class CompareScope(QWidget):
    changed=Signal()
    def __init__(self):
        super().__init__();self.documents=[];self.selected=None;layout=QHBoxLayout(self)
        self.route=QComboBox();self.reference=QComboBox();self.point=QComboBox();self.subjects=QPushButton('Choose athletes…')
        for name,control in [('Route',self.route),('Reference',self.reference),('Checkpoint',self.point)]:layout.addWidget(QLabel(name));layout.addWidget(control,1)
        layout.addWidget(self.subjects);self.subjects.clicked.connect(self.choose_subjects)
        self.route.currentIndexChanged.connect(self.route_changed);self.reference.currentIndexChanged.connect(self.changed);self.point.currentIndexChanged.connect(self.changed)
    def set_documents(self,documents):
        self.documents=documents;previous=self.route.currentText();self.route.blockSignals(True);self.route.clear();self.route.addItems(sorted({d['route'] for d in documents}));self.route.setCurrentIndex(max(0,self.route.findText(previous)));self.route.blockSignals(False);self.rebuild()
    def route_changed(self):self.selected=None;self.rebuild();self.changed.emit()
    def rebuild(self):
        docs=[d for d in self.documents if d['route']==self.route.currentText()]
        self.update_reference(docs)
        old=self.point.currentText();self.point.blockSignals(True);self.point.clear();self.point.addItem('Climb start');self.point.addItems(sorted({p['name'] for d in docs for p in d.get('checkpoints',[])}));self.point.setCurrentIndex(max(0,self.point.findText(old)));self.point.blockSignals(False)
    def set_selection(self,keys):
        self.selected=set(keys);self.rebuild();self.changed.emit()
    def update_reference(self,docs):
        old=self.reference.currentData();self.reference.blockSignals(True);self.reference.clear()
        for d in docs:
            if self.selected is None or identity(d) in self.selected:self.reference.addItem(f"{d['climber']} · {d['attempt']}",identity(d))
        self.reference.setCurrentIndex(max(0,self.reference.findData(old)));self.reference.blockSignals(False)
        self.subjects.setText(f'Choose athletes · {self.reference.count()}/{len(docs)}');self.subjects.setToolTip('Choose exactly which athletes and attempts to compare in every comparison view')
    def choose_subjects(self):
        dialog=QDialog(self);dialog.setWindowTitle('Choose athletes to compare');dialog.resize(540,420);box=QVBoxLayout(dialog)
        note=QLabel('Select the athletes and attempts you want to compare. The reference must be one of the selected attempts. Side by side displays up to 16 videos.');note.setWordWrap(True);box.addWidget(note);listing=QListWidget();listing.setAccessibleName('Athletes and attempts to compare');box.addWidget(listing,1)
        for d in self.documents:
            if d['route']!=self.route.currentText():continue
            key=identity(d);item=QListWidgetItem(f"{d['climber']} · attempt {d['attempt']} · {d['source']['file']}");item.setData(Qt.ItemDataRole.UserRole,key);item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable);item.setCheckState(Qt.CheckState.Checked if self.selected is None or key in self.selected else Qt.CheckState.Unchecked);listing.addItem(item)
        row=QHBoxLayout()
        for text,state in [('Select all',Qt.CheckState.Checked),('Clear selection',Qt.CheckState.Unchecked)]:
            b=QPushButton(text);b.clicked.connect(lambda checked=False,s=state:[listing.item(i).setCheckState(s) for i in range(listing.count())]);row.addWidget(b)
        box.addLayout(row);buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Apply|QDialogButtonBox.StandardButton.Cancel);buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(dialog.accept);buttons.rejected.connect(dialog.reject);box.addWidget(buttons)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self.set_selection(listing.item(i).data(Qt.ItemDataRole.UserRole) for i in range(listing.count()) if listing.item(i).checkState()==Qt.CheckState.Checked)
    def chosen(self):
        ref=self.reference.currentData()
        docs=[d for d in self.documents if d['route']==self.route.currentText() and (self.selected is None or identity(d) in self.selected)]
        return sorted(docs,key=lambda d:identity(d)!=ref)
