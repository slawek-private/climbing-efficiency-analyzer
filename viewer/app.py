"""Human-operated Qt labelling application. Decodes video locally with PyAV."""
import bisect
import copy
import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt,QThread,Signal,QTimer,QElapsedTimer,QEvent
from PySide6.QtGui import QImage,QPixmap,QKeySequence,QShortcut,QPainter,QColor,QPen
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,
    QPushButton,QLabel,QSlider,QComboBox,QSpinBox,QDoubleSpinBox,QLineEdit,QCheckBox,
    QGraphicsView,QGraphicsScene,QFileDialog,QMessageBox,QTableWidget,QTableWidgetItem,
    QAbstractItemView,QSplitter,QDialog,QDialogButtonBox,QFormLayout,QProgressBar,QScrollArea)

from .labels import ROOT,History,empty_labels,make_event,save,load,metrics
from .video import index_video,VideoReader
from .report import export_html,export_folder,export_csv


class IndexWorker(QThread):
    ready=Signal(object)
    progress=Signal(int)
    error=Signal(str)
    def __init__(self,path):
        super().__init__();self.path=path
    def run(self):
        try:self.ready.emit(index_video(self.path,self.progress.emit,self.isInterruptionRequested,cache_dir=ROOT/"artifacts"/"frame-indexes"))
        except Exception as error:self.error.emit(str(error))


class ImageView(QGraphicsView):
    def __init__(self):
        super().__init__();self.canvas=QGraphicsScene(self);self.setScene(self.canvas)
        self.item=self.canvas.addPixmap(QPixmap());self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setBackgroundBrush(QColor("#101b2b"));self.auto_fit=True
        self.viewport().installEventFilter(self)
        self.setToolTip("Pinch to zoom · two-finger scroll to pan · double-tap to fit · wheel to zoom")
    def display(self,rgb):
        image=QImage(rgb.data,rgb.shape[1],rgb.shape[0],rgb.strides[0],QImage.Format.Format_RGB888).copy()
        self.item.setPixmap(QPixmap.fromImage(image));self.canvas.setSceneRect(self.item.boundingRect())
        if self.auto_fit:self.fit()
    def fit(self):
        self.auto_fit=True;self.fitInView(self.item,Qt.AspectRatioMode.KeepAspectRatio)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self.auto_fit:self.fit()
    def zoom_at(self,factor,position):
        if factor<=0 or factor==1:return
        current=self.transform().m11()
        factor=max(.02,min(30,current*factor))/max(current,1e-12)
        before=self.mapToScene(position.toPoint())
        self.auto_fit=False
        self.scale(factor,factor)
        after=self.mapToScene(position.toPoint())
        offset=after-before
        self.translate(offset.x(),offset.y())
    def eventFilter(self,watched,event):
        if watched is self.viewport() and event.type()==QEvent.Type.NativeGesture:
            kind=event.gestureType()
            if kind==Qt.NativeGestureType.ZoomNativeGesture:
                self.zoom_at(1+event.value(),event.position())
            elif kind==Qt.NativeGestureType.SmartZoomNativeGesture:self.fit()
            elif kind not in (Qt.NativeGestureType.BeginNativeGesture,Qt.NativeGestureType.EndNativeGesture):
                return super().eventFilter(watched,event)
            event.accept();return True
        return super().eventFilter(watched,event)
    def wheelEvent(self,event):
        pixels=event.pixelDelta()
        if not pixels.isNull() and not event.modifiers()&Qt.KeyboardModifier.ControlModifier:
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value()-pixels.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value()-pixels.y())
        else:
            amount=pixels.y()/100 if not pixels.isNull() else event.angleDelta().y()/120
            self.zoom_at(1.2**max(-10,min(10,amount)),event.position())
        event.accept()


class Timeline(QWidget):
    seek=Signal(float)
    def __init__(self):
        super().__init__();self.setMinimumHeight(180);self.document=None;self.duration=1;self.position=0
    def paintEvent(self,event):
        painter=QPainter(self);painter.fillRect(self.rect(),QColor("#edf2f8"))
        lanes=[("L contact","contact","left"),("R contact","contact","right"),("Rest","rest","none"),
               ("Clip L/R","clip",None),("L off-wall","offwall","left"),("R off-wall","offwall","right")]
        width=max(1,self.width()-100);duration=max(.001,self.duration)
        for i,(label,kind,hand) in enumerate(lanes):
            y=8+i*26;painter.setPen(QColor("#203c60"));painter.drawText(6,y+15,label)
            painter.fillRect(95,y,width,20,QColor("#dce4ef"))
            if self.document:
                for e in self.document["events"]:
                    if e["kind"]!=kind or (hand and e["hand"]!=hand):continue
                    x=95+int(width*e["start"]["seconds"]/duration);w=max(2,int(width*(e["end"]["seconds"]-e["start"]["seconds"])/duration))
                    color=QColor({"contact":"#3475cd","rest":"#21996c","clip":"#d58b1b","offwall":"#8c59b6"}[kind])
                    if e["confidence"]<.8:color.setAlpha(115)
                    painter.fillRect(x,y,w,20,color)
        painter.setPen(QPen(QColor("#172b46"),2));x=95+int(width*self.position/duration);painter.drawLine(x,0,x,self.height())
    def mousePressEvent(self,event):
        seconds=max(0,min(1,(event.position().x()-95)/max(1,self.width()-100)))*self.duration
        self.seek.emit(seconds)


class EventDialog(QDialog):
    def __init__(self,reader,event,parent):
        super().__init__(parent);self.setWindowTitle("Edit marked interval");self.reader=reader
        form=QFormLayout(self)
        self.kind=QComboBox();self.kind.addItems(["contact","rest","clip","offwall","chalk"]);self.kind.setCurrentText(event["kind"])
        self.hand=QComboBox();self.hand.addItems(["left","right","none"]);self.hand.setCurrentText(event["hand"])
        self.target=QSpinBox();self.target.setRange(0,9999);self.target.setSpecialValueText("None");self.target.setValue(event["target"] or 0)
        self.start=QSpinBox();self.end=QSpinBox()
        for control in (self.start,self.end):control.setRange(0,len(reader.times)-1)
        self.start.setValue(event["start"]["frame"]);self.end.setValue(event["end"]["frame"])
        self.confidence=QDoubleSpinBox();self.confidence.setRange(0,1);self.confidence.setSingleStep(.1);self.confidence.setValue(event["confidence"])
        self.notes=QLineEdit(event["notes"])
        self.clip_method=QComboBox()
        for title,value in (("Answer needed",None),("Two-stage · rope in mouth","mouth"),("Direct","direct"),("Cannot tell","unknown")):self.clip_method.addItem(title,value)
        self.clip_method.setCurrentIndex(self.clip_method.findData(event.get("clip_method")))
        self.clip_reason=QComboBox()
        for title,value in [('Choose reason…',''),('Hands / rope hidden','hidden'),('Camera misses the method','camera'),('Visible but unclear','unclear')]:self.clip_reason.addItem(title,value)
        self.clip_reason.setCurrentIndex(max(0,self.clip_reason.findData(event.get('clip_reason',''))));form.addRow('Reason (Cannot tell)',self.clip_reason)
        for label,control in (("Kind",self.kind),("Hand",self.hand),("Hold / quickdraw number",self.target),("Clip method",self.clip_method),("Start frame",self.start),("End frame (release / completion)",self.end),("Subjective confidence",self.confidence),("Notes",self.notes)):form.addRow(label,control)
        hint=QLabel("Frames are zero-based. Start included, end excluded.\nUse the player and current frame display to locate boundaries.");form.addRow(hint)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);form.addRow(buttons)
    def result_event(self,event):
        event={k:v for k,v in event.items() if k not in ("clip_method","clip_reason")}
        if self.kind.currentText()=="clip" and self.clip_method.currentData():event["clip_method"]=self.clip_method.currentData()
        if event.get('clip_method')=='unknown':event['clip_reason']=self.clip_reason.currentData()
        return {**event,"kind":self.kind.currentText(),"hand":self.hand.currentText(),"target":self.target.value() or None,
                "start":self.reader.point(self.start.value()),"end":self.reader.point(self.end.value()),
                "confidence":self.confidence.value(),"notes":self.notes.text()}


class Window(QMainWindow):
    def __init__(self,video=None):
        super().__init__();self.setWindowTitle("Blue route · manual climbing labels");self.resize(1450,950)
        self.reader=None;self.worker=None;self.history=None;self.video_path=None;self.label_path=None;self.saved=None;self.frame_number=0;self.playing=False;self.rendering=False
        self.timer=QTimer(self);self.timer.setInterval(15);self.timer.timeout.connect(self.tick);self.elapsed=QElapsedTimer()
        self.progress=QProgressBar();self.progress.hide()
        root=QWidget();self.setCentralWidget(root);layout=QVBoxLayout(root)
        toolbar=QHBoxLayout()
        for text,callback in (("Open video",self.open_video),("Load labels",self.load_labels),("Save labels",self.save_labels),
                              ("Export HTML",self.export_report),("Compare saved labels",self.compare_reports),("Export CSV",self.csv)):
            button=QPushButton(text);button.clicked.connect(callback);toolbar.addWidget(button)
        layout.addLayout(toolbar);layout.addWidget(self.progress)
        splitter=QSplitter(Qt.Orientation.Horizontal);layout.addWidget(splitter,1)
        player=QWidget();player_layout=QVBoxLayout(player);self.image=ImageView();player_layout.addWidget(self.image,1)
        controls=QHBoxLayout();self.play_button=QPushButton("Play · Space");self.play_button.clicked.connect(self.toggle_play);controls.addWidget(self.play_button)
        for text,delta in (("◀ Frame · ←",-1),("Frame ▶ · →",1)):
            button=QPushButton(text);button.clicked.connect(lambda checked=False,d=delta:self.step(d));controls.addWidget(button)
        self.speed=QComboBox();self.speed.addItems(["0.25×","0.5×","1×","1.5×","2×"]);self.speed.setCurrentIndex(2);self.speed.currentIndexChanged.connect(self.reset_clock);controls.addWidget(self.speed)
        fit=QPushButton("Fit / reset zoom");fit.clicked.connect(self.image.fit);controls.addWidget(fit);player_layout.addLayout(controls)
        self.position=QLabel("Open a local video. Indexing scans all actual presentation timestamps.");player_layout.addWidget(self.position)
        self.slider=QSlider(Qt.Orientation.Horizontal);self.slider.sliderPressed.connect(self.pause);self.slider.valueChanged.connect(self.slider_changed);player_layout.addWidget(self.slider)
        self.timeline=Timeline();self.timeline.seek.connect(self.seek_seconds);player_layout.addWidget(self.timeline)
        splitter.addWidget(player)
        side=QWidget();side_layout=QVBoxLayout(side)
        identity=QFormLayout();self.climber=QLineEdit();self.attempt=QLineEdit("1");self.outcome=QComboBox();self.outcome.addItems(["unknown","failed","completed","abandoned"])
        self.notes=QLineEdit()
        identity.addRow("Climber",self.climber);identity.addRow("Attempt ID",self.attempt);identity.addRow("Outcome",self.outcome);identity.addRow("Attempt notes",self.notes);side_layout.addLayout(identity)
        self.climber.editingFinished.connect(self.update_identity);self.attempt.editingFinished.connect(self.update_identity);self.notes.editingFinished.connect(self.update_identity);self.outcome.currentIndexChanged.connect(self.update_identity)
        self.left_hold=QSpinBox();self.right_hold=QSpinBox();self.draw=QSpinBox()
        for spin in (self.left_hold,self.right_hold,self.draw):spin.setRange(1,9999)
        self.clip_hand=QComboBox();self.clip_hand.addItems(["left","right"])
        self.confidence=QDoubleSpinBox();self.confidence.setRange(0,1);self.confidence.setSingleStep(.1);self.confidence.setValue(1)
        tagging=QFormLayout();tagging.addRow("Left blue hold",self.left_hold);tagging.addRow("Right blue hold",self.right_hold);tagging.addRow("Clip hand",self.clip_hand);tagging.addRow("Quickdraw number",self.draw);tagging.addRow("New event confidence",self.confidence);side_layout.addLayout(tagging)
        buttons=QGridLayout()
        actions=[("L · left grab / release",lambda:self.mark("contact","left")),("R · right grab / release",lambda:self.mark("contact","right")),
                 ("T · rest start / end",lambda:self.mark("rest","none")),("C · rope take / clip done",lambda:self.mark("clip",self.clip_hand.currentText())),
                 ("Q · left off-wall start / end",lambda:self.mark("offwall","left")),("W · right off-wall start / end",lambda:self.mark("offwall","right")),
                 ("S · grip on blue hold 1",self.set_start),("F · first rope-weighting",self.set_failure)]
        for i,(text,callback) in enumerate(actions):
            button=QPushButton(text);button.clicked.connect(callback);buttons.addWidget(button,i//2,i%2)
        side_layout.addLayout(buttons)
        end_button=QPushButton("Mark completion / other end here");end_button.clicked.connect(self.set_other_end);side_layout.addWidget(end_button)
        self.active=QLabel("No open events");self.active.setWordWrap(True);side_layout.addWidget(self.active)
        self.review={}
        side_layout.addWidget(QLabel("Mark complete only after reviewing the entire attempt:"))
        review_layout=QGridLayout()
        for i,key in enumerate(("boundaries","left_contacts","right_contacts","rests","clips","left_offwall","right_offwall")):
            checkbox=QCheckBox(key.replace("_"," "));checkbox.toggled.connect(lambda checked,k=key:self.set_review(k,checked));self.review[key]=checkbox;review_layout.addWidget(checkbox,i//2,i%2)
        side_layout.addLayout(review_layout)
        self.summary=QLabel();self.summary.setWordWrap(True);side_layout.addWidget(self.summary)
        self.table=QTableWidget(0,6);self.table.setHorizontalHeaderLabels(["Kind","Hand","Hold/draw","Start s","End s","Duration s"]);self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemDoubleClicked.connect(lambda item:self.edit_event());self.table.itemSelectionChanged.connect(self.selected_event);side_layout.addWidget(self.table,1)
        edits=QHBoxLayout()
        for text,callback in (("A · add",self.add_event),("Enter · edit",self.edit_event),("Delete",self.delete_event),("Undo",self.undo),("Redo",self.redo)):
            button=QPushButton(text);button.clicked.connect(callback);edits.addWidget(button)
        side_layout.addLayout(edits)
        hint=QLabel("Space play/pause · arrows exact frame · [ / ] previous/next event\nL/R contact · T rest · C clip · Q/W off-wall · S start · F rope-weighting\nCtrl+S save · Ctrl+Z undo · Ctrl+Y redo · Escape cancel open events\nWheel zoom · drag pan. Pause on the exact boundary, then mark it.");hint.setWordWrap(True);side_layout.addWidget(hint)
        side.setMinimumWidth(500);self.table.setMinimumHeight(160)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(side);splitter.addWidget(scroll);splitter.setSizes([850,600])
        shortcuts={"Space":self.toggle_play,"Left":lambda:self.step(-1),"Right":lambda:self.step(1),"L":lambda:self.mark("contact","left"),"R":lambda:self.mark("contact","right"),"T":lambda:self.mark("rest","none"),"C":lambda:self.mark("clip",self.clip_hand.currentText()),"Q":lambda:self.mark("offwall","left"),"W":lambda:self.mark("offwall","right"),"S":self.set_start,"F":self.set_failure,"A":self.add_event,"Return":self.edit_event,"Delete":self.delete_event,"Ctrl+S":self.save_labels,"Ctrl+Z":self.undo,"Ctrl+Y":self.redo,"[":lambda:self.jump_event(-1),"]":lambda:self.jump_event(1),"Escape":self.cancel_open}
        self.shortcuts=[]
        for key,callback in shortcuts.items():
            shortcut=QShortcut(QKeySequence(key),self);shortcut.setProperty("manual_key",key);shortcut.activated.connect(lambda cb=callback:self.shortcut(cb));self.shortcuts.append(shortcut)
        QApplication.instance().focusChanged.connect(self.focus_changed)
        if video:QTimer.singleShot(0,lambda:self.begin_video(Path(video)))
    def labels_folder(self):return ROOT/"artifacts"/"labels"
    def shortcut(self,callback):
        # Do not steal tagging keys while the user types or adjusts fields.
        if isinstance(QApplication.focusWidget(),(QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox)):
            if callback!=self.save_labels:return
        callback()
    def focus_changed(self,old,new):
        editing=isinstance(new,(QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox))
        for shortcut in self.shortcuts:
            shortcut.setEnabled(not editing or shortcut.property("manual_key")=="Ctrl+S")
    def error(self,message):QMessageBox.warning(self,"Cannot apply action",str(message))
    def document(self):return self.history.document if self.history else None
    def commit(self,document):
        try:self.history.apply(document);self.refresh();return True
        except Exception as error:self.error(error);self.refresh();return False
    def dirty(self):return self.history is not None and self.saved!=self.document()
    def allow_change(self):
        if not self.dirty():return True
        answer=QMessageBox.question(self,"Unsaved labels","Save changes before leaving this video?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No|QMessageBox.StandardButton.Cancel)
        if answer==QMessageBox.StandardButton.Cancel:return False
        if answer==QMessageBox.StandardButton.Yes:return self.save_labels()
        return True
    def open_video(self):
        if self.worker and self.worker.isRunning():return
        if not self.allow_change():return
        path,_=QFileDialog.getOpenFileName(self,"Open climbing video",str(ROOT/"videos"),"Video (*.mp4 *.mov *.MP4 *.MOV)")
        if path:self.begin_video(Path(path))
    def begin_video(self,path):
        self.pause()
        if self.reader:self.reader.close()
        self.reader=None;self.history=None;self.video_path=path;self.label_path=None;self.saved=None
        self.table.setRowCount(0);self.summary.setText("");self.position.setText("Indexing exact frames… This may take a minute for 4K videos.")
        self.progress.setValue(0);self.progress.show();self.worker=IndexWorker(path)
        self.worker.progress.connect(self.progress.setValue);self.worker.ready.connect(self.index_ready);self.worker.error.connect(self.index_error);self.worker.start()
    def index_error(self,message):self.progress.hide();self.position.setText("Video could not be indexed");self.error(message)
    def index_ready(self,index):
        self.progress.hide()
        try:
            self.reader=VideoReader(self.video_path,index);self.history=History(empty_labels(index["source"]));self.saved=copy.deepcopy(self.document())
            self.slider.setRange(0,len(self.reader.times)-1);self.frame_number=0;self.refresh();self.show_frame(0)
            path=self.labels_folder()/(self.video_path.stem+".labels.json")
            if path.exists():
                if QMessageBox.question(self,"Existing labels","Load the saved labels for this video?")==QMessageBox.StandardButton.Yes:self.read_labels(path)
        except Exception as error:self.error(error)
    def show_frame(self,number):
        if not self.reader:return
        number=max(0,min(len(self.reader.times)-1,int(number)))
        try:
            self.image.display(self.reader.frame(number));self.frame_number=number
            point=self.reader.point(number);self.position.setText(f"Frame {number} / {len(self.reader.times)-1} · {point['seconds']:.3f}s · PTS {point['pts']} · time base {self.reader.index['source']['time_base']}")
            self.slider.blockSignals(True);self.slider.setValue(number);self.slider.blockSignals(False)
            self.timeline.position=point["seconds"];self.timeline.duration=self.reader.times[-1];self.timeline.update()
        except Exception as error:self.pause();self.error(error)
    def slider_changed(self,value):
        if self.reader:self.pause();self.show_frame(value)
    def step(self,delta):self.pause();self.show_frame(self.frame_number+delta)
    def seek_seconds(self,seconds):
        if not self.reader:return
        self.pause();self.show_frame(min(len(self.reader.times)-1,bisect.bisect_left(self.reader.times,seconds)))
    def reset_clock(self):
        if self.reader:self.play_start=self.reader.times[self.frame_number];self.elapsed.restart()
    def toggle_play(self):
        if not self.reader:return
        if self.playing:self.pause()
        else:self.playing=True;self.reset_clock();self.timer.start();self.play_button.setText("Pause · Space")
    def pause(self):self.playing=False;self.timer.stop();self.play_button.setText("Play · Space")
    def tick(self):
        if not self.reader:return
        rate=(.25,.5,1,1.5,2)[self.speed.currentIndex()];seconds=self.play_start+self.elapsed.elapsed()/1000*rate
        frame=min(len(self.reader.times)-1,max(0,bisect.bisect_right(self.reader.times,seconds)-1))
        if frame!=self.frame_number:self.show_frame(frame)
        if frame==len(self.reader.times)-1:self.pause()
    def mark(self,kind,hand):
        if not self.reader:return
        self.pause();doc=copy.deepcopy(self.document());point=self.reader.point(self.frame_number)
        opened=next((e for e in doc["open_events"] if e["kind"]==kind and e["hand"]==hand),None)
        # Any edit invalidates completeness claims until re-reviewed.
        doc["reviewed"]={k:False for k in doc["reviewed"]}
        if opened:
            doc["events"].append(make_event(opened,point));doc["open_events"].remove(opened)
        else:
            target=self.left_hold.value() if kind=="contact" and hand=="left" else self.right_hold.value() if kind=="contact" else self.draw.value() if kind=="clip" else None
            doc["open_events"].append({"kind":kind,"hand":hand,"target":target,"start":point,"confidence":self.confidence.value(),"notes":""})
        self.commit(doc)
    def set_start(self):
        if not self.reader:return
        self.pause();doc=copy.deepcopy(self.document());doc["start"]=self.reader.point(self.frame_number);doc["reviewed"]["boundaries"]=False;self.commit(doc)
    def set_failure(self):
        if not self.reader:return
        self.pause();doc=copy.deepcopy(self.document());doc["end"]=self.reader.point(self.frame_number);doc["outcome"]="failed";doc["reviewed"]["boundaries"]=False;self.commit(doc)
    def set_other_end(self):
        if not self.reader:return
        self.pause();doc=copy.deepcopy(self.document());doc["end"]=self.reader.point(self.frame_number);doc["outcome"]=self.outcome.currentText();doc["reviewed"]["boundaries"]=False;self.commit(doc)
    def update_identity(self):
        if self.rendering or not self.history:return
        doc=copy.deepcopy(self.document());doc.update(climber=self.climber.text().strip(),attempt=self.attempt.text().strip(),outcome=self.outcome.currentText(),notes=self.notes.text())
        if doc!=self.document():
            doc["reviewed"]["boundaries"]=False;self.commit(doc)
    def set_review(self,key,value):
        if self.rendering or not self.history:return
        doc=copy.deepcopy(self.document());doc["reviewed"][key]=value;self.commit(doc)
    def cancel_open(self):
        if not self.history:return
        doc=copy.deepcopy(self.document());doc["open_events"]=[];self.commit(doc)
    def refresh(self):
        if not self.history:return
        self.rendering=True;doc=self.document()
        self.climber.setText(doc["climber"]);self.attempt.setText(doc["attempt"]);self.outcome.setCurrentText(doc["outcome"]);self.notes.setText(doc["notes"])
        for key,checkbox in self.review.items():checkbox.setChecked(doc["reviewed"].get(key,False))
        self.active.setText("Open: "+" · ".join(f"{e['hand']} {e['kind']} #{e['target'] or '—'} from {e['start']['seconds']:.3f}s" for e in doc["open_events"]) if doc["open_events"] else "No open events")
        result=metrics(doc)
        def value(key):return "not reviewed" if result[key] is None else f"{result[key]:.3f}" if isinstance(result[key],float) else str(result[key])
        self.summary.setText(f"Climb: {value('climb_seconds')} s · Holds: {value('unique_holds')}\nRests: {value('rest_count')} · Rest time: {value('rest_seconds')} s\nStart: {doc['start']['seconds'] if doc['start'] else 'unmarked'} · End: {doc['end']['seconds'] if doc['end'] else 'unmarked'}")
        self.visible_events=sorted(doc["events"],key=lambda e:e["start"]["seconds"])
        self.table.blockSignals(True);self.table.setRowCount(len(self.visible_events))
        for row,e in enumerate(self.visible_events):
            values=(e["kind"],e["hand"],str(e["target"] or "—"),f"{e['start']['seconds']:.3f}",f"{e['end']['seconds']:.3f}",f"{e['end']['seconds']-e['start']['seconds']:.3f}")
            for col,text in enumerate(values):
                item=QTableWidgetItem(text)
                if e["confidence"]<.8:item.setBackground(QColor("#ffebc8"))
                item.setToolTip(f"Subjective confidence: {e['confidence']:.2f}\n{e['notes']}");self.table.setItem(row,col,item)
        self.table.blockSignals(False);self.table.resizeColumnsToContents();self.timeline.document=doc;self.timeline.update();self.rendering=False
        self.setWindowTitle(f"Blue route · {self.video_path.name if self.video_path else ''}"+(" *" if self.dirty() else ""))
    def selected_event(self):
        row=self.table.currentRow()
        if self.reader and 0<=row<len(self.visible_events):self.pause();self.show_frame(self.visible_events[row]["start"]["frame"])
    def event_dialog(self,event,is_new=False):
        self.pause();dialog=EventDialog(self.reader,event,self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        doc=copy.deepcopy(self.document());changed=dialog.result_event(event)
        if is_new:doc["events"].append(changed)
        else:doc["events"]=[changed if e["id"]==event["id"] else e for e in doc["events"]]
        doc["reviewed"]={k:False for k in doc["reviewed"]};self.commit(doc)
    def add_event(self):
        if not self.reader or self.frame_number>=len(self.reader.times)-1:return
        event=make_event({"kind":"contact","hand":"left","target":self.left_hold.value(),"start":self.reader.point(self.frame_number),"confidence":self.confidence.value(),"notes":""},self.reader.point(self.frame_number+1));self.event_dialog(event,True)
    def edit_event(self):
        row=self.table.currentRow()
        if self.reader and 0<=row<len(self.visible_events):self.event_dialog(self.visible_events[row])
    def delete_event(self):
        row=self.table.currentRow()
        if not self.history or not 0<=row<len(self.visible_events):return
        doc=copy.deepcopy(self.document());identifier=self.visible_events[row]["id"];doc["events"]=[e for e in doc["events"] if e["id"]!=identifier];doc["reviewed"]={k:False for k in doc["reviewed"]};self.commit(doc)
    def jump_event(self,direction):
        if not self.reader or not self.history:return
        frames=sorted({p["frame"] for e in self.document()["events"] for p in (e["start"],e["end"])})
        choices=[f for f in frames if f>self.frame_number] if direction>0 else [f for f in frames if f<self.frame_number]
        if choices:self.pause();self.show_frame(choices[0] if direction>0 else choices[-1])
    def undo(self):
        if self.history:self.history.undo();self.refresh()
    def redo(self):
        if self.history:self.history.redo();self.refresh()
    def save_labels(self):
        if not self.history:return False
        default=self.label_path or self.labels_folder()/(self.video_path.stem+".labels.json")
        path,_=QFileDialog.getSaveFileName(self,"Save manual labels",str(default),"Labels (*.labels.json)")
        if not path:return False
        try:
            save(self.document(),path);self.label_path=Path(path);self.saved=copy.deepcopy(self.document());self.refresh();self.statusBar().showMessage(f"Saved {path}",8000);return True
        except Exception as error:self.error(error);return False
    def load_labels(self):
        if not self.reader:return
        if not self.allow_change():return
        path,_=QFileDialog.getOpenFileName(self,"Load manual labels",str(self.labels_folder()),"Labels (*.labels.json *.json)")
        if path:self.read_labels(Path(path))
    def read_labels(self,path):
        try:
            doc=load(path)
            if doc["source"]!=self.reader.index["source"]:raise ValueError("Labels refer to a different video or timestamp index")
            for e in doc["events"]+doc["open_events"]:
                for p in [e["start"]]+([e["end"]] if "end" in e else []):
                    if p!=self.reader.point(p["frame"]):raise ValueError("Label frame does not match the video's presentation timestamp")
            for p in (doc["start"],doc["end"]):
                if p and p!=self.reader.point(p["frame"]):raise ValueError("Attempt boundary does not match video frame")
            self.history=History(doc);self.label_path=path;self.saved=copy.deepcopy(doc);self.refresh()
        except Exception as error:self.error(error)
    def export_report(self):
        if not self.history:return
        path,_=QFileDialog.getSaveFileName(self,"Export human-labelled HTML report",str(ROOT/"artifacts"/"reports"/(self.video_path.stem+"-manual.html")),"HTML (*.html)")
        if path:
            try:export_html([self.document()],path);self.statusBar().showMessage(f"HTML exported: {path}",10000)
            except Exception as error:self.error(error)
    def compare_reports(self):
        folder=QFileDialog.getExistingDirectory(self,"Folder containing saved labels",str(self.labels_folder()))
        if not folder:return
        path,_=QFileDialog.getSaveFileName(self,"Save comparison report",str(ROOT/"artifacts"/"reports"/"manual-comparison.html"),"HTML (*.html)")
        if path:
            try:export_folder(folder,path);self.statusBar().showMessage(f"Comparison exported: {path}",10000)
            except Exception as error:self.error(error)
    def csv(self):
        if not self.history:return
        path,_=QFileDialog.getSaveFileName(self,"Export event and summary CSV",str(ROOT/"artifacts"/"reports"/(self.video_path.stem+"-events.csv")),"CSV (*.csv)")
        if path:
            try:export_csv(self.document(),path);self.statusBar().showMessage(f"CSV exported: {path}",8000)
            except Exception as error:self.error(error)
    def closeEvent(self,event):
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            if not self.worker.wait(5000):event.ignore();return
        if not self.allow_change():event.ignore();return
        self.pause()
        if self.reader:self.reader.close()
        event.accept()


def main(video=None):
    app=QApplication.instance() or QApplication(sys.argv);app.setStyle("Fusion")
    window=Window(video)
    if app.primaryScreen():
        available=app.primaryScreen().availableGeometry();window.resize(min(1450,available.width()-40),min(950,available.height()-40))
    window.show();return app.exec()
