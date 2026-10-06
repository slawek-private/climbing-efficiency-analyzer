"""Responsive charts for the shared selection, with explicit eligibility per metric."""
from html import escape
from PySide6.QtCore import QByteArray,Qt
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QWidget,QVBoxLayout,QLabel,QScrollArea,QSizePolicy
from .labels import rest_breakdown


class ResponsiveChart(QSvgWidget):
    def __init__(self,svg,height):
        super().__init__();self.load(QByteArray(svg.encode()));self.base_height=height
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed);self.setMaximumWidth(1000)
    def resizeEvent(self,event):
        self.setFixedHeight(max(self.base_height,int(self.width()*self.base_height/900)));super().resizeEvent(event)


class ComparisonCharts(QWidget):
    def __init__(self):
        super().__init__();self.documents=[];self.dark=False;self.checkpoint='Climb start';layout=QVBoxLayout(self)
        note=QLabel('Reference first, then selected attempts. Only matched, closed measurements appear. Unreviewed annotations are provisional; missing is unknown.');note.setWordWrap(True);layout.addWidget(note)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(True);layout.addWidget(self.scroll)
    def set_documents(self,documents):self.documents=documents;self.redraw()
    def redraw(self):
        container=QWidget();column=QVBoxLayout(container);column.setSpacing(14)
        docs=self.documents;names=[f"{d['climber']} · {d['attempt']}" for d in docs]
        def closed(d,kinds):return not any(e['kind'] in kinds for e in d['open_events'])
        def plot(title,values,unit,review):
            heading=QLabel(title);heading.setObjectName('section');column.addWidget(heading)
            items=[(i,v) for i,v in enumerate(values) if v is not None]
            excluded=len(values)-len(items);note=QLabel(f'{len(items)} eligible · {excluded} missing or unfinished. '+review);note.setWordWrap(True);note.setObjectName('muted');column.addWidget(note)
            if not items:return
            ink='#d6e2f4' if self.dark else '#25334a';height=20+len(items)*44;maximum=max([v for _,v in items]+[1])
            svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 {height}">'
            for row,(i,value) in enumerate(items):
                y=12+row*44;bar=510*value/maximum;color='#92c5ff' if self.dark and i==0 else '#245fc4' if i==0 else '#8293a8'
                svg+=f'<text x="0" y="{y+19}" fill="{ink}" font-size="14">{escape(names[i][:26])}</text><rect x="235" y="{y}" width="{bar}" height="26" rx="4" fill="{color}"/><text x="{245+bar}" y="{y+19}" fill="{ink}" font-size="14">{value:.1f}{unit}</text>'
            column.addWidget(ResponsiveChart(svg+'</svg>',height))
        plot('Marked recovery · share of marked climb',[(rest_breakdown(d)['total_marked_rest_share']*100 if rest_breakdown(d)['total_marked_rest_share'] is not None else None) if closed(d,{'rest','chalk'}) else None for d in docs],' %','Rest and chalking overlap once. This is not an efficiency score.')
        if self.checkpoint!='Climb start':
            values=[min([p['point']['seconds']-d['start']['seconds'] for p in d.get('checkpoints',[]) if p['name']==self.checkpoint and d['start'] and p['point']['seconds']>=d['start']['seconds'] and (not d['end'] or p['point']['seconds']<=d['end']['seconds'])],default=None) for d in docs]
            plot('Arrival at '+self.checkpoint,values,' s','Seconds from each marked climb start.')
        draws=sorted({e['target'] for d in docs for e in d['events'] if e['kind']=='clip' and e['target'] is not None})
        for draw in draws:
            values=[]
            for d in docs:
                clips=[e for e in d['events'] if e['kind']=='clip' and e['target']==draw and d['start'] and d['end'] and e['start']['seconds']>=d['start']['seconds'] and e['end']['seconds']<=d['end']['seconds']]
                values.append(clips[0]['end']['seconds']-clips[0]['start']['seconds'] if len(clips)==1 and closed(d,{'clip'}) else None)
            plot(f'Quickdraw {draw} · clip duration',values,' s','One complete clip at this draw within climb boundaries; repeated clips excluded.')
        if not docs:column.addWidget(QLabel('Select attempts on the same route to compare.'))
        column.addStretch();old=self.scroll.takeWidget();self.scroll.setWidget(container)
        if old:old.deleteLater()
