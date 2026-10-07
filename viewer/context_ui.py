"""Native session, roster, intake and clip-decision flows."""
import copy
from pathlib import Path
from uuid import uuid4
from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (QWidget,QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QPushButton,
    QComboBox,QLineEdit,QDateEdit,QDialogButtonBox,QTableWidget,QTableWidgetItem,QCheckBox,
    QTreeWidget,QTreeWidgetItem,QMenu,QInputDialog,QSizePolicy)
from . import identity
from .labels import save


def persist(w):
    try:w.workspace.save();w.workspace_error=None;return True
    except OSError as error:
        w.workspace_error='Workspace not saved: '+str(error);w.refresh_live();w.error(error);return False


def combo(data, group, current='', placeholder='Choose…'):
    control=QComboBox();control.addItem(placeholder,'')
    label={'athletes':identity.athlete_label,'sessions':identity.session_label,'routes':identity.route_label}[group]
    for item in data[group]:control.addItem(label(item),item['id'])
    control.setCurrentIndex(max(0,control.findData(current)))
    return control


def create_athlete(w, existing=None):
    dialog=QDialog(w);dialog.setWindowTitle('Edit athlete' if existing else 'Add athlete');form=QFormLayout(dialog)
    name=QLineEdit(existing['name'] if existing else '');label=QLineEdit(existing.get('label','') if existing else '')
    teams=QLineEdit(', '.join(existing.get('teams',[])) if existing else '')
    form.addRow('Name / anonymous label',name);form.addRow('Distinguishing label (e.g. club)',label);form.addRow('Teams (optional, comma separated)',teams)
    note=QLabel('Names do not merge people. Use a distinguishing label for people with the same name.');note.setWordWrap(True);form.addRow(note)
    error=QLabel();error.setWordWrap(True);form.addRow(error)
    buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);form.addRow(buttons)
    def accept():
        if not name.text().strip():error.setText('Enter a name or a descriptive anonymous label.');return
        duplicates=[a for a in w.workspace.organisation['athletes'] if a is not existing and a['name'].casefold()==name.text().strip().casefold()]
        if duplicates and (not label.text().strip() or any(a['label'].casefold()==label.text().strip().casefold() for a in duplicates)):
            error.setText('This name already exists. Add a unique distinguishing label, or cancel and choose the existing athlete.');return
        dialog.accept()
    buttons.accepted.connect(accept);buttons.rejected.connect(dialog.reject)
    if dialog.exec()!=QDialog.DialogCode.Accepted:return None
    values=dict(name=name.text().strip(),label=label.text().strip(),teams=list(dict.fromkeys(t.strip() for t in teams.text().split(',') if t.strip())))
    item=existing
    if item:item.update(values)
    else:item=identity.athlete(w.workspace.organisation,**values)
    return item if persist(w) else None


def create_route(w):
    dialog=QDialog(w);dialog.setWindowTitle('Add route version');form=QFormLayout(dialog)
    name=QLineEdit();version=QLineEdit();version.setPlaceholderText('e.g. set 5 October 2026');discipline=QComboBox();discipline.addItems(['lead','boulder','speed','other'])
    form.addRow('Route name / grade',name);form.addRow('Version / setting date',version);form.addRow('Discipline',discipline)
    note=QLabel('Reuse this version while the physical route is unchanged. A reset needs a new version, even when the name stays the same.');note.setWordWrap(True);form.addRow(note)
    buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);form.addRow(buttons);error=QLabel();form.addRow(error)
    def accept():
        if not name.text().strip() or not version.text().strip():error.setText('Enter a name and a route version.');return
        dialog.accept()
    buttons.accepted.connect(accept);buttons.rejected.connect(dialog.reject)
    if dialog.exec()!=QDialog.DialogCode.Accepted:return None
    item=identity.route(w.workspace.organisation,name.text(),version.text(),discipline.currentText());return item if persist(w) else None


def create_session(w):
    dialog=QDialog(w);dialog.setWindowTitle('New session');form=QFormLayout(dialog)
    kind=QComboBox();kind.addItem('Training','training');kind.addItem('Competition','competition')
    name=QLineEdit();day=QDateEdit(QDate.currentDate());day.setCalendarPopup(True);day.setDisplayFormat('dd MMM yyyy')
    team=QLineEdit();event=QLineEdit();round_name=QLineEdit();goal=QLineEdit()
    for title,field in [('Purpose',kind),('Session name',name),('Date',day),('Team (optional)',team),('Event',event),('Round',round_name),('Training goal (optional)',goal)]:form.addRow(title,field)
    def purpose():
        competition=kind.currentData()=='competition'
        for field in (event,round_name):field.setEnabled(competition)
        goal.setEnabled(not competition)
    kind.currentIndexChanged.connect(purpose);purpose()
    error=QLabel();error.setWordWrap(True);form.addRow(error)
    buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);form.addRow(buttons)
    def accept():
        previous=w.workspace.session_id;item=None
        try:
            item=identity.session(w.workspace.organisation,name.text(),kind.currentData(),day.date().toString('yyyy-MM-dd'),team.text(),event.text() if event.isEnabled() else '',round_name.text() if round_name.isEnabled() else '',goal.text() if goal.isEnabled() else '')
            w.workspace.session_id=item['id'];w.workspace.save();dialog.accept()
        except (ValueError,OSError) as e:
            if item:w.workspace.organisation['sessions'].remove(item)
            w.workspace.session_id=previous;error.setText(str(e))
    buttons.accepted.connect(accept);buttons.rejected.connect(dialog.reject)
    if dialog.exec()==QDialog.DialogCode.Accepted:w.refresh_collection();w.library.render();return True
    return False


class AssignmentDialog(QDialog):
    """Rows are (path, existing document or None). No automatic identity inference."""
    def __init__(self,w,rows,reassign=False):
        super().__init__(w);self.w=w;self.rows=rows;self.queued=False;self.result_assignments=[]
        self.setWindowTitle('Reassign attempt' if reassign else 'Assign videos / attempts');self.resize(850,500)
        box=QVBoxLayout(self);note=QLabel('Choose the session, athlete and route version for every row. Files with multiple athletes need a separate assigned attempt for each climb. No names are inferred from filenames.');note.setWordWrap(True);box.addWidget(note)
        self.session=combo(w.workspace.organisation,'sessions',w.workspace.session_id, 'Choose session…');self.session.setAccessibleName('Session for these attempts')
        bar=QHBoxLayout();bar.addWidget(QLabel('Session'));bar.addWidget(self.session,1)
        new=QPushButton('New session…');new.clicked.connect(self.new_session);bar.addWidget(new);box.addLayout(bar)
        bar=QHBoxLayout();self.bulk=combo(w.workspace.organisation,'athletes');bar.addWidget(self.bulk,1)
        apply=QPushButton('Assign to checked rows');apply.clicked.connect(self.bulk_assign);bar.addWidget(apply)
        for text,callback in [('Add athlete…',self.add_athlete),('Add route…',self.add_route)]:
            button=QPushButton(text);button.clicked.connect(callback);bar.addWidget(button)
        box.addLayout(bar)
        self.table=QTableWidget(len(rows),4);self.table.setHorizontalHeaderLabels(['Select','Recording / existing attempt','Athlete · required','Route version · required'])
        self.table.verticalHeader().hide();self.table.horizontalHeader().setStretchLastSection(True);self.table.setColumnWidth(1,260);self.table.setColumnWidth(2,210);box.addWidget(self.table,1)
        self.athletes=[];self.routes=[]
        for n,(path,doc) in enumerate(rows):
            check=QCheckBox();check.setChecked(True);check.setAccessibleName('Select '+Path(path).name);self.table.setCellWidget(n,0,check)
            description=Path(path).name+(' / '+doc['climber']+' · attempt '+doc['attempt'] if doc else '')
            item=QTableWidgetItem(description);item.setFlags(item.flags()&~Qt.ItemFlag.ItemIsEditable);self.table.setItem(n,1,item)
            a=doc.get('assignment',{}) if reassign and doc else {}
            athlete=combo(w.workspace.organisation,'athletes',a.get('athlete',{}).get('id',''),'Choose athlete…')
            route=combo(w.workspace.organisation,'routes',a.get('route',{}).get('id',''),'Choose route…')
            athlete.setAccessibleName('Athlete for '+description);route.setAccessibleName('Route for '+description)
            self.athletes.append(athlete);self.routes.append(route);self.table.setCellWidget(n,2,athlete);self.table.setCellWidget(n,3,route)
            athlete.currentIndexChanged.connect(self.check);route.currentIndexChanged.connect(self.check)
            if a:self.session.setCurrentIndex(max(0,self.session.findData(a['session']['id'])))
        self.status=QLabel();self.status.setWordWrap(True);box.addWidget(self.status)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);self.save_button=buttons.button(QDialogButtonBox.StandardButton.Save);self.save_button.setText('Confirm assignment')
        if not reassign and all(doc is None for _,doc in rows):
            queue=buttons.addButton('Queue files · assign later',QDialogButtonBox.ButtonRole.ActionRole);queue.clicked.connect(self.queue)
        buttons.accepted.connect(self.accept_assignments);buttons.rejected.connect(self.reject);box.addWidget(buttons);self.session.currentIndexChanged.connect(self.check);self.check()
    def refill(self):
        data=self.w.workspace.organisation
        for field,group in [(self.session,'sessions'),(self.bulk,'athletes')]+[(c,'athletes') for c in self.athletes]+[(c,'routes') for c in self.routes]:
            old=field.currentData();field.blockSignals(True);field.clear();other=combo(data,group,old);field.addItem(other.itemText(0),'')
            for i in range(1,other.count()):field.addItem(other.itemText(i),other.itemData(i))
            field.setCurrentIndex(max(0,field.findData(old)));field.blockSignals(False)
        self.check()
    def new_session(self):
        if create_session(self.w):self.refill();self.session.setCurrentIndex(self.session.findData(self.w.workspace.session_id))
    def add_athlete(self):
        item=create_athlete(self.w)
        if item:self.refill();self.bulk.setCurrentIndex(self.bulk.findData(item['id']))
    def add_route(self):
        item=create_route(self.w)
        if item:
            self.refill()
            for route in self.routes:
                if not route.currentData():route.setCurrentIndex(route.findData(item['id']))
    def bulk_assign(self):
        if not self.bulk.currentData():return
        for n,athlete in enumerate(self.athletes):
            if self.table.cellWidget(n,0).isChecked():athlete.setCurrentIndex(athlete.findData(self.bulk.currentData()))
    def check(self):
        if not hasattr(self,'save_button'):return
        remaining=sum(not a.currentData() or not r.currentData() for a,r in zip(self.athletes,self.routes))
        self.save_button.setEnabled(bool(self.session.currentData()) and not remaining)
        self.status.setText('Choose a session.' if not self.session.currentData() else f'{remaining} row(s) need athlete / route assignment.' if remaining else 'Every row is assigned. Confirm to continue.')
    def accept_assignments(self):
        if not self.save_button.isEnabled():return
        self.result_assignments=[(path,doc,athlete.currentData(),self.session.currentData(),route.currentData()) for (path,doc),athlete,route in zip(self.rows,self.athletes,self.routes)]
        self.accept()
    def queue(self):self.queued=True;self.reject()


def intake(w,paths):
    dialog=AssignmentDialog(w,[(p,None) for p in paths])
    if dialog.exec()!=QDialog.DialogCode.Accepted:return dialog.queued
    for path,_,athlete,session,route in dialog.result_assignments:
        w.workspace.assignments[str(Path(path).resolve())]={'athlete':athlete,'session':session,'route':route}
    w.workspace.session_id=dialog.session.currentData();return persist(w)


def apply_assignments(w,dialog):
    try:_apply_assignments(w,dialog)
    except OSError as error:w.workspace_error='Assignment not saved: '+str(error);w.refresh_live();w.error(error)


def _apply_assignments(w,dialog):
    for path,old,athlete,session,route in dialog.result_assignments:
        d=copy.deepcopy(old);d.setdefault('attempt_id',uuid4().hex);identity.assign(d,w.workspace.organisation,athlete,session,route)
        if w.document() and w.document().get('attempt_id')==old.get('attempt_id') and w.video_path and str(w.video_path.resolve())==path:
            w.workspace.session_id=session
            w.commit(d)
            if not w.autosave():return
        else:
            state=next((s for p,s in list(w.workspace.states.items())+[(e['path'],e['state']) for e in w.workspace.attempts] if p==path and s['document'].get('attempt_id')==old.get('attempt_id')),None)
            if state:
                if state.get('label_path'):save(d,Path(state['label_path']))
                state['document']=d;w.session_histories.pop(path,None)
        w.workspace.assignments.pop(path,None)
    w.workspace.save();w.refresh_collection();w.refresh_live();w.library.render()


def reassign(w):
    if not w.document() or not w.flush_autosave():return
    dialog=AssignmentDialog(w,[(str(w.video_path.resolve()),w.document())],True)
    if dialog.exec()==QDialog.DialogCode.Accepted:apply_assignments(w,dialog)


def organise(w):
    if not w.flush_autosave():return
    rows=[(p,s['document']) for p,s in list(w.workspace.states.items())+[(e['path'],e['state']) for e in w.workspace.attempts] if not identity.assigned(s['document'])]
    if not rows:w.statusBar().showMessage('All measured attempts are assigned.',5000);return
    dialog=AssignmentDialog(w,rows)
    if dialog.exec()==QDialog.DialogCode.Accepted:apply_assignments(w,dialog)


class SessionBar(QWidget):
    def __init__(self,w):
        super().__init__();self.w=w;line=QHBoxLayout(self);line.setContentsMargins(0,0,0,0)
        self.sessions=QComboBox();self.sessions.setAccessibleName('Current session');self.sessions.setMinimumWidth(200);self.sessions.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed);line.addWidget(self.sessions,1)
        new=QPushButton('New session…');new.clicked.connect(lambda:create_session(w));line.addWidget(new)
        manage=QPushButton('Athletes & sessions ▾');menu=QMenu(manage);manage.setMenu(menu);line.addWidget(manage)
        for title,callback in [('Add athlete…',lambda:self.add()),('Rename / edit athlete…',self.edit),('Athlete history…',self.history),('Add route version…',lambda:create_route(w)),('Organise existing attempts…',lambda:organise(w))]:menu.addAction(title,callback)
        self.sessions.currentIndexChanged.connect(self.changed)
        self.pending=QPushButton();self.pending.clicked.connect(self.review_pending);line.addWidget(self.pending)
    def refresh(self):
        self.sessions.blockSignals(True);self.sessions.clear();self.sessions.addItem('Unorganised drafts','')
        for item in self.w.workspace.organisation['sessions']:self.sessions.addItem(identity.session_label(item),item['id'])
        self.sessions.setCurrentIndex(max(0,self.sessions.findData(self.w.workspace.session_id)));self.sessions.blockSignals(False)
        count=sum(len(identity.unanswered(d)) for d in self.w.workspace.documents())
        self.pending.setText(f'{count} clip answer(s) needed');self.pending.setVisible(count>0)
    def changed(self):
        self.w.workspace.session_id=self.sessions.currentData() or ''
        if persist(self.w):self.w.refresh_collection();self.w.library.activate()
    def review_pending(self):
        dialog=QDialog(self.w);dialog.setWindowTitle('Clips that need a method');dialog.resize(760,400);box=QVBoxLayout(dialog)
        note=QLabel('Draft timing is saved. Double-click a clip to open its exact source frame and choose Direct, Two-stage or Cannot tell.');note.setWordWrap(True);box.addWidget(note)
        tree=QTreeWidget();tree.setHeaderLabels(['Athlete / attempt / clip','Session / route']);box.addWidget(tree)
        for path,state in list(self.w.workspace.states.items())+[(e['path'],e['state']) for e in self.w.workspace.attempts]:
            d=state['document']
            for e in identity.unanswered(d):
                item=QTreeWidgetItem([d['climber']+f" · attempt {d['attempt']} · QD {e['target'] or '?'} · {e['hand']}",identity.context(d)])
                item.setData(0,Qt.ItemDataRole.UserRole,(path,d,e));tree.addTopLevelItem(item)
        def open_item(item,col):
            path,d,e=item.data(0,Qt.ItemDataRole.UserRole);dialog.accept();self.w.pending_clip_review=e['id'];self.w.open_comparison_document(path,d,e['start']['frame'])
        tree.itemDoubleClicked.connect(open_item);tree.resizeColumnToContents(0)
        close=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);close.rejected.connect(dialog.reject);box.addWidget(close);dialog.exec()
    def add(self):
        create_athlete(self.w);self.w.refresh_collection()
    def edit(self):
        values=self.w.workspace.organisation['athletes']
        if not values:return self.add()
        names=[identity.athlete_label(a) for a in values];name,ok=QInputDialog.getItem(self,'Edit athlete','Athlete',names,0,False)
        if not ok:return
        if create_athlete(self.w,values[names.index(name)]):
            try:
                for path,state in list(self.w.workspace.states.items())+[(e['path'],e['state']) for e in self.w.workspace.attempts]:
                    d=copy.deepcopy(state['document']);identity.refresh(d,self.w.workspace.organisation)
                    if state.get('label_path'):save(d,Path(state['label_path']))
                    state['document']=d
                if self.w.document():
                    d=copy.deepcopy(self.w.document());identity.refresh(d,self.w.workspace.organisation);self.w.commit(d)
                self.w.session_histories={};self.w.workspace.save();self.w.refresh_collection()
            except OSError as error:self.w.workspace_error='Athlete changes not fully saved: '+str(error);self.w.refresh_live();self.w.error(error)
    def history(self):
        dialog=QDialog(self.w);dialog.setWindowTitle('Athlete history');dialog.resize(800,450);box=QVBoxLayout(dialog)
        picker=combo(self.w.workspace.organisation,'athletes');box.addWidget(picker);tree=QTreeWidget();tree.setHeaderLabels(['Session / route / attempt','Recording']);box.addWidget(tree)
        def update():
            tree.clear()
            for path,state in list(self.w.workspace.states.items())+[(e['path'],e['state']) for e in self.w.workspace.attempts]:
                d=state['document']
                if d.get('assignment',{}).get('athlete',{}).get('id')!=picker.currentData():continue
                item=QTreeWidgetItem([identity.context(d)+' · attempt '+d['attempt'],Path(path).name]);item.setData(0,Qt.ItemDataRole.UserRole,(path,d,state.get('frame',0)));tree.addTopLevelItem(item)
        def open_item(item,col):
            path,d,frame=item.data(0,Qt.ItemDataRole.UserRole);dialog.accept();self.w.open_comparison_document(path,d,frame)
        picker.currentIndexChanged.connect(update);tree.itemDoubleClicked.connect(open_item)
        close=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);close.rejected.connect(dialog.reject);box.addWidget(close)
        if picker.count()>1:picker.setCurrentIndex(1)
        update();dialog.exec()


class AttemptNavigation(QComboBox):
    def __init__(self,w):
        super().__init__();self.w=w;self.setAccessibleName('Athletes and attempts in this session');self.setMinimumWidth(100);self.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed);self.activated.connect(self.open)
    def refresh(self):
        self.blockSignals(True);self.clear();groups={}
        current=self.w.document().get('attempt_id') if self.w.document() else None;selected=-1
        for path,state in list(self.w.workspace.states.items())+[(e['path'],e['state']) for e in self.w.workspace.attempts]:
            d=state['document'];a=d.get('assignment',{})
            if a.get('session',{}).get('id','')!=self.w.workspace.session_id:continue
            groups.setdefault(a.get('athlete',{}).get('id',d['climber']),[]).append((path,state))
        for records in groups.values():
            for path,state in records:
                d=state['document'];self.addItem(d['climber']+' · attempt '+d['attempt']+' · '+d['route']+' · '+Path(path).name,(path,d,state.get('frame',0)))
                if d.get('attempt_id')==current:selected=self.count()-1
        self.setCurrentIndex(selected);self.setPlaceholderText('Choose an athlete’s attempt');self.blockSignals(False)
    def open(self,index):
        item=self.itemData(index)
        if item:self.w.open_comparison_document(*item)


class ClipReview(QWidget):
    def __init__(self,w):
        super().__init__();self.w=w;self.event_id=None;root=QVBoxLayout(self);root.setContentsMargins(0,0,0,0)
        self.toggle=QPushButton('Clipping review ▸');self.toggle.setCheckable(True);root.addWidget(self.toggle)
        self.body=QWidget();box=QVBoxLayout(self.body);box.setContentsMargins(0,0,0,0);box.setSpacing(6);root.addWidget(self.body);self.body.hide();self.toggle.toggled.connect(self.body.setVisible)
        self.queue=QComboBox();self.queue.setAccessibleName('Clip method review queue');self.queue.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed);self.queue.currentIndexChanged.connect(self.select);box.addWidget(self.queue)
        self.title=QLabel();self.title.setWordWrap(True);box.addWidget(self.title)
        line=QHBoxLayout();self.buttons={}
        for label,method in [('Direct','direct'),('Two-stage\nrope in mouth','mouth'),('Cannot tell','unknown')]:
            button=QPushButton(label);button.setCheckable(True);button.setAutoExclusive(True);button.setAccessibleName(label.replace('\n',' '));button.clicked.connect(lambda checked=False,m=method:self.answer(m));line.addWidget(button);self.buttons[method]=button
        box.addLayout(line);self.reason=QComboBox();self.reason.setAccessibleName('Reason clipping method cannot be seen')
        for text,value in [('Choose reason…',''),('Hands / rope hidden','hidden'),('Camera misses the method','camera'),('Visible but unclear','unclear')]:self.reason.addItem(text,value)
        self.reason.currentIndexChanged.connect(self.reason_changed);box.addWidget(self.reason)
        line=QHBoxLayout();jump=QPushButton('Jump to this clip');jump.clicked.connect(self.jump);line.addWidget(jump)
        gap=QPushButton('Clip not recorded…');gap.clicked.connect(self.gap);line.addWidget(gap);box.addLayout(line)
        self.gaps=QComboBox();self.gaps.setAccessibleName('Clip visibility gaps');box.addWidget(self.gaps)
        line=QHBoxLayout();jump_gap=QPushButton('Jump to gap note');jump_gap.clicked.connect(self.jump_gap);line.addWidget(jump_gap)
        remove=QPushButton('Remove gap note');remove.clicked.connect(self.remove_gap);line.addWidget(remove);self.gap_actions=QWidget();self.gap_actions.setLayout(line);box.addWidget(self.gap_actions)
        self.hint=QLabel();self.hint.setWordWrap(True);box.addWidget(self.hint)
    def current(self):return next((e for e in (self.w.document() or {}).get('events',[]) if e['id']==self.event_id and e['kind']=='clip'),None)
    def refresh(self,document):
        fingerprint=(document.get('attempt_id'),self.event_id,repr(document.get('events',[])),repr(document.get('clip_gaps',[]))) if document else None
        if getattr(self,'fingerprint',object())==fingerprint:return
        self.fingerprint=fingerprint
        events=[e for e in (document or {}).get('events',[]) if e['kind']=='clip'];pending=identity.unanswered(document) if document else []
        events=sorted(events,key=lambda e:(identity.clip_answered(e),e['start']['seconds']))
        count=len(pending)
        self.toggle.setText(f'Clipping review · {count} answer(s) needed' if count else 'Clipping review · methods answered' if events else 'Clipping review / visibility gaps ▸')
        if count>getattr(self,'pending_count',0):self.toggle.setChecked(True)
        if not count and getattr(self,'pending_count',0):self.toggle.setChecked(False)
        self.pending_count=count
        old=self.event_id;self.queue.blockSignals(True);self.queue.clear()
        for e in events:self.queue.addItem(f"QD {e['target'] or '?'} · {e['hand']} · "+({'direct':'Direct','mouth':'Two-stage','unknown':'Cannot tell'}.get(e.get('clip_method'),'Answer needed') if identity.clip_answered(e) else 'Answer needed'),e['id'])
        self.queue.setCurrentIndex(max(0,self.queue.findData(old)));self.event_id=self.queue.currentData();self.queue.blockSignals(False)
        e=self.current();self.title.setText(f"QD {e['target'] or '?'} · {e['hand'].capitalize()} hand · how was it clipped?" if e else 'Complete a clip timer to choose its method.')
        self.queue.setVisible(bool(e))
        for button in self.buttons.values():button.setAutoExclusive(False)
        for method,button in self.buttons.items():button.setEnabled(bool(e));button.setChecked(bool(e and e.get('clip_method')==method))
        for button in self.buttons.values():button.setAutoExclusive(True)
        self.reason.blockSignals(True);self.reason.setCurrentIndex(max(0,self.reason.findData(e.get('clip_reason','') if e else '')));self.reason.blockSignals(False);self.reason.setVisible(bool(e and e.get('clip_method')=='unknown'))
        self.hint.setText(f'{len(pending)} clip method(s) need an answer. Timing is saved; answer before finishing review.' if pending else 'Clip methods answered. Cannot tell stays unknown; gap notes never create a duration.')
        self.gaps.clear()
        for gap in (document or {}).get('clip_gaps',[]):self.gaps.addItem(f"QD {gap['target'] or '?'} · {gap['visibility']} · {gap['notes']}",gap['id'])
        self.gaps.setVisible(self.gaps.count()>0);self.gap_actions.setVisible(self.gaps.count()>0)
        self.setVisible(bool(document))
    def select(self):self.event_id=self.queue.currentData();self.refresh(self.w.document())
    def answer(self,method):
        if not self.current():return
        if self.current().get('clip_method')==method:return
        d=copy.deepcopy(self.w.document());d['schema_version']='1.4.0'
        for e in d['events']:
            if e['id']==self.event_id:
                e['clip_method']=method;e.pop('clip_reason',None)
                if method=='unknown':e['clip_reason']=''
        d['reviewed']['clips']=False;self.w.commit(d)
    def reason_changed(self):
        e=self.current()
        if not e or e.get('clip_method')!='unknown':return
        d=copy.deepcopy(self.w.document())
        for event in d['events']:
            if event['id']==self.event_id:event['clip_reason']=self.reason.currentData()
        d['reviewed']['clips']=False;self.w.commit(d)
    def jump(self):
        e=self.current()
        if e:self.w.pause();self.w.show_frame(e['start']['frame'])
    def gap(self):
        if not self.w.ready_to_mark():return
        visibility,ok=QInputDialog.getItem(self,'Clip visibility gap','What is missing?',['Whole clip not recorded','Only part of the clip visible'],0,False)
        if not ok:return
        text,ok=QInputDialog.getText(self,'Clip visibility gap','Describe what the footage misses. No timing will be invented.')
        if not ok or not text.strip():return
        target,ok=QInputDialog.getInt(self,'Clip visibility gap','Known quickdraw number (0 = unknown)',0,0,9999)
        if not ok:return
        d=copy.deepcopy(self.w.document());d['schema_version']='1.4.0';d.setdefault('clip_gaps',[]).append({'id':uuid4().hex,'target':target or None,'point':self.w.reader.point(self.w.frame_number),'visibility':'missing' if visibility.startswith('Whole') else 'partial','notes':text.strip()});d['reviewed']['clips']=False;self.w.commit(d)
    def jump_gap(self):
        gap=next((g for g in self.w.document().get('clip_gaps',[]) if g['id']==self.gaps.currentData()),None)
        if gap:self.w.pause();self.w.show_frame(gap['point']['frame'])
    def remove_gap(self):
        d=copy.deepcopy(self.w.document());d['clip_gaps']=[g for g in d.get('clip_gaps',[]) if g['id']!=self.gaps.currentData()];d['reviewed']['clips']=False;self.w.commit(d)


def report_permission(w,documents):
    issues=[d['climber']+' · '+d['attempt']+': '+', '.join(identity.review_issues(d)) for d in documents if identity.review_issues(d)]
    if not issues:return True
    dialog=QDialog(w);dialog.setWindowTitle('Report review');dialog.resize(620,350);box=QVBoxLayout(dialog)
    note=QLabel('These attempts have an incomplete review. Fix them before a reviewed report, or explicitly export a draft.\n\n'+'\n\n'.join(issues));note.setWordWrap(True);box.addWidget(note)
    buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel);draft=buttons.addButton('Export clearly marked draft',QDialogButtonBox.ButtonRole.AcceptRole);draft.clicked.connect(dialog.accept);buttons.rejected.connect(dialog.reject);box.addWidget(buttons)
    return dialog.exec()==QDialog.DialogCode.Accepted
