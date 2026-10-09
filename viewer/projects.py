"""Projects group a collection's videos, measurements and reports, e.g. one per event or route.

The original layout (artifacts/workspaces, artifacts/labels, artifacts/reports) is the default project
"My climbs"; new projects live in projects/<slug>/. Smooth previews and frame indexes are keyed by
video checksum and shared by all projects. A .climbproject file is a zip of one project, optionally
with its videos, for archiving or moving to another computer.
"""
import json
import re
import shutil
import time
import zipfile
from pathlib import Path, PurePosixPath
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QAbstractItemView,
                               QHeaderView, QInputDialog, QMessageBox, QFileDialog, QProgressDialog, QCheckBox)
from .version import __version__

FORMAT = 2
EXTENSION = '.climbproject'
TOP_LEVEL = {'project.json', 'workspace.json', 'labels', 'reports', 'videos'}


class Project:
    def __init__(self, folder, legacy=False):
        self.folder = Path(folder);self.legacy = legacy
        self.workspace_file = self.folder/'workspaces'/'current.json' if legacy else self.folder/'workspace.json'
        self.labels = self.folder/'labels';self.reports = self.folder/'reports'
        self.backups = self.folder/('measurement-backups' if legacy else 'backups')
    @property
    def slug(self):return '' if self.legacy else self.folder.name
    def meta(self):
        try:return json.loads((self.folder/'project.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):return {}
    @property
    def name(self):return self.meta().get('name') or ('My climbs' if self.legacy else self.folder.name)
    def save_meta(self, **values):
        data = {'format': FORMAT, 'name': self.name, **self.meta(), **values};self.folder.mkdir(parents=True, exist_ok=True)
        target=self.folder/'project.json';temporary=target.with_suffix('.tmp');temporary.write_text(json.dumps(data, indent=2), encoding='utf-8');temporary.replace(target)
    def touch(self):self.save_meta(last_opened=time.time())
    def workspace(self):
        try:return json.loads(self.workspace_file.read_text(encoding='utf-8'))
        except (OSError, ValueError):return {'videos': [], 'states': {}, 'point_names': []}
    def stats(self):
        data = self.workspace();states = data.get('states', {})
        return {'videos': len(data.get('videos', [])), 'measured': sum(1 for s in states.values() if s['document'].get('start')), 'last_opened': self.meta().get('last_opened')}
    def __eq__(self, other):return isinstance(other, Project) and self.folder == other.folder
    def __hash__(self):return hash(self.folder)


def default(root):return Project(Path(root)/'artifacts', legacy=True)


def all_projects(root):
    folder = Path(root)/'projects'
    return [default(root)]+sorted((Project(p.parent) for p in folder.glob('*/project.json')), key=lambda p:p.name.casefold()) if folder.exists() else [default(root)]


def find(root, slug):return next((p for p in all_projects(root) if p.slug == slug), default(root))


def create(root, name):
    name = name.strip() or 'Untitled project';base = re.sub(r'[^A-Za-z0-9]+', '-', name).strip('-').lower() or 'project';slug = base;n = 2
    while (Path(root)/'projects'/slug).exists():slug = f'{base}-{n}';n += 1
    names = {p.name.casefold() for p in all_projects(root)};shown = name;n = 2
    while shown.casefold() in names:shown = f'{name} {n}';n += 1
    project = Project(Path(root)/'projects'/slug);project.save_meta(name=shown, created=time.time(), last_opened=time.time());return project


def unique(name, used):
    stem, suffix = Path(name).stem, Path(name).suffix;candidate = name;n = 2
    while candidate.casefold() in used:candidate = f'{stem}-{n}{suffix}';n += 1
    used.add(candidate.casefold());return candidate


def export_project(project, target, include_videos=True, progress=lambda text:None, cancelled=lambda:False):
    """Write one .climbproject zip. Videos are stored uncompressed (they are already compressed)."""
    data = project.workspace();target = Path(target);temporary = target.with_name(target.name+'.part');videos = {};labels = {};used_videos = set();used_labels = set()
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
            for i, path in enumerate(data.get('videos', [])):
                if cancelled():raise InterruptedError('Export cancelled')
                if include_videos and Path(path).is_file():
                    progress(f'Adding video {i+1} of {len(data["videos"])}: {Path(path).name}')
                    name = 'videos/'+unique(Path(path).name, used_videos);archive.write(path, name, compress_type=zipfile.ZIP_STORED);videos[path] = name
                else:videos[path] = path
            files = [p for p in project.labels.glob('*.labels.json')] if project.labels.exists() else []
            files += [Path(s['label_path']) for s in [*data.get('states', {}).values(),*[e['state'] for e in data.get('attempts',[])]] if s.get('label_path') and Path(s['label_path']).is_file()]
            for file in files:
                if str(file.resolve()) in labels:continue
                name = 'labels/'+unique(file.name, used_labels);archive.write(file, name);labels[str(file.resolve())] = name
            if project.reports.exists():
                progress('Adding reports')
                for file in project.reports.rglob('*'):
                    if file.is_file():archive.write(file, 'reports/'+file.relative_to(project.reports).as_posix())
            states = {}
            for path, state in data.get('states', {}).items():
                label = state.get('label_path');states[videos.get(path, path)] = {**state, 'label_path': labels.get(str(Path(label).resolve()), label) if label else None}
            attempts=[{'path':videos.get(e['path'],e['path']),'state':{**e['state'],'label_path':labels.get(str(Path(e['state']['label_path']).resolve()),e['state']['label_path']) if e['state'].get('label_path') else None}} for e in data.get('attempts',[])]
            assignments={videos.get(p,p):a for p,a in data.get('assignments',{}).items()}
            archive.writestr('workspace.json', json.dumps({**data,'assignments':assignments,'attempts':attempts, 'videos': [videos[p] for p in data.get('videos', [])], 'states': states}, indent=2))
            archive.writestr('project.json', json.dumps({**project.meta(),'format': FORMAT, 'name': project.name, 'exported_with': __version__, 'exported': time.time()}, indent=2))
        temporary.replace(target);return target
    finally:temporary.unlink(missing_ok=True)


def safe_members(archive):
    """Reject absolute paths, parent references and unexpected top-level entries (zip-slip)."""
    for info in archive.infolist():
        parts = PurePosixPath(info.filename.replace('\\', '/')).parts
        if not parts or info.filename.startswith(('/', '\\')) or '..' in parts or ':' in parts[0] or parts[0] not in TOP_LEVEL:
            raise ValueError(f'Unsafe or unexpected entry in project file: {info.filename}')
    return archive.infolist()


def import_project(root, source, progress=lambda text:None, cancelled=lambda:False):
    with zipfile.ZipFile(source) as archive:
        members = safe_members(archive)
        meta = json.loads(archive.read('project.json'));data = json.loads(archive.read('workspace.json'))
        if meta.get('format') not in (1,FORMAT):raise ValueError('Unsupported project file version')
        project = create(root, meta.get('name', Path(source).stem));base = project.folder.resolve()
        try:
            for info in members:
                if cancelled():raise InterruptedError('Import cancelled')
                if info.filename in ('project.json', 'workspace.json') or info.is_dir():continue
                destination = (project.folder/info.filename).resolve()
                if base not in destination.parents:raise ValueError(f'Unsafe entry in project file: {info.filename}')
                progress(f'Extracting {info.filename}');destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as reader, destination.open('wb') as writer:shutil.copyfileobj(reader, writer, 8*1024*1024)
        except BaseException:
            shutil.rmtree(project.folder, ignore_errors=True);raise
    def local(path):return str((project.folder/path).resolve()) if path and not Path(path).is_absolute() else path
    states = {local(p):{**s, 'label_path': local(s.get('label_path'))} for p, s in data.get('states', {}).items()}
    attempts=[{'path':local(e['path']),'state':{**e['state'],'label_path':local(e['state'].get('label_path'))}} for e in data.get('attempts',[])]
    project.workspace_file.write_text(json.dumps({**data,'assignments':{local(p):a for p,a in data.get('assignments',{}).items()},'attempts':attempts, 'videos': [local(p) for p in data.get('videos', [])], 'states': states}, indent=2), encoding='utf-8')
    from .workspace import Workspace
    restored=Workspace(project.workspace_file)
    if restored.load_error:
        shutil.rmtree(project.folder,ignore_errors=True);raise ValueError('Invalid project workspace: '+restored.load_error)
    return project


class Job(QThread):
    message = Signal(str)
    succeeded = Signal(object)
    failed = Signal(str)
    def __init__(self, work):super().__init__();self.work = work
    def run(self):
        try:self.succeeded.emit(self.work(self.message.emit, self.isInterruptionRequested))
        except InterruptedError:pass
        except Exception as error:self.failed.emit(str(error))


class ProjectBrowser(QDialog):
    def __init__(self, window):
        super().__init__(window);self.window = window;self.setWindowTitle('Projects');self.resize(820, 460);self.job = None
        layout = QVBoxLayout(self)
        intro = QLabel('A project groups the videos, measurements and reports of one event, route or training block. '
                       'Smooth previews are shared between projects. Export a project as one .climbproject file to archive it or move it to another computer.')
        intro.setWordWrap(True);intro.setObjectName('muted');layout.addWidget(intro)
        self.table = QTableWidget(0, 5);self.table.setHorizontalHeaderLabels(['', 'Project', 'Videos', 'Measured', 'Last opened'])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().hide();self.table.setShowGrid(False);self.table.setAlternatingRowColors(True);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents);self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellDoubleClicked.connect(lambda row, col:self.open());layout.addWidget(self.table, 1)
        from PySide6.QtWidgets import QMenu
        line = QHBoxLayout()
        for text, callback, role in [('Open', self.open, 'primary'), ('New…', self.new, None), ('Import…', self.import_file, None)]:
            b = QPushButton(text);b.clicked.connect(callback);line.addWidget(b)
            if role:b.setProperty('role', role)
        from .design import icon_button
        more = icon_button('more',None,None,'More');more.setToolTip('Rename, export, show the folder of, or delete the selected project');menu = QMenu(more)
        for text, callback in [('Rename…', self.rename), ('Export as a file…', self.export), ('Show folder', self.reveal), (None, None), ('Delete…', self.delete)]:
            if text:menu.addAction(text, callback)
            else:menu.addSeparator()
        more.setMenu(menu);line.addWidget(more)
        line.addStretch();close = QPushButton('Close');close.clicked.connect(self.reject);line.addWidget(close);layout.addLayout(line);self.render()
    def render(self):
        self.projects = all_projects(self.window.data_root());self.table.setRowCount(len(self.projects))
        for row, project in enumerate(self.projects):
            s = project.stats();opened = time.strftime('%Y-%m-%d %H:%M', time.localtime(s['last_opened'])) if s['last_opened'] else '—'
            current = project == self.window.project
            for col, value in enumerate(['●' if current else '', project.name, s['videos'], s['measured'], opened]):
                item = QTableWidgetItem(str(value));item.setToolTip(('Open now · ' if current else '')+str(project.folder))
                if current:font = item.font();font.setBold(True);item.setFont(font)
                self.table.setItem(row, col, item)
            if current:self.table.selectRow(row)
    def selected(self):
        row = self.table.currentRow();return self.projects[row] if 0 <= row < len(self.projects) else None
    def open(self):
        project = self.selected()
        if project and self.window.open_project(project):self.accept()
    def new(self):
        name, ok = QInputDialog.getText(self, 'New project', 'Project name (e.g. event, venue or route):')
        if ok and name.strip():
            project = create(self.window.data_root(), name)
            if self.window.open_project(project):self.accept()
            else:self.render()
    def rename(self):
        project = self.selected()
        if not project:return
        name, ok = QInputDialog.getText(self, 'Rename project', 'Project name:', text=project.name)
        if ok and name.strip():project.save_meta(name=name.strip());self.window.update_project_label();self.render()
    def run_job(self, title, work, done):
        dialog = QProgressDialog(title, 'Cancel', 0, 0, self);dialog.setWindowModality(Qt.WindowModality.WindowModal);dialog.setMinimumDuration(0)
        self.job = Job(work);self.job.message.connect(dialog.setLabelText);dialog.canceled.connect(self.job.requestInterruption)
        self.job.succeeded.connect(done);self.job.failed.connect(lambda e:QMessageBox.warning(self, title, e));self.job.finished.connect(dialog.close);self.job.start();dialog.show()
    def done(self, result):
        if self.job and self.job.isRunning():self.job.requestInterruption();self.job.wait()
        super().done(result)
    def export_current(self):
        self.table.selectRow(self.projects.index(self.window.project));self.export()
    def export(self):
        project = self.selected()
        if not project:return
        if project == self.window.project:self.window.remember_current()
        include = QMessageBox.question(self, 'Include videos?', 'Include the video files in the project file?\n\nYes: one self-contained file that opens on any computer (large).\n'
                                       'No: measurements and reports only; videos stay where they are.') == QMessageBox.StandardButton.Yes
        path, _ = QFileDialog.getSaveFileName(self, 'Export project', str(Path(self.window.settings.value('project_folder', str(Path.home())))/(project.name+EXTENSION)), f'Climb Studio project (*{EXTENSION})')
        if not path:return
        path = path if path.endswith(EXTENSION) else path+EXTENSION;self.window.settings.setValue('project_folder', str(Path(path).parent))
        self.run_job('Exporting project', lambda progress, cancelled:export_project(project, path, include, progress, cancelled),
                     lambda target:QMessageBox.information(self, 'Project exported', f'Saved {Path(target).name} ({Path(target).stat().st_size/2**20:.0f} MB).'))
    def import_file(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Import project', self.window.settings.value('project_folder', str(Path.home())), f'Climb Studio project (*{EXTENSION})')
        if path:self.import_path(path)
    def import_path(self, path):
        self.window.settings.setValue('project_folder', str(Path(path).parent))
        def done(project):
            self.render()
            if QMessageBox.question(self, 'Project imported', f'Imported “{project.name}”. Open it now?') == QMessageBox.StandardButton.Yes and self.window.open_project(project):self.accept()
        self.run_job('Importing project', lambda progress, cancelled:import_project(self.window.data_root(), path, progress, cancelled), done)
    def reveal(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        project = self.selected()
        if project:project.folder.mkdir(parents=True, exist_ok=True);QDesktopServices.openUrl(QUrl.fromLocalFile(str(project.folder)))
    def delete(self):
        project = self.selected()
        if not project:return
        if project.legacy:return QMessageBox.information(self, 'Default project', 'The default project cannot be deleted. Use Measurements › Clear measurements instead.')
        if project == self.window.project:return QMessageBox.information(self, 'Project is open', 'Open another project before deleting this one.')
        box = QMessageBox(self);box.setWindowTitle('Delete project?');box.setIcon(QMessageBox.Icon.Warning)
        box.setText(f'Delete “{project.name}”?');box.setInformativeText('Deletes the project folder: its measurements, reports and any videos imported into it. Videos stored elsewhere are not touched. This cannot be undone.')
        confirm = QCheckBox('I exported or no longer need this project');box.setCheckBox(confirm);delete = box.addButton('Delete', QMessageBox.ButtonRole.DestructiveRole);box.addButton(QMessageBox.StandardButton.Cancel);box.exec()
        if box.clickedButton() == delete and confirm.isChecked():shutil.rmtree(project.folder, ignore_errors=True);self.render()
