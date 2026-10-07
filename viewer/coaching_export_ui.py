"""Snapshot-based background report export; including footage is an explicit choice."""
import copy
from pathlib import Path
from PySide6.QtCore import QThread,Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QDialog,QFormLayout,QLabel,QComboBox,QCheckBox,QDialogButtonBox,QFileDialog,QPushButton,QProgressBar
from .coaching_report import export_report

class ExportWorker(QThread):
    progress=Signal(str);ready=Signal(str);failed=Signal(str)
    def __init__(self,documents,path,options,parent):super().__init__(parent);self.documents=documents;self.path=path;self.options=options
    def run(self):
        try:self.ready.emit(str(export_report(self.documents,self.path,progress=self.progress.emit,cancelled=self.isInterruptionRequested,**self.options)))
        except Exception as e:self.failed.emit(str(e))

def export_dialog(w):
    if w.coaching_export_worker and w.coaching_export_worker.isRunning():return w.statusBar().showMessage('A coaching report is already being prepared.',5000)
    if not w.flush_autosave():return
    w.remember_current();w.refresh_collection();current=w.document();selected=w.comparison_documents
    if not current and not selected:return w.error('Open a video in Video analysis or select an attempt first.')
    dialog=QDialog(w);dialog.setWindowTitle('Export coaching review');form=QFormLayout(dialog)
    scope=QComboBox();scope.addItem('Current attempt','current');scope.addItem('Selected comparison attempts','selected');scope.setCurrentIndex(0 if current else 1);form.addRow('Attempts',scope)
    media=QComboBox()
    for label,value in [('Measurements only · no footage','none'),('Link originals · this computer only','links'),('Portable H.264 sections and stills','clips')]:media.addItem(label,value)
    form.addRow('Video',media);notice=QLabel('Video stays local. Portable sections are compressed review copies with original frame/PTS provenance; keep the accompanying media folder with the HTML. Including footage is optional.');notice.setWordWrap(True);form.addRow(notice)
    hands=QCheckBox('Include hand intervals and all points as video sections too');form.addRow(hands)
    anonymous=QCheckBox('Replace athlete names with Athlete 1, Athlete 2…');form.addRow(anonymous)
    note=QLabel('Anonymous names do not redact people visible in footage or names written in notes or session titles.');note.setWordWrap(True);note.setObjectName('muted');form.addRow(note)
    pdf=QCheckBox('Also create a printable PDF');pdf.setChecked(True);form.addRow(pdf)
    buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);form.addRow(buttons)
    if dialog.exec()!=QDialog.DialogCode.Accepted:return
    documents=[current] if scope.currentData()=='current' and current else selected
    if not documents:return w.error('Choose at least one attempt.')
    from .context_ui import report_permission
    if not report_permission(w,documents):return
    filename,_=QFileDialog.getSaveFileName(w,'Save private coaching review',str(w.project.reports/'coaching-review.html'),'HTML (*.html)')
    if not filename:return
    sources={}
    for path,state in list(w.workspace.states.items())+[(e['path'],e['state']) for e in w.workspace.attempts]:
        d=state['document'];sources[d.get('attempt_id') or d['source']['sha256']]=path
    options=dict(sources=sources,media=media.currentData(),include_hands=hands.isChecked(),anonymous=anonymous.isChecked(),pdf=pdf.isChecked(),cache_root=w.data_root())
    worker=ExportWorker(copy.deepcopy(documents),Path(filename),options,w);w.coaching_export_worker=worker
    progress=QDialog(w);progress.setWindowTitle('Preparing coaching review');progress.setModal(False);box=QFormLayout(progress);label=QLabel('Preparing local report…');label.setWordWrap(True);box.addRow(label);bar=QProgressBar();bar.setRange(0,0);box.addRow(bar);cancel=QPushButton('Cancel export');cancel.clicked.connect(worker.requestInterruption);box.addRow(cancel);progress.rejected.connect(worker.requestInterruption)
    def done(path):
        progress.accept();w.statusBar().showMessage('Coaching report saved to '+path,15000);QDesktopServices.openUrl(QUrl.fromLocalFile(path))
    def failed(message):
        progress.reject()
        if message=='Report export cancelled':w.statusBar().showMessage(message,6000)
        else:w.error(message)
    worker.progress.connect(label.setText);worker.ready.connect(done);worker.failed.connect(failed);worker.finished.connect(lambda:setattr(w,'coaching_export_worker',None));progress.show();worker.start()
