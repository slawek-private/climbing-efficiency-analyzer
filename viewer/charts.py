"""Compact comparison dashboards below the shared overview table."""
from PySide6.QtCore import QByteArray
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QScrollArea,QSizePolicy,QToolTip,QComboBox
from .reporting import records,chart_specs,svg_chart,row_text

class ResponsiveChart(QSvgWidget):
    def __init__(self,svg,height,details=None,step=54):
        super().__init__();from PySide6.QtWidgets import QApplication
        from html import escape
        svg=svg.replace('<svg ', '<svg font-family="'+escape(QApplication.font().family(),quote=True)+'" ',1);self.load(QByteArray(svg.encode()));self.base_height=height;self.step=step;self.details=details or [];self.setMouseTracking(True);self.setAccessibleDescription('\n'.join(self.details))
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed);self.setMaximumWidth(1000)
    def resizeEvent(self,event):
        self.setFixedHeight(max(55,int(self.width()*self.base_height/600)));super().resizeEvent(event)
    def hover_text(self,y):
        scale=min(self.width()/600,self.height()/self.base_height);top=(self.height()-self.base_height*scale)/2
        row=int(((y-top)/max(.001,scale)-12)//self.step)
        return self.details[row] if 0<=row<len(self.details) else ''
    def mouseMoveEvent(self,event):
        tip=self.hover_text(event.position().y())
        if tip:QToolTip.showText(event.globalPosition().toPoint(),tip,self)
        else:QToolTip.hideText()

class ComparisonCharts(QWidget):
    def __init__(self,embedded=False):
        super().__init__();self.documents=[];self.dark=False;self.checkpoint='Climb start';self.embedded=embedded;self.draw_page=0;layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        self.body=QWidget();self.grid=QGridLayout(self.body);self.grid.setContentsMargins(0,0,0,0);self.grid.setSpacing(16)
        if embedded:layout.addWidget(self.body)
        else:
            self.scroll=QScrollArea();self.scroll.setWidgetResizable(True);self.scroll.setWidget(self.body);layout.addWidget(self.scroll)
    def set_documents(self,documents):self.documents=documents;self.redraw()
    def redraw(self):
        while self.grid.count():
            item=self.grid.takeAt(0)
            if item.widget():
                widget=item.widget();widget.setParent(None);widget.deleteLater()
        data=records(self.documents);draws=sorted({n for r in data for n in r['clips']},key=float);self.draw_page=min(self.draw_page,max(0,len(draws)-1))
        arrival,clips,recovery,foot=chart_specs(data,self.checkpoint,draws[self.draw_page:self.draw_page+1])
        def add_plot(column,spec):
            title=QLabel(spec['title']);title.setObjectName('section');column.addWidget(title)
            note=QLabel(spec['note']);note.setObjectName('muted');note.setWordWrap(True);column.addWidget(note)
            svg,height,step=svg_chart(spec,self.dark);column.addWidget(ResponsiveChart(svg,height,[row_text(r,spec) for r in spec['rows']],step))
        for index,spec in enumerate([arrival,None,recovery,foot]):
            card=QWidget();card.setObjectName('dashboardCard');v=QVBoxLayout(card);v.setContentsMargins(12,12,12,12)
            if index==1:
                line=QHBoxLayout();line.addWidget(QLabel('Clip duration · matching draws'));selector=QComboBox()
                for i in range(len(draws)):selector.addItem('Quickdraw '+draws[i],i)
                selector.setCurrentIndex(self.draw_page);selector.setEnabled(len(draws)>1);selector.setToolTip('Choose a matching quickdraw. Shared athlete and reference selection applies.');selector.currentIndexChanged.connect(self.select_draw_page);line.addWidget(selector);v.addLayout(line)
                for clip in clips:add_plot(v,clip)
                if not clips:v.addWidget(QLabel('No complete clip annotations.'))
            else:add_plot(v,spec)
            v.addStretch();self.grid.addWidget(card,index//2,index%2)
        self.grid.setColumnStretch(0,1);self.grid.setColumnStretch(1,1)
    def select_draw_page(self,index):
        if index>=0 and index!=self.draw_page:self.draw_page=index;self.redraw()

class DetailPlots(QWidget):
    """Charts paired with the existing detailed numeric tables."""
    def __init__(self):super().__init__();self.specs=[];self.column=QVBoxLayout(self);self.column.setContentsMargins(0,0,0,0)
    def set_specs(self,specs):
        self.specs=specs
        while self.column.count():
            item=self.column.takeAt(0)
            if item.widget():
                widget=item.widget();widget.setParent(None);widget.deleteLater()
        dark=self.palette().window().color().lightness()<128
        for spec in specs:
            title=QLabel(spec['title']);title.setObjectName('section');self.column.addWidget(title)
            note=QLabel(spec['note']);note.setObjectName('muted');note.setWordWrap(True);self.column.addWidget(note)
            svg,height,step=svg_chart(spec,dark);self.column.addWidget(ResponsiveChart(svg,height,[row_text(r,spec) for r in spec['rows']],step))
