"""Focused interface: climb boundaries, named arrivals, left/right holds."""
import copy
import bisect
import sys
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from pathlib import Path
from PySide6.QtCore import QTimer,QSettings
from PySide6.QtGui import QShortcut,QKeySequence
from PySide6.QtWidgets import QApplication,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QLineEdit,QGroupBox,QTableWidget,QTableWidgetItem,QFileDialog,QMessageBox,QInputDialog,QComboBox
from .app import Window as LegacyWindow
from .labels import ROOT, make_event,History,empty_labels,load,save
from .version import APP_NAME,__version__
from .comparison import export_comparison,load_collection,rows
from .video import VideoReader
from .discovery import matching_labels
from .workspace import Workspace
from .collection import CollectionWorker

class SharedPointSelector(QComboBox):
    def __init__(self):
        super().__init__();self.setEditable(True);self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    def text(self):return self.currentText()
    def setText(self,value):self.setEditText(value)
    def setPlaceholderText(self,value):self.lineEdit().setPlaceholderText(value)

class Window(LegacyWindow):
    def __init__(self,video=None):
        self.workspace=Workspace(ROOT/"artifacts"/"workspaces"/"current.json");self.session_histories={};self.session_indexes={};self.collection_worker=None
        self.settings=QSettings("ClimbingEfficiencyAnalyzer","ClimbStudio")
        self.resource_monitor=None;self.preview_worker=None
        self.simple_ready=False
        self.async_decode=True;self.decoder=ThreadPoolExecutor(max_workers=1);self.decode_future=None;self.decode_requested=None;self.decode_seek=False;self.play_after_decode=False
        self.decode_poll=QTimer();self.decode_poll.setInterval(20);self.decode_poll.timeout.connect(self.poll_decode)
        self.scrub_timer=QTimer();self.scrub_timer.setSingleShot(True);self.scrub_timer.setInterval(100);self.scrub_timer.timeout.connect(self.finish_scrub)
        super().__init__(video)
        layout=self.centralWidget().layout()
        toolbar=layout.itemAt(0).layout()
        while toolbar.count():
            item=toolbar.takeAt(0)
            if item.widget():item.widget().hide()
        for title,callback in [('Open video',self.open_video),('Load measurements',self.load_labels),('Save athlete measurements',self.save_labels),('Export ALL athletes · HTML + CSV',self.export_all)]:
            b=QPushButton(title);b.clicked.connect(callback);toolbar.addWidget(b)
        splitter=layout.itemAt(2).widget();splitter.widget(1).hide()
        panel=QWidget();side=QVBoxLayout(panel);side.setSpacing(5)
        heading=QLabel('Measure this climb');heading.setStyleSheet('font-size:24px;font-weight:700');side.addWidget(heading)
        instruction=QLabel('Pause on the exact frame, then press the action below.\nAll measurements use the frame currently on screen.');instruction.setWordWrap(True);side.addWidget(instruction)
        identity=QHBoxLayout();identity.addWidget(QLabel('Athlete'));self.climber.setParent(panel);identity.addWidget(self.climber);identity.addWidget(QLabel('Attempt'));self.attempt.setParent(panel);identity.addWidget(self.attempt);side.addLayout(identity)
        group=QGroupBox('1   Climb start and end');g=QVBoxLayout(group)
        self.start_status=QLabel();self.end_status=QLabel();self.duration_status=QLabel()
        for title,callback,status in [('CLIMB START · first grip on hold 1',self.set_start,self.start_status),('CLIMB END · rope becomes weighted',self.set_failure,self.end_status)]:
            b=QPushButton(title);b.setMinimumHeight(40);b.clicked.connect(callback);g.addWidget(b);g.addWidget(status)
        g.addWidget(self.duration_status);side.addWidget(group)
        group=QGroupBox('2   Arrival at a point');g=QVBoxLayout(group)
        self.point_name=SharedPointSelector();self.point_name.setText('A');self.point_name.setPlaceholderText('Point name, e.g. A, B, roof');g.addWidget(QLabel('Use the SAME point names for every athlete.'));g.addWidget(self.point_name)
        b=QPushButton('MARK ARRIVAL at this point · current frame');b.clicked.connect(self.add_point);g.addWidget(b)
        self.points_table=QTableWidget(0,4);self.points_table.setHorizontalHeaderLabels(['Point','Video time','From climb start','Comment']);self.points_table.setMaximumHeight(80);self.points_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers);self.points_table.cellClicked.connect(self.seek_point);g.addWidget(self.points_table)
        actions=QHBoxLayout()
        for title,callback in [('Rename selected point',self.rename_point),('Delete selected point',self.delete_point)]:
            b=QPushButton(title);b.clicked.connect(callback);actions.addWidget(b)
        g.addLayout(actions);side.addWidget(group)
        group=QGroupBox('3   Rest and clipping timers');g=QVBoxLayout(group);self.interval_status={};self.interval_start={};self.interval_stop={}
        line=QHBoxLayout();line.addWidget(QLabel('Clipping hand'));self.clip_hand.setParent(group);line.addWidget(self.clip_hand);line.addWidget(QLabel('Quickdraw #'));self.draw.setParent(group);line.addWidget(self.draw);g.addLayout(line)
        for kind,title in [('rest','REST'),('clip','CLIP')]:
            status=QLabel();g.addWidget(status);self.interval_status[kind]=status
            line=QHBoxLayout()
            for opening,store,word in [(True,self.interval_start,'START'),(False,self.interval_stop,'STOP')]:
                b=QPushButton(word+' '+title);b.clicked.connect(lambda checked=False,k=kind,o=opening:self.interval_action(k,o));line.addWidget(b);store[kind]=b
            b=QPushButton('Cancel');b.clicked.connect(lambda checked=False,k=kind:self.cancel_interval(k));line.addWidget(b);g.addLayout(line)
        hint=QLabel('Rest: deliberate recovery on the wall. Clip: rope taken → rope clipped.');hint.setWordWrap(True);g.addWidget(hint);side.addWidget(group)
        group=QGroupBox('4   Time each hand stays on a hold');g=QVBoxLayout(group);self.hand_status={};self.grab_buttons={};self.release_buttons={}
        for hand,spin in [('left',self.left_hold),('right',self.right_hold)]:
            line=QHBoxLayout();line.addWidget(QLabel(hand.upper()+' HAND · hold #'));spin.setParent(group);line.addWidget(spin);g.addLayout(line)
            status=QLabel();status.setStyleSheet('font-weight:700;font-size:16px');g.addWidget(status);self.hand_status[hand]=status
            line=QHBoxLayout()
            for title,opening,store in [('GRAB · start hold timer',True,self.grab_buttons),('RELEASE · stop hold timer',False,self.release_buttons)]:
                b=QPushButton(title);b.clicked.connect(lambda checked=False,h=hand,o=opening:self.hand_action(h,o));line.addWidget(b);store[hand]=b
            g.addLayout(line)
            cancel=QPushButton('Cancel unfinished '+hand+' hold');cancel.clicked.connect(lambda checked=False,h=hand:self.cancel_hand(h));g.addWidget(cancel)
        side.addWidget(group)
        side.addWidget(QLabel('Recorded holds, rests and clips · select to jump; double-click to edit'))
        self.table.setParent(panel);side.addWidget(self.table)
        actions=QHBoxLayout()
        for title,callback in [('Edit selected interval',self.edit_event),('Delete selected interval',self.delete_event),('Undo',self.undo),('Redo',self.redo)]:
            b=QPushButton(title);b.clicked.connect(callback);actions.addWidget(b)
        side.addLayout(actions);side.addWidget(QLabel('Space: play/pause    ← / →: one exact frame\nSave each athlete, then export ALL athletes into one report.'))
        from PySide6.QtWidgets import QScrollArea
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(panel);scroll.setMinimumWidth(490);splitter.addWidget(scroll);splitter.setSizes([850,0,520])
        self.timeline.hide()
        for shortcut in self.shortcuts:
            if shortcut.property('manual_key') not in ('Space','Left','Right','Ctrl+S','Ctrl+Z','Ctrl+Y','S','E','P','L','R','Q','W','C','V','Delete','Shift+Left','Shift+Right'):shortcut.setEnabled(False)
        self.slider.sliderReleased.connect(self.finish_scrub)
        self.simple_ready=True
        from .design import build
        build(self);self.install_timer_shortcuts();self.refresh_live();self.refresh_collection();self.refresh_preview_status()
    def install_timer_shortcuts(self):
        actions={'Delete':self.delete_selected,'Shift+Left':lambda:self.step(-1,True),'Shift+Right':lambda:self.step(1,True),'S':self.set_start,'E':self.set_failure,'P':self.add_point,'L':lambda:self.toggle_hand_timer('clip','left'),'R':lambda:self.toggle_hand_timer('clip','right'),'Q':lambda:self.toggle_hand_timer('rest','left'),'W':lambda:self.toggle_hand_timer('rest','right'),'C':lambda:self.toggle_hand_timer('chalk','left'),'V':lambda:self.toggle_hand_timer('chalk','right')}
        for key,callback in actions.items():
            existing=next((s for s in self.shortcuts if s.property('manual_key')==key),None)
            if existing:existing.activated.disconnect()
            else:existing=QShortcut(QKeySequence(key),self);existing.setProperty('manual_key',key);self.shortcuts.append(existing)
            existing.setAutoRepeat(False);existing.activated.connect(lambda cb=callback:self.shortcut(cb))
        self.focus_changed(None,QApplication.focusWidget())
    def toggle_hold(self,hand):
        self.mark('contact',hand)
    def toggle_hand_timer(self,kind,hand):
        if not self.ready_to_mark():return
        d=copy.deepcopy(self.document());d['schema_version']='1.2.0';now=self.reader.point(self.frame_number)
        pending=next((e for e in d['open_events'] if e['kind']==kind and e['hand']==hand),None)
        if pending:
            if now['seconds']<=pending['start']['seconds']:
                self.statusBar().showMessage('Advance the video before stopping this timer.',4000);return
            d['events'].append(make_event(pending,now));d['open_events'].remove(pending)
        else:
            if any(e['kind']==kind and e['hand']==hand and e['start']['seconds']<=now['seconds']<e['end']['seconds'] for e in d['events']):
                self.statusBar().showMessage('This hand already has a marked interval here. Edit it in Recorded.',5000);return
            d['open_events'].append({'kind':kind,'hand':hand,'target':self.draw.value() if kind=='clip' else None,'start':now,'confidence':1,'notes':''})
        d['reviewed']={k:False for k in d['reviewed']}
        if self.commit(d) and pending and kind=='clip':
            self.draw.setValue(min(self.draw.maximum(),max(self.draw.value(),(pending['target'] or 1)+1)));self.remember_current()
    def stop_legacy_rest(self):
        if not self.ready_to_mark():return
        d=copy.deepcopy(self.document());pending=next((e for e in d['open_events'] if e['kind']=='rest' and e['hand']=='none'),None)
        if not pending:return
        d['events'].append(make_event(pending,self.reader.point(self.frame_number)));d['open_events'].remove(pending);d['reviewed']={k:False for k in d['reviewed']};self.commit(d)
    def cancel_hand_timer(self,kind,hand):
        if not self.history:return
        d=copy.deepcopy(self.document());d['open_events']=[e for e in d['open_events'] if not (e['kind']==kind and e['hand']==hand)];self.commit(d)
    def focus_changed(self,old,new):
        super().focus_changed(old,new)
        for shortcut in self.shortcuts:
            if shortcut.property('manual_key') not in ('Space','Left','Right','Ctrl+S','Ctrl+Z','Ctrl+Y','S','E','P','L','R','Q','W','C','V','Delete','Shift+Left','Shift+Right'):shortcut.setEnabled(False)
    def refresh(self):
        super().refresh()
        if not self.simple_ready or not self.history:return
        d=self.document();self.table.blockSignals(True);self.table.setRowCount(len(self.visible_events))
        self.table.setHorizontalHeaderLabels(['Type','Hand','Hold/draw','Climb start s','Climb stop s','Duration s'])
        for row,e in enumerate(self.visible_events):
            for col,value in enumerate(({'contact':'Hold','rest':'Rest','clip':'Clip','offwall':'Off-wall','chalk':'Chalk'}[e['kind']],e['hand'],e['target'] or '—',f"{e['start']['seconds']-d['start']['seconds']:.3f}" if d['start'] else 'Start missing',f"{e['end']['seconds']-d['start']['seconds']:.3f}" if d['start'] else 'Start missing',f"{e['end']['seconds']-e['start']['seconds']:.3f}")):
                item=QTableWidgetItem(str(value));item.setToolTip(f"Video time: {e['start']['seconds']:.3f}–{e['end']['seconds']:.3f} s");self.table.setItem(row,col,item)
        self.table.blockSignals(False)
        self.point_rows=sorted(d.get('checkpoints',[]),key=lambda p:p['point']['seconds']);self.points_table.setRowCount(len(self.point_rows))
        for row,p in enumerate(self.point_rows):
            for col,v in enumerate((p['name'],f"{p['point']['seconds']:.3f} s",f"{p['point']['seconds']-d['start']['seconds']:.3f} s" if d['start'] and p['point']['seconds']>=d['start']['seconds'] else 'Start missing / before start',p.get('comment',''))):self.points_table.setItem(row,col,QTableWidgetItem(v))
        self.points_table.setVisible(bool(self.point_rows));self.points_table.resizeColumnsToContents();self.refresh_live();self.setWindowTitle(APP_NAME+' · v'+__version__+' · '+self.video_path.name+(' *' if self.dirty() else ''))
    def set_frame_step(self,value):
        self.settings.setValue('frame_step',value)
        if hasattr(self,'step_back_button'):self.step_back_button.setText(f'← {value} frames');self.step_forward_button.setText(f'{value} frames →')
    def step(self,delta,single=False):
        if not self.reader:return
        self.pause();base=getattr(self,'pending_scrub',self.decode_requested if self.decode_seek and self.decode_future is not None else self.frame_number)
        self.scrub_timer.stop()
        if hasattr(self,'pending_scrub'):del self.pending_scrub
        self.show_frame(base+delta*(1 if single else self.frame_step.value()))
    def select_timeline_event(self,identifier):
        row=next((i for i,e in enumerate(self.visible_events) if e['id']==identifier),None)
        if row is not None:self.table.selectRow(row);self.table.setFocus()
    def clear_boundary(self,key):
        if not self.history:return
        d=copy.deepcopy(self.document());d[key]=None;d['outcome']='unknown' if key=='end' else d['outcome'];d['reviewed']={k:False for k in d['reviewed']};self.commit(d)
    def delete_selected(self):
        if QApplication.focusWidget() in (self.points_table,self.points_table.viewport()):self.delete_point()
        else:self.delete_event()
    def delete_event(self):
        if not self.history:return
        selected=sorted({item.row() for item in self.table.selectedItems()})
        if not selected:self.statusBar().showMessage('Select a recorded event or click its timeline bar first.',5000);return
        ids={self.visible_events[row]['id'] for row in selected if row<len(self.visible_events)};d=copy.deepcopy(self.document());d['events']=[e for e in d['events'] if e['id'] not in ids];d['reviewed']={k:False for k in d['reviewed']}
        if self.commit(d):self.statusBar().showMessage(f'Removed {len(ids)} measurement(s). Ctrl+Z restores them.',6000)
    def delete_point(self):
        if not self.history:return
        selected={item.row() for item in self.points_table.selectedItems()}
        if not selected:self.statusBar().showMessage('Select an arrival point to remove.',5000);return
        ids={self.point_rows[row]['id'] for row in selected};d=copy.deepcopy(self.document());d['checkpoints']=[p for p in d.get('checkpoints',[]) if p['id'] not in ids];self.commit(d)
    def scrub_seconds(self,seconds):
        if not self.reader:return
        times=self.reader.times;i=bisect.bisect_left(times,seconds)
        i=min(len(times)-1,i)
        if i and abs(times[i-1]-seconds)<=abs(times[i]-seconds):i-=1
        self.slider_changed(i)
    def slider_changed(self,value):
        if not self.reader:return
        self.pause();self.pending_scrub=value
        if self.reader.backend=='preview':
            self.scrub_timer.setInterval(16)
            if not self.scrub_timer.isActive():self.scrub_timer.start()
        else:self.scrub_timer.setInterval(100);self.scrub_timer.start()
    def finish_scrub(self):
        self.scrub_timer.stop()
        if self.reader and hasattr(self,"pending_scrub"):
            number=self.pending_scrub;del self.pending_scrub;self.show_frame(number)
    def show_frame(self,number):
        if not self.reader:return
        if not self.async_decode:
            super().show_frame(number)
            if self.simple_ready:self.refresh_live()
            return
        number=max(0,min(len(self.reader.times)-1,int(number)))
        self.decode_requested=number;self.decode_seek=not self.playing
        if self.decode_future is None:self.submit_decode()
        if not self.decode_poll.isActive():self.decode_poll.start()
    def submit_decode(self):
        self.decode_number=self.decode_requested
        decode=self.reader.playback_frame if self.playing and not self.decode_seek else self.reader.frame
        self.decode_future=self.decoder.submit(decode,self.decode_number)
    def poll_decode(self):
        if self.decode_future is None or not self.decode_future.done():return
        try:rgb=self.decode_future.result()
        except Exception as error:
            self.decode_future=None;self.decode_poll.stop();self.pause();self.error(error);return
        number=self.decode_number;self.decode_future=None
        if number!=self.decode_requested and not self.playing:self.submit_decode();return
        self.decode_poll.stop();self.decode_seek=False;self.frame_number=number;self.image.display(rgb)
        self.position.setText(f"Frame {number} / {len(self.reader.times)-1} · {self.reader.times[number]:.3f}s")
        if not self.slider.isSliderDown():
            self.slider.blockSignals(True);self.slider.setValue(number);self.slider.blockSignals(False)
        self.refresh_live()
        if self.play_after_decode:self.start_playback()
        if self.playing and number==len(self.reader.times)-1:self.pause()
        if self.playing and number!=self.decode_requested:self.submit_decode();self.decode_poll.start()
    def start_playback(self):
        self.play_after_decode=False;self.playing=True;self.reset_clock();self.timer.start();self.play_button.setText('Pause · Space')
    def toggle_play(self):
        if not self.reader:return
        if self.playing or self.play_after_decode:self.pause();return
        self.finish_scrub()
        if self.frame_number==len(self.reader.times)-1:
            self.play_after_decode=True;self.show_frame(0)
            if not self.async_decode:self.start_playback()
            else:self.play_button.setText('Cancel starting…')
        elif self.decode_future is not None and self.decode_seek:
            self.play_after_decode=True;self.play_button.setText('Cancel starting…')
        else:self.start_playback()
    def tick(self):
        if not self.reader or not self.playing:return
        rate=(.25,.5,1,1.5,2)[self.speed.currentIndex()];seconds=self.play_start+self.elapsed.elapsed()/1000*rate
        frame=min(len(self.reader.times)-1,max(0,bisect.bisect_right(self.reader.times,seconds)-1))
        if frame!=self.frame_number and (self.decode_future is None or frame!=self.decode_requested):self.show_frame(frame)
        if not self.async_decode and self.frame_number==len(self.reader.times)-1:self.pause()
    def pause(self):
        self.play_after_decode=False
        was_playing=self.playing
        super().pause()
        if was_playing:
            self.decode_requested=self.frame_number;self.decode_seek=False
    def ready_to_mark(self):
        self.pause();self.finish_scrub()
        if self.async_decode and self.decode_future is not None and self.decode_seek:
            self.pause();self.statusBar().showMessage('Frame is loading. Mark once the requested frame is visible.',4000);return False
        return bool(self.reader)
    def begin_video(self,path):
        self.remember_current()
        self.workspace.add(path)
        self.scrub_timer.stop();self.decode_poll.stop()
        if hasattr(self,'pending_scrub'):del self.pending_scrub
        if self.decode_future is not None:
            try:self.decode_future.result()
            except Exception:pass
            self.decode_future=None
        key=str(Path(path).resolve());cached=self.session_indexes.get(key)
        if cached and cached[0]==(Path(path).stat().st_size,Path(path).stat().st_mtime_ns):
            self.pause()
            if self.reader:self.reader.close()
            self.reader=None;self.history=None;self.video_path=Path(path);self.label_path=None;self.saved=None;self.index_ready(cached[1])
        else:super().begin_video(path)
        self.refresh_collection()
    def closeEvent(self,event):
        if self.preview_worker and self.preview_worker.isRunning():
            self.preview_worker.requestInterruption();self.preview_worker.wait()
        if self.resource_monitor:
            self.resource_monitor.requestInterruption();self.resource_monitor.wait(7000)
        self.remember_current()
        if self.collection_worker and self.collection_worker.isRunning():
            self.collection_worker.requestInterruption();self.collection_worker.wait(5000)
        self.scrub_timer.stop();self.decode_poll.stop()
        if self.decode_future is not None:
            try:self.decode_future.result()
            except Exception:pass
            self.decode_future=None
        super().closeEvent(event)
        if event.isAccepted():self.decoder.shutdown(wait=True)
    def refresh_live(self):
        if not self.simple_ready:return
        d=self.document();now=self.reader.times[self.frame_number] if self.reader else 0
        if hasattr(self,"empty_hint"):self.empty_hint.setVisible(not bool(self.reader))
        self.start_status.setText('Start: '+(f"{d['start']['seconds']:.3f} s in video" if d and d['start'] else 'not marked'))
        self.end_status.setText('End: '+(f"{d['end']['seconds']:.3f} s · "+{'failed':'Fell / failed','completed':'Topped'}.get(d['outcome'],d['outcome']) if d and d['end'] else 'not marked'))
        self.duration_status.setText('Climb time  ·  '+(f"{d['end']['seconds']-d['start']['seconds']:.3f} seconds" if d and d['start'] and d['end'] else 'mark start and end'))
        for kind in ('rest','clip'):
            pending=next((e for e in d['open_events'] if e['kind']==kind),None) if d else None
            current=next((e for e in d['events'] if e['kind']==kind and e['start']['seconds']<=now<e['end']['seconds']),None) if d else None
            current=pending if pending and pending['start']['seconds']<=now else current
            self.interval_status[kind].setText(f"{now-current['start']['seconds']:.3f} s"+(' · '+current['hand']+' hand' if kind=='clip' else '') if current else 'Ready to measure')
            self.interval_start[kind].setEnabled(bool(d) and pending is None and current is None);self.interval_stop[kind].setEnabled(bool(pending) and now>pending['start']['seconds'])
        for (kind,hand),control in getattr(self,'hand_timer_buttons',{}).items():
            pending=next((e for e in d['open_events'] if e['kind']==kind and e['hand']==hand),None) if d else None
            current=next((e for e in d['events'] if e['kind']==kind and e['hand']==hand and e['start']['seconds']<=now<e['end']['seconds']),None) if d else None
            key={'clip':{'left':'L','right':'R'},'rest':{'left':'Q','right':'W'},'chalk':{'left':'C','right':'V'}}[kind][hand]
            control.setText(('Stop ' if pending else 'Start ')+hand.capitalize()+' '+kind+' · '+key)
            role='stop' if pending else 'start'
            if control.property('role')!=role:control.setProperty('role',role);control.style().unpolish(control);control.style().polish(control)
            visible=pending if pending and pending['start']['seconds']<=now else current
            status=f"{now-visible['start']['seconds']:.2f} s · "+('running' if pending else 'recorded') if visible else 'Seek forward to stop' if pending else 'Ready to measure'

            if kind=='chalk' and d:
                completed=[e for e in d['events'] if e['kind']=='chalk' and e['hand']==hand]
                status+=f" · {len(completed)}× / {sum(e['end']['seconds']-e['start']['seconds'] for e in completed):.1f}s"
            self.hand_timer_status[kind,hand].setText(status);control.setEnabled(bool(d) and (not current or bool(pending)))
        if hasattr(self,'precision_scrubber'):
            self.precision_scrubber.sync(self.reader.times[-1] if self.reader else 1,now,d)
        if hasattr(self,'event_timeline'):
            self.event_timeline.document=d;self.event_timeline.position=now;self.event_timeline.duration=self.reader.times[-1] if self.reader else 1;self.event_timeline.update()
        if hasattr(self,'legacy_rest_panel'):self.legacy_rest_panel.setVisible(bool(d) and any(e['kind']=='rest' and e['hand']=='none' for e in d['open_events']))
        clip_pending=bool(d) and any(e['kind']=='clip' for e in d['open_events'])
        self.clip_hand.setEnabled(not clip_pending);self.draw.setEnabled(bool(d))
        for hand in ('left','right'):
            pending=next((e for e in d['open_events'] if e['kind']=='contact' and e['hand']==hand),None) if d else None
            current=next((e for e in d['events'] if e['kind']=='contact' and e['hand']==hand and e['start']['seconds']<=now<e['end']['seconds']),None) if d else None
            current=pending if pending and pending['start']['seconds']<=now else current
            self.hand_status[hand].setText(f"HOLD #{current['target']} · {now-current['start']['seconds']:.3f} s held" if current else 'No marked hold at this frame')
            if pending and now<pending['start']['seconds']:self.hand_status[hand].setText(f"Timer starts later at {pending['start']['seconds']:.3f} s · seek forward to release")
            self.grab_buttons[hand].setEnabled(bool(d) and pending is None and current is None);self.release_buttons[hand].setEnabled(bool(pending) and now>pending['start']['seconds']);getattr(self,hand+'_hold').setEnabled(pending is None)
    def interval_action(self,kind,opening):
        if not self.ready_to_mark():return
        self.pause();d=copy.deepcopy(self.document());pending=next((e for e in d["open_events"] if e["kind"]==kind),None)
        if opening:
            if pending:return
            d["open_events"].append({"kind":kind,"hand":self.clip_hand.currentText() if kind=="clip" else "none","target":self.draw.value() if kind=="clip" else None,"start":self.reader.point(self.frame_number),"confidence":1,"notes":""})
        else:
            if not pending:return
            d["events"].append(make_event(pending,self.reader.point(self.frame_number)));d["open_events"].remove(pending)
        d["reviewed"]={k:False for k in d["reviewed"]};self.commit(d)
    def cancel_interval(self,kind):
        if not self.history:return
        d=copy.deepcopy(self.document());d["open_events"]=[e for e in d["open_events"] if e["kind"]!=kind];self.commit(d)
    def mark(self,kind,hand):
        if self.ready_to_mark():return super().mark(kind,hand)
    def set_start(self):
        if self.ready_to_mark():return super().set_start()
    def choose_climb_outcome(self):
        dialog=QMessageBox(self);dialog.setWindowTitle('Climb result');dialog.setText('How did this climb end?')
        failed=dialog.addButton('Fell / failed',QMessageBox.ButtonRole.AcceptRole)
        topped=dialog.addButton('Topped',QMessageBox.ButtonRole.AcceptRole)
        dialog.addButton(QMessageBox.StandardButton.Cancel);dialog.exec()
        return 'failed' if dialog.clickedButton()==failed else 'completed' if dialog.clickedButton()==topped else None
    def set_failure(self):
        if not self.ready_to_mark():return
        self.pause();moment=self.reader.point(self.frame_number);outcome=self.choose_climb_outcome()
        if outcome is None:return
        d=copy.deepcopy(self.document());d['end']=moment;d['outcome']=outcome;d['reviewed']['boundaries']=False;self.commit(d)
    def edit_climb_outcome(self):
        if not self.history or not self.document()['end']:
            self.statusBar().showMessage('Mark climb end first.',4000);return
        self.pause();outcome=self.choose_climb_outcome()
        if outcome is not None:
            d=copy.deepcopy(self.document());d['outcome']=outcome;d['reviewed']['boundaries']=False;self.commit(d)
    def hand_action(self,hand,opening):
        if not self.history:return
        pending=any(e['kind']=='contact' and e['hand']==hand for e in self.document()['open_events'])
        if opening==pending:return
        self.mark('contact',hand)
    def cancel_hand(self,hand):
        if not self.history:return
        d=copy.deepcopy(self.document());d["open_events"]=[e for e in d["open_events"] if not (e["kind"]=="contact" and e["hand"]==hand)];self.commit(d)
    def add_point(self):
        if not self.ready_to_mark():return
        name=self.workspace.add_point_name(self.point_name.text())
        if not name:return self.error('Enter a point name first, for example A.')
        self.pause();d=copy.deepcopy(self.document());d.setdefault('checkpoints',[]).append({'id':str(uuid4()),'name':name,'point':self.reader.point(self.frame_number)});self.commit(d)
    def seek_point(self,row,col):
        if 0<=row<len(self.point_rows):self.pause();self.show_frame(self.point_rows[row]['point']['frame'])
    def comment_at_frame(self):
        if not self.ready_to_mark():return
        self.pause();moment=self.reader.point(self.frame_number)
        text,ok=QInputDialog.getMultiLineText(self,'Comment at current frame',f"Video time {moment['seconds']:.3f} s · frame {moment['frame']}")
        if ok and text.strip():
            d=copy.deepcopy(self.document());d.setdefault('checkpoints',[]).append({'id':str(uuid4()),'name':'Comment','point':moment,'comment':text.strip()});self.commit(d)
    def edit_point_comment(self):
        row=self.points_table.currentRow()
        if not self.history or not 0<=row<len(self.point_rows):
            self.statusBar().showMessage('Select a marked point first.',4000);return
        self.pause();p=self.point_rows[row]
        text,ok=QInputDialog.getMultiLineText(self,'Edit point comment',f"{p['name']} · video time {p['point']['seconds']:.3f} s",p.get('comment',''))
        if ok:
            d=copy.deepcopy(self.document())
            for item in d['checkpoints']:
                if item['id']==p['id']:item['comment']=text.strip()
            self.commit(d)
    def rename_point(self):
        row=self.points_table.currentRow()
        if not self.history or not 0<=row<len(self.point_rows):return
        p=self.point_rows[row];name,ok=QInputDialog.getText(self,'Rename point','Point name',text=p['name'])
        if ok and name.strip():
            d=copy.deepcopy(self.document())
            for item in d['checkpoints']:
                if item['id']==p['id']:item['name']=name.strip()
            self.commit(d)
    def index_ready(self,index):
        self.progress.hide()
        try:
            self.reader=self.open_video_reader(index);self.decoder_choice.blockSignals(True);self.decoder_choice.setCurrentIndex(1 if self.reader.backend=='cuda' else 0);self.decoder_choice.blockSignals(False);self.history=History(empty_labels(index['source']));self.saved=copy.deepcopy(self.document());self.slider.setRange(0,len(self.reader.times)-1);self.frame_number=0
            folders=[self.video_path.parent,ROOT/'videos',ROOT/'artifacts'/'labels']
            folder=self.settings.value('labels_folder','')
            if folder:folders.append(Path(folder))
            candidates=matching_labels(index['source']['sha256'],folders)
            loaded=False
            for path,doc in candidates:
                if self.read_labels(path,quiet=True):
                    loaded=True;self.statusBar().showMessage(f'Loaded saved measurements · {doc["climber"]} · attempt {doc["attempt"]}'+(' · most recently saved attempt' if len(candidates)>1 else ''),15000);break
            if not loaded:self.refresh()
            key=str(self.video_path.resolve());self.session_indexes[key]=((self.video_path.stat().st_size,self.video_path.stat().st_mtime_ns),index)
            state=self.workspace.states.get(key)
            if state and state["document"]["source"]["sha256"]==index["source"]["sha256"]:
                d=copy.deepcopy(state["document"]);d["source"]=copy.deepcopy(index["source"]);self.history=self.session_histories.get(key,History(d));self.label_path=Path(state["label_path"]) if state["label_path"] else None
                self.saved=copy.deepcopy(d);self.refresh();self.show_frame(min(state["frame"],len(self.reader.times)-1))
            else:self.show_frame(0)
            next_draw=max([e["target"] or 0 for e in self.document()["events"] if e["kind"]=="clip"]+[0])+1
            self.draw.setValue(self.workspace.states.get(key,{}).get("quickdraw",next_draw));self.refresh_collection();self.refresh_preview_status()
        except Exception as error:self.error(error)
    def read_labels(self,path,quiet=False):
        try:
            d=load(path);expected=self.reader.index['source']
            if any(d['source'][k]!=expected[k] for k in expected if k!='file'):raise ValueError('Measurements do not match the video checksum or timestamp index')
            points=[p for p in (d['start'],d['end']) if p]
            for e in d['events']+d['open_events']:points.extend([e['start']]+([e['end']] if 'end' in e else []))
            points.extend(p['point'] for p in d.get('checkpoints',[]))
            if any(p!=self.reader.point(p['frame']) for p in points):raise ValueError('A label does not match the exact video frame')
            d['source']=copy.deepcopy(expected);self.history=History(d);self.label_path=Path(path);self.saved=copy.deepcopy(d);self.settings.setValue('labels_folder',str(Path(path).parent));self.refresh();return True
        except Exception as e:
            if not quiet:self.error(e)
            return False
    def open_video_reader(self,index):
        from .preview_cache import open_preview
        return open_preview(ROOT/'artifacts'/'preview-cache',index) or VideoReader(self.video_path,index,backend=self.settings.value('decoder_backend','auto'))
    def prepare_preview(self):
        if self.preview_worker and self.preview_worker.isRunning():
            self.preview_worker.requestInterruption();self.preview_status.setText('Cancelling preview preparation…');return
        if not self.reader:return
        if self.reader.backend=='preview':return
        self.pause()
        from .preview_cache import PreviewWorker
        self.preview_worker=PreviewWorker(self.video_path,copy.deepcopy(self.reader.index),ROOT/'artifacts'/'preview-cache')
        self.preview_worker.progress.connect(lambda value:self.preview_status.setText(f'Preparing local preview · {value}%'))
        self.preview_worker.ready.connect(self.preview_ready)
        self.preview_worker.error.connect(lambda message:self.error('Preview preparation failed: '+message))
        self.preview_worker.finished.connect(self.refresh_preview_status)
        self.preview_button.setText('Cancel preparation');self.preview_worker.start()
    def preview_ready(self,digest):
        if not self.reader or self.reader.index['source']['sha256']!=digest:return
        self.pause()
        if self.decode_future is not None:
            QTimer.singleShot(30,lambda:self.preview_ready(digest));return
        from .preview_cache import open_preview
        replacement=open_preview(ROOT/'artifacts'/'preview-cache',self.reader.index)
        if replacement:
            old=self.reader;self.reader=replacement;old.close();self.show_frame(self.frame_number);self.refresh_preview_status()
    def refresh_preview_status(self):
        if not hasattr(self,'preview_button'):return
        running=bool(self.preview_worker and self.preview_worker.isRunning())
        cached=bool(self.reader and self.reader.backend=='preview')
        self.preview_button.setText('Cancel preparation' if running else 'Smooth preview ready' if cached else 'Prepare smooth preview')
        self.preview_button.setEnabled(bool(self.reader) and (running or not cached));self.decoder_choice.setEnabled(not cached)
        if cached:
            self.decoder_choice.blockSignals(True);self.decoder_choice.setCurrentIndex(2);self.decoder_choice.blockSignals(False)
        if not running:self.preview_status.setText('Fast local preview · original frame timestamps preserved' if cached else 'Original video · prepare once for fast seeking')
    def change_decoder(self,index):
        if not self.reader:return
        if index==2:
            self.pause()
            from .preview_cache import open_preview
            replacement=open_preview(ROOT/'artifacts'/'preview-cache',self.reader.index)
            if replacement:self.preview_ready(self.reader.index['source']['sha256']);replacement.close()
            else:
                self.decoder_choice.blockSignals(True);self.decoder_choice.setCurrentIndex(1 if self.reader.backend=='cuda' else 0);self.decoder_choice.blockSignals(False);self.prepare_preview()
            return
        if self.reader.backend=='preview':return
        if self.decode_future is not None:
            self.statusBar().showMessage('Pause and wait for the current frame before switching decoder.',5000);self.decoder_choice.blockSignals(True);self.decoder_choice.setCurrentIndex(1 if self.reader.backend=='cuda' else 0);self.decoder_choice.blockSignals(False);return
        self.pause();old=self.reader;backend='cuda' if index==1 else 'cpu'
        try:
            replacement=VideoReader(self.video_path,old.index,backend);replacement.frame(self.frame_number)
        except Exception as e:
            if 'replacement' in locals():replacement.close()
            self.decoder_choice.blockSignals(True);self.decoder_choice.setCurrentIndex(1 if old.backend=='cuda' else 0);self.decoder_choice.blockSignals(False);self.error('Decoder unavailable: '+str(e));return
        self.reader=replacement;self.settings.setValue("decoder_backend",backend);old.close();self.show_frame(self.frame_number)
    def save_labels(self):
        if self.history and self.video_path and self.label_path is None:
            import re
            attempt=re.sub(r"[^A-Za-z0-9_-]", "_", self.document()["attempt"])
            self.label_path=ROOT/"artifacts"/"labels"/(self.video_path.stem+"-attempt-"+attempt+".labels.json")
        result=super().save_labels()
        if result:self.settings.setValue("labels_folder",str(self.label_path.parent));self.remember_current();self.refresh_collection()
        return result
    def remember_current(self):
        if not self.history or not self.video_path:return
        key=str(self.video_path.resolve());self.session_histories[key]=self.history
        self.workspace.remember(self.video_path,self.document(),self.label_path,self.frame_number)
        self.workspace.states[key]['quickdraw']=self.draw.value()
        try:self.workspace.save()
        except OSError as e:self.statusBar().showMessage('Workspace could not be saved: '+str(e),10000)
    def commit(self,document):
        result=super().commit(document)
        if result:self.remember_current();self.refresh_collection()
        return result
    def undo(self):
        super().undo();self.remember_current();self.refresh_collection()
    def redo(self):
        super().redo();self.remember_current();self.refresh_collection()
    def open_video(self):
        if self.worker and self.worker.isRunning():return
        paths,_=QFileDialog.getOpenFileNames(self,'Add climbing videos',str(ROOT/'videos'),'Video (*.mp4 *.mov *.mkv *.MP4 *.MOV *.MKV)')
        if paths:self.add_videos(paths)
    def add_videos(self,paths):
        for path in paths:self.workspace.add(path)
        self.workspace.save();self.refresh_collection()
        if not self.reader and not (self.worker and self.worker.isRunning()):self.begin_video(Path(paths[0]))
        if self.collection_worker and self.collection_worker.isRunning():
            self.statusBar().showMessage('Videos added. Saved measurements will load as you open each video.',6000);return
        folders=[ROOT/'videos',ROOT/'artifacts'/'labels']
        last=self.settings.value('labels_folder','')
        if last:folders.append(Path(last))
        self.collection_worker=CollectionWorker([p for p in self.workspace.videos if p not in self.workspace.states],folders)
        self.collection_worker.found.connect(self.collection_found);self.collection_worker.failed.connect(lambda p,e:self.statusBar().showMessage(Path(p).name+': '+e,8000));self.collection_worker.start()
    def collection_found(self,path,match):
        if match and path not in self.workspace.states and (not self.video_path or path!=str(self.video_path.resolve())):
            label_path,doc=match;self.workspace.remember(path,doc,label_path);self.workspace.save()
        self.refresh_collection()
    def select_video(self,index):
        if not 0<=index<len(self.workspace.videos):return
        path=Path(self.workspace.videos[index])
        if self.video_path and path==self.video_path.resolve():return
        if self.worker and self.worker.isRunning():
            self.statusBar().showMessage('Finish opening the current video before switching.',5000);self.refresh_collection();return
        self.begin_video(path)
    def next_video(self,direction):
        if not self.workspace.videos:return
        index=self.video_selector.currentIndex();self.select_video(max(0,min(len(self.workspace.videos)-1,index+direction)))
    def refresh_collection(self):
        if not hasattr(self,'video_selector'):return
        self.video_selector.blockSignals(True);self.video_selector.clear()
        for path in self.workspace.videos:
            state=self.workspace.states.get(path);name=state['document']['climber'] if state else Path(path).stem
            self.video_selector.addItem(name+' · '+Path(path).name)
        current=str(self.video_path.resolve()) if self.video_path else None
        self.video_selector.setCurrentIndex(self.workspace.videos.index(current) if current in self.workspace.videos else -1);self.video_selector.blockSignals(False)
        documents=list(self.workspace.documents())
        if self.document() and current:
            documents=[d for d in documents if not (d['source']['sha256']==self.document()['source']['sha256'] and d['attempt']==self.document()['attempt'])];documents.append(self.document())
        for doc in documents:
            for point in doc.get("checkpoints",[]):self.workspace.add_point_name(point["name"])
        selected_name=self.point_name.text();self.point_name.blockSignals(True);self.point_name.clear();self.point_name.addItems(self.workspace.shared_points());self.point_name.setText(selected_name);self.point_name.blockSignals(False)
        self.comparison_documents=documents;overview,points,holds=rows(documents)
        activity_rows=[]
        for doc in documents:
            for event in sorted(doc['events'],key=lambda e:e['start']['seconds']):
                if event['kind'] not in ('rest','clip','chalk'):continue
                base=doc['start']['seconds'] if doc['start'] else None
                activity_rows.append([doc['climber'],event['kind'],event['hand'],event['start']['seconds']-base if base is not None else None,event['end']['seconds']-base if base is not None else None,event['end']['seconds']-event['start']['seconds']])
        self.comparison_activity_table.setRowCount(len(activity_rows))
        for row,values in enumerate(activity_rows):
            for col,value in enumerate(values):self.comparison_activity_table.setItem(row,col,QTableWidgetItem('Start missing' if value is None else f'{value:.2f}' if isinstance(value,float) else str(value)))
        columns=[('Athlete','athlete'),('Result','outcome'),('Climb (s)','climb_seconds'),('Total rest incl. chalk (s)','total_rest_marked_seconds'),('Total rest episodes','total_rest_marked_count'),('Total rest share','total_marked_rest_share'),('Dedicated rest (s)','rest_marked_seconds'),('Dedicated rest count','rest_marked_count'),('Clip (s)','clip_marked_seconds'),('Clip count','clip_marked_count'),('Chalk count','chalk_marked_count'),('Chalk (s)','chalk_marked_seconds'),('Left chalk (s)','left_chalk_marked_seconds'),('Right chalk (s)','right_chalk_marked_seconds'),('Left rest (s)','left_rest_marked_seconds'),('Right rest (s)','right_rest_marked_seconds'),('Left clip (s)','left_clip_marked_seconds'),('Right clip (s)','right_clip_marked_seconds')]
        names=sorted({p['point'] for p in points});headers=[c[0] for c in columns]+[name+' (s)' for name in names]
        table=self.comparison_table;table.setColumnCount(len(headers));table.setHorizontalHeaderLabels(headers);table.setRowCount(len(overview));self.comparison_rows=overview
        for row,summary in enumerate(overview):
            for col,(title,key) in enumerate(columns):
                value=summary[key];text='Unmarked' if value is None else f'{value*100:.1f}%' if key in ('marked_rest_share','total_marked_rest_share') else f'{value:.2f}' if isinstance(value,float) else str(value)
                table.setItem(row,col,QTableWidgetItem(text))
            for col,name in enumerate(names,len(columns)):
                arrivals=[p['seconds_from_climb_start'] for p in points if p['point']==name and all(p[k]==summary[k] for k in ('athlete','attempt','video')) and p['seconds_from_climb_start'] is not None]
                item=QTableWidgetItem(' / '.join(f'{t:.2f}' for t in arrivals) or 'Unmarked')
                best=min((p['seconds_from_climb_start'] for p in points if p['point']==name and p['seconds_from_climb_start'] is not None),default=None)
                if arrivals and min(arrivals)==best:
                    from PySide6.QtGui import QColor
                    item.setBackground(QColor('#def3e9'));item.setForeground(QColor('#116047'));item.setToolTip('Fastest marked arrival at this point')
                table.setItem(row,col,item)
        self.pattern_dashboard.update_documents(documents)
        self.comparison_charts.set_documents(documents)
        table.resizeColumnsToContents();self.collection_summary.setText(f'{len(self.workspace.videos)} videos · {len(documents)} measured attempts · Fastest point arrivals highlighted in green')
    def comparison_open(self,row,col):
        if not 0<=row<len(self.comparison_documents):return
        summary=self.comparison_rows[row]
        for path,state in self.workspace.states.items():
            d=state['document']
            if all(d[k]==summary[j] for k,j in [('climber','athlete'),('attempt','attempt')]) and d['source']['file']==summary['video']:
                self.select_video(self.workspace.videos.index(path));self.main_tabs.setCurrentIndex(0);return
    def toggle_theme(self):
        from .design import apply_theme
        apply_theme(self,"light" if self.theme=="dark" else "dark")
    def start_resource_monitor(self):
        from .resources import ResourceMonitor,format_usage
        self.resource_monitor=ResourceMonitor(self);self.resource_monitor.sampled.connect(lambda data:self.usage_label.setText(format_usage(data)));self.resource_monitor.start()
    def clear_athlete(self):
        if not self.history:return self.error('Open an athlete video first.')
        self.pause();name=self.document()['climber']
        answer=QMessageBox.question(self,'Clear this athlete?',f'Clear all loaded measurements for {name}, across their attempts in this collection? Saved labels will be replaced with empty measurements. Local backups will be kept.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)
        if answer==QMessageBox.StandardButton.Yes:self.apply_reset(athlete=name)
    def clear_measurements(self):
        if not self.history and not self.workspace.states:return self.error('There are no measurements to clear.')
        self.pause()
        dialog=QMessageBox(self);dialog.setWindowTitle('Clear measurements?');dialog.setText('Choose what to reset.');dialog.setInformativeText('Removes climb start/end, points, holds, rests, clips, chalking and unfinished timers. Athlete names and videos stay. Saved label files are replaced with empty measurements; a backup is kept locally.')
        current=dialog.addButton('Current attempt',QMessageBox.ButtonRole.DestructiveRole);current.setEnabled(bool(self.history))
        all_videos=dialog.addButton('All videos in collection',QMessageBox.ButtonRole.DestructiveRole)
        importing=bool(self.collection_worker and self.collection_worker.isRunning());all_videos.setEnabled(not importing)
        if importing:dialog.setInformativeText(dialog.informativeText()+'\n\nAll-collection reset becomes available after saved measurements finish loading.')
        cancel=dialog.addButton(QMessageBox.StandardButton.Cancel);dialog.setDefaultButton(cancel);dialog.exec()
        choice=dialog.clickedButton()
        if choice not in (current,all_videos):return
        self.apply_reset(choice==all_videos)
    def apply_reset(self,all_videos=False,athlete=None):
        self.remember_current();key=str(self.video_path.resolve()) if self.video_path else None
        targets=[p for p,s in self.workspace.states.items() if s["document"]["climber"]==athlete] if athlete else list(self.workspace.states) if all_videos else [key]
        try:
            for path in targets:
                if path not in self.workspace.states:continue
                state=self.workspace.states[path];old=state['document'];fresh=empty_labels(old['source']);fresh.update(climber=old['climber'],attempt=old['attempt'])
                from uuid import uuid4
                backup=ROOT/'artifacts'/'measurement-backups'/(Path(path).stem+'-'+str(uuid4())+'.labels.json');save(old,backup)
                if state['label_path']:save(fresh,state['label_path'])
                self.workspace.remember(path,fresh,state['label_path'],0);self.session_histories[path]=History(fresh)
                if path==key:self.history=self.session_histories[path];self.saved=copy.deepcopy(fresh)
            self.workspace.save()
            if self.history:self.refresh();self.show_frame(0)
            self.refresh_collection();self.statusBar().showMessage('Measurements cleared. Previous measurements backed up in artifacts/measurement-backups.',10000)
        except Exception as error:self.error(error)
    def export_pdf(self):
        self.remember_current();self.refresh_collection()
        if not self.comparison_documents:return self.error('Add videos and measure at least one climb first.')
        path,_=QFileDialog.getSaveFileName(self,'Export private PDF comparison',str(ROOT/'artifacts'/'reports'/'all-athletes.pdf'),'PDF (*.pdf)')
        if path:
            try:
                from .pdf_report import export_pdf
                source=Path(path).with_name(Path(path).stem+'-source.html')
                export_comparison(self.comparison_documents,source)
                focus=self.comparison_charts.focus.currentText()
                export_pdf(source,path,None if focus=='All athletes' else focus)
                self.statusBar().showMessage('PDF and source HTML/CSV saved locally.',10000)
            except Exception as error:self.error(error)
    def export_all(self):
        self.remember_current();self.refresh_collection()
        if not self.comparison_documents:return self.error('Add videos and measure at least one climb first.')
        path,_=QFileDialog.getSaveFileName(self,'Export this workspace comparison',str(ROOT/'artifacts'/'reports'/'all-athletes.html'),'HTML (*.html)')
        if path:
            try:export_comparison(self.comparison_documents,path);self.statusBar().showMessage('All workspace measurements exported as HTML and CSV.',10000)
            except Exception as e:self.error(e)

def main(video=None):
    app=QApplication.instance() or QApplication(sys.argv);app.setStyle('Fusion');window=Window(video)
    available=app.primaryScreen().availableGeometry();window.resize(min(1450,available.width()-40),min(1000,available.height()-40));window.show();window.start_resource_monitor();return app.exec()
