"""Import & library: per-video metadata, preview recommendations, storage estimates and a bulk queue."""
import hashlib
import io
import shutil
from pathlib import Path
import av
from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,QGridLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                               QAbstractItemView, QHeaderView, QMessageBox,QCheckBox,QMenu,QComboBox,QSizePolicy)
from .controls import Button as QPushButton
from . import storage
from . import identity

COLUMNS = ['Video', 'Athlete', 'Resolution', 'FPS', 'Codec', 'Duration', 'File size', 'Smooth preview', 'Preview size', 'Notes','Status','Action','Session','Route version','Attempts']
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
    if meta['fps'] and meta['fps'] < 49:out.append(f"{1000/meta['fps']:.0f} ms/frame")
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
        from .controls import info_button
        head=QHBoxLayout();self.heading=QLabel();self.heading.setObjectName('section');head.addWidget(self.heading);head.addWidget(info_button(intro.text()));head.addStretch();layout.addLayout(head)
        self.open_now=QLabel();self.open_now.setObjectName('muted');self.open_now.hide()
        filters=QHBoxLayout();filters.setSpacing(8);self.session_filter=QComboBox()
        for label,key in [('Current session + unassigned','current'),('All sessions','all'),('Needs assignment','pending')]:self.session_filter.addItem(label,key)
        self.athlete_filter=QComboBox();self.athlete_filter.addItem('All athletes','');self.route_filter=QComboBox();self.route_filter.addItem('All route versions','')
        for name,control in [('Session scope',self.session_filter),('Athlete',self.athlete_filter),('Route version',self.route_filter)]:control.setAccessibleName(name);control.setToolTip(name);control.setProperty('chip',True);control.setMinimumWidth(90);control.setMaximumWidth(260);control.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed);filters.addWidget(control,1);control.currentIndexChanged.connect(self.render)
        self.assign_button=assign=QPushButton('Assign selected…');assign.clicked.connect(self.assign_selected);filters.addWidget(assign)
        bar = filters;self.buttons = {};self.more_actions={};more=QPushButton("More ▾");more_menu=QMenu(more);more.setMenu(more_menu)
        for key, text, callback, tip in [
            ('add', 'Add videos…', window.open_video, 'Add video files to this project.'),
            ('recommended', 'Prepare all recommended', lambda:self.prepare(recommended=True), 'Queue every video marked Recommended that has no smooth preview yet.'),
            ('selected', 'Prepare selected', lambda:self.prepare(recommended=False), 'Queue the selected rows.'),
            ('cancel', 'Cancel queue', self.cancel, 'Stop after discarding the preview currently being prepared.'),
            ('remove', 'Remove from project', self.remove, 'Remove the selected videos from this project. Video files and saved measurements are kept.'),
            ('storage', 'Storage…', window.show_storage, 'See and limit disk space used by previews and frame indexes.')]:
            b = QPushButton(text);b.setToolTip(tip);b.clicked.connect(callback);self.buttons[key] = b
            if key in ("add","selected","cancel"):bar.insertWidget(len(self.buttons)-1,b)
            else:
                b.hide();action=more_menu.addAction(text);action.setToolTip(tip);action.triggered.connect(callback);self.more_actions[key]=action
        self.buttons['add'].setProperty('role', 'primary');self.buttons['cancel'].setEnabled(False);bar.insertStretch(3);bar.addWidget(more);layout.addLayout(bar)
        self.selection_hint=QLabel();self.selection_hint.setObjectName('muted');self.selection_hint.setWordWrap(True);self.selection_hint.hide()
        self.table = QTableWidget(0, len(COLUMNS));self.table.setHorizontalHeaderLabels(COLUMNS);self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.table.setAlternatingRowColors(True);self.table.setShowGrid(False);self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents);self.table.horizontalHeader().setStretchLastSection(False);self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch);self.table.horizontalHeader().moveSection(10,1);self.table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
        self.details=QCheckBox('Show recording details');self.details.toggled.connect(self.show_details);self.details.hide();self.show_details(False)
        more_menu.addSeparator();details=more_menu.addAction('Show recording details');details.setCheckable(True);details.toggled.connect(self.details.setChecked)
        self.table.itemSelectionChanged.connect(self.selection_changed);self.table.cellDoubleClicked.connect(self.open_row);self.table.setToolTip('Double-click a video to open it in the Video workspace.');layout.addWidget(self.table, 1)
        layout.addStretch();self.summary = QLabel();self.summary.setObjectName('muted');self.summary.setWordWrap(True);layout.addWidget(self.summary)
    def show_details(self,show):
        for column in (2,3,4,5,6,9):self.table.setColumnHidden(column,not show)
    def update_heading(self):
        current=self.window.video_path;self.heading.setText(f'{self.window.project.name} · {len(self.paths())} videos')
        self.open_now.setText('Open now: '+current.name+' · choose another video below' if current else 'Choose a video below to open it in Video analysis.')
    def path_assignments(self,path):
        ws=self.window.workspace;docs=[s['document'] for p,s in list(ws.states.items())+[(e['path'],e['state']) for e in ws.attempts] if p==path]
        snapshots=[d['assignment'] for d in docs if identity.assigned(d)]
        if not snapshots and path in ws.assignments:
            a=ws.assignments[path];snapshots=[{key:identity.entry(ws.organisation,group,a[key]) for key,group in [('athlete','athletes'),('session','sessions'),('route','routes')]}]
        return [a for a in snapshots if all(a.values())]
    def paths(self):
        ws=self.window.workspace;paths=[]
        for path in ws.videos:
            values=self.path_assignments(path);scope=self.session_filter.currentData()
            if scope=='pending' and values:continue
            if scope=='current' and values:values=[a for a in values if a['session']['id']==ws.session_id]
            if scope=='current' and self.path_assignments(path) and not values:continue
            if self.athlete_filter.currentData():values=[a for a in values if a['athlete']['id']==self.athlete_filter.currentData()]
            if self.route_filter.currentData():values=[a for a in values if a['route']['id']==self.route_filter.currentData()]
            if (self.athlete_filter.currentData() or self.route_filter.currentData()) and not values:continue
            paths.append(path)
        return paths
    def refresh_filters(self):
        for control,group,label,format_label in [(self.athlete_filter,'athletes','All athletes',identity.athlete_label),(self.route_filter,'routes','All route versions',identity.route_label)]:
            old=control.currentData();control.blockSignals(True);control.clear();control.addItem(label,'')
            for item in self.window.workspace.organisation[group]:control.addItem(format_label(item),item['id'])
            control.setCurrentIndex(max(0,control.findData(old)));control.blockSignals(False)
    def assign_selected(self):
        from .context_ui import AssignmentDialog,apply_assignments
        if not self.window.flush_autosave():return
        paths=self.paths();chosen=[paths[r] for r in sorted({i.row() for i in self.table.selectedItems()})]
        if not chosen:return
        current=str(self.window.video_path.resolve()) if self.window.video_path else None
        rows=[(p,self.window.document() if p==current else self.window.workspace.states.get(p,{}).get('document')) for p in chosen]
        dialog=AssignmentDialog(self.window,rows,True)
        if dialog.exec()!=dialog.DialogCode.Accepted:return
        existing=[r for r in dialog.result_assignments if r[1] is not None]
        for path,doc,a,s,r in dialog.result_assignments:
            if doc is None:self.window.workspace.assignments[path]={'athlete':a,'session':s,'route':r}
        dialog.result_assignments=existing;apply_assignments(self.window,dialog)
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
        self.refresh_filters()
        self.update_heading();paths = self.paths()
        if tuple(paths)!=getattr(self,'displayed_paths',()):self.table.clearSelection();self.displayed_paths=tuple(paths)
        self.table.setRowCount(len(paths));states = self.window.workspace.states;wanted = 0;candidates = low_fps = low_res = hdr = 0
        for row, path in enumerate(paths):
            m = self.meta.get(path, {});state = states.get(path)
            if not Path(path).is_file():values=[Path(path).name]+['']*6+['Missing — double-click to locate']+['']*2
            elif 'error' in m:values = [Path(path).name, '', '', '', '', '', '', self.status.get(path, 'Unreadable'), '', m['error']]
            elif m:
                ready = self.preview_ready(m);advice = 'Ready' if ready else {'Optional':'Not needed'}.get(recommendation(m),recommendation(m))
                if not ready and advice == 'Recommended' and m['preview_bytes']:wanted += m['preview_bytes']
                w, h = (m['height'], m['width']) if m['rotation'] in (90, 270) else (m['width'], m['height'])
                values = [m['file'], state['document']['climber'] if state else '—', f'{w}×{h}', f"{m['fps']:.2f}".rstrip('0').rstrip('.') if m['fps'] else '?', m['codec'].upper(),
                          f"{m['duration']:.0f} s" if m['duration'] else '?', storage.human(m['size_bytes']), self.status.get(path) or advice, '~'+storage.human(m['preview_bytes']) if m['preview_bytes'] else '?', notes(m)]
                candidates += (not ready and advice == 'Recommended')
                low_fps += bool(m['fps'] and m['fps'] < 49);low_res += min(m['width'], m['height']) < 1080;hdr += bool(m['hdr'])
            else:values = [Path(path).name]+['']*6+[self.status.get(path, 'Waiting')]+['']*2
            current=bool(self.window.video_path and path==str(self.window.video_path.resolve()));missing=not Path(path).is_file();readiness='Open' if current else 'Missing source' if missing else 'Cannot read' if 'error' in m else 'Ready' if m else 'Reading metadata'
            values += [readiness,'']
            assignments=self.path_assignments(path)
            values[1]=' / '.join(dict.fromkeys(identity.athlete_label(a['athlete']) for a in assignments)) or 'Needs assignment'
            count=sum(p==path for p in self.window.workspace.states)+sum(e['path']==path for e in self.window.workspace.attempts)
            values+=[' / '.join(dict.fromkeys(identity.session_label(a['session']) for a in assignments)),' / '.join(dict.fromkeys(identity.route_label(a['route']) for a in assignments)),str(count) if count else 'Not started']
            if not assignments and not missing:values[10]='Needs athlete'
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if current and col in (0,10):font=item.font();font.setBold(True);item.setFont(font)
                if col == 9 and value:item.setToolTip('Milliseconds/frame is nominal spacing, not an error bound; actual timestamps can vary. <1080p: small hands and quickdraws. HDR: colours may look flat.')
                if col in (0,1):item.setToolTip('\n'.join(identity.session_label(a['session'])+' / '+identity.route_label(a['route']) for a in assignments) or 'Assign athlete, session and route before analysis.')
                if col == 7:item.setToolTip({'Ready': 'Smooth preview prepared: scrubbing and stepping use it automatically.', 'Recommended': '4K or HEVC: scrubbing the original is slow. Prepare a smooth preview.', 'Not needed': 'Usually smooth enough without a preview.'}.get(value, ''))
                self.table.setItem(row, col, item)
            action=self.table.cellWidget(row,11)
            if action is None:
                action=QPushButton();action.clicked.connect(lambda checked=False,b=action:self.row_action(b.property('videoRow'),True));self.table.setCellWidget(row,11,action)
            action.setProperty('videoRow',row);action.setText('Locate…' if missing else 'Return to video' if current else 'Open')
        root = self.window.data_root();cache = sum(r['preview_bytes']+r['index_bytes'] for r in storage.entries(root));limit = float(self.window.settings.value('cache_limit_gb', storage.DEFAULT_LIMIT_GB))
        self.table.setColumnHidden(12,self.session_filter.currentData()=='current')
        rows=self.table.rowCount();self.table.setMaximumHeight(self.table.horizontalHeader().height()+sum(self.table.rowHeight(r) for r in range(rows))+8 if 0<rows<=12 else 16777215)
        free = shutil.disk_usage(root if root.exists() else Path.home()).free
        flags = [f'{n} {what}' for n, what in ((low_fps, 'under 50 fps (wider frame spacing)'), (low_res, 'below 1080p'), (hdr, 'HDR')) if n]
        self.summary.setText(f'{len(paths)} videos'+(' · '+', '.join(flags) if flags else '')+f' · cache {storage.human(cache)} of {limit:g} GB · {storage.human(free)} free'
                             +(f' · recommended previews to prepare: ~{storage.human(wanted)}' if wanted else ''))
        running = bool(self.bulk and self.bulk.isRunning());self.buttons['cancel'].setEnabled(running)
        self.selection_changed()
        self.buttons['recommended'].setEnabled(not running and candidates > 0)
        self.buttons['recommended'].setText(f'Prepare {candidates} recommended' if candidates else 'Nothing to prepare')
        for key,action in self.more_actions.items():action.setEnabled(self.buttons[key].isEnabled());action.setText(self.buttons[key].text())
    def selection_changed(self):
        selected={item.row() for item in self.table.selectedItems()};paths=self.paths()
        running=bool(self.bulk and self.bulk.isRunning())
        eligible=[paths[r] for r in selected if r<len(paths) and Path(paths[r]).is_file() and 'error' not in self.meta.get(paths[r],{}) and not self.preview_ready(self.meta.get(paths[r],{}))]
        self.buttons['selected'].setEnabled(bool(eligible) and not running)
        self.selection_hint.setText('Preview queue running · Cancel queue to stop it.' if running else 'Select videos to prepare previews or assign athletes.' if not selected else f'{len(selected)} selected · {len(eligible)} need a preview. Assign selected changes their athlete, session and route.')
        self.buttons['selected'].setToolTip('Prepare previews for selected videos.' if eligible else 'Select videos without a prepared preview first.')
        self.buttons['remove'].setEnabled(bool(selected) and not running);self.assign_button.setEnabled(bool(selected))
        self.buttons['selected'].setAccessibleDescription('Select videos without a prepared preview first.' if not eligible else 'Queue local previews for selected videos.')
        if 'remove' in self.more_actions:self.more_actions['remove'].setEnabled(self.buttons['remove'].isEnabled())
    def row_action(self,row,open_video):
        if open_video:self.open_row(row,0)
        else:self.table.clearSelection();self.table.selectRow(row);self.prepare(False)
    def prepare(self, recommended):
        if self.bulk and self.bulk.isRunning():return
        if self.window.preview_worker and self.window.preview_worker.isRunning():return QMessageBox.information(self,'Preparation running','Wait for the current preview to finish, or cancel it in Video analysis, before starting a queue.')
        paths = self.paths()
        rows = range(len(paths)) if recommended else sorted({i.row() for i in self.table.selectedItems()})
        queue = [paths[r] for r in rows if Path(paths[r]).is_file() and 'error' not in self.meta.get(paths[r], {}) and not self.preview_ready(self.meta.get(paths[r], {}))
                 and (not recommended or (self.meta.get(paths[r]) and recommendation(self.meta[paths[r]]) == 'Recommended'))]
        if not queue:return QMessageBox.information(self, 'Nothing to prepare', 'Every chosen video already has a smooth preview, or none is recommended.')
        if not self.confirm_previews(queue):return
        for i,p in enumerate(queue,1):self.status[p] = f'Queued {i}/{len(queue)}'
        self.bulk = BulkWorker(queue, self.window.data_root());self.bulk.progress.connect(self.progress);self.bulk.done.connect(self.finished_one);self.bulk.failed.connect(lambda p, e:self.progress(p, 'Failed: '+e))
        self.bulk.finished.connect(self.queue_finished);self.bulk.start();self.render()
    def confirm_previews(self,queue):
        estimate = sum(self.meta.get(p, {}).get('preview_bytes') or 0 for p in queue);limit = float(self.window.settings.value('cache_limit_gb', storage.DEFAULT_LIMIT_GB))*2**30
        if estimate > limit and QMessageBox.question(self, 'Over the storage limit', f'These previews need about {storage.human(estimate)}, more than the {storage.human(limit)} storage limit. '
                'Older previews would be removed to make room. Continue? (Raise the limit in Storage…)') != QMessageBox.StandardButton.Yes:return
        free=shutil.disk_usage(self.window.data_root()).free
        if estimate+512*2**20>free:
            QMessageBox.warning(self,'Not enough free storage',f'Estimated previews: {storage.human(estimate)}; free: {storage.human(free)}. Keep at least 512 MB free. Reduce the selection or clear unused previews.');return False
        estimate_text=storage.human(estimate)+' (sample estimate; actual size varies)' if all(self.meta.get(p,{}).get('preview_bytes') for p in queue) else 'not yet available'
        return QMessageBox.question(self,'Prepare local previews',f'{len(queue)} video(s) · estimated cache: {estimate_text} · {storage.human(free)} free. Creates a local frame cache for smoother seeking. Originals, frames and timestamps are unchanged. Manage cache size in File → Storage. Start in the background?')==QMessageBox.StandardButton.Yes
    def progress(self, path, text):
        self.status[path] = text;row = self.paths().index(path) if path in self.paths() else -1
        if row >= 0 and self.table.item(row, 7):self.table.item(row, 7).setText(text)
        else:self.render()
    def finished_one(self, path, digest):
        self.status[path] = 'Preview ready';self.window.preview_prepared(digest);self.render()
    def queue_finished(self):
        for p, s in list(self.status.items()):
            if s.startswith('Queued'):self.status[p] = 'Cancelled'
        self.window.enforce_storage();self.render();self.window.statusBar().showMessage('Preview queue stopped. See each video’s status for completed, failed or cancelled jobs.', 8000)
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
            self.window.workspace.videos.remove(p);self.window.workspace.states.pop(p, None);self.window.workspace.assignments.pop(p,None);self.meta.pop(p, None)
        self.window.workspace.attempts=[e for e in self.window.workspace.attempts if e['path'] not in chosen]
        self.window.workspace.save();self.window.refresh_collection();self.render()
    def open_row(self, row, col):
        paths=self.paths()
        if not 0<=row<len(paths):return
        self.window.select_video(self.window.workspace.videos.index(paths[row]));self.window.main_tabs.setCurrentIndex(0);self.render()
    def shutdown(self):
        for worker in (self.meta_worker, self.bulk):
            if worker and worker.isRunning():worker.requestInterruption();worker.wait()
