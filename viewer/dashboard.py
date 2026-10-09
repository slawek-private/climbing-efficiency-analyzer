"""Live local comparison dashboards with selectable athletes."""
from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QPainter,QColor,QBrush
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QTabWidget,QTableWidget,QTableWidgetItem,QAbstractItemView,QComboBox,QScrollArea,QToolTip
from .analytics import patterns,matched_clips,between_clips
from .comparison import rows

class AllocationChart(QWidget):
    def __init__(self):super().__init__();self.data=[];self.setMinimumHeight(220);self.hits=[];self.setMouseTracking(True);self.setAccessibleName('Time allocation: labelled segments and exact values in the table above')
    def paintEvent(self,event):
        self.hits=[];p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);patterns={'rest':Qt.BrushStyle.BDiagPattern,'chalk':Qt.BrushStyle.FDiagPattern,'overlap':Qt.BrushStyle.CrossPattern,'unclassified':Qt.BrushStyle.Dense6Pattern};palette={'clip':'#377deb','rest':'#1d9874','chalk':'#a16cda','overlap':'#e29b3e','unclassified':'#8997ab'};maximum=max([sum(r['allocation'].values()) for r in self.data if r['allocation']]+[1]);width=max(30,self.width()-230)
        for i,r in enumerate(self.data):
            y=20+i*44;p.setPen(self.palette().windowText().color());p.drawText(5,y+18,r['athlete']+' / '+r['attempt']);x=140
            if r['allocation'] is None:p.drawText(x,y+18,'Mark climb start and end');continue
            for key,seconds in r['allocation'].items():
                w=seconds/maximum*width;rect=QRectF(x,y,w,24);p.fillRect(rect,QColor(palette[key]));pattern=patterns.get(key,Qt.BrushStyle.NoBrush)
                if pattern!=Qt.BrushStyle.NoBrush:p.fillRect(rect,QBrush(QColor('#151719'),pattern))
                label=f'{key.capitalize()} {seconds:.1f}s'
                if w>=p.fontMetrics().horizontalAdvance(label)+8:
                    p.setPen(QColor('#ffffff'));label_width=p.fontMetrics().horizontalAdvance(label)+6;p.fillRect(QRectF(x+(w-label_width)/2,y+3,label_width,18),QColor('#20252b'));p.drawText(rect,Qt.AlignmentFlag.AlignCenter,label)
                self.hits.append((rect,f"{r['athlete']} · attempt {r['attempt']} · {key}: {seconds:.3f} s"));x+=w
            p.setPen(self.palette().windowText().color());p.drawText(int(x)+8,y+18,f"{sum(r['allocation'].values()):.2f}s")
        x=5;y=35+len(self.data)*44
        for key,color in palette.items():
            rect=QRectF(x,y,14,14);p.fillRect(rect,QColor(color))
            if key in patterns:p.fillRect(rect,QBrush(QColor('#151719'),patterns[key]))
            p.setPen(self.palette().windowText().color());p.drawText(x+19,y+12,'Rest' if key=='rest' else key.capitalize());x+=max(100,int(self.width()/5))
    def hover_text(self,position):return next((text for rect,text in self.hits if rect.contains(position)),'')
    def mouseMoveEvent(self,event):
        tip=self.hover_text(event.position())
        if tip:QToolTip.showText(event.globalPosition().toPoint(),tip,self)
        else:QToolTip.hideText()

def table():
    t=QTableWidget();t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);t.setAlternatingRowColors(True);t.setShowGrid(False);t.verticalHeader().hide();return t

def fill(t,headers,data):
    t.setColumnCount(len(headers));t.setHorizontalHeaderLabels([h.replace('_',' ').replace('marked','recorded').capitalize() for h in headers]);t.setRowCount(len(data))
    for row,values in enumerate(data):
        for col,v in enumerate(values):t.setItem(row,col,QTableWidgetItem('—' if v is None else f'{v:.2f}' if isinstance(v,float) else str(v)))
    t.resizeColumnsToContents()

class Dashboard(QWidget):
    def __init__(self):
        super().__init__();self.documents=[];layout=QVBoxLayout(self);layout.setContentsMargins(20,16,20,16);title=QLabel('Hand patterns');title.setObjectName('section');layout.addWidget(title)
        line=QHBoxLayout();line.addWidget(QLabel('Compare'));self.first=QComboBox();self.second=QComboBox();line.addWidget(self.first);line.addWidget(self.second);line.addStretch();layout.addLayout(line);self.first.hide();self.second.hide()
        for i in range(line.count()):
            if line.itemAt(i).widget():line.itemAt(i).widget().hide()
        note=QLabel('Observed hand choices, not a score: route geometry and stance affect clipping hand. More alternation or less rest is not automatically better. Missing chalking is unknown, not zero.');note.setWordWrap(True);note.setObjectName('muted');layout.addWidget(note)
        self.tabs=QTabWidget();layout.addWidget(self.tabs,1);self.hands=table();self.recovery=table();self.clips=table();self.point_table=table()
        self.tabs.addTab(self.hands,'Clipping hands');self.tabs.addTab(self.recovery,'Rest && chalk')
        from .charts import DetailPlots
        def paired(t,title):
            scroll=QScrollArea();scroll.setWidgetResizable(True);page=QWidget();v=QVBoxLayout(page);t.setFixedHeight(220);v.addWidget(t);plots=DetailPlots();v.addWidget(plots);v.addStretch();scroll.setWidget(page);self.tabs.addTab(scroll,title);return plots,v
        self.clip_plots,clip_layout=paired(self.clips,'Same quickdraw');self.draw_selector=QComboBox();clip_layout.insertWidget(1,self.draw_selector);self.draw_selector.currentIndexChanged.connect(self.render_clip_plots)
        self.point_plots,_=paired(self.point_table,'Same point');self.checkpoint='Climb start'
        self.split_table=table();self.split_plots,_=paired(self.split_table,'Between clips')
        page=QWidget();v=QVBoxLayout(page);self.chart=AllocationChart();self.allocation_table=table();v.addWidget(self.allocation_table,1);v.addWidget(self.chart);n=QLabel('Chalking contributes to total rest while remaining a separate band. Unclassified time can include movement, reading, hesitation or unmarked activity. Overlaps occupy a separate band so time is never counted twice.');n.setWordWrap(True);v.addWidget(n);self.tabs.addTab(page,'Time allocation')
        self.foot_table=table();self.foot_plots,foot_layout=paired(self.foot_table,'Footwork');self.foot_timelines=QWidget();self.foot_column=QVBoxLayout(self.foot_timelines);foot_layout.insertWidget(2,self.foot_timelines)
        self.first.currentIndexChanged.connect(self.render);self.second.currentIndexChanged.connect(self.render)
    def update_documents(self,documents):
        self.documents=documents
        for selector in (self.first,self.second):
            previous=selector.currentData();selector.blockSignals(True);selector.clear();selector.addItem('All measured athletes',None)
            for i,d in enumerate(documents):selector.addItem(d['climber']+' / '+d['attempt'],i)
            index=selector.findData(previous);selector.setCurrentIndex(max(0,index));selector.blockSignals(False)
        self.render()
    def render(self):
        selected={s.currentData() for s in (self.first,self.second) if s.currentData() is not None};documents=[d for i,d in enumerate(self.documents) if not selected or i in selected];self.active_documents=documents;data=[patterns(d) for d in documents]
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

        from .reporting import records,chart_specs,split_specs
        presentation=records(documents);self.draw_selector.blockSignals(True);previous=self.draw_selector.currentData();self.draw_selector.clear();draws=sorted({n for r in presentation for n in r['clips']},key=float)
        for i in range(0,len(draws),4):self.draw_selector.addItem('Quickdraws '+', '.join(draws[i:i+4]),i//4)
        self.draw_selector.setCurrentIndex(max(0,self.draw_selector.findData(previous)));self.draw_selector.blockSignals(False)
        from .footwork import observations
        from .reporting import footwork_timeline
        from PySide6.QtSvgWidgets import QSvgWidget
        from PySide6.QtCore import QByteArray
        foot_rows=[]
        while self.foot_column.count():
            item=self.foot_column.takeAt(0);widget=item.widget()
            if widget:widget.setParent(None);widget.deleteLater()
        for d in documents:
            for e in observations(d):
                if e['kind'] in ('slip','both_off','foot_release'):foot_rows.append([d['climber']+' · '+d['attempt'],e['label'],e['limb'],e['status'],e['intent'],e['start']['frame'],e['start']['seconds']-d['start']['seconds'] if d['start'] else None])
            label=QLabel(d['climber']+' · '+d['attempt']);label.setObjectName('section');self.foot_column.addWidget(label)
            svg=footwork_timeline(d,self.palette().window().color().lightness()<128)
            if svg.startswith('<svg'):
                timeline=QSvgWidget();timeline.load(QByteArray(svg.encode()));timeline.setFixedHeight(160);timeline.setToolTip('Seconds from climb start. Solid: checked; hatch: hidden; pale: unreviewed. Filled: confirmed; outline: candidate; circle: intentional. Exact source frames are in the table.');self.foot_column.addWidget(timeline)
            else:self.foot_column.addWidget(QLabel('Climb boundaries missing.'))
        fill(self.foot_table,['Athlete / attempt','Observation','Limb','Review','Intent','Source frame','Climb seconds'],foot_rows)
        self.foot_plots.set_specs([])
        self.render_clip_plots();self.point_plots.set_specs([chart_specs(presentation,self.checkpoint)[0]]);self.split_plots.set_specs(split_specs(documents))
    def render_clip_plots(self,*_):
        from .reporting import records,chart_specs
        presentation=records(getattr(self,'active_documents',self.documents));draws=sorted({n for r in presentation for n in r['clips']},key=float);page=self.draw_selector.currentData() or 0
        self.clip_plots.set_specs(chart_specs(presentation,self.checkpoint,draws[page*4:page*4+4])[1])
