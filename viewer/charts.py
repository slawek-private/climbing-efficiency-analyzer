"""Live Qt charts using the same embedded SVGs as the HTML reports."""
from html.parser import HTMLParser
from PySide6.QtCore import QByteArray,Qt
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QScrollArea,QGridLayout
from .comparison import rows
from .report_visuals import charts

class SVGs(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=False);self.items=[];self.current=None;self.title=''
    def handle_starttag(self,tag,attrs):
        if tag=='svg':
            self.title=dict(attrs).get('aria-label','Comparison chart');self.current=[self.get_starttag_text()]
        elif self.current is not None:self.current.append(self.get_starttag_text())
    def handle_startendtag(self,tag,attrs):
        if self.current is not None:self.current.append(self.get_starttag_text())
    def handle_endtag(self,tag):
        if self.current is not None:
            self.current.append('</'+tag+'>')
            if tag=='svg':self.items.append((self.title,''.join(self.current)));self.current=None
    def handle_data(self,data):
        if self.current is not None:self.current.append(data)
    def handle_entityref(self,name):
        if self.current is not None:self.current.append('&'+name+';')
    def handle_charref(self,name):
        if self.current is not None:self.current.append('&#'+name+';')

class ComparisonCharts(QWidget):
    def __init__(self):
        super().__init__();self.documents=[];layout=QVBoxLayout(self)
        header=QHBoxLayout();header.addWidget(QLabel('Comparison charts'));header.addStretch();header.addWidget(QLabel('Highlight athlete'));self.focus=QComboBox();header.addWidget(self.focus);layout.addLayout(header)
        self.note=QLabel('Combined recovery includes dedicated rest and chalking; overlaps count once. Unmarked time is unknown.');self.note.setWordWrap(True);layout.addWidget(self.note)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(True);layout.addWidget(self.scroll,1);self.focus.currentTextChanged.connect(self.redraw)
    def set_documents(self,documents):
        self.documents=documents;selected=self.focus.currentText();self.focus.blockSignals(True);self.focus.clear();self.focus.addItem('All athletes')
        self.focus.addItems(sorted({d['climber'] for d in documents if d['climber']}));i=self.focus.findText(selected);self.focus.setCurrentIndex(max(0,i));self.focus.blockSignals(False);self.redraw()
    def redraw(self):
        overview,points,_=rows(self.documents)
        rename=lambda data:[{k.replace('_',' '):v for k,v in row.items()} for row in data]
        focus=self.focus.currentText();focus=None if focus=='All athletes' else focus
        markup=charts(rename(overview),rename(points),[],lambda title,body:body,lambda headers,data:'',focus=focus)
        parser=SVGs();parser.feed(markup);container=QWidget();grid=QGridLayout(container)
        donut_count=0;bar_row=0
        for i,(title,svg) in enumerate(parser.items):
            card=QWidget();card.setStyleSheet('QWidget { background: #ffffff; color: #18334f; border-radius: 10px; }');box=QVBoxLayout(card);label=QLabel(title);label.setWordWrap(True);box.addWidget(label)
            svg=svg.replace('<svg ','<svg xmlns="http://www.w3.org/2000/svg" ',1).replace('class="donut-value"','font-size="25" font-weight="700"').replace('class="donut-caption"','font-size="11"').replace('<text ','<text fill="#34516f" ')
            widget=QSvgWidget();widget.load(QByteArray(svg.encode('utf-8')));widget.renderer().setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio);widget.setMinimumHeight(220);box.addWidget(widget)
            if '%' in title:
                grid.addWidget(card,donut_count//3,donut_count%3);donut_count+=1
            else:
                grid.addWidget(card,(donut_count+2)//3+bar_row,0,1,3);bar_row+=1
                if '<rect' not in svg:box.addWidget(QLabel('No matched measurements yet.'));widget.setMaximumHeight(30)
        if not parser.items:grid.addWidget(QLabel('Mark climb boundaries to show charts.'),0,0)
        grid.setRowStretch((donut_count+2)//3+bar_row,1);old=self.scroll.takeWidget();self.scroll.setWidget(container)
        if old:old.deleteLater()
