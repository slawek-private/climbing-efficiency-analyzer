"""In-app updates from GitHub Releases: check, download, verify SHA-256, then hand over to the platform installer.

Only a plain HTTPS request to GitHub is made; no identifiers or usage data are sent.
"""
import hashlib
import re
import sys
import tempfile
import threading
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from .version import __version__

REPOSITORY = 'slawek-private/climbing-efficiency-analyzer'
LATEST = f'https://api.github.com/repos/{REPOSITORY}/releases/latest'
RELEASES = f'https://github.com/{REPOSITORY}/releases/latest'
SUFFIX = {'darwin': '-macOS-arm64.dmg', 'win32': '-Windows-x64-setup.exe'}.get(sys.platform)


def version_tuple(text):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', text.strip())
    return tuple(map(int, match.groups())) if match else None


def is_newer(tag, current=__version__):
    new, old = version_tuple(tag), version_tuple(current)
    return bool(new and old and new > old)


def pick_assets(release, suffix=SUFFIX):
    """Installer for this platform and the checksum list published next to it."""
    assets = {a['name']:a['browser_download_url'] for a in release.get('assets', [])}
    installer = next((name for name in assets if suffix and name.endswith(suffix)), None)
    return (installer, assets[installer] if installer else None, assets.get('SHA256SUMS.txt'))


def compatibility_reason(release,current=__version__,target=None):
    """Fail closed when a release cannot establish a supported upgrade path."""
    from .platform_runtime import update_target
    target=target or update_target();manifest=release.get('update_manifest')
    if not isinstance(manifest,dict):return 'Compatibility information is unavailable. Use the release page.'
    try:
        if manifest['format']!=1 or manifest['version']!=release['tag_name'].lstrip('v'):return 'The compatibility manifest does not match this release.'
        minimum=version_tuple(manifest['minimum_app']);maximum=version_tuple(manifest['maximum_app']);running=version_tuple(current)
        if not minimum or not maximum or not running or not minimum<=running<=maximum:return 'This version requires an intermediate update; see the release notes.'
        supported=next((p for p in manifest['platforms'] if p['os']==target[0] and p['arch']==target[1]),None)
        if supported is None:return 'No installer supports this operating system and architecture.'
        if not target[2] or target[2]<tuple(supported['minimum_os']):return 'Your operating system is older than this release supports.'
        if manifest['migration']!='additive-v1':return 'This release needs a manual data migration; see the release notes.'
    except (KeyError,TypeError,ValueError):return 'Invalid compatibility information; update was not started.'
    return None

def expected_digest(sums, name):
    for line in sums.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip('*') == name and re.fullmatch(r'[0-9a-f]{64}', parts[0]):return parts[0]
    return None


def file_digest(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda:source.read(8*1024*1024), b''):digest.update(chunk)
    return digest.hexdigest()


def can_self_update():
    """Installed builds only; a source checkout updates with git pull."""
    from .platform_runtime import self_update_blocker
    return getattr(sys, 'frozen', False) and SUFFIX is not None and self_update_blocker() is None


class Updater(QObject):
    available = Signal(dict)
    current = Signal()
    progress = Signal(int)
    ready = Signal(object)
    failed = Signal(str)
    def __init__(self, parent=None):
        super().__init__(parent);self.network = QNetworkAccessManager(self);self.reply = None;self.target = None
    def request(self, url):
        request = QNetworkRequest(QUrl(url));request.setRawHeader(b'User-Agent', f'ClimbStudio/{__version__}'.encode())
        request.setRawHeader(b'Accept', b'application/vnd.github+json');request.setTransferTimeout(30000)
        return request
    def check(self):
        reply = self.network.get(self.request(LATEST));reply.finished.connect(lambda:self.checked(reply))
    def checked(self, reply):
        import json
        reply.deleteLater()
        if reply.error() != QNetworkReply.NetworkError.NoError:return self.failed.emit('Could not reach GitHub: '+reply.errorString())
        try:release = json.loads(bytes(reply.readAll()).decode())
        except ValueError:return self.failed.emit('Unexpected answer from GitHub')
        if is_newer(release.get('tag_name', '')):
            url=next((a['browser_download_url'] for a in release.get('assets',[]) if a['name']=='update.json'),None)
            if not url:self.available.emit(release);return
            manifest=self.network.get(self.request(url));manifest.finished.connect(lambda:self.got_manifest(manifest,release))
        else:self.current.emit()
    def got_manifest(self,reply,release):
        import json
        try:
            if reply.error()==QNetworkReply.NetworkError.NoError:release['update_manifest']=json.loads(bytes(reply.readAll()).decode())
        except (ValueError,UnicodeError):pass
        reply.deleteLater();self.available.emit(release)
    def download(self, release):
        reason=compatibility_reason(release)
        if reason:return self.failed.emit(reason)
        name, url, sums_url = pick_assets(release)
        if not url or not sums_url:return self.failed.emit('This release has no verified installer for your system; download it from the release page.')
        sums = self.network.get(self.request(sums_url))
        sums.finished.connect(lambda:self.got_sums(sums, name, url))
    def got_sums(self, reply, name, url):
        reply.deleteLater()
        digest = expected_digest(bytes(reply.readAll()).decode(errors='replace'), name) if reply.error() == QNetworkReply.NetworkError.NoError else None
        if not digest:return self.failed.emit('Could not read the release checksum; the update was not installed.')
        folder = Path(tempfile.mkdtemp(prefix='climb-studio-update-'));self.target = folder/name;handle = self.target.open('wb')
        self.reply = self.network.get(self.request(url))
        self.reply.readyRead.connect(lambda:handle.write(bytes(self.reply.readAll())))
        self.reply.downloadProgress.connect(lambda done, total:self.progress.emit(int(100*done/total) if total > 0 else 0))
        self.reply.finished.connect(lambda:self.downloaded(handle, digest))
    def downloaded(self, handle, digest):
        handle.write(bytes(self.reply.readAll()));handle.close();reply = self.reply;self.reply = None;reply.deleteLater()
        if reply.error() != QNetworkReply.NetworkError.NoError:return self.failed.emit('Download failed: '+reply.errorString())
        if file_digest(self.target) != digest:
            self.target.unlink(missing_ok=True);return self.failed.emit('The download did not match the published checksum and was deleted.')
        from .platform_runtime import prepare_update
        def work():
            try:self.ready.emit(prepare_update(self.target))
            except Exception as error:self.failed.emit('Could not prepare the update: '+str(error))
        threading.Thread(target=work, daemon=True).start()
    def cancel(self):
        if self.reply:self.reply.abort()
