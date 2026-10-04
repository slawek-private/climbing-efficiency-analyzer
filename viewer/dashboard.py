"""Live local comparison dashboards with selectable athletes."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter,QColor
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QTabWidget,QTableWidget,QTableWidgetItem,QAbstractItemView,QComboBox,QScrollArea
from .analytics import patterns,matched_clips,between_clips
from .comparison import rows

class AllocationChart(QWidget):
    def __init__(self):super().__init__();self.data=[];self.setMinimumHeight(220)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);palette={'clip':'#377deb','rest':'#1d9874','chalk':'#a16cda','overlap':'#e29b3e','unclassified':'#8997ab'};maximum=max([sum(r['allocation'].values()) for r in self.data if r['allocation']]+[1]);width=max(30,self.width()-230)
        for i,r in enumerate(self.data):
            y=20+i*44;p.setPen(self.palette().windowText().color());p.drawText(5,y+18,r['athlete']+' / '+r['attempt']);x=140
            if r['allocation'] is None:p.drawText(x,y+18,'Mark climb start and end');continue
            for key,seconds in r['allocation'].items():
                w=seconds/maximum*width;p.fillRect(int(x),y,int(w),24,QColor(palette[key]));x+=w
            p.setPen(self.palette().windowText().color());p.drawText(int(x)+8,y+18,f"{sum(r['allocation'].values()):.2f}s")
        x=5;y=35+len(self.data)*44
        for key,color in palette.items():p.fillRect(x,y,10,10,QColor(color));p.setPen(self.palette().windowText().color());p.drawText(x+15,y+10,'Dedicated rest' if key=='rest' else key.capitalize());x+=max(100,int(self.width()/5))

def table():
    t=QTableWidget();t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);t.setAlternatingRowColors(True);t.setShowGrid(False);t.verticalHeader().hide();return t

def fill(t,headers,data):
    t.setColumnCount(len(headers));t.setHorizontalHeaderLabels(headers);t.setRowCount(len(data))
    for row,values in enumerate(data):
        for col,v in enumerate(values):t.setItem(row,col,QTableWidgetItem('Unmarked' if v is None else f'{v:.2f}' if isinstance(v,float) else str(v)))
    t.resizeColumnsToContents()

class Dashboard(QWidget):
    def __init__(self):
        super().__init__();self.documents=[];layout=QVBoxLayout(self);layout.setContentsMargins(20,16,20,16);title=QLabel('Hand patterns & efficiency');title.setObjectName('brand');layout.addWidget(title)
        line=QHBoxLayout();line.addWidget(QLabel('Compare'));self.first=QComboBox();self.second=QComboBox();line.addWidget(self.first);line.addWidget(self.second);line.addStretch();layout.addLayout(line)
        note=QLabel('Observed hand choices, not a score: route geometry and stance affect clipping hand. More alternation or less rest is not automatically better. Missing chalking is unknown, not zero.');note.setWordWrap(True);note.setObjectName('muted');layout.addWidget(note)
        self.tabs=QTabWidget();layout.addWidget(self.tabs,1);self.hands=table();self.recovery=table();self.clips=table();self.point_table=table()
        self.tabs.addTab(self.hands,'Clipping hands');self.tabs.addTab(self.recovery,'Rest & chalk');self.tabs.addTab(self.clips,'Same quickdraw');self.tabs.addTab(self.point_table,'Same point');self.split_table=table();self.tabs.addTab(self.split_table,'Between clips')
        page=QWidget();v=QVBoxLayout(page);self.chart=AllocationChart();v.addWidget(self.chart);self.allocation_table=table();v.addWidget(self.allocation_table,1);n=QLabel('Chalking contributes to total rest while remaining a separate band. Unclassified time can include movement, reading, hesitation or unmarked activity. Overlaps occupy a separate band so time is never counted twice.');n.setWordWrap(True);v.addWidget(n);self.tabs.addTab(page,'Time allocation')
        self.first.currentIndexChanged.connect(self.render);self.second.currentIndexChanged.connect(self.render)
    def update_documents(self,documents):
        self.documents=documents
        for selector in (self.first,self.second):
            previous=selector.currentData();selector.blockSignals(True);selector.clear();selector.addItem('All measured athletes',None)
            for i,d in enumerate(documents):selector.addItem(d['climber']+' / '+d['attempt'],i)
            index=selector.findData(previous);selector.setCurrentIndex(max(0,index));selector.blockSignals(False)
        self.render()
    def render(self):
        selected={s.currentData() for s in (self.first,self.second) if s.currentData() is not None};documents=[d for i,d in enumerate(self.documents) if not selected or i in selected];data=[patterns(d) for d in documents]
        keys=['athlete','attempt','clip_sequence','clip_hand_switches','observed_transitions','longest_same_hand_clip_run','left_clip_count','right_clip_count','left_clip_mean_seconds','right_clip_mean_seconds','left_clip_median_seconds','right_clip_median_seconds','unfinished_timers']
        fill(self.hands,[k.replace('_',' ') for k in keys],[[r[k] for k in keys] for r in data])
        keys=['athlete','attempt','total_rest_marked_seconds','total_rest_marked_count','total_marked_rest_share']+[h+'_'+k+'_'+v for k in ('rest','chalk') for h in ('left','right') for v in ('count','seconds','mean_seconds')]
        fill(self.recovery,[k.replace('_',' ') for k in keys],[[r[k] for k in keys] for r in data])
        clips=matched_clips(documents);draws=sorted({r['quickdraw'] for r in clips});headers=['Quickdraw']+[d['climber']+' · hand / clip s / completion s' for d in documents];matrix=[]
        for draw in draws:
            row=[draw]
            for d in documents:
                matching=[r for r in clips if r['quickdraw']==draw and r['video']==d['source']['file'] and r['attempt']==d['attempt'] and r['athlete']==d['climber']]
                row.append(' ; '.join(f"{r['hand']} / {r['duration_seconds']:.2f} / "+(f"{r['end_from_climb_seconds']:.2f}" if r['end_from_climb_seconds'] is not None else 'start missing') for r in matching) or None)
            matrix.append(row)
        fill(self.clips,headers,matrix)
        points=rows(documents)[1];names=sorted({p['point'] for p in points});fill(self.point_table,['Point']+[d['climber']+' · arrival s' for d in documents],[[name]+[' / '.join(f"{p['seconds_from_climb_start']:.2f}" for p in points if p['point']==name and p['athlete']==d['climber'] and p['attempt']==d['attempt'] and p['video']==d['source']['file'] and p['seconds_from_climb_start'] is not None) or None for d in documents] for name in names])
        splits=between_clips(documents);keys=['athlete','from_quickdraw','to_quickdraw','gap_seconds','completion_to_completion_seconds','next_clip_duration_seconds','dedicated_rest_in_gap_seconds','chalk_in_gap_seconds','total_marked_rest_in_gap_seconds','gap_outside_marked_rest_seconds','status'];fill(self.split_table,[k.replace('_',' ') for k in keys],[[r[k] for k in keys] for r in splits])
        self.chart.data=data;self.chart.setMinimumHeight(max(220,80+len(data)*44));self.chart.update();keys=['clip','rest','chalk','overlap','unclassified'];fill(self.allocation_table,['Athlete']+[k+' (s)' for k in keys],[[r['athlete']]+[r['allocation'][k] if r['allocation'] and (k not in ('clip','rest','chalk') or r[k+'_labelled']) else None for k in keys] for r in data])
