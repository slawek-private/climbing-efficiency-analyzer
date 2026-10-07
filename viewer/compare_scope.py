"""Shared route, attempt and checkpoint selection for every comparison view."""
from PySide6.QtCore import Signal,Qt
from PySide6.QtWidgets import QWidget,QHBoxLayout,QLabel,QComboBox,QPushButton,QDialog,QVBoxLayout,QTreeWidget,QTreeWidgetItem,QDialogButtonBox,QCheckBox,QSizePolicy
from . import identity as identities


def identity(doc):
    return doc.get('attempt_id') or '|'.join((doc['source']['sha256'],doc['climber'],doc['attempt']))


class CompareScope(QWidget):
    changed=Signal()
    def __init__(self):
        super().__init__();self.documents=[];self.selected=None;self.organisation=identities.empty();self.session_id='';self.current=None
        box=QVBoxLayout(self);box.setContentsMargins(0,0,0,0);top=QHBoxLayout();box.addLayout(top);layout=QHBoxLayout();box.addLayout(layout)
        self.intent=QComboBox()
        for label,value in [('Training · athlete progress','personal'),('Training · team review','team'),('Competition · round','competition')]:self.intent.addItem(label,value)
        self.athlete=QComboBox();self.athlete.setAccessibleName('Athlete for training progress');self.history=QCheckBox('Include previous training sessions')
        self.team=QComboBox();self.team.addItem('All session athletes','');self.team.setAccessibleName('Optional team roster filter')
        self.history.setToolTip('Explicitly widen to training sessions on this route version, then choose exact attempts. Competition is excluded.')
        top.addWidget(self.intent);top.addWidget(self.athlete,1);top.addWidget(self.team,1);top.addWidget(self.history)
        self.route=QComboBox();self.reference=QComboBox();self.point=QComboBox();self.subjects=QPushButton('Choose athletes & attempts…')
        for control in (self.athlete,self.team,self.route,self.reference,self.point):
            control.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon);control.setMinimumContentsLength(10);control.setMinimumWidth(90);control.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
        for name,control in [('Route',self.route),('Reference',self.reference),('Checkpoint',self.point)]:layout.addWidget(QLabel(name));layout.addWidget(control,1)
        layout.addWidget(self.subjects);self.subjects.clicked.connect(self.choose_subjects)
        self.intent.currentIndexChanged.connect(self.scope_changed);self.athlete.currentIndexChanged.connect(self.scope_changed);self.history.toggled.connect(self.scope_changed)
        self.team.currentIndexChanged.connect(self.scope_changed)
        self.route.currentIndexChanged.connect(self.route_changed);self.reference.currentIndexChanged.connect(self.changed);self.point.currentIndexChanged.connect(self.changed)
    def set_context(self,organisation,session_id,current):
        changed=session_id!=self.session_id;self.organisation=organisation;self.session_id=session_id;self.current=current
        session=identities.entry(organisation,'sessions',session_id);self.intent.setEnabled(bool(session));self.intent.blockSignals(True)
        if changed or not session:
            self.intent.setCurrentIndex(2 if session and session['kind']=='competition' else 0)
            self.selected=set() if session and session['kind']=='competition' else None
        for i in range(self.intent.count()):self.intent.model().item(i).setEnabled(bool(session) and ((i==2)==(session['kind']=='competition')))
        self.intent.blockSignals(False)
    def eligible(self):
        if not self.session_id:return [d for d in self.documents if not identities.assigned(d)]
        docs=[];mode=self.intent.currentData()
        for d in self.documents:
            a=d.get('assignment')
            if not a:continue
            session=a['session']
            if self.history.isChecked() and mode!='competition':
                if session['kind']!='training':continue
            elif session['id']!=self.session_id:continue
            if mode=='personal' and a['athlete']['id']!=self.athlete.currentData():continue
            if mode=='team' and self.team.currentData() and self.team.currentData() not in a['athlete']['teams']:continue
            docs.append(d)
        return docs
    def candidates(self):return [d for d in self.eligible() if identities.route_key(d)==self.route.currentData()]
    def set_documents(self,documents):
        self.documents=documents;old=self.athlete.currentData();self.athlete.blockSignals(True);self.athlete.clear()
        ids={d['assignment']['athlete']['id'] for d in documents if d.get('assignment',{}).get('session',{}).get('id')==self.session_id}
        for a in self.organisation['athletes']:
            if a['id'] in ids:self.athlete.addItem(identities.athlete_label(a),a['id'])
        preferred=old or (self.current or {}).get('assignment',{}).get('athlete',{}).get('id');self.athlete.setCurrentIndex(max(0,self.athlete.findData(preferred)));self.athlete.blockSignals(False)
        old_team=self.team.currentData();self.team.blockSignals(True);self.team.clear();self.team.addItem('All session athletes','')
        for team in sorted({team for d in documents if identities.assigned(d) for team in d['assignment']['athlete']['teams']}):self.team.addItem(team,team)
        self.team.setCurrentIndex(max(0,self.team.findData(old_team)));self.team.blockSignals(False);self.rebuild_routes()
    def scope_changed(self):self.selected=set() if self.intent.currentData() in ('team','competition') and self.session_id else None;self.rebuild_routes();self.changed.emit()
    def rebuild_routes(self):
        mode=self.intent.currentData();self.athlete.setVisible(bool(self.session_id) and mode=='personal');self.team.setVisible(bool(self.session_id) and mode=='team');self.history.setVisible(bool(self.session_id) and mode!='competition')
        previous=self.route.currentData();self.route.blockSignals(True);self.route.clear();seen=set()
        for d in self.eligible():
            key=identities.route_key(d)
            if key not in seen:self.route.addItem(d['route'],key);seen.add(key)
        self.route.setCurrentIndex(max(0,self.route.findData(previous)));self.route.blockSignals(False);self.rebuild()
    def route_changed(self):self.selected=set() if self.session_id and self.intent.currentData() in ('team','competition') else None;self.rebuild();self.changed.emit()
    def rebuild(self):
        docs=self.candidates()
        self.update_reference(docs)
        old=self.point.currentText();self.point.blockSignals(True);self.point.clear();self.point.addItem('Climb start');self.point.addItems(sorted({p['name'] for d in docs for p in d.get('checkpoints',[])}));self.point.setCurrentIndex(max(0,self.point.findText(old)));self.point.blockSignals(False)
    def set_selection(self,keys):
        self.selected=set(keys);self.rebuild();self.changed.emit()
    def update_reference(self,docs):
        old=self.reference.currentData();self.reference.blockSignals(True);self.reference.clear()
        for d in docs:
            if self.selected is None or identity(d) in self.selected:self.reference.addItem(f"{d['climber']} · {d['attempt']} · "+identities.context(d),identity(d))
        self.reference.setCurrentIndex(max(0,self.reference.findData(old)));self.reference.blockSignals(False)
        self.reference.setToolTip(self.reference.currentText());self.route.setToolTip(self.route.currentText())
        chosen=[d for d in docs if self.selected is None or identity(d) in self.selected];people={d.get('assignment',{}).get('athlete',{}).get('id',d['climber']) for d in chosen}
        self.subjects.setText(f'{len(people)} athletes · {len(chosen)} attempts…');self.subjects.setToolTip('Choose athletes and exact attempts within this session and route version.')
    def choose_subjects(self):
        dialog=QDialog(self);dialog.setWindowTitle('Choose athletes & attempts');dialog.resize(680,460);box=QVBoxLayout(dialog)
        note=QLabel(self.description()+'. Select attempts under each athlete. The reference must be selected. Side by side displays up to 16 attempts.');note.setWordWrap(True);box.addWidget(note)
        listing=QTreeWidget();listing.setHeaderLabels(['Athlete / attempt / session','Recording']);listing.setAccessibleName('Athletes and attempts to compare');box.addWidget(listing,1);groups={};items=[]
        for d in self.candidates():
            person=d.get('assignment',{}).get('athlete',{}).get('id',d['climber'])
            if person not in groups:
                parent=QTreeWidgetItem([d['climber']]);parent.setFlags(parent.flags()|Qt.ItemFlag.ItemIsUserCheckable|Qt.ItemFlag.ItemIsAutoTristate);listing.addTopLevelItem(parent);groups[person]=parent
            key=identity(d);item=QTreeWidgetItem(groups[person],[f"Attempt {d['attempt']} · "+identities.context(d),d['source']['file']]);item.setData(0,Qt.ItemDataRole.UserRole,key);item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable);item.setCheckState(0,Qt.CheckState.Checked if self.selected is None or key in self.selected else Qt.CheckState.Unchecked);items.append(item)
        listing.expandAll();listing.resizeColumnToContents(0)
        row=QHBoxLayout()
        for text,state in [('Select all',Qt.CheckState.Checked),('Clear selection',Qt.CheckState.Unchecked)]:
            b=QPushButton(text);b.clicked.connect(lambda checked=False,s=state:[item.setCheckState(0,s) for item in items]);row.addWidget(b)
        box.addLayout(row);buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Apply|QDialogButtonBox.StandardButton.Cancel);buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(dialog.accept);buttons.rejected.connect(dialog.reject);box.addWidget(buttons)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self.set_selection(item.data(0,Qt.ItemDataRole.UserRole) for item in items if item.checkState(0)==Qt.CheckState.Checked)
    def chosen(self):
        ref=self.reference.currentData()
        docs=[d for d in self.candidates() if self.selected is None or identity(d) in self.selected]
        return sorted(docs,key=lambda d:identity(d)!=ref)
    def description(self):
        session=identities.entry(self.organisation,'sessions',self.session_id)
        if not session:return 'Unorganised drafts · assign identities before reviewed reporting'
        return identities.session_label(session)+(' · '+session['event']+' / '+session['round']+' · annotation timing, not official results' if session['kind']=='competition' else ' · '+self.intent.currentText()+(' · previous training sessions included' if self.history.isChecked() else ''))
