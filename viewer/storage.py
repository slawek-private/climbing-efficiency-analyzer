"""Local cache accounting and clean-up: smooth previews and frame indexes, never labels or videos."""
import json
import shutil
from pathlib import Path

DEFAULT_LIMIT_GB = 20


def folders(root):
    return Path(root)/'artifacts'/'preview-cache', Path(root)/'artifacts'/'frame-indexes'


def size(path):
    path = Path(path)
    if path.is_file():return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob('*') if p.is_file()) if path.exists() else 0


def entries(root):
    """One row per cached video: checksum, file name, preview bytes, index bytes, last use."""
    previews, indexes = folders(root);rows = {}
    for folder in previews.glob('*') if previews.exists() else []:
        if folder.is_dir():
            manifest = folder/'manifest.json'
            rows[folder.name] = {'sha256': folder.name, 'preview_bytes': size(folder), 'complete': manifest.exists(), 'last_used': (manifest if manifest.exists() else folder).stat().st_mtime, 'index_bytes': 0, 'file': None}
    for file in indexes.glob('*.json') if indexes.exists() else []:
        row = rows.setdefault(file.stem, {'sha256': file.stem, 'preview_bytes': 0, 'complete': False, 'last_used': file.stat().st_mtime, 'index_bytes': 0, 'file': None})
        row['index_bytes'] = file.stat().st_size
        try:row['file'] = json.loads(file.read_text(encoding='utf-8'))['source']['file']
        except (OSError, ValueError, KeyError):pass
    return sorted(rows.values(), key=lambda r:r['last_used'])


def delete(root, sha256, index=False):
    previews, indexes = folders(root)
    shutil.rmtree(previews/sha256, ignore_errors=True)
    if index:(indexes/(sha256+'.json')).unlink(missing_ok=True)


def remove_incomplete(root):
    """Drop preview folders left without a manifest by an interrupted preparation."""
    for row in entries(root):
        if row['preview_bytes'] and not row['complete']:delete(root, row['sha256'])


def enforce_limit(root, limit_bytes, keep=()):
    """Delete least-recently-used previews until the cache fits the limit. Returns evicted checksums."""
    rows = [r for r in entries(root) if r['preview_bytes']];total = sum(r['preview_bytes'] for r in rows);evicted = []
    for row in rows:
        if total <= limit_bytes:break
        if row['sha256'] in keep:continue
        delete(root, row['sha256']);total -= row['preview_bytes'];evicted.append(row['sha256'])
    return evicted


def human(n):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':return f'{n:.0f} {unit}' if unit in ('B', 'KB') else f'{n:.1f} {unit}'
        n /= 1024


from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QAbstractItemView,
                               QHeaderView, QDoubleSpinBox, QMessageBox)


class StorageDialog(QDialog):
    """What the cache holds, a size limit, and deletion. Measurements and videos are never touched here."""
    def __init__(self, window):
        super().__init__(window);self.window = window;self.setWindowTitle('Storage');self.resize(820, 480)
        self.root = window.data_root();ROOT = self.root;layout = QVBoxLayout(self)
        intro = QLabel(f'Smooth previews and frame indexes speed up opening and scrubbing. They can always be rebuilt from the videos, so deleting them is safe: '
                       f'measurements, reports and video files are not stored here.\nLocation: {folders(ROOT)[0].parent}')
        intro.setWordWrap(True);intro.setObjectName('muted');layout.addWidget(intro)
        line = QHBoxLayout();line.addWidget(QLabel('Cache budget (not reserved disk space)'));self.limit = QDoubleSpinBox();self.limit.setRange(1, 2000);self.limit.setSuffix(' GB');self.limit.setDecimals(0)
        self.limit.setValue(float(window.settings.value('cache_limit_gb', DEFAULT_LIMIT_GB)));self.limit.valueChanged.connect(self.set_limit);line.addWidget(self.limit)
        line.addWidget(QLabel('· least recently used previews are removed first; active and queued previews are kept; protected data can exceed the budget'));line.addStretch();layout.addLayout(line)
        self.table = QTableWidget(0, 5);self.table.setHorizontalHeaderLabels(['Video', 'Used by a project', 'Smooth preview', 'Frame index', 'Last used'])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().hide();self.table.setShowGrid(False);self.table.setAlternatingRowColors(True);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);layout.addWidget(self.table, 1)
        self.total = QLabel();layout.addWidget(self.total)
        line = QHBoxLayout()
        for text, callback in [('Delete selected', self.delete_selected), ('Delete unused by any project', self.delete_unused), ('Delete all previews', self.delete_all), ('Show folder', self.reveal)]:
            b = QPushButton(text);b.clicked.connect(callback);line.addWidget(b)
        line.addStretch();close = QPushButton('Close');close.clicked.connect(self.accept);line.addWidget(close);layout.addLayout(line);self.render()
    def project_digests(self):
        """Checksums of videos used by any project (previews are shared between projects)."""
        from .projects import all_projects
        used = {m['sha256'] for m in self.window.library.meta.values() if m.get('sha256')}
        used |= {s['document']['source']['sha256'] for s in self.window.workspace.states.values()}
        for project in all_projects(self.root):used |= {s['document']['source']['sha256'] for s in project.workspace().get('states', {}).values()}
        return used
    def render(self):
        import time
        self.rows = entries(self.root);inside = self.project_digests();self.table.setRowCount(len(self.rows))
        for row, r in enumerate(reversed(self.rows)):
            for col, value in enumerate([r['file'] or r['sha256'][:12]+'…', 'yes' if r['sha256'] in inside else 'no', human(r['preview_bytes']) if r['preview_bytes'] else '—',
                                         human(r['index_bytes']) if r['index_bytes'] else '—', time.strftime('%Y-%m-%d', time.localtime(r['last_used']))]):
                self.table.setItem(row, col, QTableWidgetItem(value))
        previews = sum(r['preview_bytes'] for r in self.rows);indexes = sum(r['index_bytes'] for r in self.rows)
        self.total.setText(f'Smooth previews {human(previews)} · frame indexes {human(indexes)} · limit {self.limit.value():.0f} GB')
    def set_limit(self, value):
        self.window.settings.setValue('cache_limit_gb', value);self.window.enforce_storage();self.render()
    def chosen(self):
        ordered = list(reversed(self.rows));return [ordered[i.row()]['sha256'] for i in self.table.selectionModel().selectedRows()]
    def remove(self, digests, question):
        protected = self.window.protected_digests();digests = [d for d in digests if d not in protected]
        if digests and QMessageBox.question(self, 'Delete cache?', question.format(n=len(digests))) == QMessageBox.StandardButton.Yes:
            for d in digests:delete(self.root, d, index=True)
            self.render()
    def delete_selected(self):self.remove(self.chosen(), 'Delete cached previews and frame indexes for {n} video(s)? They are rebuilt when needed.')
    def delete_unused(self):
        inside = self.project_digests();self.remove([r['sha256'] for r in self.rows if r['sha256'] not in inside], 'Delete cache for {n} video(s) that no project uses?')
    def delete_all(self):self.remove([r['sha256'] for r in self.rows], 'Delete the cache for all {n} video(s)? The open video keeps its preview.')
    def reveal(self):
        folder = folders(self.root)[0].parent;folder.mkdir(parents=True, exist_ok=True);QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
