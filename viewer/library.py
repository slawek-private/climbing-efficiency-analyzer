"""Import & library: per-video metadata, preview recommendations, storage estimates and a bulk queue."""
import hashlib
import io
import shutil
from pathlib import Path
import av
from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                               QAbstractItemView, QHeaderView, QMessageBox)
from . import storage

COLUMNS = ['Video', 'Athlete', 'Resolution', 'FPS', 'Codec', 'Duration', 'File size', 'Smooth preview', 'Preview size', 'Notes']
HDR_TRANSFERS = {16, 18}  # SMPTE ST 2084 (PQ) and ARIB STD-B67 (HLG)


def probe(path):
    """Container metadata plus one sampled frame, JPEG-encoded like the preview cache, to estimate its size."""
    path = Path(path);meta = {'file': path.name, 'size_bytes': path.stat().st_size}
    with av.open(str(path)) as container:
        stream = container.streams.video[0];cc = stream.codec_context
        fps = float(stream.average_rate) if stream.average_rate else None
        duration = float(stream.duration*stream.time_base) if stream.duration else container.duration/1e6 if container.duration else None
        meta.update(codec=cc.name, width=cc.width, height=cc.height, fps=fps, duration=duration, frames=stream.frames or (round(duration*fps) if duration and fps else None),
                    bitrate=container.bit_rate, hdr=int(getattr(cc, 'color_trc', 0) or 0) in HDR_TRANSFERS, rotation=0, preview_bytes=None)
        if duration:container.seek(int(duration/2/stream.time_base), stream=stream, backward=True)
        frame = next(container.decode(stream), None)
        if frame is not None:
            meta['rotation'] = frame.rotation % 360
            scale = min(1, 1280/max(frame.width, frame.height));sample = frame.reformat(width=max(2, int(frame.width*scale)), height=max(2, int(frame.height*scale)), format='rgb24')
            buffer = io.BytesIO();Image.fromarray(sample.to_ndarray()).save(buffer, format='JPEG', quality=88, subsampling=0)
            meta['preview_bytes'] = buffer.tell()*meta['frames'] if meta['frames'] else None
    return meta


def recommendation(meta):
    """Smooth previews matter when random access is slow: large frames or HEVC."""
    longest = max(meta['width'], meta['height'])
    if longest >= 2160 or (meta['codec'] == 'hevc' and longest >= 1920):return 'Recommended'
    return 'Optional'


def notes(meta):
    """Short flags per row; the explanation is written once in the summary line."""
    out = []
    if meta['fps'] and meta['fps'] < 49:out.append(f"±{1000/meta['fps']:.0f} ms")
    if min(meta['width'], meta['height']) < 1080:out.append('<1080p')
    if meta['hdr']:out.append('HDR')
    return ' · '.join(out)


def checksum(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda:source.read(8*1024*1024), b''):digest.update(chunk)
    return digest.hexdigest()


class MetaWorker(QThread):
    probed = Signal(str, object)
    def __init__(self, paths, known):super().__init__();self.paths = paths;self.known = known
    def run(self):
        for path in self.paths:
            if self.isInterruptionRequested():return
            try:
                stat = Path(path).stat();key = (path, stat.st_size, stat.st_mtime_ns)
                meta = self.known.get(key) or {**probe(path), 'sha256': checksum(path)}
                self.probed.emit(path, {**meta, 'key': key})
            except Exception as error:self.probed.emit(path, {'error': str(error)})


class BulkWorker(QThread):
    """Index and prepare smooth previews one video after another; safe to leave running."""
    progress = Signal(str, str)
    done = Signal(str, str)
    failed = Signal(str, str)
    def __init__(self, paths, root):super().__init__();self.paths = paths;self.root = Path(root)
    def run(self):
        from .preview_cache import build_preview
        from .video import index_video
        for path in self.paths:
            if self.isInterruptionRequested():return
            try:
                self.progress.emit(path, 'Reading frames…')
                index = index_video(path, lambda v, p=path:self.progress.emit(p, f'Reading frames {v}%'), self.isInterruptionRequested, cache_dir=self.root/'artifacts'/'frame-indexes')
                build_preview(path, index, self.root/'artifacts'/'preview-cache', lambda v, p=path:self.progress.emit(p, f'Preparing preview {v}%'), self.isInterruptionRequested)
                self.done.emit(path, index['source']['sha256'])
            except InterruptedError:self.progress.emit(path, 'Cancelled');return
            except Exception as error:self.failed.emit(path, str(error))


class LibraryTab(QWidget):
    def __init__(self, window):
        super().__init__();self.window = window;self.meta = {};self.known = {};self.status = {};self.meta_worker = None;self.bulk = None
        layout = QVBoxLayout(self);layout.setContentsMargins(14, 12, 14, 10);layout.setSpacing(8)
        intro = QLabel('Every video in this project with its recording settings. Prepare smooth previews in bulk and leave it running: '
                       'videos are processed one after another in the background while you keep working. Originals are never modified.')
        intro.setWordWrap(True);intro.setObjectName('muted');layout.addWidget(intro)
        bar = QHBoxLayout();self.buttons = {}
        for key, text, callback, tip in [
            ('add', 'Add videos…', window.open_video, 'Add video files to this project.'),
            ('recommended', 'Prepare all recommended', lambda:self.prepare(recommended=True), 'Queue every video marked Recommended that has no smooth preview yet.'),
            ('selected', 'Prepare selected', lambda:self.prepare(recommended=False), 'Queue the selected rows.'),
            ('cancel', 'Cancel queue', self.cancel, 'Stop after discarding the preview currently being prepared.'),
            ('remove', 'Remove from project', self.remove, 'Remove the selected videos from this project. Video files and saved measurements are kept.'),
            ('storage', 'Storage…', window.show_storage, 'See and limit disk space used by previews and frame indexes.')]:
            b = QPushButton(text);b.setToolTip(tip);b.clicked.connect(callback);bar.addWidget(b);self.buttons[key] = b
        self.buttons['recommended'].setProperty('role', 'primary');self.buttons['cancel'].setEnabled(False);bar.addStretch();layout.addLayout(bar)
        self.table = QTableWidget(0, len(COLUMNS));self.table.setHorizontalHeaderLabels(COLUMNS);self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.table.setAlternatingRowColors(True);self.table.setShowGrid(False);self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents);self.table.horizontalHeader().setStretchLastSection(True);self.table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
        self.table.cellDoubleClicked.connect(self.open_row);self.table.setToolTip('Double-click a video to open it in the Video workspace.');layout.addWidget(self.table, 1)
        self.summary = QLabel();self.summary.setObjectName('muted');self.summary.setWordWrap(True);layout.addWidget(self.summary)
    def paths(self):return list(self.window.workspace.videos)
    def activate(self):
        self.render()
        missing = [p for p in self.paths() if p not in self.meta and Path(p).is_file()]
        if missing and not (self.meta_worker and self.meta_worker.isRunning()):
            self.meta_worker = MetaWorker(missing, self.known);self.meta_worker.probed.connect(self.probed);self.meta_worker.finished.connect(self.render);self.meta_worker.start()
            for p in missing:self.status.setdefault(p, 'Reading metadata…')
            self.render()
    def probed(self, path, meta):
        self.meta[path] = meta
        if 'key' in meta:self.known[meta['key']] = {k:v for k, v in meta.items() if k != 'key'}
        if self.status.get(path) == 'Reading metadata…':self.status.pop(path)
        self.render()
    def preview_ready(self, meta):
        return bool(meta.get('sha256')) and (storage.folders(self.window.data_root())[0]/meta['sha256']/'manifest.json').exists()
    def render(self):
        paths = self.paths();self.table.setRowCount(len(paths));states = self.window.workspace.states;wanted = 0;candidates = low_fps = low_res = hdr = 0
        for row, path in enumerate(paths):
            m = self.meta.get(path, {});state = states.get(path)
            if 'error' in m:values = [Path(path).name, '', '', '', '', '', '', self.status.get(path, 'Unreadable'), '', m['error']]
            elif m:
                ready = self.preview_ready(m);advice = 'Ready' if ready else recommendation(m)
                if not ready and advice == 'Recommended' and m['preview_bytes']:wanted += m['preview_bytes']
                w, h = (m['height'], m['width']) if m['rotation'] in (90, 270) else (m['width'], m['height'])
                values = [m['file'], state['document']['climber'] if state else '—', f'{w}×{h}', f"{m['fps']:.2f}".rstrip('0').rstrip('.') if m['fps'] else '?', m['codec'].upper(),
                          f"{m['duration']:.0f} s" if m['duration'] else '?', storage.human(m['size_bytes']), self.status.get(path) or advice, '~'+storage.human(m['preview_bytes']) if m['preview_bytes'] else '?', notes(m)]
                candidates += (not ready and advice == 'Recommended')
                low_fps += bool(m['fps'] and m['fps'] < 49);low_res += min(m['width'], m['height']) < 1080;hdr += bool(m['hdr'])
            else:values = [Path(path).name]+['']*6+[self.status.get(path, 'Waiting')]+['']*2
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col == 9 and value:item.setToolTip('±N ms: under 50 fps, a mark can be off by up to one frame. <1080p: small hands and quickdraws. HDR: colours may look flat.')
                if col == 7:item.setToolTip({'Ready': 'Smooth preview prepared: scrubbing and stepping use it automatically.', 'Recommended': '4K or HEVC: scrubbing the original is slow. Prepare a smooth preview.', 'Optional': 'Usually smooth enough without a preview.'}.get(value, ''))
                self.table.setItem(row, col, item)
        root = self.window.data_root();cache = sum(r['preview_bytes']+r['index_bytes'] for r in storage.entries(root));limit = float(self.window.settings.value('cache_limit_gb', storage.DEFAULT_LIMIT_GB))
        free = shutil.disk_usage(root if root.exists() else Path.home()).free
        flags = [f'{n} {what}' for n, what in ((low_fps, 'under 50 fps (marks less precise)'), (low_res, 'below 1080p'), (hdr, 'HDR')) if n]
        self.summary.setText(f'{len(paths)} videos'+(' · '+', '.join(flags) if flags else '')+f' · cache {storage.human(cache)} of {limit:g} GB · {storage.human(free)} free'
                             +(f' · recommended previews to prepare: ~{storage.human(wanted)}' if wanted else ''))
        running = bool(self.bulk and self.bulk.isRunning());self.buttons['cancel'].setEnabled(running)
        for key in ('selected', 'remove'):self.buttons[key].setEnabled(not running)
        self.buttons['recommended'].setEnabled(not running and candidates > 0)
        self.buttons['recommended'].setText(f'Prepare {candidates} recommended' if candidates else 'Nothing to prepare')
    def prepare(self, recommended):
        paths = self.paths()
        rows = range(len(paths)) if recommended else sorted({i.row() for i in self.table.selectedItems()})
        queue = [paths[r] for r in rows if 'error' not in self.meta.get(paths[r], {}) and not self.preview_ready(self.meta.get(paths[r], {}))
                 and (not recommended or (self.meta.get(paths[r]) and recommendation(self.meta[paths[r]]) == 'Recommended'))]
        if not queue:return QMessageBox.information(self, 'Nothing to prepare', 'Every chosen video already has a smooth preview, or none is recommended.')
        estimate = sum(self.meta.get(p, {}).get('preview_bytes') or 0 for p in queue);limit = float(self.window.settings.value('cache_limit_gb', storage.DEFAULT_LIMIT_GB))*2**30
        if estimate > limit and QMessageBox.question(self, 'Over the storage limit', f'These previews need about {storage.human(estimate)}, more than the {storage.human(limit)} storage limit. '
                'Older previews would be removed to make room. Continue? (Raise the limit in Storage…)') != QMessageBox.StandardButton.Yes:return
        for p in queue:self.status[p] = 'Queued'
        self.bulk = BulkWorker(queue, self.window.data_root());self.bulk.progress.connect(self.progress);self.bulk.done.connect(self.finished_one);self.bulk.failed.connect(lambda p, e:self.progress(p, 'Failed: '+e))
        self.bulk.finished.connect(self.queue_finished);self.bulk.start();self.render()
    def progress(self, path, text):
        self.status[path] = text;row = self.paths().index(path) if path in self.paths() else -1
        if row >= 0 and self.table.item(row, 7):self.table.item(row, 7).setText(text)
        else:self.render()
    def finished_one(self, path, digest):
        self.status[path] = 'Preview ready';self.window.preview_prepared(digest);self.render()
    def queue_finished(self):
        for p, s in list(self.status.items()):
            if s == 'Queued':self.status[p] = 'Cancelled'
        self.render();self.window.statusBar().showMessage('Bulk preview preparation finished.', 8000)
    def cancel(self):
        if self.bulk and self.bulk.isRunning():self.bulk.requestInterruption()
    def remove(self):
        paths = self.paths();chosen = [paths[r] for r in sorted({i.row() for i in self.table.selectedItems()})]
        current = str(self.window.video_path.resolve()) if self.window.video_path else None
        if current in chosen:return QMessageBox.information(self, 'Video is open', 'Switch to another video before removing the one that is open.')
        if not chosen:return
        if QMessageBox.question(self, 'Remove from project?', f'Remove {len(chosen)} video(s) from this project? Video files and saved measurement files stay on disk. '
                                'Their smooth previews can be deleted in Storage….') != QMessageBox.StandardButton.Yes:return
        for p in chosen:
            self.window.workspace.videos.remove(p);self.window.workspace.states.pop(p, None);self.meta.pop(p, None)
        self.window.workspace.save();self.window.refresh_collection();self.render()
    def open_row(self, row, col):
        self.window.select_video(row);self.window.main_tabs.setCurrentIndex(0)
    def shutdown(self):
        for worker in (self.meta_worker, self.bulk):
            if worker and worker.isRunning():worker.requestInterruption();worker.wait()
