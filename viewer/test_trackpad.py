"""Synthetic macOS-style Qt input; no real footage or Mac required."""
import numpy as np
import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QNativeGestureEvent, QPointingDevice, QWheelEvent
from PySide6.QtWidgets import QApplication
from viewer.app import ImageView
from viewer.scrubber import PrecisionScrubber


def gesture(kind, value=0., position=QPointF(412,55)):
    return QNativeGestureEvent(kind,QPointingDevice.primaryPointingDevice(),2,
                              position,position,position,value,QPointF())


def wheel(pixels=QPoint(),angles=QPoint(),modifiers=Qt.KeyboardModifier.NoModifier):
    return QWheelEvent(QPointF(412,55),QPointF(412,55),pixels,angles,
                      Qt.MouseButton.NoButton,modifiers,Qt.ScrollPhase.ScrollUpdate,False)


def test_timeline_native_pinch_anchor_pan_and_reset():
    app=QApplication.instance() or QApplication([])
    w=PrecisionScrubber();w.resize(824,102);w.sync(240,120,None);w.set_span(60)
    seeks=[];w.seek.connect(seeks.append)
    anchor=w.seconds_at(212)
    QApplication.sendEvent(w,gesture(Qt.NativeGestureType.ZoomNativeGesture,.25,QPointF(212,55)))
    assert w.span==pytest.approx(48)
    assert w.seconds_at(212)==pytest.approx(anchor)
    QApplication.sendEvent(w,gesture(Qt.NativeGestureType.ZoomNativeGesture,-.2,QPointF(212,55)))
    assert w.span==pytest.approx(60)
    before=w.bounds();QApplication.sendEvent(w,wheel(QPoint(80,0)))
    assert w.bounds()[0]<before[0] and w.span==pytest.approx(60)
    QApplication.sendEvent(w,wheel());assert w.span==pytest.approx(60)
    QApplication.sendEvent(w,wheel(QPoint(0,25),modifiers=Qt.KeyboardModifier.ControlModifier))
    assert w.span<60
    QApplication.sendEvent(w,gesture(Qt.NativeGestureType.SmartZoomNativeGesture))
    assert w.bounds()==(0,240) and not seeks
    w.close()


def test_video_native_pinch_pixel_pan_and_zero_scroll():
    app=QApplication.instance() or QApplication([])
    w=ImageView();w.resize(824,500);w.show()
    w.display(np.zeros((1200,1600,3),dtype=np.uint8));app.processEvents()
    initial=w.transform().m11()
    QApplication.sendEvent(w.viewport(),gesture(Qt.NativeGestureType.ZoomNativeGesture,1.))
    assert w.transform().m11()==pytest.approx(initial*2) and not w.auto_fit
    QApplication.sendEvent(w.viewport(),wheel());assert w.transform().m11()==pytest.approx(initial*2)
    scroll=w.horizontalScrollBar().value()
    QApplication.sendEvent(w.viewport(),wheel(QPoint(20,0)))
    assert w.horizontalScrollBar().value()<scroll
    assert w.transform().m11()==pytest.approx(initial*2)
    QApplication.sendEvent(w.viewport(),wheel(angles=QPoint(0,120)))
    assert w.transform().m11()==pytest.approx(initial*2*1.2)
    QApplication.sendEvent(w.viewport(),gesture(Qt.NativeGestureType.SmartZoomNativeGesture))
    assert w.auto_fit and w.transform().m11()==pytest.approx(initial)
    w.close()
