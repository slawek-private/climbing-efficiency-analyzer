"""Live Qt charts using the same embedded SVGs as the HTML reports."""
from html.parser import HTMLParser
from PySide6.QtCore import QByteArray,Qt
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QScrollArea
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
    """Ranked bars from the report generator. Donuts are left to the HTML report; here one precise
    encoding per metric, one decimal, neutral bars and one highlighted athlete."""
    def __init__(self):
        super().__init__();self.documents=[];self.dark=False;layout=QVBoxLayout(self);layout.setContentsMargins(16,12,16,12)
        header=QHBoxLayout();self.note=QLabel('Recovery combines dedicated rest and chalking, counting overlaps once. Unmarked time is unknown.');self.note.setWordWrap(True);self.note.setObjectName('muted');header.addWidget(self.note,1)
        header.addWidget(QLabel('Highlight'));self.focus=QComboBox();header.addWidget(self.focus);layout.addLayout(header)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(True);layout.addWidget(self.scroll,1);self.focus.currentTextChanged.connect(self.redraw)
    def set_documents(self,documents):
        self.documents=documents;selected=self.focus.currentText();self.focus.blockSignals(True);self.focus.clear();self.focus.addItem('All athletes')
        self.focus.addItems(sorted({d['climber'] for d in documents if d['climber']}));i=self.focus.findText(selected);self.focus.setCurrentIndex(max(0,i));self.focus.blockSignals(False);self.redraw()
    def redraw(self):
        import re
        overview,points,_=rows(self.documents)
        rename=lambda data:[{k.replace('_',' '):v for k,v in row.items()} for row in data]
        focus=self.focus.currentText();focus=None if focus=='All athletes' else focus
        markup=charts(rename(overview),rename(points),[],lambda title,body:body,lambda headers,data:'',focus=focus)
        parser=SVGs();parser.feed(markup);container=QWidget();column=QVBoxLayout(container);column.setSpacing(18)
        ink,bar,highlight=('#d6e2f4','#4a5a70','#e8edf4') if self.dark else ('#25334a','#a3aec0','#141a24')
        titles={'Combined marked recovery percentage':'Recovery · share of the climb','REST arrival':'Arrival at REST · seconds from climb start','Eight-clip total':'Total clipping time · attempts with eight clips'}
        shown=0
        for title,svg in parser.items:
            if 'viewBox="0 0 210 200"' in svg:continue  # donut
            svg=svg.replace('<svg ','<svg xmlns="http://www.w3.org/2000/svg" ',1).replace('<text ',f'<text fill="{ink}" ').replace('#4784df',bar).replace('#f0a340',highlight)
            svg=re.sub(r'>(\d+\.\d+)(%| s)<',lambda m:f'>{float(m.group(1)):.1f}'+(' %' if m.group(2)=='%' else ' s')+'<',svg)  # round, as the table does
            box=QVBoxLayout();heading=QLabel(titles.get(title,title));heading.setObjectName('section');box.addWidget(heading)
            height=int(re.search(r'viewBox="0 0 700 (\d+)"',svg).group(1)) if 'viewBox="0 0 700' in svg else 120
            widget=QSvgWidget();widget.load(QByteArray(svg.encode('utf-8')));widget.setFixedSize(int(700*.82),int(height*.82))
            if '<rect' not in svg:
                empty=QLabel('No matched measurements yet.');empty.setObjectName('muted');box.addWidget(empty)
            else:box.addWidget(widget,0,Qt.AlignmentFlag.AlignLeft)
            column.addLayout(box);shown+=1
        if not shown:
            empty=QLabel('Mark climb start and end for at least one athlete to show charts.');empty.setObjectName('muted');column.addWidget(empty)
        column.addStretch();old=self.scroll.takeWidget();self.scroll.setWidget(container)
        if old:old.deleteLater()
