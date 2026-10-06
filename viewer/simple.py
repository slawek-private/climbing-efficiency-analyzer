"""Focused interface: climb boundaries, named arrivals, left/right holds."""
import copy
import bisect
import sys
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from pathlib import Path
from PySide6.QtCore import QTimer,QSettings
from PySide6.QtGui import QShortcut,QKeySequence
from PySide6.QtWidgets import QApplication,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QLineEdit,QGroupBox,QTableWidget,QTableWidgetItem,QFileDialog,QMessageBox,QInputDialog,QComboBox,QDialog,QDialogButtonBox,QCheckBox
from .app import Window as LegacyWindow
from .labels import ROOT, make_event,History,empty_labels,load,save
from .version import APP_NAME,__version__
from .comparison import export_comparison,load_collection,rows
from .video import VideoReader
from .discovery import matching_labels
from .workspace import Workspace
from .collection import CollectionWorker
from .platform_runtime import GPU_BACKEND

ALLOWED_KEYS=('Space','Left','Right','Ctrl+S','Ctrl+Z','Ctrl+Y','S','E','P','L','R','Q','W','C','V','Delete','Shift+Left','Shift+Right','Ctrl+[','Ctrl+]')

def timecode(seconds):
    minutes=int(seconds//60);return f'{minutes:02d}:{seconds-minutes*60:06.3f}'

class SharedPointSelector(QComboBox):
    def __init__(self):
        super().__init__();self.setEditable(True);self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    def text(self):return self.currentText()
    def setText(self,value):self.setEditText(value)
    def setPlaceholderText(self,value):self.lineEdit().setPlaceholderText(value)

class Window(LegacyWindow):
    def __init__(self,video=None):
        self.settings=QSettings("ClimbingEfficiencyAnalyzer","ClimbStudio")
        from .projects import find
        self.project=find(ROOT,self.settings.value('current_project',''))
        self.workspace=Workspace(self.project.workspace_file);self.session_histories={};self.session_indexes={};self.collection_worker=None
        self.updater=None;self.release=None;self.pending_update=None;self.guidance=False;self.save_error=None;self.workspace_error=None
        self.autosave_timer=QTimer();self.autosave_timer.setSingleShot(True);self.autosave_timer.setInterval(600);self.autosave_timer.timeout.connect(self.autosave)
        self.resource_monitor=None;self.preview_worker=None;self.replay_range=None;self.coaching_export_worker=None
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
            if shortcut.property('manual_key') not in ALLOWED_KEYS:shortcut.setEnabled(False)
        self.slider.sliderReleased.connect(self.finish_scrub)
        self.simple_ready=True
        from .design import build
        build(self);self.install_timer_shortcuts()
        points=self.workspace.shared_points();self.point_name.setText(self.settings.value('last_point','') or (points[-1] if points else 'A'))
        self.refresh_live();self.refresh_collection();self.refresh_preview_status();self.update_project_label()
        if not video and self.workspace.videos:self.show_view(self.library)
    def install_timer_shortcuts(self):
        actions={'Ctrl+[':lambda:self.next_video(-1),'Ctrl+]':lambda:self.next_video(1),'Delete':self.delete_selected,'Shift+Left':lambda:self.step(-1,True),'Shift+Right':lambda:self.step(1,True),'S':self.set_start,'E':self.set_failure,'P':self.add_point,'L':lambda:self.toggle_hand_timer('clip','left'),'R':lambda:self.toggle_hand_timer('clip','right'),'Q':lambda:self.toggle_hand_timer('rest','left'),'W':lambda:self.toggle_hand_timer('rest','right'),'C':lambda:self.toggle_hand_timer('chalk','left'),'V':lambda:self.toggle_hand_timer('chalk','right')}
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
        d=copy.deepcopy(self.document());d['schema_version']='1.3.0' if d['schema_version']=='1.3.0' else '1.2.0';now=self.reader.point(self.frame_number)
        pending=next((e for e in d['open_events'] if e['kind']==kind and e['hand']==hand),None)
        if pending:
            if now['seconds']<=pending['start']['seconds']:
                self.statusBar().showMessage('Advance the video before stopping this timer.',4000);return
            closed=make_event(pending,now)
            d['events'].append(closed);d['open_events'].remove(pending)
        else:
            if any(e['kind']==kind and e['hand']==hand and e['start']['seconds']<=now['seconds']<e['end']['seconds'] for e in d['events']):
                event=next(e for e in d['events'] if e['kind']==kind and e['hand']==hand and e['start']['seconds']<=now['seconds']<e['end']['seconds'])
                self.events_body.show();self.select_timeline_event(event['id']);self.edit_event();return
            event={'kind':kind,'hand':hand,'target':self.draw.value() if kind=='clip' else None,'start':now,'confidence':1,'notes':''}
            if kind=='clip' and self.clip_method.currentData():event['clip_method']=self.clip_method.currentData()
            d['open_events'].append(event)
        d['reviewed']={k:False for k in d['reviewed']}
        if self.commit(d) and pending and kind=='clip':
            self.clip_method.setCurrentIndex(0)
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
            if shortcut.property('manual_key') not in ALLOWED_KEYS:shortcut.setEnabled(False)
    def refresh(self):
        super().refresh()
        if not self.simple_ready or not self.history:return
        d=self.document();kind=self.event_kind.currentData();hand=self.event_hand.currentData();query=self.event_search.text().strip().casefold()
        self.visible_events=[e for e in self.visible_events if (kind is None or e['kind']==kind) and (hand is None or e['hand']==hand) and (not query or query in (' '.join(str(e.get(k) or '') for k in ('target','notes','clip_method'))).casefold())]
        self.table.blockSignals(True);self.table.setRowCount(len(self.visible_events))
        self.table.setHorizontalHeaderLabels(['Event','Hand','#','Start','End','Time'])
        self.points_table.setHorizontalHeaderLabels(['Point','Video','Climb','Comment'])
        for col,tip in enumerate(['','Seconds in the video','Seconds from climb start','']):self.points_table.horizontalHeaderItem(col).setToolTip(tip)
        for col,tip in enumerate(['','','Hold or quickdraw number, with clip method','Seconds from climb start','Seconds from climb start','Seconds']):self.table.horizontalHeaderItem(col).setToolTip(tip)
        for row,e in enumerate(self.visible_events):
            for col,value in enumerate(({'contact':'Hold','rest':'Rest','clip':'Clip','offwall':'Hand away','chalk':'Chalk'}[e['kind']],{'left':'Left','right':'Right','none':'—'}[e['hand']],str(e['target'] or '—')+{'mouth':' · mouth','direct':' · direct'}.get(e.get('clip_method'),''),f"{e['start']['seconds']-d['start']['seconds']:.2f}" if d['start'] else '—',f"{e['end']['seconds']-d['start']['seconds']:.2f}" if d['start'] else '—',f"{e['end']['seconds']-e['start']['seconds']:.2f}")):
                item=QTableWidgetItem(str(value));item.setToolTip(f"Video time: {e['start']['seconds']:.3f}–{e['end']['seconds']:.3f} s"+('' if d['start'] else ' · mark the climb start for climb-relative times'));self.table.setItem(row,col,item)
        self.table.blockSignals(False)
        self.point_rows=sorted(d.get('checkpoints',[]),key=lambda p:p['point']['seconds']);self.points_table.setRowCount(len(self.point_rows))
        for row,p in enumerate(self.point_rows):
            for col,v in enumerate((p['name'],f"{p['point']['seconds']:.2f} s",f"{p['point']['seconds']-d['start']['seconds']:.2f} s" if d['start'] and p['point']['seconds']>=d['start']['seconds'] else '—',p.get('comment',''))):self.points_table.setItem(row,col,QTableWidgetItem(v))
        self.points_table.setVisible(bool(self.point_rows));self.points_table.resizeColumnsToContents();self.events_toggle.setText(('▾' if self.events_body.isVisible() else '▸')+f'  Events · {len(self.visible_events)}/{len(d["events"])}');self.refresh_live();self.update_project_label()
    def set_frame_step(self,value):
        self.settings.setValue('frame_step',value)
        if hasattr(self,'step_back_button'):self.step_back_button.setToolTip(f'Back {value} frames (←) · Shift+← one frame');self.step_forward_button.setToolTip(f'Forward {value} frames (→) · Shift+→ one frame')
    def sync_active(self):return hasattr(self,'compare_tabs') and self.main_tabs.currentWidget() is self.compare_page and self.compare_tabs.currentWidget() is self.sync_view
    def show_view(self,widget):
        """Open a view, including those nested inside Compare."""
        if widget in (self.comparison_page,self.comparison_charts,self.pattern_dashboard,self.sync_view):
            self.main_tabs.setCurrentWidget(self.compare_page);self.compare_tabs.setCurrentWidget(widget)
        else:self.main_tabs.setCurrentWidget(widget)
    def step(self,delta,single=False):
        if self.sync_active():return self.sync_view.step_frames(delta*(1 if single else self.frame_step.value()))
        if not self.reader:return
        self.pause();base=getattr(self,'pending_scrub',self.decode_requested if self.decode_seek and self.decode_future is not None else self.frame_number)
        self.scrub_timer.stop()
        if hasattr(self,'pending_scrub'):del self.pending_scrub
        self.show_frame(base+delta*(1 if single else self.frame_step.value()))
    def select_timeline_event(self,identifier):
        if any(e["id"]==identifier for e in self.document().get("footwork",{}).get("events",[])):
            self.footwork_panel.select(identifier);return
        if any(e['id']==identifier for e in self.document()['events']) and not any(e['id']==identifier for e in self.visible_events):
            for field in (self.event_kind,self.event_hand):field.blockSignals(True);field.setCurrentIndex(0);field.blockSignals(False)
            self.event_search.blockSignals(True);self.event_search.clear();self.event_search.blockSignals(False);self.refresh()
        row=next((i for i,e in enumerate(self.visible_events) if e['id']==identifier),None)
        if row is not None:self.table.selectRow(row);self.table.setFocus()
    def clear_boundary(self,key):
        if not self.history:return
        d=copy.deepcopy(self.document());d[key]=None;d['outcome']='unknown' if key=='end' else d['outcome'];d['reviewed']={k:False for k in d['reviewed']};self.commit(d)
    def delete_selected(self):
        if QApplication.focusWidget() in (self.footwork_panel.table,self.footwork_panel.table.viewport()):self.footwork_panel.delete();return
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
        if not self.slider.isSliderDown():
            self.slider.blockSignals(True);self.slider.setValue(number);self.slider.blockSignals(False)
        self.refresh_live()
        if self.play_after_decode:self.start_playback()
        if self.playing and number==len(self.reader.times)-1 and not self.replay_range:self.pause()
        if self.playing and number!=self.decode_requested:self.submit_decode();self.decode_poll.start()
    def start_playback(self):
        self.play_after_decode=False;self.playing=True;self.reset_clock();self.timer.start();self.play_button.setText('Pause · Space')
    def toggle_play(self):
        if self.sync_active():return self.sync_view.toggle_play()
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
        if self.replay_range and self.reader.times[self.frame_number]>=self.replay_range[1]:
            bounds=self.replay_range;self.pause();self.show_frame(max(0,bisect.bisect_right(self.reader.times,bounds[0])-1));self.replay_range=bounds
            if self.decode_future is not None:self.play_after_decode=True
            else:self.start_playback()
            return
        rate=(.25,.5,1,1.5,2)[self.speed.currentIndex()];seconds=self.play_start+self.elapsed.elapsed()/1000*rate
        frame=min(len(self.reader.times)-1,max(0,bisect.bisect_right(self.reader.times,seconds)-1))
        if frame!=self.frame_number and (self.decode_future is None or frame!=self.decode_requested):self.show_frame(frame)
        if not self.async_decode and self.frame_number==len(self.reader.times)-1 and not self.replay_range:self.pause()
    def pause(self):
        self.replay_range=None
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
        if not self.flush_autosave():return
        if not Path(path).is_file():return self.locate_video(path)
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
        self.refresh_collection();self.refresh_live()
    def closeEvent(self,event):
        if self.coaching_export_worker and self.coaching_export_worker.isRunning():
            self.coaching_export_worker.requestInterruption();self.coaching_export_worker.wait()
        if self.preview_worker and self.preview_worker.isRunning():
            self.preview_worker.requestInterruption();self.preview_worker.wait()
        if self.resource_monitor:
            self.resource_monitor.requestInterruption();self.resource_monitor.wait(7000)
        if not self.flush_autosave():event.ignore();return
        self.remember_current()
        if self.collection_worker and self.collection_worker.isRunning():
            self.collection_worker.requestInterruption();self.collection_worker.wait(5000)
        self.scrub_timer.stop();self.decode_poll.stop()
        if self.decode_future is not None:
            try:self.decode_future.result()
            except Exception:pass
            self.decode_future=None
        super().closeEvent(event)
        if event.isAccepted():
            self.decoder.shutdown(wait=True)
            if hasattr(self,'sync_view'):self.sync_view.shutdown()
            if hasattr(self,'library'):self.library.shutdown()
            if self.pending_update:self.pending_update();self.pending_update=None
    def check_completeness(self):
        if not self.history:return
        self.pause();dialog=QDialog(self);dialog.setWindowTitle('Check completeness');box=QVBoxLayout(dialog)
        explanation=QLabel('Check a box only after checking the whole climb and marking every event of that type. Reports use this to distinguish complete review from partial markings. Missing data stays unknown. Stop all running hand timers before saving checked boxes. Editing measurements clears these checks. Footwork uses its own visible/hidden video review.');explanation.setWordWrap(True);box.addWidget(explanation);fields={}
        titles={'boundaries':'Start and end are correct','left_contacts':'All left-hand hold contacts are marked','right_contacts':'All right-hand hold contacts are marked','rests':'All rest and chalk intervals are marked','clips':'All clips are marked','left_offwall':'All left-hand releases are marked','right_offwall':'All right-hand releases are marked'}
        for key,title in titles.items():
            field=QCheckBox(title);field.setChecked(self.document()['reviewed'].get(key,False));box.addWidget(field);fields[key]=field
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);box.addWidget(buttons)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            d=copy.deepcopy(self.document());d['reviewed']={key:field.isChecked() for key,field in fields.items()}
            self.commit(d)
    def edit_coaching(self):
        from .coaching_ui import edit_coaching
        edit_coaching(self)
    def export_coaching(self):
        from .coaching_export_ui import export_dialog
        export_dialog(self)
    def replay_observation(self,event):
        if not self.reader:return
        self.pause();a=max(0,event["start"]["seconds"]-2);b=min(self.reader.times[-1],(event.get("end") or event["start"])["seconds"]+2)
        self.show_frame(max(0,bisect.bisect_right(self.reader.times,a)-1));self.replay_range=(a,b)
        if self.decode_future is not None:self.play_after_decode=True
        else:self.start_playback()
    def refresh_live(self):
        if not self.simple_ready:return
        d=self.document();now=self.reader.times[self.frame_number] if self.reader else 0
        if hasattr(self,'footwork_panel'):self.footwork_panel.refresh(d,now)
        if hasattr(self,"empty_hint"):
            loaded=bool(self.reader);opening=bool(self.worker and self.worker.isRunning())
            for widget in (self.image,self.precision_scrubber,self.transport,self.boundary_box,self.climb_box,self.events_card):widget.setVisible(loaded)
            self.empty_hint.setVisible(not loaded);self.empty_panel.hide();self.measure_page.widget(0).layout().activate();self.measurement_scroll.setVisible(loaded and not self.settings.value('inspector_hidden',False,type=bool))
            foot_pending=d.get('footwork',{}).get('pending') if d else None
            self.active_timers.setVisible(loaded and not self.measurement_scroll.isVisible() and bool(d and (d['open_events'] or foot_pending)))
            self.active_timers.setText((f"Both feet off running: {max(0,now-foot_pending['start']['seconds']):.1f} s · " if foot_pending else '')+' · '.join(f"{e['hand'].capitalize()} {e['kind']} running: {max(0,now-e['start']['seconds']):.1f} s" for e in (d['open_events'] if d else [])))
            self.drop_title.setText(f'Opening {self.video_path.name}…' if opening and self.video_path else 'Drop climbing videos here')
            self.drop_choose.setVisible(not opening);self.drop_note.setText('Reading the file once: checksum and every frame timestamp. Cached afterwards.' if opening else 'MP4, MOV or MKV · originals stay where they are, nothing is uploaded')
            if loaded:self.position.setText(f'<span style="font-size:19px;font-weight:600">{timecode(now)}</span>&nbsp;&nbsp;<span style="font-size:11px;color:{"#b2b8bf" if self.theme=="dark" else "#59616b"}">frame {self.frame_number}</span>')
            self.start_button.setText(f"Replace start · {d['start']['seconds']:.3f} s" if d and d['start'] else 'Mark start');self.start_clear.setVisible(bool(d and d['start']))
            self.end_button.setText(f"Replace end · {d['end']['seconds']:.3f} s · "+{'failed':'fell','completed':'topped'}.get(d['outcome'],d['outcome']) if d and d['end'] else 'Mark end')
            self.end_edit.setVisible(bool(d and d['end']));self.end_clear.setVisible(bool(d and d['end']))
            failure=self.save_error or self.workspace_error or self.workspace.load_error
            self.save_state.setProperty('state','error' if failure else 'ok');self.save_state.setStyleSheet('font-weight:600;' if failure else '')
            persisted=bool(self.label_path and self.label_path.exists() and self.saved==d)
            self.save_state.setText('⚠ Not saved' if failure else '' if not d else 'Saving…' if self.autosave_timer.isActive() else '✓ Saved' if persisted else 'No changes saved yet')
            self.save_state.setToolTip(failure or ('Saved to '+str(self.label_path) if persisted else 'Make a measurement or choose Save to create a labels file.'))
            self.save_banner.setVisible(bool(failure));self.save_detail.setText(failure or '')
        self.start_status.setText('Start: '+(f"{d['start']['seconds']:.3f} s in video" if d and d['start'] else 'not marked'))
        self.end_status.setText('End: '+(f"{d['end']['seconds']:.3f} s · "+{'failed':'Fell / failed','completed':'Topped'}.get(d['outcome'],d['outcome']) if d and d['end'] else 'not marked'))
        self.duration_status.setText('Climb time  '+(f"{d['end']['seconds']-d['start']['seconds']:.3f} s" if d and d['start'] and d['end'] else '—  mark start and end'))
        for kind in ('rest','clip'):
            pending=next((e for e in d['open_events'] if e['kind']==kind),None) if d else None
            current=next((e for e in d['events'] if e['kind']==kind and e['start']['seconds']<=now<e['end']['seconds']),None) if d else None
            current=pending if pending and pending['start']['seconds']<=now else current
            self.interval_status[kind].setText(f"{now-current['start']['seconds']:.3f} s"+(' · '+current['hand']+' hand' if kind=='clip' else '') if current else 'Ready to measure')
            self.interval_start[kind].setEnabled(bool(d) and pending is None and current is None);self.interval_stop[kind].setEnabled(bool(pending) and now>pending['start']['seconds'])
        for (kind,hand),control in getattr(self,'hand_timer_buttons',{}).items():
            pending=next((e for e in d['open_events'] if e['kind']==kind and e['hand']==hand),None) if d else None
            current=next((e for e in d['events'] if e['kind']==kind and e['hand']==hand and e['start']['seconds']<=now<e['end']['seconds']),None) if d else None
            role='stop' if pending else 'start'
            if control.property('role')!=role:control.setProperty('role',role);control.setStyleSheet('')
            visible=pending if pending and pending['start']['seconds']<=now else current
            name=kind.capitalize();text='Start '+name.lower()
            if pending and visible:text=f'Stop {name.lower()}\n{now-visible["start"]["seconds"]:.1f} s'
            elif pending:text=f'■ {name} · seek forward'
            elif visible:text=f'{name} · {visible["end"]["seconds"]-visible["start"]["seconds"]:.1f} s\nEdit interval'
            control.setText(text);control.setEnabled(bool(d))
            if pending and kind=='clip':control.setToolTip(f"Quickdraw {pending['target']} · {pending.get('clip_method','method not set')} · captured when started")
            if kind=='chalk' and d:control.setToolTip(f"{hand.capitalize()} hand chalk · {sum(1 for e in d['events'] if e['kind']=='chalk' and e['hand']==hand)} recorded · press to start or stop (key {control.key})")
            self.hand_timer_cancel[kind,hand].setVisible(bool(pending))
        if hasattr(self,'precision_scrubber'):
            self.precision_scrubber.sync(self.reader.times[-1] if self.reader else 1,now,d)
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
        self.pause();d=copy.deepcopy(self.document());d.setdefault('checkpoints',[]).append({'id':str(uuid4()),'name':name,'point':self.reader.point(self.frame_number)})
        if self.commit(d):self.settings.setValue('last_point',name)
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
            self.reader=self.open_video_reader(index);self.decoder_choice.blockSignals(True);self.decoder_choice.setCurrentIndex(1 if self.reader.backend==GPU_BACKEND else 0);self.decoder_choice.blockSignals(False);self.history=History(empty_labels(index['source']));self.saved=copy.deepcopy(self.document());self.slider.setRange(0,len(self.reader.times)-1);self.frame_number=0
            folders=[self.video_path.parent,ROOT/'videos',self.project.labels]
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
            self.draw.setValue(self.workspace.states.get(key,{}).get("quickdraw",next_draw));self.refresh_collection();self.refresh_preview_status();self.refresh_live();self.offer_tour();self.apply_comparison_document()
        except Exception as error:self.error(error)
    def read_labels(self,path,quiet=False):
        try:
            d=load(path);expected=self.reader.index['source']
            if any(d['source'][k]!=expected[k] for k in expected if k!='file'):raise ValueError('Measurements do not match the video checksum or timestamp index')
            points=[p for p in (d['start'],d['end']) if p]
            for e in d['events']+d['open_events']:points.extend([e['start']]+([e['end']] if 'end' in e else []))
            points.extend(p['point'] for p in d.get('checkpoints',[]))
            from .footwork import validate_track
            points.extend(validate_track(d))
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
        if self.library.bulk and self.library.bulk.isRunning():
            self.statusBar().showMessage('A preview queue is running. Manage or cancel it in Library.',6000);return
        if self.reader.backend=='preview':return
        self.pause()
        from .preview_cache import PreviewWorker
        self.preview_worker=PreviewWorker(self.video_path,copy.deepcopy(self.reader.index),ROOT/'artifacts'/'preview-cache')
        self.preview_worker.progress.connect(lambda value:self.preview_button.setText(f'Preparing preview {value}% · cancel'))
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
        self.enforce_storage()
    def refresh_preview_status(self):
        if not hasattr(self,'preview_button'):return
        running=bool(self.preview_worker and self.preview_worker.isRunning())
        cached=bool(self.reader and self.reader.backend=='preview')
        if not running:self.preview_button.setText('● Smooth preview' if cached else 'Prepare smooth preview')
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
                self.decoder_choice.blockSignals(True);self.decoder_choice.setCurrentIndex(1 if self.reader.backend==GPU_BACKEND else 0);self.decoder_choice.blockSignals(False);self.prepare_preview()
            return
        if self.reader.backend=='preview':return
        if self.decode_future is not None:
            self.statusBar().showMessage('Pause and wait for the current frame before switching decoder.',5000);self.decoder_choice.blockSignals(True);self.decoder_choice.setCurrentIndex(1 if self.reader.backend==GPU_BACKEND else 0);self.decoder_choice.blockSignals(False);return
        self.pause();old=self.reader;backend=GPU_BACKEND if index==1 else 'cpu'
        try:
            replacement=VideoReader(self.video_path,old.index,backend);replacement.frame(self.frame_number)
        except Exception as e:
            if 'replacement' in locals():replacement.close()
            self.decoder_choice.blockSignals(True);self.decoder_choice.setCurrentIndex(1 if old.backend==GPU_BACKEND else 0);self.decoder_choice.blockSignals(False);self.error('Decoder unavailable: '+str(e));return
        self.reader=replacement;self.settings.setValue("decoder_backend",backend);old.close();self.show_frame(self.frame_number)
    def toggle_inspector(self):
        hidden=not self.settings.value('inspector_hidden',False,type=bool)
        self.settings.setValue('inspector_hidden',hidden);self.inspector_button.setText('Show controls' if hidden else 'Hide controls');self.refresh_live()
    def set_route(self):
        if not self.history:return
        route,ok=QInputDialog.getText(self,'Route identity','Use the same route name only for attempts on the same route.',text=self.document()['route'])
        if ok and route.strip():
            d=copy.deepcopy(self.document());d['route']=route.strip();self.commit(d)
    def new_attempt(self):
        if not self.reader or not self.flush_autosave():return
        self.remember_current();self.workspace.archive(self.video_path)
        old=self.document();doc=empty_labels(copy.deepcopy(old['source']));doc['climber']=old['climber'];doc['route']=old['route']
        doc['attempt']=str(max([int(d['attempt']) for d in self.workspace.documents() if d['source']['sha256']==doc['source']['sha256'] and d['attempt'].isdigit()]+[0])+1)
        self.history=History(doc);self.saved=None;self.label_path=None;self.draw.setValue(1)
        self.autosave();self.refresh();self.refresh_collection()
    def choose_attempt(self):
        if not self.reader or not self.flush_autosave():return
        key=str(self.video_path.resolve());entries=[e for e in self.workspace.attempts if e['path']==key]
        if not entries:return self.statusBar().showMessage('No earlier attempts. Choose New attempt to record another climb.',6000)
        names=[f"{i+1}. {e['state']['document']['climber']} · attempt {e['state']['document']['attempt']}" for i,e in enumerate(entries)]
        chosen,ok=QInputDialog.getItem(self,'Open attempt','Saved attempts',names,0,False)
        if not ok:return
        entry=entries[names.index(chosen)];self.remember_current();self.workspace.archive(key);self.workspace.attempts.remove(entry)
        state=entry['state'];self.history=History(state['document']);self.saved=copy.deepcopy(self.document());self.label_path=Path(state['label_path']) if state['label_path'] else None
        self.remember_current();self.refresh();self.refresh_collection();self.show_frame(state['frame'])
    def locate_video(self,path):
        from .library import checksum
        chosen,_=QFileDialog.getOpenFileName(self,'Locate original video — checksum must match',self.settings.value('videos_folder',''),'Video (*.mp4 *.mov *.mkv *.m4v)')
        if not chosen:return
        try:self.workspace.relink(path,chosen,checksum(chosen))
        except (ValueError,OSError) as error:return self.error(error)
        self.session_histories.pop(str(Path(path).resolve()),None);self.refresh_collection();self.begin_video(Path(chosen))
    def save_copy(self):
        if not self.history:return
        path,_=QFileDialog.getSaveFileName(self,'Save measurements copy',str(self.project.labels/'measurements.labels.json'),'Labels (*.labels.json)')
        if not path:return
        previous=self.label_path;self.label_path=Path(path)
        if not self.autosave():self.label_path=previous
    def show_save_folder(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.project.labels)))
    def schedule_autosave(self):
        if self.history:self.autosave_timer.start();self.refresh_live()
    def autosave(self):
        """Write the measurements to their label file; no dialog. Returns False when writing failed."""
        self.autosave_timer.stop()
        if not self.history or not self.video_path:return True
        if self.saved==self.document() and self.label_path and self.label_path.exists() and not self.save_error:
            self.remember_current();self.refresh_live();return self.workspace_error is None
        if not self.document().get('attempt_id'):
            self.document()['attempt_id']=uuid4().hex;self.label_path=None
        if self.label_path is None:
            self.label_path=self.project.labels/(self.document()['source']['sha256']+'-'+self.document()['attempt_id']+'.labels.json')
        try:
            save(self.document(),self.label_path);self.saved=copy.deepcopy(self.document());self.save_error=None
            self.settings.setValue("labels_folder",str(self.label_path.parent));self.remember_current()
        except Exception as error:self.save_error=f'Not saved to {self.label_path}: {error}'
        self.refresh_live();self.update_project_label();return self.save_error is None and self.workspace_error is None
    def flush_autosave(self):
        if self.autosave_timer.isActive() or self.dirty() or self.save_error or self.workspace_error:return self.autosave()
        return True
    def save_labels(self):
        result=self.autosave()
        if result:self.refresh_collection();self.statusBar().showMessage('Saved '+str(self.label_path),4000)
        return result
    def allow_change(self):
        if not self.flush_autosave():return False
        return super().allow_change()
    def remember_current(self):
        if not self.history or not self.video_path:return
        key=str(self.video_path.resolve());self.session_histories[key]=self.history
        self.workspace.remember(self.video_path,self.document(),self.label_path,self.frame_number)
        self.workspace.states[key]['quickdraw']=self.draw.value()
        try:self.workspace.save();self.workspace_error=None
        except OSError as e:self.workspace_error='Workspace not saved: '+str(e)
        return self.workspace_error is None
    def commit(self,document):
        result=super().commit(document)
        if result:self.remember_current();self.refresh_collection();self.schedule_autosave()
        return result
    def undo(self):
        super().undo();self.remember_current();self.refresh_collection();self.schedule_autosave()
    def redo(self):
        super().redo();self.remember_current();self.refresh_collection();self.schedule_autosave()
    def open_video(self):
        if self.worker and self.worker.isRunning():return
        folder=self.settings.value('videos_folder','') or str(ROOT/'videos')
        paths,_=QFileDialog.getOpenFileNames(self,'Add climbing videos',folder,'Video (*.mp4 *.mov *.mkv *.m4v *.MP4 *.MOV *.MKV *.M4V)')
        if paths:self.settings.setValue('videos_folder',str(Path(paths[0]).parent));self.add_videos(paths)
    def add_videos(self,paths):
        for path in paths:self.workspace.add(path)
        self.workspace.save();self.refresh_collection()
        if not self.reader and not (self.worker and self.worker.isRunning()):self.begin_video(Path(paths[0]))
        if self.collection_worker and self.collection_worker.isRunning():
            self.statusBar().showMessage('Videos added. Saved measurements will load as you open each video.',6000);return
        folders=[ROOT/'videos',self.project.labels]
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
            self.video_selector.addItem(name+' · '+Path(path).name+(' · Missing — locate' if not Path(path).is_file() else ''))
        current=str(self.video_path.resolve()) if self.video_path else None
        index=self.workspace.videos.index(current) if current in self.workspace.videos else -1
        self.video_selector.setCurrentIndex(index);self.video_selector.blockSignals(False)
        self.video_count.setText(f'Viewing {index+1}/{len(self.workspace.videos)}' if index>=0 else f'{len(self.workspace.videos)} videos')
        title='Open now: '+Path(current).name if current else 'Choose a project video'
        self.current_video_label.setText(title);self.current_video_label.setToolTip(title)
        self.video_navigation.refresh(self.workspace.videos,current)
        self.library.update_heading()
        documents=list(self.workspace.documents())
        if self.document() and current:
            documents=[d for d in documents if not (d.get('attempt_id')==self.document().get('attempt_id') if d.get('attempt_id') else d['source']['sha256']==self.document()['source']['sha256'] and d['attempt']==self.document()['attempt'])];documents.append(self.document())
        for doc in documents:
            for point in doc.get("checkpoints",[]):self.workspace.add_point_name(point["name"])
        selected_name=self.point_name.text();self.point_name.blockSignals(True);self.point_name.clear();self.point_name.addItems(self.workspace.shared_points());self.point_name.setText(selected_name);self.point_name.blockSignals(False)
        self.compare_scope.set_documents(documents);self.refresh_comparison()
    def refresh_comparison(self):
        documents=self.compare_scope.chosen();self.comparison_documents=documents;overview,points,_=rows(documents)
        self.fill_leaderboard(overview,points);self.pattern_dashboard.update_documents(documents)
        self.comparison_charts.checkpoint=self.compare_scope.point.currentText();self.comparison_charts.set_documents(documents)
        reference=documents[0]['climber']+' · '+documents[0]['attempt'] if documents else 'none'
        self.collection_summary.setText(f'{len(documents)} attempts · route {self.compare_scope.route.currentText()} · reference {reference}. Gaps compare the same checkpoint. Marked recovery is descriptive; lower is not necessarily better. Review status appears in each metric’s tooltip.')
        if self.sync_active():self.sync_view.activate()
    def fill_leaderboard(self,overview,points):
        """Seven questions a coach asks, one row per attempt; every other number lives in the exports."""
        from PySide6.QtGui import QColor
        from PySide6.QtCore import Qt
        class Sortable(QTableWidgetItem):
            def __lt__(self,other):
                a,b=self.data(Qt.ItemDataRole.UserRole),other.data(Qt.ItemDataRole.UserRole)
                if a is None or b is None:return (a is None)<(b is None)
                return a<b
        self.comparison_rows=overview
        names=sorted({p['point'] for p in points},key=str.casefold)
        headers=['Athlete','Result','Climb','Marked recovery','Clips','Clip method']+names+['Review status']
        table=self.comparison_table;table.setSortingEnabled(False);table.clear();table.setColumnCount(len(headers));table.setHorizontalHeaderLabels(headers);table.setRowCount(len(overview))
        tips=['','','Climb start to marked end','Dedicated rest and chalking, overlaps counted once, as a share of the climb','Completed clips · average clip time','Rope to mouth / direct, where marked']+['Arrival from climb start · gap to the reference attempt']*len(names)+['Boundary / recovery / clip review. Unfinished timers remain provisional.']
        for col,tip in enumerate(tips):table.horizontalHeaderItem(col).setToolTip(tip)
        shares=[o['total_marked_rest_share'] for o in overview if o['total_marked_rest_share'] is not None];top=max(shares,default=0)
        reference=overview[0] if overview else {}
        best={name:min((p['seconds_from_climb_start'] for p in points if p['point']==name and all(p[k]==reference.get(k) for k in ('athlete','attempt','video','attempt_id')) and p['seconds_from_climb_start'] is not None),default=None) for name in names}
        for row,o in enumerate(overview):
            clips=o['clip_marked_count'];average=o['clip_marked_seconds']/clips if clips else None
            methods=' / '.join(f'{o[k]} {w}' for k,w in (('clip_mouth_count','mouth'),('clip_direct_count','direct')) if o[k]) if o['clip_mouth_count'] is not None else None
            result={'Fell / failed':'Fell','unknown':'—'}.get(o['outcome'],o['outcome'])
            cells=[(o['athlete']+('' if o['attempt']=='1' else f' · {o["attempt"]}'),o['athlete'].casefold()),(result,o['outcome']),
                   (f"{o['climb_seconds']:.1f} s" if o['climb_seconds'] is not None else '—',o['climb_seconds']),
                   (f"{o['total_marked_rest_share']*100:.1f} %" if o['total_marked_rest_share'] is not None else '—',o['total_marked_rest_share']),
                   (f'{clips} · {average:.1f} s avg' if average is not None else '—',clips),(methods or '—',methods)]
            for name in names:
                arrivals=[p['seconds_from_climb_start'] for p in points if p['point']==name and all(p[k]==o[k] for k in ('athlete','attempt','video','attempt_id')) and p['seconds_from_climb_start'] is not None]
                first=min(arrivals,default=None);gap=first-best[name] if first is not None and best[name] is not None else None
                cells.append((('—' if first is None else f'{first:.1f} s · '+('reference missing' if gap is None else f'{gap:+.1f} s vs ref')),first))
            document=self.comparison_documents[row];reviewed=[name for key,name in [('boundaries','start/end'),('rests','recovery'),('clips','clips')] if document['reviewed'].get(key)]
            status=(f"{len(document['open_events'])} unfinished · " if document['open_events'] else '')+('Reviewed: '+', '.join(reviewed) if reviewed else 'Not reviewed')
            cells.append((status,status))
            for col,(text,key) in enumerate(cells):
                item=Sortable(text);item.setData(Qt.ItemDataRole.UserRole,key)
                if col==0:item.setData(Qt.ItemDataRole.UserRole+1,row)
                if col==3:item.setData(Qt.ItemDataRole.UserRole+2,top)
                doc=self.comparison_documents[row];review_key={2:'boundaries',3:'rests',4:'clips',5:'clips'}.get(col,'boundaries')
                pending=any(e['kind'] in ({'rest','chalk'} if col==3 else {'clip'} if col in (4,5) else {'rest','clip','chalk','contact','offwall'}) for e in doc['open_events'])
                item.setToolTip(('Unfinished timer — provisional. ' if pending else '')+('Reviewed' if doc['reviewed'].get(review_key) and doc['reviewed'].get('boundaries') else 'Not reviewed — marked measurements only'))
                if text=='—':item.setToolTip('Not marked')
                table.setItem(row,col,item)
        table.setItemDelegateForColumn(3,self.bar_delegate);table.setSortingEnabled(True);table.resizeColumnsToContents();table.horizontalHeader().setStretchLastSection(True);table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
        # Fit the leaderboard to its rows so the detail below gets the space.
        table.setMaximumHeight(table.horizontalHeader().height()+sum(table.rowHeight(r) for r in range(table.rowCount()))+6 if table.rowCount()<12 else 16777215)
        if table.columnWidth(3)<140:table.setColumnWidth(3,140)
        self.comparison_selected()
    def comparison_summary(self,row):
        from PySide6.QtCore import Qt
        item=self.comparison_table.item(row,0)
        index=item.data(Qt.ItemDataRole.UserRole+1) if item else None
        return self.comparison_rows[index] if index is not None and index<len(self.comparison_rows) else None
    def comparison_selected(self):
        table=self.comparison_activity_table;summary=self.comparison_summary(self.comparison_table.currentRow()) if self.comparison_table.selectedItems() else None
        if not summary:
            table.setRowCount(0);self.comparison_detail_title.setText('Select an athlete to see every rest, clip and chalk.');return
        doc=next((d for d in self.comparison_documents if d['climber']==summary['athlete'] and d['attempt']==summary['attempt'] and d['source']['file']==summary['video'] and d.get('attempt_id','')==summary.get('attempt_id','')),None)
        events=[e for e in sorted(doc['events'],key=lambda e:e['start']['seconds']) if e['kind'] in ('rest','clip','chalk')] if doc else []
        base=doc['start']['seconds'] if doc and doc['start'] else None
        self.comparison_detail_title.setText(f"{summary['athlete']} · attempt {summary['attempt']} · {len(events)} rests, clips and chalks")
        table.setRowCount(len(events))
        for row,e in enumerate(events):
            values=[e['kind'].capitalize(),e['hand'].capitalize(),str(e['target']) if e['kind']=='clip' and e['target'] else '—',{'mouth':'Rope to mouth','direct':'Direct'}.get(e.get('clip_method'),'—') if e['kind']=='clip' else '—',
                    f"{e['start']['seconds']-base:.2f}" if base is not None else '—',f"{e['end']['seconds']-base:.2f}" if base is not None else '—',f"{e['end']['seconds']-e['start']['seconds']:.2f}"]
            for col,value in enumerate(values):table.setItem(row,col,QTableWidgetItem(value))
    def comparison_open(self,row,col):
        summary=self.comparison_summary(row)
        if not summary:return
        records=list(self.workspace.states.items())+[(e['path'],e['state']) for e in self.workspace.attempts]
        for path,state in records:
            d=state['document']
            if all(d[k]==summary[j] for k,j in [('climber','athlete'),('attempt','attempt')]) and d['source']['file']==summary['video'] and d.get('attempt_id','')==summary.get('attempt_id',''):
                self.open_comparison_document(path,d,state.get('frame',0));return
    def open_comparison_document(self,path,doc,frame):
        if not self.flush_autosave():return
        if not Path(path).is_file():return self.locate_video(path)
        self.pending_comparison=(copy.deepcopy(doc),frame)
        if self.video_path and str(self.video_path.resolve())==path:
            self.apply_comparison_document()
        else:self.begin_video(Path(path))
        self.show_view(self.measure_page)
    def apply_comparison_document(self):
        if not getattr(self,'pending_comparison',None) or not self.reader:return
        doc,frame=self.pending_comparison
        if doc['source']['sha256']!=self.reader.index['source']['sha256']:return
        self.pending_comparison=None
        if self.document().get('attempt_id')!=doc.get('attempt_id'):
            self.remember_current();self.workspace.archive(self.video_path)
            self.workspace.attempts=[e for e in self.workspace.attempts if e['state']['document'].get('attempt_id')!=doc.get('attempt_id')]
        self.history=History(doc);self.saved=copy.deepcopy(doc);self.label_path=self.project.labels/(doc['source']['sha256']+'-'+doc['attempt_id']+'.labels.json') if doc.get('attempt_id') else None
        self.remember_current();self.refresh();self.show_frame(frame)
    def data_root(self):return ROOT
    def labels_folder(self):return self.project.labels
    def update_project_label(self):
        if hasattr(self,'project_button'):self.project_button.setText(self.project.name+'  ▾')
        self.setWindowTitle(APP_NAME+' · '+self.project.name+(' · '+self.video_path.name if self.video_path else ''))
    def toggle_events(self):
        self.events_body.setVisible(not self.events_body.isVisible());self.settings.setValue('events_open',self.events_body.isVisible());self.refresh()
    def show_about(self):
        QMessageBox.about(self,'About '+APP_NAME,f'<b>{APP_NAME} {__version__}</b><p>Frame-accurate climbing video measurements, fully local.</p><p>MIT License · <a href="https://github.com/slawek-private/climbing-efficiency-analyzer">github.com/slawek-private/climbing-efficiency-analyzer</a></p>')
    def show_diagnostics(self):
        QMessageBox.information(self,'Diagnostics',f'{APP_NAME} {__version__}\n\n'+(self.usage_label.toolTip() if self.usage_label.toolTip().startswith('App CPU') else self.usage_label.text())+f'\n\nData folder: {ROOT}\nDecoder: '+(self.reader.backend if self.reader else 'no video open'))
    VIDEO_SUFFIXES=('.mp4','.mov','.mkv','.m4v')
    def dropped_paths(self,event):
        return [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile() and Path(u.toLocalFile()).suffix.lower() in self.VIDEO_SUFFIXES+('.climbproject',)] if event.mimeData().hasUrls() else []
    def dragEnterEvent(self,event):
        if self.dropped_paths(event):event.acceptProposedAction()
        else:event.ignore()
    def dragMoveEvent(self,event):self.dragEnterEvent(event)
    def dropEvent(self,event):
        paths=self.dropped_paths(event)
        if not paths:return event.ignore()
        event.acceptProposedAction();projects=[p for p in paths if p.suffix.lower()=='.climbproject'];videos=[str(p) for p in paths if p.suffix.lower()!='.climbproject']
        if videos:self.settings.setValue('videos_folder',str(Path(videos[0]).parent));self.add_videos(videos);self.show_view(self.measure_page)
        if projects:self.show_projects(('import_path',projects[0]))
    def show_projects(self,action=None):
        from .projects import ProjectBrowser
        dialog=ProjectBrowser(self)
        if isinstance(action,tuple):QTimer.singleShot(0,lambda:dialog.import_path(action[1]))
        elif action:QTimer.singleShot(0,{'new':dialog.new,'import':dialog.import_file,'export':dialog.export_current}[action])
        dialog.exec()
    def open_project(self,project):
        """Switch to another project; the current one is saved first. Returns False when the user cancels."""
        if project==self.project:self.show_view(self.library);return True
        if not self.allow_change():return False
        self.remember_current();self.pause()
        for worker in (self.collection_worker,getattr(self.library,'bulk',None),self.preview_worker):
            if worker and worker.isRunning():worker.requestInterruption();worker.wait()
        if self.worker and self.worker.isRunning():self.worker.requestInterruption();self.worker.wait()
        self.finish_scrub();self.decode_poll.stop()
        if self.decode_future is not None:
            try:self.decode_future.result()
            except Exception:pass
            self.decode_future=None
        if self.reader:self.reader.close()
        self.reader=None;self.history=None;self.video_path=None;self.label_path=None;self.saved=None;self.frame_number=0
        from PySide6.QtGui import QPixmap
        self.image.item.setPixmap(QPixmap());self.position.setText('');self.table.setRowCount(0);self.points_table.setRowCount(0)
        self.project=project;project.touch();self.settings.setValue('current_project',project.slug)
        self.workspace=Workspace(project.workspace_file);self.session_histories={};self.sync_view.clear();self.library.meta.clear();self.library.status.clear()
        self.refresh_collection();self.refresh_live();self.refresh_preview_status();self.update_project_label()
        self.library.shutdown();self.show_view(self.library);self.library.activate()
        self.statusBar().showMessage(f'Opened project “{project.name}”.',6000);return True
    def show_storage(self):
        from .storage import StorageDialog
        StorageDialog(self).exec();self.library.render()
    def current_digest(self):return self.reader.index['source']['sha256'] if self.reader else None
    def protected_digests(self):
        keep={self.current_digest()}-{None}
        keep.update(t.reader.index['source']['sha256'] for t in self.sync_view.tiles)
        bulk=self.library.bulk
        if bulk and bulk.isRunning():keep.update(m['sha256'] for p,m in self.library.meta.items() if p in bulk.paths and 'sha256' in m)
        worker=self.coaching_export_worker
        if worker and worker.isRunning():keep.update(d['source']['sha256'] for d in worker.documents)
        return keep
    def enforce_storage(self,keep=()):
        from . import storage
        limit=float(self.settings.value('cache_limit_gb',storage.DEFAULT_LIMIT_GB))*2**30
        evicted=storage.enforce_limit(ROOT,limit,self.protected_digests()|set(keep))
        if evicted:self.statusBar().showMessage(f'Storage limit reached: removed {len(evicted)} least recently used smooth preview(s).',10000)
    def preview_prepared(self,digest):
        """A background job finished a preview: switch the open video to it and keep the cache within its limit."""
        if self.reader and self.current_digest()==digest and self.reader.backend!='preview':self.preview_ready(digest)
        self.enforce_storage({digest})
    def show_tips(self):
        from .guide import TipsDialog
        TipsDialog(self,self.settings).exec()
    def show_tour(self):
        from .guide import Tour,steps
        self.settings.setValue('inspector_hidden',False);self.refresh_live();self.inspector_button.setText('Hide controls')
        self.main_tabs.setCurrentIndex(0)
        def done():self.settings.setValue('tour_done',True);self.tour=None
        self.tour=Tour(self,steps(self),done);self.tour.start()
    def first_run(self):
        """Clean the cache and check for updates. Guidance waits for a loaded video."""
        from . import storage
        storage.remove_incomplete(ROOT);self.enforce_storage()
        if self.settings.value('show_tips',False,type=bool):self.show_tips()
        import time
        if self.settings.value('auto_update',True,type=bool) and time.time()-float(self.settings.value('update_checked',0))>20*3600:self.check_updates(manual=False)
    def offer_tour(self):
        if self.guidance and self.reader and not self.settings.value('tour_done',False,type=bool):self.statusBar().showMessage('New to Climb Studio? Choose Help → Show tour when you are ready.',12000)
    def check_updates(self,manual=False):
        from .updater import Updater
        import time
        if self.updater is None:
            self.updater=Updater(self);self.updater.available.connect(self.update_available);self.updater.progress.connect(lambda v:self.update_text.setText(f'Downloading Climb Studio {self.release["tag_name"].lstrip("v")} · {v}%'))
            self.updater.ready.connect(self.update_downloaded);self.updater.failed.connect(self.update_failed)
        self.update_manual=manual;self.settings.setValue('update_checked',time.time())
        try:self.updater.current.disconnect()
        except (RuntimeError,TypeError):pass
        if manual:self.updater.current.connect(lambda:QMessageBox.information(self,'Climb Studio is up to date',f'You have the latest version, {__version__}.'))
        self.updater.check()
    def update_available(self,release):
        version=release['tag_name'].lstrip('v')
        if not self.update_manual and self.settings.value('skipped_version','')==version:return
        from .updater import can_self_update,compatibility_reason
        from .platform_runtime import self_update_blocker
        self.release=release;blocked=compatibility_reason(release);automatic=can_self_update() and not blocked
        reason='' if automatic else ' · '+(blocked or (self_update_blocker() if getattr(sys,'frozen',False) else None) or 'Running from source: update with git pull, or download the installer.')
        self.update_text.setText(f'<b>Climb Studio {version}</b> is available (you have {__version__}).'+reason)
        self.update_buttons['install'].setText('Update now' if automatic else 'Download');self.update_buttons['install'].setEnabled(True);self.update_banner.show()
    def update_action(self,key):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from .updater import can_self_update,compatibility_reason
        if key=='later':self.update_banner.hide()
        elif key=='skip':self.settings.setValue('skipped_version',self.release['tag_name'].lstrip('v'));self.update_banner.hide()
        elif key=='notes':QDesktopServices.openUrl(QUrl(self.release['html_url']))
        elif key=='restart':self.close()
        elif key=='install':
            if not can_self_update() or compatibility_reason(self.release):QDesktopServices.openUrl(QUrl(self.release['html_url']));return
            from .updater import pick_assets
            name,_,_=pick_assets(self.release);size=next((a.get('size',0) for a in self.release.get('assets',[]) if a['name']==name),0)
            from .storage import human
            review=QMessageBox(self);review.setWindowTitle('Review update');review.setText(f"Climb Studio {__version__} → {self.release['tag_name']} · {human(size)}\nCompatible with this installation. Measurements are kept. Download now, then restart when ready.");review.setDetailedText(self.release.get('body','No release notes provided.'));review.setStandardButtons(QMessageBox.StandardButton.Ok|QMessageBox.StandardButton.Cancel)
            if review.exec()!=QMessageBox.StandardButton.Ok:return
            self.update_buttons['install'].setEnabled(False);self.update_text.setText('Downloading the update…');self.updater.download(self.release)
    def update_downloaded(self,launcher):
        self.pending_update=launcher;version=self.release['tag_name'].lstrip('v')
        self.update_text.setText(f'Climb Studio {version} is ready. Restart to finish updating; your work is saved first.')
        b=self.update_buttons['install'];b.setText('Restart now');b.setEnabled(True);b.clicked.disconnect();b.clicked.connect(lambda:self.update_action('restart'))
        # Leave the restart decision in the banner; never interrupt annotation with a modal prompt.
    def update_failed(self,message):
        if self.update_manual or self.update_banner.isVisible():
            self.update_text.setText('Update problem: '+message);self.update_buttons['install'].setEnabled(True);self.update_banner.show()
    def toggle_theme(self):
        from .design import apply_theme
        apply_theme(self,"light" if self.theme=="dark" else "dark")
    def start_resource_monitor(self):
        from .resources import ResourceMonitor
        self.resource_monitor=ResourceMonitor(self);self.resource_monitor.sampled.connect(self.show_usage);self.resource_monitor.start()
    def show_usage(self,data):
        from .resources import format_usage
        self.usage_label.setText(f"CPU {data['cpu_percent']:.0f}% · RAM {data['ram_mb']/1024:.1f} GB");self.usage_label.setToolTip(format_usage(data))
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
        records=[(p,s,False) for p,s in self.workspace.states.items()]+[(e['path'],e['state'],True) for e in self.workspace.attempts]
        targets=[r for r in records if r[1]['document']['climber']==athlete] if athlete else records if all_videos else [r for r in records if r[0]==key and not r[2]]
        try:
            for path,state,archived in targets:
                old=state['document'];fresh=empty_labels(old['source']);fresh.update(climber=old['climber'],attempt=old['attempt'],route=old['route'],attempt_id=old.get('attempt_id',fresh['attempt_id']))
                backup=self.project.backups/(Path(path).stem+'-'+str(uuid4())+'.labels.json');save(old,backup)
                if state['label_path']:save(fresh,state['label_path'])
                if archived:state['document']=fresh;state['frame']=0
                else:
                    self.workspace.remember(path,fresh,state['label_path'],0);self.session_histories[path]=History(fresh)
                    if path==key:self.history=self.session_histories[path];self.saved=copy.deepcopy(fresh)
            self.workspace.save()
            if self.history:self.refresh();self.show_frame(0)
            self.refresh_collection();self.statusBar().showMessage('Measurements cleared. Previous measurements backed up in '+str(self.project.backups),10000)
        except Exception as error:self.error(error)
    def export_pdf(self):
        self.remember_current();self.refresh_collection()
        if not self.comparison_documents:return self.error('Add videos and measure at least one climb first.')
        path,_=QFileDialog.getSaveFileName(self,'Export private PDF comparison',str(self.project.reports/'all-athletes.pdf'),'PDF (*.pdf)')
        if path:
            try:
                from .pdf_report import export_pdf
                source=Path(path).with_name(Path(path).stem+'-source.html')
                export_comparison(self.comparison_documents,source)
                focus=self.comparison_documents[0]['climber'] if self.comparison_documents else None
                export_pdf(source,path,focus)
                self.statusBar().showMessage('PDF and source HTML/CSV saved locally.',10000)
            except Exception as error:self.error(error)
    def export_all(self):
        self.remember_current();self.refresh_collection()
        if not self.comparison_documents:return self.error('Add videos and measure at least one climb first.')
        path,_=QFileDialog.getSaveFileName(self,'Export this workspace comparison',str(self.project.reports/'all-athletes.html'),'HTML (*.html)')
        if path:
            try:export_comparison(self.comparison_documents,path);self.statusBar().showMessage('Selected comparison exported as HTML and CSV.',10000)
            except Exception as e:self.error(e)

def main(video=None):
    app=QApplication.instance() or QApplication(sys.argv);app.setStyle('Fusion')
    from PySide6.QtGui import QIcon
    app.setWindowIcon(QIcon(str(Path(__file__).resolve().parent/'assets'/'icon.png')));window=Window(video)
    available=app.primaryScreen().availableGeometry();window.resize(min(1450,available.width()-40),min(1000,available.height()-40));window.guidance=True;window.show();QTimer.singleShot(0,lambda:window.resize(min(1450,available.width()-40),min(1000,available.height()-40)));window.start_resource_monitor();QTimer.singleShot(400,window.first_run);return app.exec()
