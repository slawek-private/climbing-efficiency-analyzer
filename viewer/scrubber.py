"""Zoomable, PTS-based video ruler. Painting never decodes video."""
import math
from PySide6.QtCore import Qt, Signal, QRectF, QEvent
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget, QToolTip


class PrecisionScrubber(QWidget):
    seek=Signal(float)
    released=Signal()
    zoomChanged=Signal(float)
    def __init__(self):
        super().__init__();self.setMinimumHeight(92);self.setMaximumHeight(92)
        self.duration=1.;self.position=0.;self.document=None;self.dark=False
        self.span=0.;self.center=0.;self.dragging=False;self.panning=False
        self.setMouseTracking(True)
        self.setToolTip('Pinch to zoom · two-finger scroll to pan · double-tap for full video · wheel to zoom')
    def bounds(self):
        span=min(self.duration,self.span) if self.span else self.duration
        span=max(.001,span);a=max(0.,min(self.center-span/2,max(0.,self.duration-span)))
        return a,a+span
    def set_span(self,seconds):
        self.span=max(0.,float(seconds));self.center=self.position;self.update();self.zoomChanged.emit(self.span)
    def sync(self,duration,position,document):
        if abs(duration-self.duration)>.001:self.center=position
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
        minutes=int(seconds//60);return f'{minutes:02d}:{seconds-minutes*60:06.3f}'
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg='#172438' if self.dark else '#f0f4fa';text='#b8c7de' if self.dark else '#52647c'
        p.fillRect(self.rect(),QColor(bg));a,b=self.bounds();span=b-a
        # Select a readable ruler interval, including subsecond ticks when zoomed.
        desired=span/max(2,self.width()/90)
        step=next((v for v in (.1,.2,.5,1,2,5,10,15,30,60,120,300,600) if v>=desired),600)
        t=math.ceil(a/step)*step
        while t<=b:
            x=self.x_at(t);p.setPen(QColor(text));p.drawLine(int(x),29,int(x),43)
            label=self.time_text(t)[:-4] if step>=1 else self.time_text(t)[:-2]
            p.drawText(QRectF(max(0.,min(self.width()-70.,x-35)),5,70,20),Qt.AlignmentFlag.AlignCenter,label)
            for j in range(1,5):
                minor=t+j*step/5
                if minor<b:p.drawLine(int(self.x_at(minor)),36,int(self.x_at(minor)),43)
            t+=step
        p.fillRect(12,46,max(1,self.width()-24),25,QColor('#263b57' if self.dark else '#dce5f1'))
        d=self.document
        if d:
            for e in d['events']:
                x=max(a,e['start']['seconds']);end=min(b,e['end']['seconds'])
                if end<=x:continue
                color={'clip':'#4386f5','rest':'#20ab85','chalk':'#ab7ce7'}.get(e['kind'],'#90a3ba')
                row={'clip':0,'rest':1,'chalk':2}.get(e['kind'],0)
                p.fillRect(int(self.x_at(x)),47+row*8,max(2,int((end-x)/span*(self.width()-24))),7,QColor(color))
            for marker in d.get('checkpoints',[]):
                t=marker['point']['seconds']
                if a<=t<=b:
                    x=int(self.x_at(t));p.setPen(QPen(QColor('#e3a83a'),2));p.drawLine(x,42,x,73)
            for key,word in (('start','START'),('end','END')):
                if d[key] and a<=d[key]['seconds']<=b:
                    x=int(self.x_at(d[key]['seconds']));p.setPen(QColor(('#e8edf4' if self.dark else '#141a24') if key=='start' else '#ec6966'));p.drawLine(x,29,x,73);p.drawText(x+3,86,word)
        if a<=self.position<=b:
            x=int(self.x_at(self.position));p.setPen(QPen(QColor('#ed6964'),2));p.drawLine(x,26,x,74)
            p.setBrush(QColor('#ed6964'));p.drawEllipse(QRectF(x-4,25,8,8))
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.RightButton:
            self.panning=True;self.pan_x=event.position().x();self.pan_center=sum(self.bounds())/2;return
        if event.button()==Qt.MouseButton.LeftButton:
            self.dragging=True;self.seek.emit(self.seconds_at(event.position().x()))
    def mouseMoveEvent(self,event):
        if self.panning:
            a,b=self.bounds();self.center=max(0.,min(self.duration,self.pan_center-(event.position().x()-self.pan_x)/(max(1,self.width()-24))*(b-a)));self.update()
        elif self.dragging:self.seek.emit(self.seconds_at(event.position().x()))
        else:QToolTip.showText(event.globalPosition().toPoint(),self.time_text(self.seconds_at(event.position().x())),self)
    def mouseReleaseEvent(self,event):
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
        if event.type()==QEvent.Type.NativeGesture:
            kind=event.gestureType()
            if kind==Qt.NativeGestureType.ZoomNativeGesture:self.zoom_at(1+event.value(),event.position().x())
            elif kind==Qt.NativeGestureType.SmartZoomNativeGesture:self.set_span(0)
            elif kind not in (Qt.NativeGestureType.BeginNativeGesture,Qt.NativeGestureType.EndNativeGesture):return super().event(event)
            event.accept();return True
        return super().event(event)
    def wheelEvent(self,event):
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
