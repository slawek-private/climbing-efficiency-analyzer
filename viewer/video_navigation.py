"""One project source chooser beside the athlete/attempt chooser."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QMenu, QSizePolicy
from .controls import Button

class VideoNavigation(QWidget):
    def __init__(self, window):
        super().__init__();self.window=window;self.paths=();self.buttons=[]
        row=QHBoxLayout(self);row.setContentsMargins(0,0,0,0)
        self.count=Button();self.count.setProperty('role','quiet');self.count.setMinimumWidth(110)
        self.count.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
        self.menu=QMenu(self.count);self.count.setMenu(self.menu);row.addWidget(self.count)
    def refresh(self, paths, current):
        paths=tuple(paths);self.setVisible(bool(paths))
        if paths!=self.paths:
            self.menu.clear();self.paths=paths;self.buttons=[]
            for index,path in enumerate(paths):
                action=self.menu.addAction(f'{index+1} · {Path(path).name}');action.setCheckable(True)
                action.setToolTip(path);action.triggered.connect(lambda checked=False,i=index:self.choose(i));self.buttons.append(action)
            self.menu.addSeparator();self.menu.addAction('All project videos…',lambda:self.window.show_view(self.window.library))
        index=paths.index(current) if current in paths else -1
        title=f'Video {index+1} of {len(paths)} · {Path(current).name} ▾' if index>=0 else f'Choose video · {len(paths)} ▾'
        prefix=f'Video {index+1} of {len(paths)}' if index>=0 else f'Choose video · {len(paths)}'
        remaining=max(0,self.width()-35-self.count.fontMetrics().horizontalAdvance(prefix))
        suffix=self.count.fontMetrics().elidedText(' · '+Path(current).name,Qt.TextElideMode.ElideMiddle,remaining) if index>=0 else ''
        self.count.setText(prefix+suffix+' ▾')
        self.count.setAccessibleName(title);self.count.setToolTip(title+'\nChoose any project video; missing sources can be located here.')
        for path,action in zip(paths,self.buttons):action.setChecked(path==current)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self.paths:self.refresh(self.paths,str(self.window.video_path.resolve()) if self.window.video_path else None)
    def choose(self,index):
        self.window.select_video(index)
        self.refresh(self.window.workspace.videos,str(self.window.video_path.resolve()) if self.window.video_path else None)
