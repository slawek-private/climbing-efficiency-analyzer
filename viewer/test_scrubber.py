from types import SimpleNamespace
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from viewer.scrubber import PrecisionScrubber
from viewer.simple import Window


def test_zoom_scrub_release_and_pan():
    app=QApplication.instance() or QApplication([])
    w=PrecisionScrubber();w.resize(824,102);w.sync(240,120,None);w.set_span(1)
    assert w.bounds()==(119.5,120.5)
    assert abs(w.seconds_at(412)-120)<1e-9
    values=[];released=[];w.seek.connect(values.append);w.released.connect(lambda:released.append(True))
    w.show();app.processEvents()
    QTest.mousePress(w,Qt.MouseButton.LeftButton,pos=QPoint(412,55))
    QTest.mouseRelease(w,Qt.MouseButton.LeftButton,pos=QPoint(812,55))
    assert values[-1]==120.5 and released==[True] and not w.dragging
    QTest.mousePress(w,Qt.MouseButton.RightButton,pos=QPoint(412,55))
    QTest.mouseMove(w,QPoint(612,55));QTest.mouseRelease(w,Qt.MouseButton.RightButton,pos=QPoint(612,55))
    assert w.bounds()[0]<119.5
    w.position=0;w.set_span(1);assert w.bounds()==(0,1)
    w.position=240;w.set_span(1);assert w.bounds()==(239,240)
    w.set_span(0);assert w.bounds()==(0,240)
    w.close()


def test_scrubbing_snaps_to_nearest_vfr_timestamp():
    values=[]
    fake=SimpleNamespace(reader=SimpleNamespace(times=[0,.04,.1,.17,.25]),slider_changed=values.append)
    for value in (-1,.08,.169,99):Window.scrub_seconds(fake,value)
    assert values==[0,2,3,4]
