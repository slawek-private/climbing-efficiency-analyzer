"""Optional footwork and coaching controls for the measurement inspector."""
import copy
from uuid import uuid4
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QComboBox,QDialog,QFormLayout,QSpinBox,QDialogButtonBox,QPlainTextEdit,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QMenu)
from .footwork import enable,metrics,KINDS,INTENTS

HELP=('Both feet off means neither foot visibly contacting a hold, wall, volume or rock. Smears and hooks count as contact. '
      'It does not measure force or prove arms-only loading. Intentional cuts are separate from unplanned releases. '
      'Mark reviewed coverage only where both feet are visible and all slips / feet-off intervals have been reviewed and annotated. Occluded/unreviewed footage stays unknown. '
      'For a fall, mark when the fall starts so time in the air after falling is excluded. All boundaries use original frame timestamps.')

class ObservationDialog(QDialog):
    def __init__(self,w,event,coverage=False):
        super().__init__(w);self.setWindowTitle('Review coverage' if coverage else 'Review observation');self.resize(470,500);self.w=w;self.event=event;self.coverage=coverage
        form=QFormLayout(self);note=QLabel(HELP);note.setWordWrap(True);form.addRow(note);self.frames={}
        for key in ('start','end') if coverage or event['kind']=='both_off' else ('start',):
            field=QSpinBox();field.setRange(0,len(w.reader.times)-1);field.setValue(event[key]['frame']);field.setSuffix(' · original frame');field.setAccessibleName(key.capitalize()+' original frame');self.frames[key]=field;form.addRow(key.capitalize(),field)
        self.choices={};self.texts={}
        options={'state':('reviewed','obscured')} if coverage else {'limb':('both',) if event['kind']=='both_off' else ('left','right','both','uncertain'),'intent':INTENTS,'status':('candidate','uncertain','confirmed')}
        for key,values in options.items():
            field=QComboBox();field.addItems(values);field.setCurrentText(event[key]);field.setAccessibleName(key.capitalize());self.choices[key]=field;form.addRow(key.capitalize(),field)
        if not coverage:
            for key,title in [('observation','Visible observation'),('interpretation','Coach interpretation'),('action','Agreed action')]:
                field=QPlainTextEdit(event[key]);field.setMaximumHeight(70);field.setAccessibleName(title);self.texts[key]=field;form.addRow(title,field)
        self.error=QLabel();self.error.setWordWrap(True);form.addRow(self.error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.check);buttons.rejected.connect(self.reject);form.addRow(buttons)
    def value(self):
        result=copy.deepcopy(self.event)
        for key,field in self.frames.items():result[key]=self.w.reader.point(field.value())
        for key,field in self.choices.items():result[key]=field.currentText()
        for key,field in self.texts.items():result[key]=field.toPlainText().strip()
        if not self.coverage and result['kind']!='both_off':result['kind']='foot_release' if result['intent']=='intentional' else 'slip'
        return result
    def check(self):
        from .labels import validate
        d=copy.deepcopy(self.w.document());track=enable(d);key='coverage' if self.coverage else 'events';result=self.value()
        track[key]=[e for e in track[key] if e['id']!=result['id']]+[result]
        if not self.coverage and result['kind']=='both_off':track['pending']=None
        try:validate(d)
        except Exception as e:self.error.setText(str(e).split('\n')[0]);return
        self.result_document=d;self.accept()

class FootworkPanel(QWidget):
    def __init__(self,w):
        super().__init__();self.w=w;self.entries=[];self.displayed=None;box=QVBoxLayout(self);box.setContentsMargins(0,8,0,0);box.setSpacing(8)
        heading=QHBoxLayout();self.toggle=QPushButton('Footwork ▸');self.toggle.setProperty('role','quiet');self.toggle.setCheckable(True);self.toggle.setChecked(w.settings.value('footwork_open',False,type=bool));self.toggle.toggled.connect(self.expanded);heading.addWidget(self.toggle);heading.addStretch();box.addLayout(heading)
        self.body=QWidget();body=QVBoxLayout(self.body);body.setContentsMargins(0,0,0,0);body.setSpacing(8);box.addWidget(self.body)
        line=QHBoxLayout()
        for limb in ('left','right'):
            b=QPushButton('Mark '+limb+' slip');b.setAccessibleName('Mark '+limb+' foot slip');b.clicked.connect(lambda checked=False,l=limb:self.mark_slip(l));line.addWidget(b)
        body.addLayout(line)
        self.both=QPushButton('Start both-feet-off interval');self.both.setToolTip(HELP);self.both.clicked.connect(self.toggle_both);body.addWidget(self.both)
        line=QHBoxLayout();self.coverage=QPushButton('Review coverage…');self.coverage.clicked.connect(self.add_coverage);line.addWidget(self.coverage)
        more=QPushButton('More ▾');menu=QMenu(more)
        for title,callback in [('Mark simultaneous slip',lambda:self.mark_slip('both')),('Mark uncertain slip',lambda:self.mark_slip('uncertain')),('Mark where the fall starts',self.fall_onset),('Remove fall-start mark',self.clear_fall),('Cancel feet-off timer',self.cancel_timer)]:menu.addAction(title,callback)
        more.setMenu(menu);line.addWidget(more);body.addLayout(line)
        self.summary=QLabel();self.summary.setWordWrap(True);self.summary.setObjectName('muted');self.summary.setToolTip(HELP);body.addWidget(self.summary)
        self.table=QTableWidget(0,4);self.table.setHorizontalHeaderLabels(['Event','Intent','Review','Time']);self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection);self.table.verticalHeader().hide();self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);self.table.setMaximumHeight(155);self.table.cellDoubleClicked.connect(lambda *_:self.edit());body.addWidget(self.table)
        line=QHBoxLayout()
        for title,callback in [('Replay',self.replay),('Edit',self.edit),('Delete',self.delete)]:b=QPushButton(title);b.clicked.connect(callback);line.addWidget(b)
        body.addLayout(line);self.expanded(self.toggle.isChecked())
    def expanded(self,on):self.body.setVisible(on);self.toggle.setText('Footwork '+('▾' if on else '▸'));self.w.settings.setValue('footwork_open',on)
    def edit_document(self,event,coverage=False):
        if not self.w.ready_to_mark():return
        self.w.pause();dialog=ObservationDialog(self.w,event,coverage)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.w.commit(dialog.result_document)
    def mark_slip(self,limb):
        if not self.w.ready_to_mark():return
        point=self.w.reader.point(self.w.frame_number)
        self.edit_document(dict(id=uuid4().hex,kind='slip',limb=limb,start=point,end=None,intent='uncertain',status='candidate',observation='',interpretation='',action=''))
    def toggle_both(self):
        if not self.w.ready_to_mark():return
        d=copy.deepcopy(self.w.document());track=enable(d);point=self.w.reader.point(self.w.frame_number);pending=track['pending']
        if pending:
            self.edit_document(dict(id=uuid4().hex,kind='both_off',limb='both',start=pending['start'],end=point,intent=pending['intent'],status='candidate',observation='',interpretation='',action=''))
        else:track['pending']={'start':point,'intent':'uncertain'};self.w.commit(d)
    def add_coverage(self):
        if not self.w.ready_to_mark():return
        d=self.w.document();start=d['start'] or self.w.reader.point(self.w.frame_number);end=d['end'] or self.w.reader.point(min(start['frame']+1,len(self.w.reader.times)-1))
        self.edit_document(dict(id=uuid4().hex,start=start,end=end,state='reviewed'),True)
    def fall_onset(self):
        if not self.w.ready_to_mark():return
        d=copy.deepcopy(self.w.document());enable(d)['fall_onset']=self.w.reader.point(self.w.frame_number);self.w.commit(d)
    def clear_fall(self):
        if not self.w.history:return
        d=copy.deepcopy(self.w.document());enable(d)['fall_onset']=None;self.w.commit(d)
    def cancel_timer(self):
        if not self.w.history:return
        d=copy.deepcopy(self.w.document());enable(d)['pending']=None;self.w.commit(d)
    def selected(self):return self.entries[self.table.currentRow()] if 0<=self.table.currentRow()<len(self.entries) else None
    def edit(self):
        e=self.selected()
        if e:self.edit_document(e,e.get('state') is not None)
    def delete(self):
        e=self.selected()
        if not e:return
        d=copy.deepcopy(self.w.document());key='coverage' if 'state' in e else 'events';d['footwork'][key]=[x for x in d['footwork'][key] if x['id']!=e['id']];self.w.commit(d)
    def replay(self):
        e=self.selected()
        if e:self.w.replay_observation(e)
    def select(self,identifier):
        self.toggle.setChecked(True)
        for row,e in enumerate(self.entries):
            if e['id']==identifier:self.table.selectRow(row);self.w.measurement_scroll.ensureWidgetVisible(self.table);break
    def refresh(self,d,now):
        self.setVisible(bool(d))
        if not d:self.entries=[];self.displayed=None;self.table.setRowCount(0);return
        track=d.get('footwork',{});m=metrics(d);pending=track.get('pending')
        self.both.setText(f'Stop both feet off · {max(0,now-pending["start"]["seconds"]):.1f} s' if pending else 'Start both-feet-off interval');
        role='primary' if pending else 'idle'
        if self.both.property('role')!=role:self.both.setProperty('role',role);self.both.style().unpolish(self.both);self.both.style().polish(self.both)
        text='Coverage not reviewed' if not m['reviewed_seconds'] else f"Reviewed {m['reviewed_seconds']:.1f} s · {m['coverage_share']:.0%} coverage"
        if m['fall_review_needed']:text+=' · mark where the fall starts'
        elif m['confirmed_slips'] is not None:text+=f"\nConfirmed slips: {m['confirmed_slips']} · {m['candidate_slips']} candidates · both feet off {str(round(m['both_off_seconds'],1))+' s' if m['both_off_seconds'] is not None else 'not finalized'}"
        self.summary.setText(text)
        if getattr(self,'displayed',None) is d:return
        self.displayed=d;self.entries=sorted(track.get('events',[])+track.get('coverage',[]),key=lambda e:e['start']['seconds']);identifier=self.table.item(self.table.currentRow(),0).data(Qt.ItemDataRole.UserRole) if self.table.currentRow()>=0 and self.table.item(self.table.currentRow(),0) else None
        self.table.blockSignals(True);self.table.setRowCount(len(self.entries))
        for row,e in enumerate(self.entries):
            event_name='Coverage' if 'state' in e else {'slip':'Slip','both_off':'Both off','foot_release':'Release'}[e['kind']]
            if 'state' not in e and e['kind']!='both_off':event_name={'left':'L','right':'R','both':'Both','uncertain':'?'}[e['limb']]+' '+event_name.lower()
            values=(event_name,e.get('intent','—'),e.get('status',e.get('state')),f"{e['start']['seconds']:.3f} s")
            for col,value in enumerate(values):
                item=QTableWidgetItem(value);item.setData(Qt.ItemDataRole.UserRole,e['id']);item.setToolTip(('Coverage · '+e['state'] if 'state' in e else KINDS[e['kind']]+' · '+e['limb'])+' · original frame '+str(e['start']['frame'])+' · double-click to edit');self.table.setItem(row,col,item)
            if e['id']==identifier:self.table.selectRow(row)
        self.table.blockSignals(False)


def edit_coaching(w):
    if not w.history:return
    w.pause();d=copy.deepcopy(w.document());dialog=QDialog(w);dialog.setWindowTitle('Coaching goal and attempt context');dialog.resize(500,650);form=QFormLayout(dialog);fields={}
    for group,items in [('coaching',{'goal':'Session goal','reflection':'Athlete reflection','action':'Agreed next action','retest':'Next-session check'}),('context',{'discipline':'Discipline','grade':'Route grade','wall_angle':'Wall angle','familiarity':'Route familiarity'})]:
        for key,title in items.items():
            field=QPlainTextEdit(d.get(group,{}).get(key,''));field.setMaximumHeight(55);field.setAccessibleName(title);fields[group,key]=field;form.addRow(title,field)
    buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);form.addRow(buttons)
    if dialog.exec()==QDialog.DialogCode.Accepted:
        enable(d)
        for (group,key),field in fields.items():d.setdefault(group,{})[key]=field.toPlainText().strip()
        w.commit(d)
