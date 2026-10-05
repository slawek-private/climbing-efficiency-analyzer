"""Compact event timeline with quickdraw labels and exact-frame navigation."""
from PySide6.QtCore import Signal,Qt
from PySide6.QtGui import QPainter,QColor,QPen
from PySide6.QtWidgets import QWidget,QToolTip

class EventTimeline(QWidget):
    seek=Signal(float)
    selected=Signal(str)
    def __init__(self):
        super().__init__();self.setMinimumHeight(145);self.setMaximumHeight(145);self.document=None;self.position=0;self.duration=1;self.dark=False;self.hits=[];self.setMouseTracking(True)
    def bounds(self):
        d=self.document
        return (d['start']['seconds'] if d and d['start'] else 0,d['end']['seconds'] if d and d['end'] else max(self.duration,1))
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);a,b=self.bounds();span=max(.001,b-a);width=max(1,self.width()-78);self.hits=[]
        text='#c9d6eb' if self.dark else '#65748b';track='#243349' if self.dark else '#edf2f8';p.setPen(QColor(text))
        for row,(kind,hand,title) in enumerate([('clip','left','Clip L'),('clip','right','Clip R'),('rest','left','Rest L'),('rest','right','Rest R'),('chalk','left','Chalk L'),('chalk','right','Chalk R')]):
            y=7+row*20;p.setPen(QColor(text));p.drawText(0,y+13,title);p.fillRect(66,y,width,16,QColor(track))
            if not self.document:continue
            for e in self.document['events']:
                if e['kind']!=kind or e['hand'] not in (hand,'none'):continue
                start=max(a,e['start']['seconds']);end=min(b,e['end']['seconds'])
                if end<=start:continue
                x=66+(start-a)/span*width;w=max(3,(end-start)/span*width);p.fillRect(int(x),y,int(w),16,QColor('#377deb' if kind=='clip' else '#a16cda' if kind=='chalk' else '#1d9874'));p.setPen(QColor('white'))
                if kind=='clip':p.drawText(int(x)+2,y+12,'#'+str(e['target'] or '?')+{'mouth':' M','direct':' D'}.get(e.get('clip_method'),''))
                self.hits.append((x,y,w,e))
        if self.document:
            for point in self.document.get('checkpoints',[]):
                t=point['point']['seconds']
                if a<=t<=b:
                    x=66+(t-a)/span*width;p.setPen(QPen(QColor('#d18a2c'),1,Qt.PenStyle.DashLine));p.drawLine(int(x),2,int(x),126)
        x=66+(self.position-a)/span*width
        if 66<=x<=66+width:p.setPen(QPen(QColor('#f06a63'),2));p.drawLine(int(x),0,int(x),127)
        p.setPen(QColor(text));p.drawText(66,142,'0 s' if self.document and self.document['start'] else f'{a:.1f} s');p.drawText(max(66,self.width()-75),142,f'{span:.1f} s')
    def mousePressEvent(self,event):
        x,y=event.position().x(),event.position().y()
        for left,top,width,e in self.hits:
            if left<=x<=left+width and top<=y<=top+16:self.selected.emit(e["id"]);return
        a,b=self.bounds();self.seek.emit(a+max(0,min(1,(event.position().x()-66)/max(1,self.width()-78)))*(b-a))
    def mouseMoveEvent(self,event):
        x,y=event.position().x(),event.position().y()
        for left,top,width,e in self.hits:
            if left<=x<=left+width and top<=y<=top+16:
                base=self.document['start']['seconds'] if self.document['start'] else 0
                QToolTip.showText(event.globalPosition().toPoint(),f"{e['hand']} {e['kind']} · quickdraw {e['target'] or '—'}\n{e['start']['seconds']-base:.2f}–{e['end']['seconds']-base:.2f} s · duration {e['end']['seconds']-e['start']['seconds']:.2f} s",self);return
        QToolTip.hideText()
