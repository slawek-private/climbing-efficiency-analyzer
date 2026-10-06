"""Compact project-video switcher; no decoding, thumbnails or private asset copies."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget,QHBoxLayout,QPushButton,QScrollArea

class VideoNavigation(QWidget):
    def __init__(self,window):
        super().__init__();self.window=window;self.paths=();self.buttons=[]
        row=QHBoxLayout(self);row.setContentsMargins(0,0,0,0);row.setSpacing(6)
        self.count=QPushButton('Videos');self.count.setProperty('role','quiet');self.count.setToolTip('See every video in this project in the Library');self.count.clicked.connect(lambda:window.show_view(window.library));row.addWidget(self.count)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(True);self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded);self.scroll.setFixedHeight(50)
        self.content=QWidget();self.line=QHBoxLayout(self.content);self.line.setContentsMargins(0,0,0,0);self.line.setSpacing(6);self.scroll.setWidget(self.content);row.addWidget(self.scroll,1)
    def refresh(self,paths,current):
        paths=tuple(paths);self.setVisible(bool(paths));self.count.setText(f'Videos · {len(paths)}')
        if paths!=self.paths:
            while self.line.count():
                item=self.line.takeAt(0)
                if item.widget():item.widget().deleteLater()
            self.paths=paths;self.buttons=[]
            for index,path in enumerate(paths):
                name=Path(path).name;b=QPushButton();b.setCheckable(True);b.setFixedWidth(170);b.setFixedHeight(34);b.setAccessibleName(f'Video {index+1}: {name}');b.clicked.connect(lambda checked=False,i=index:self.choose(i));self.line.addWidget(b);self.buttons.append(b)
            self.line.addStretch()
        for index,(path,b) in enumerate(zip(paths,self.buttons)):
            active=path==current;missing=not Path(path).is_file();name=Path(path).name
            b.setChecked(active);b.setText(b.fontMetrics().elidedText(f'{index+1} · '+name,Qt.TextElideMode.ElideMiddle,145));b.setToolTip(('Open now · ' if active else 'Locate missing video · ' if missing else 'Open video · ')+name+'\n'+path);b.setAccessibleDescription('Currently open' if active else 'Missing; click to locate' if missing else 'Click to open')
            if active:self.scroll.ensureWidgetVisible(b,10,0)
    def choose(self,index):
        self.window.select_video(index)
        current=str(self.window.video_path.resolve()) if self.window.video_path else None
        self.refresh(self.window.workspace.videos,current)
