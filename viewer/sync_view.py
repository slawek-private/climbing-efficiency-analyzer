"""Side-by-side playback of several videos on one clock aligned at a shared marked moment."""
import bisect
import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QElapsedTimer,QEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QSlider, QFrame
from .controls import Button as QPushButton
from .app import ImageView
from .labels import ROOT
from .video import index_video, VideoReader

SPEEDS = (.25, .5, 1, 1.5, 2)


def anchor_seconds(document, anchor):
    """Video time of the alignment moment: climb start, or the first arrival at a named point."""
    if anchor == 'start':
        return document['start']['seconds'] if document['start'] else None
    arrivals = [p['point']['seconds'] for p in document.get('checkpoints', []) if p['name'].casefold() == anchor.casefold()]
    return min(arrivals, default=None)


def best_columns(count, width, height, aspect, gap=2,footer=0):
    """Column count that shows `count` videos of width/height `aspect` as large as possible."""
    best, choice = -1., 1
    for columns in range(1, max(1, count)+1):
        rows = math.ceil(count/columns);cell_w = (width-gap*(columns-1))/columns;cell_h = (height-gap*(rows-1))/rows
        shown_w = min(cell_w, max(1,cell_h-footer)*aspect);area = shown_w*shown_w/aspect
        if area > best+1e-6:best, choice = area, columns
    return choice


def frame_at(times, seconds):
    """Frame shown at a video time: the last frame whose timestamp is not after it.
    A microsecond of tolerance keeps sums like 0.7 + 0.2 = 0.8999… on the intended frame."""
    return max(0, min(len(times)-1, bisect.bisect_right(times, seconds+1e-6)-1))


class IndexAll(QThread):
    indexed = Signal(str, object)
    failed = Signal(str, str)
    def __init__(self, paths, known):
        super().__init__();self.paths = paths;self.known = known
    def run(self):
        for path in self.paths:
            if self.isInterruptionRequested():return
            try:
                cached = self.known.get(path)
                stat = Path(path).stat()
                index = cached[1] if cached and cached[0] == (stat.st_size, stat.st_mtime_ns) else index_video(path, cancelled=self.isInterruptionRequested, cache_dir=ROOT/'artifacts'/'frame-indexes')
                self.indexed.emit(path, index)
            except Exception as error:self.failed.emit(path, str(error))


class Tile(QWidget):
    """Identity and decode status stay outside the aspect-correct video."""
    def __init__(self, document, reader, anchor):
        super().__init__();self.document = document;self.reader = reader;self.anchor = anchor;self.aspect = None
        self.pool = ThreadPoolExecutor(max_workers=1);self.future = None;self.wanted = 0;self.shown = None;self.pending = None
        self.view = ImageView();self.view.setParent(self);self.view.setFrameShape(QFrame.Shape.NoFrame)
        result = {'failed': 'fell', 'completed': 'topped'}.get(document['outcome'], '')
        self.title = QLabel(f"{document['climber']} · {document['attempt']}"+(f' · {result}' if result else ''), self);self.status = QLabel(self)
        if document.get('assignment'):
            session=document['assignment']['session'];self.title.setText(self.title.text()+' · '+session['name']+' · '+session['date'])
        for label in (self.title,self.status):label.setObjectName('muted')
        self.full_title=self.title.text();self.title.setToolTip(self.full_title);self.title.setAccessibleName(self.full_title)
        from .scrubber import PrecisionScrubber
        self.timeline=PrecisionScrubber(read_only=True);self.timeline.setParent(self);self.timeline.time_origin=anchor;self.timeline.sync(reader.times[-1],reader.times[0],document)
    def resizeEvent(self, event):
        height=max(0,self.height()-self.timeline.height()-48);self.view.setGeometry(0,26,self.width(),height);self.timeline.setGeometry(0,height+48,self.width(),self.timeline.height());self.title.setGeometry(6,0,max(0,self.width()-12),24);self.title.setText(self.title.fontMetrics().elidedText(self.full_title,Qt.TextElideMode.ElideRight,max(0,self.width()-12)));self.place_status()
    def place_status(self):self.status.setGeometry(6,self.height()-self.timeline.height()-22,max(0,self.width()-12),22);self.status.setToolTip(self.status.text())
    def seek(self, t):
        seconds = self.anchor+t;self.wanted = frame_at(self.reader.times, seconds)
        note = ' · not started' if seconds < 0 else ' · ended' if seconds > self.reader.times[-1] else ''
        self.note=note
        if self.shown==self.wanted:self.update_labels(self.shown)
        else:self.status.setText(('Loading' if self.shown is None else f'Showing frame {self.shown} · loading')+f' frame {self.wanted}'+note);self.place_status()
    def update_labels(self,number):
        self.status.setText(f'{self.reader.times[number]:.3f} s · frame {number}'+getattr(self,'note',''));self.place_status();self.timeline.sync(self.reader.times[-1],self.reader.times[number],self.document)
    def pump(self, playing):
        """Returns True when the first frame reveals the video's shape, so the layout can adapt."""
        changed = False
        if self.future and self.future.done():
            try:
                rgb = self.future.result();self.view.display(rgb);self.shown = self.pending;self.update_labels(self.shown)
                if self.aspect is None:self.aspect = rgb.shape[1]/rgb.shape[0];changed = True
            except Exception as error:self.status.setText('Cannot decode: '+str(error));self.place_status()
            self.future = None
        if self.future is None and self.wanted != self.shown:
            self.pending = self.wanted;self.future = self.pool.submit(self.reader.frame, self.wanted, not playing)
        return changed
    def close_reader(self):
        if self.future:
            try:self.future.result()
            except Exception:pass
        self.pool.shutdown(wait=True);self.reader.close()


class TileArea(QWidget):
    """Places tiles in the grid that makes them largest for this window, centred, with 2 px gaps."""
    GAP = 2
    def __init__(self):super().__init__();self.tiles = []
    def set_tiles(self, tiles):
        self.tiles = tiles
        for tile in tiles:tile.setParent(self);tile.show()
        self.relayout()
    def relayout(self):
        if not self.tiles:return
        known = sorted(t.aspect for t in self.tiles if t.aspect);aspect = known[len(known)//2] if known else 16/9
        footer=max(t.timeline.height()+48 for t in self.tiles);columns = best_columns(len(self.tiles), self.width(), self.height(), aspect, self.GAP,footer);rows = math.ceil(len(self.tiles)/columns)
        cell_w = (self.width()-self.GAP*(columns-1))/columns;cell_h = (self.height()-self.GAP*(rows-1))/rows
        w = min(cell_w, max(1,cell_h-footer)*aspect);h = w/aspect+footer;left = (self.width()-(w*columns+self.GAP*(columns-1)))/2;top = (self.height()-(h*rows+self.GAP*(rows-1)))/2
        for i, tile in enumerate(self.tiles):
            r, c = divmod(i, columns);tile.setGeometry(int(left+c*(w+self.GAP)), int(top+r*(h+self.GAP)), int(w), int(h))
    def resizeEvent(self, event):self.relayout()


class SyncView(QWidget):
    def __init__(self, window):
        super().__init__();self.window = window;self.tiles = [];self.indexes = {};self.index_errors={};self.worker = None
        self.t = 0.;self.lo = 0.;self.hi = 1.;self.playing = False;self.clock = QElapsedTimer();self.play_from = 0.
        self.timer = QTimer(self);self.timer.setInterval(15);self.timer.timeout.connect(self.tick)
        layout = QVBoxLayout(self);layout.setContentsMargins(4, 4, 4, 4);layout.setSpacing(4)
        top = QHBoxLayout()
        reload = QPushButton('Reload videos');reload.setProperty('role', 'quiet');reload.clicked.connect(lambda:self.load(retry=True));top.addWidget(reload)
        self.note = QLabel();self.note.setWordWrap(True);self.note.setObjectName('muted');top.addWidget(self.note, 1)
        self.full = QPushButton('Full screen');self.full.setProperty('role','quiet');self.full.setToolTip('Use the whole screen for the videos (Esc or click again to leave).');self.full.clicked.connect(self.toggle_full_screen);top.addWidget(self.full);layout.addLayout(top)
        self.area = TileArea();layout.addWidget(self.area, 1)
        controls = QHBoxLayout();controls.setSpacing(4)
        self.play_button = QPushButton('Play');self.play_button.setProperty('role', 'primary');self.play_button.clicked.connect(self.toggle_play);controls.addWidget(self.play_button)
        for text, seconds, frames in (('← 1 s', -1., 0), ('← frame', 0, -1), ('frame →', 0, 1), ('1 s →', 1., 0)):
            b = QPushButton(text);b.setProperty('role','quiet');b.clicked.connect(lambda checked=False, s=seconds, f=frames:self.step(s) if s else self.step_frames(f));controls.addWidget(b)
        self.speed = QComboBox();self.speed.addItems([f'{s:g}×' for s in SPEEDS]);self.speed.setCurrentIndex(2);self.speed.currentIndexChanged.connect(self.restart_clock);controls.addWidget(self.speed)
        controls.addWidget(QLabel('Shared timeline'));self.slider = QSlider(Qt.Orientation.Horizontal);self.slider.setAccessibleName('Shared timeline for all comparison videos');self.slider.setToolTip('Drag to move every selected video together. Individual label timelines are read-only.');self.slider.valueChanged.connect(lambda ms:self.seek(ms/1000));self.slider.sliderPressed.connect(self.pause);controls.addWidget(self.slider, 1)
        self.position = QLabel();self.position.setMinimumWidth(150);controls.addWidget(self.position);layout.addLayout(controls)
    def eventFilter(self,obj,event):
        if event.type()==QEvent.Type.MouseButtonDblClick:
            tile=next((t for t in self.tiles if t.view.viewport() is obj),None)
            if tile:
                self.pause();self.window.open_comparison_document(tile.path,tile.document,tile.shown if tile.shown is not None else tile.wanted);return True
        return super().eventFilter(obj,event)
    def toggle_full_screen(self):
        if self.window.isFullScreen():self.window.showNormal()
        else:self.window.showFullScreen()
        self.full.setText('Exit full screen' if self.window.isFullScreen() else 'Full screen')
    def selected_entries(self):
        records=[(p,s) for p,s in self.window.workspace.states.items()]+[(e['path'],e['state']) for e in self.window.workspace.attempts]
        from .compare_scope import identity
        chosen=self.window.compare_scope.chosen()
        return [(p,{'document':d}) for d in chosen for p,s in records if identity(s['document'])==identity(d)][:16]
    def activate(self):
        self.window.remember_current()
        self.window.compare_scope.set_documents(self.window.workspace.documents())
        self.load()
    def load(self,retry=False):
        if retry:self.index_errors.clear()
        if self.worker and self.worker.isRunning():return
        paths = list(dict.fromkeys(p for p,_ in self.selected_entries()))
        missing = [p for p in paths if p not in self.indexes and p not in self.index_errors]
        if missing:
            self.note.setText(f'Indexing {len(missing)} video(s)… first time only');self.worker = IndexAll(missing, dict(self.window.session_indexes))
            self.worker.indexed.connect(lambda p, i:self.indexes.__setitem__(p, i));self.worker.failed.connect(lambda p,e:self.index_errors.__setitem__(p,e))
            self.worker.finished.connect(self.load);self.worker.start()
        else:self.rebuild()
    def clear(self):
        self.pause()
        for tile in self.tiles:tile.close_reader();tile.deleteLater()
        self.tiles = [];self.area.tiles = []
    def rebuild(self):
        if self.worker and self.worker.isRunning():return
        saved_time=self.t;self.clear();point=self.window.compare_scope.point.currentText();anchor='start' if point=='Climb start' or not point else point;skipped = []
        from .preview_cache import open_preview
        for path,state in self.selected_entries():
            index = self.indexes.get(path)
            if not state or not index:continue
            d = state['document'];seconds = anchor_seconds(d, anchor)
            if seconds is None or index['source']['sha256'] != d['source']['sha256']:skipped.append(d['climber']);continue
            # One decoder per tile; 'auto' uses the hardware decoder (VideoToolbox / CUDA) when the file allows.
            reader = open_preview(ROOT/'artifacts'/'preview-cache', index) or VideoReader(path, index, 'auto')
            tile=Tile(d,reader,seconds);tile.timeline.dark=self.window.theme=='dark';tile.path=path;tile.view.viewport().installEventFilter(self);tile.view.setToolTip('Double-click to open this attempt in Video analysis at the displayed frame.');self.tiles.append(tile)
        self.area.set_tiles(self.tiles)
        self.lo = min((-t.anchor for t in self.tiles), default=0.);self.hi = max((t.reader.times[-1]-t.anchor for t in self.tiles), default=1.)
        for tile in self.tiles:tile.timeline.view_range=(self.lo+tile.anchor,self.hi+tile.anchor)
        self.slider.blockSignals(True);self.slider.setRange(int(self.lo*1000), int(self.hi*1000));self.slider.blockSignals(False)
        what = 'climb start' if anchor == 'start' else 'point '+anchor
        self.note.setText(f'{len(self.tiles)} video(s) aligned at {what}'+(f" · not marked: {', '.join(skipped)}" if skipped else '') if self.tiles else 'Choose athletes and mark their climb start (or the chosen point) to compare.')
        failed=[Path(p).name for p,_ in self.selected_entries() if p in self.index_errors]
        if failed:self.note.setText(self.note.text()+' · Cannot open: '+', '.join(failed))
        if len(self.window.compare_scope.chosen())>16:self.note.setText(self.note.text()+' · First 16 shown; narrow the selection')
        self.seek(saved_time)
        if self.tiles:self.timer.start()
    def seek(self, t):
        self.t = max(self.lo, min(self.hi, t))
        for tile in self.tiles:tile.seek(self.t)
        self.slider.blockSignals(True);self.slider.setValue(int(self.t*1000));self.slider.blockSignals(False)
        self.position.setText(f'{self.t:+.3f} s from alignment')
        if self.playing:self.restart_clock()
    def step(self, seconds):self.pause();self.seek(self.t+seconds)
    def step_frames(self, count):
        """Move by the shortest frame duration among the videos, so no video skips a frame."""
        self.pause()
        for _ in range(abs(count)):
            candidates=[]
            for tile in self.tiles:
                times=tile.reader.times;position=frame_at(times,tile.anchor+self.t)
                i=position+1 if count>0 else bisect.bisect_left(times,tile.anchor+self.t-1e-6)-1
                if 0<=i<len(times):candidates.append(times[i]-tile.anchor)
            if not candidates:break
            self.seek(min(candidates) if count>0 else max(candidates))
    def frame_seconds(self):
        gaps = [sorted(b-a for a, b in zip(t.reader.times, t.reader.times[1:]))[len(t.reader.times)//2-1] for t in self.tiles if len(t.reader.times) > 2]
        return min(gaps, default=1/30)
    def restart_clock(self):self.play_from = self.t;self.clock.restart()
    def toggle_play(self):
        if self.playing:return self.pause()
        if not self.tiles:return
        if self.t >= self.hi:self.seek(self.lo)
        self.playing = True;self.restart_clock();self.play_button.setText('Pause')
    def pause(self):
        self.playing = False;self.play_button.setText('Play')
    def tick(self):
        if self.playing:
            t = self.play_from+self.clock.elapsed()/1000*SPEEDS[self.speed.currentIndex()]
            if t >= self.hi:self.pause();t = self.hi
            self.t = max(self.lo, min(self.hi, t))
            for tile in self.tiles:tile.seek(self.t)
            self.slider.blockSignals(True);self.slider.setValue(int(self.t*1000));self.slider.blockSignals(False);self.position.setText(f'{self.t:+.3f} s from alignment')
        if any([tile.pump(self.playing) for tile in self.tiles]):self.area.relayout()
    def shutdown(self):
        if self.worker and self.worker.isRunning():self.worker.requestInterruption();self.worker.wait()
        self.timer.stop();self.clear()
