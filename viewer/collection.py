"""Background checksum discovery for a video collection."""
import hashlib
from pathlib import Path
from PySide6.QtCore import QThread,Signal
from .discovery import matching_labels

class CollectionWorker(QThread):
    found=Signal(str,object)
    failed=Signal(str,str)
    def __init__(self,paths,folders):super().__init__();self.paths=paths;self.folders=folders
    def run(self):
        for name in self.paths:
            if self.isInterruptionRequested():return
            try:
                digest=hashlib.sha256()
                with Path(name).open('rb') as f:
                    for chunk in iter(lambda:f.read(8*1024*1024),b''):
                        if self.isInterruptionRequested():return
                        digest.update(chunk)
                matches=matching_labels(digest.hexdigest(),[Path(name).parent,*self.folders])
                self.found.emit(name,matches[0] if matches else None)
            except Exception as e:self.failed.emit(name,str(e))
