"""Zoomable, PTS-based video ruler. Painting never decodes video."""
import math
from PySide6.QtCore import Qt, Signal, QRectF, QEvent,QPointF
from PySide6.QtGui import QColor, QPainter, QPen,QPolygonF,QBrush
from PySide6.QtWidgets import QWidget, QToolTip


class PrecisionScrubber(QWidget):
    seek=Signal(float)
    released=Signal()
    zoomChanged=Signal(float)
    observationSelected=Signal(str)
    def __init__(self,read_only=False):
        super().__init__();self.setMinimumHeight(92);self.setMaximumHeight(92)
        self.read_only=read_only;self.view_range=None;self.time_origin=0.;self.event_hits=[];self.playhead_rect=QRectF();self.duration=1.;self.position=0.;self.document=None;self.dark=False
        self.span=0.;self.center=0.;self.dragging=False;self.panning=False;self.foot_hits=[]
        self.setMouseTracking(True)
        self.setAccessibleName('Read-only event timeline' if read_only else 'Video event timeline');self.setToolTip('Read-only labels · hover for activity, hand and time · use the shared slider to move all videos' if read_only else 'Pinch to zoom · two-finger scroll to pan · double-tap for full video · wheel to zoom · hover labels for details')
    def bounds(self):
        if self.view_range is not None:return self.view_range
        span=min(self.duration,self.span) if self.span else self.duration
        span=max(.001,span);a=max(0.,min(self.center-span/2,max(0.,self.duration-span)))
        return a,a+span
    def set_span(self,seconds):
        self.span=max(0.,float(seconds));self.center=self.position;self.update();self.zoomChanged.emit(self.span)
    def sync(self,duration,position,document):
        if abs(duration-self.duration)>.001:self.center=position
        height=118 if document and document.get("footwork") else 92
        self.setMinimumHeight(height);self.setMaximumHeight(height)
        self.duration=max(.001,duration);self.position=position;self.document=document
        a,b=self.bounds()
        if not self.dragging and not self.panning and not a<=position<=b:self.center=position
        self.update()
    def seconds_at(self,x):
        a,b=self.bounds();return a+max(0.,min(1.,(x-12)/max(1,self.width()-24)))*(b-a)
    def x_at(self,seconds):
        a,b=self.bounds();return 12+(seconds-a)/(b-a)*max(1,self.width()-24)
    @staticmethod
    def time_text(seconds):
        sign='−' if seconds<0 else '';seconds=abs(seconds);minutes=int(seconds//60);return sign+f'{minutes:02d}:{seconds-minutes*60:06.3f}'
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg='#202326' if self.dark else '#f4f5f6';text='#b2b8bf' if self.dark else '#59616b'
        p.fillRect(self.rect(),QColor(bg));a,b=self.bounds();span=b-a
        # Select a readable ruler interval, including subsecond ticks when zoomed.
        desired=span/max(2,self.width()/90)
        step=next((v for v in (.1,.2,.5,1,2,5,10,15,30,60,120,300,600) if v>=desired),600)
        t=math.ceil((a-self.time_origin)/step)*step+self.time_origin
        while t<=b:
            x=self.x_at(t);p.setPen(QColor(text));p.drawLine(int(x),29,int(x),43)
            label=self.time_text(t-self.time_origin)[:-4] if step>=1 else self.time_text(t-self.time_origin)[:-2]
            p.drawText(QRectF(max(0.,min(self.width()-70.,x-35)),5,70,20),Qt.AlignmentFlag.AlignCenter,label)
            for j in range(1,5):
                minor=t+j*step/5
                if minor<b:p.drawLine(int(self.x_at(minor)),36,int(self.x_at(minor)),43)
            t+=step
        p.fillRect(12,46,max(1,self.width()-24),25,QColor('#383e45' if self.dark else '#e5e7eb'))
        d=self.document;self.foot_hits=[];self.event_hits=[];self.playhead_rect=QRectF()
        p.setPen(QColor(text));p.drawText(12,86,'Hands · clip / rest / chalk')
        if d:
            for e in d['events']:
                x=max(a,e['start']['seconds']);end=min(b,e['end']['seconds'])
                if end<=x:continue
                color={'clip':'#4386f5','rest':'#20ab85','chalk':'#ab7ce7'}.get(e['kind'],'#90a3ba')
                row={'clip':0,'rest':1,'chalk':2}.get(e['kind'],0)
                rect=QRectF(self.x_at(x),47+row*8,max(2,(end-x)/span*(self.width()-24)),7);p.fillRect(rect,QColor(color))
                pattern=Qt.BrushStyle.BDiagPattern if e['kind']=='rest' else Qt.BrushStyle.FDiagPattern if e['kind']=='chalk' else Qt.BrushStyle.NoBrush
                if pattern!=Qt.BrushStyle.NoBrush:p.fillRect(rect,QBrush(QColor('#20252b'),pattern))
                self.event_hits.append((rect.adjusted(0,-2,0,2),e))
            track=d.get('footwork')
            if track:
                p.setPen(QColor(text));p.drawText(12,113,'Feet · reviewed / obscured / off / slip')
                p.fillRect(12,89,max(1,self.width()-24),12,QColor('#383e45' if self.dark else '#e5e7eb'))
                for c in track['coverage']:
                    x,end=max(a,c['start']['seconds']),min(b,c['end']['seconds'])
                    if end<=x:continue
                    rect=QRectF(self.x_at(x),89,max(2,(end-x)/span*(self.width()-24)),12)
                    p.fillRect(rect,QColor('#117451' if c['state']=='reviewed' else '#727c87'))
                    if c['state']=='obscured':
                        p.save();p.setClipRect(rect);p.setPen(QColor('#e5e7eb'))
                        for xx in range(int(rect.left())-12,int(rect.right())+12,8):p.drawLine(xx,89,xx+12,101)
                        p.restore()
                for e in track['events']:
                    x,end=max(a,e['start']['seconds']),min(b,(e.get('end') or e['start'])['seconds'])
                    if e['end'] and end<=x or not e['end'] and not a<=e['start']['seconds']<=b:continue
                    rect=QRectF(self.x_at(x)-3,87,max(6,(end-x)/span*(self.width()-24)),16)
                    color='#a16b09' if e['intent']=='intentional' else '#df664e'
                    p.setPen(QPen(QColor(color),2));p.setBrush(QColor(color) if e['status']=='confirmed' else Qt.BrushStyle.NoBrush);
                    if e['end']:p.drawRect(rect)
                    self.foot_hits.append((rect,e))
                    # Intent has a shape cue as well as a colour: circles deliberate, triangles unplanned/unclear.
                    if not e['end']:
                        if e['intent']=='intentional':p.drawEllipse(rect)
                        else:p.drawPolygon(QPolygonF([QPointF(rect.center().x(),rect.top()),rect.bottomLeft(),rect.bottomRight()]))
            for marker in d.get('checkpoints',[]):
                t=marker['point']['seconds']
                if a<=t<=b:
                    x=int(self.x_at(t));p.setPen(QPen(QColor('#e3a83a'),2));p.drawLine(x,42,x,73)
            for key,word in (('start','START'),('end','END')):
                if d[key] and a<=d[key]['seconds']<=b:
                    x=int(self.x_at(d[key]['seconds']));p.setPen(QColor(('#e8edf4' if self.dark else '#141a24') if key=='start' else '#ec6966'));p.drawLine(x,29,x,73);p.drawText(x+3,42,word)
        if a<=self.position<=b:
            x=int(self.x_at(self.position));halo=QColor('#f3f4f5' if self.dark else '#151719');gold=QColor('#ffd447')
            p.setPen(QPen(halo,6));p.drawLine(x,26,x,self.height()-5);p.setPen(QPen(gold,3));p.drawLine(x,26,x,self.height()-5)
            p.setPen(QPen(halo,2));p.setBrush(gold);p.drawPolygon(QPolygonF([QPointF(x-7,25),QPointF(x+7,25),QPointF(x,34)]))
            text='NOW '+self.time_text(self.position-self.time_origin);font=p.font();font.setBold(True);font.setPixelSize(11);p.setFont(font);width=p.fontMetrics().horizontalAdvance(text)+12
            self.playhead_rect=QRectF(max(1,min(self.width()-width-1,x-width/2)),1,width,22);p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#151719'));p.drawRoundedRect(self.playhead_rect,4,4);p.setPen(QColor('#ffffff'));p.drawText(self.playhead_rect,Qt.AlignmentFlag.AlignCenter,text)
    def hover_text(self,position):
        if self.playhead_rect.contains(position):return 'Current video time · '+self.time_text(self.position)+' · gold line marks the displayed frame'
        selected=next((e for r,e in self.foot_hits+self.event_hits if r.contains(position)),None)
        if selected:
            name={'clip':'Clip','rest':'Rest','chalk':'Chalk','contact':'Hold contact','offwall':'Hand away','slip':'Foot slip','foot_release':'Intentional foot release','both_off':'Both feet off'}[selected['kind']];limb=selected.get('hand',selected.get('limb',''))
            end=selected.get('end');duration=f" · {end['seconds']-selected['start']['seconds']:.3f} s" if end else ''
            return f"{limb.capitalize()} · {name} · video {selected['start']['seconds']:.3f} s"+duration+' · '+selected.get('intent','')+' '+selected.get('status','')
        d=self.document or {}
        for c in d.get('footwork',{}).get('coverage',[]):
            if 89<=position.y()<=101 and c['start']['seconds']<=self.seconds_at(position.x())<=c['end']['seconds']:return ('Both feet visible and checked' if c['state']=='reviewed' else 'Feet hidden · unknown')+f" · {c['start']['seconds']:.3f}–{c['end']['seconds']:.3f} s"
        return self.time_text(self.seconds_at(position.x())-self.time_origin)+(' from alignment · viewing only' if self.read_only else ' · drag to seek')
    def mousePressEvent(self,event):
        if self.read_only:event.accept();return
        if event.button()==Qt.MouseButton.RightButton:
            self.panning=True;self.pan_x=event.position().x();self.pan_center=sum(self.bounds())/2;return
        if event.button()==Qt.MouseButton.LeftButton:
            for rect,observation in self.foot_hits:
                if rect.contains(event.position()):self.observationSelected.emit(observation["id"])
            self.dragging=True;self.seek.emit(self.seconds_at(event.position().x()))
    def mouseMoveEvent(self,event):
        if self.panning:
            a,b=self.bounds();self.center=max(0.,min(self.duration,self.pan_center-(event.position().x()-self.pan_x)/(max(1,self.width()-24))*(b-a)));self.update()
        elif self.dragging:self.seek.emit(self.seconds_at(event.position().x()))
        else:
            QToolTip.showText(event.globalPosition().toPoint(),self.hover_text(event.position()),self)
    def mouseReleaseEvent(self,event):
        if self.read_only:event.accept();return
        if self.dragging:
            self.seek.emit(self.seconds_at(event.position().x()));self.dragging=False;self.released.emit()
        self.panning=False
    def zoom_at(self,factor,x):
        if factor<=0 or factor==1:return
        a,b=self.bounds();anchor=self.seconds_at(x);fraction=(anchor-a)/(b-a)
        span=max(min(.5,self.duration),min(self.duration,(b-a)/factor))
        self.span=span;self.center=anchor+(0.5-fraction)*span
        self.update();self.zoomChanged.emit(span)
    def event(self,event):
        if self.read_only and event.type()==QEvent.Type.NativeGesture:event.accept();return True
        if event.type()==QEvent.Type.NativeGesture:
            kind=event.gestureType()
            if kind==Qt.NativeGestureType.ZoomNativeGesture:self.zoom_at(1+event.value(),event.position().x())
            elif kind==Qt.NativeGestureType.SmartZoomNativeGesture:self.set_span(0)
            elif kind not in (Qt.NativeGestureType.BeginNativeGesture,Qt.NativeGestureType.EndNativeGesture):return super().event(event)
            event.accept();return True
        return super().event(event)
    def wheelEvent(self,event):
        if self.read_only:event.accept();return
        a,b=self.bounds();pixels=event.pixelDelta()
        if not pixels.isNull() and not event.modifiers()&Qt.KeyboardModifier.ControlModifier:
            distance=pixels.x() if pixels.x() else pixels.y()
            self.center=max(0.,min(self.duration,(a+b)/2-distance/max(1,self.width()-24)*(b-a)))
            self.update()
        elif event.modifiers()&Qt.KeyboardModifier.ShiftModifier:
            self.center=max(0.,min(self.duration,(a+b)/2-event.angleDelta().y()/120*(b-a)*.15));self.update()
        else:
            amount=pixels.y()/100 if not pixels.isNull() else event.angleDelta().y()/120
            self.zoom_at((1/.75)**max(-10,min(10,amount)),event.position().x())
        event.accept()
