import time
from fractions import Fraction
import av,numpy as np
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from viewer.simple import Window
from viewer.workspace import Workspace
from viewer.video import index_video
from viewer.labels import load,save

def seed_assignment(w):
    import copy
    from viewer import identity
    data=w.workspace.organisation
    if not data['athletes']:identity.athlete(data,'Synthetic athlete')
    if not data['sessions']:identity.session(data,'Training',day='2026-10-07')
    if not data['routes']:identity.route(data,'Test route','version 1')
    d=copy.deepcopy(w.document());identity.assign(d,data,data['athletes'][0]['id'],data['sessions'][0]['id'],data['routes'][0]['id']);w.commit(d)

def wait_until(app,predicate,timeout=4):
    deadline=time.monotonic()+timeout
    while not predicate() and time.monotonic()<deadline:app.processEvents();time.sleep(.005)
    assert predicate()

def test_real_play_button_end_replay_and_confirmed_reset(tmp_path,monkeypatch):
    import viewer.simple as simple
    monkeypatch.setattr(simple,'ROOT',tmp_path)
    path=tmp_path/'playback.mkv'
    with av.open(str(path),'w') as output:
        stream=output.add_stream('ffv1',rate=25);stream.width=32;stream.height=32;stream.pix_fmt='yuv420p'
        for n in range(20):
            frame=av.VideoFrame.from_ndarray(np.full((32,32,3),n*11,dtype=np.uint8),format='rgb24');frame.pts=n*40;frame.time_base=Fraction(1,1000)
            for packet in stream.encode(frame):output.mux(packet)
        for packet in stream.encode():output.mux(packet)
    app=QApplication.instance() or QApplication([]);w=Window();w.workspace=Workspace(tmp_path/'workspace.json');w.video_path=path;w.index_ready(index_video(path));w.show()
    wait_until(app,lambda:w.decode_future is None)
    QTest.mouseClick(w.play_button,Qt.MouseButton.LeftButton);wait_until(app,lambda:w.frame_number>=3)
    QTest.mouseClick(w.play_button,Qt.MouseButton.LeftButton);assert not w.playing
    paused=w.frame_number;QTest.qWait(100);assert w.frame_number==paused
    QTest.mouseClick(w.play_button,Qt.MouseButton.LeftButton);wait_until(app,lambda:w.frame_number==19 and not w.playing)
    QTest.mouseClick(w.play_button,Qt.MouseButton.LeftButton);wait_until(app,lambda:w.playing and w.frame_number<19)
    w.pause();wait_until(app,lambda:w.decode_future is None)
    w.show_frame(0);wait_until(app,lambda:w.decode_future is None);seed_assignment(w);w.set_start();w.show_frame(5);wait_until(app,lambda:w.decode_future is None);w.point_name.setText('A');w.add_point();w.show_frame(10);wait_until(app,lambda:w.decode_future is None);monkeypatch.setattr(w,'choose_climb_outcome',lambda:'failed');w.set_failure()
    assert w.document()['outcome']=='failed'
    end=w.document()['end'].copy()
    monkeypatch.setattr(w,'choose_climb_outcome',lambda:'completed');w.edit_climb_outcome()
    assert w.document()['outcome']=='completed' and w.document()['end']==end
    monkeypatch.setattr(w,'choose_climb_outcome',lambda:None);before=w.document().copy();w.set_failure()
    assert w.document()==before
    w.clear_boundary('end');assert w.document()['outcome']=='unknown' and w.document()['end'] is None
    monkeypatch.setattr(w,'choose_climb_outcome',lambda:'failed');w.set_failure()
    import copy
    from viewer.labels import make_event
    doc=copy.deepcopy(w.document());doc['events'].append(make_event({'kind':'rest','hand':'none','target':None,'start':w.reader.point(5),'confidence':1,'notes':''},w.reader.point(10)));w.commit(doc)
    label_path=tmp_path/'saved.labels.json';save(w.document(),label_path);w.label_path=label_path
    from PySide6.QtWidgets import QMessageBox
    def cancel_dialog(dialog):
        for b in dialog.buttons():
            if dialog.standardButton(b)==QMessageBox.StandardButton.Cancel:b.click();break
    monkeypatch.setattr(QMessageBox,'exec',cancel_dialog);before=w.document().copy();w.clear_measurements();assert w.document()==before
    def confirm_dialog(dialog):
        next(b for b in dialog.buttons() if b.text()=='Current attempt').click()
    monkeypatch.setattr(QMessageBox,'exec',confirm_dialog);w.clear_measurements()
    assert w.document()['start'] is None and not w.document()['checkpoints'] and not w.document()['events'] and not w.document()['open_events']
    assert load(label_path)['end'] is None
    backups=list((tmp_path/'artifacts'/'measurement-backups').glob('*.labels.json'));assert len(backups)==1 and load(backups[0])['checkpoints'][0]['name']=='A'
    other=tmp_path/'other.mkv';other.write_bytes(path.read_bytes());old=load(backups[0]);other_label=tmp_path/'other.labels.json';save(old,other_label);w.workspace.remember(other,old,other_label)
    w.apply_reset(all_videos=True);assert load(other_label)['start'] is None and all(not state['document']['events'] for state in w.workspace.states.values())
    wait_until(app,lambda:w.decode_future is None);w.saved=w.document();w.close()


def test_four_timer_shortcuts_buttons_and_typing(tmp_path,monkeypatch):
    import viewer.simple as simple
    monkeypatch.setattr(simple,'ROOT',tmp_path)
    path=tmp_path/'shortcuts.mkv'
    with av.open(str(path),'w') as out:
        stream=out.add_stream('ffv1',rate=25);stream.width=32;stream.height=32;stream.pix_fmt='yuv420p'
        for n in range(20):
            frame=av.VideoFrame.from_ndarray(np.full((32,32,3),n*12,dtype=np.uint8),format='rgb24')
            for packet in stream.encode(frame):out.mux(packet)
        for packet in stream.encode():out.mux(packet)
    app=QApplication.instance() or QApplication([]);w=Window();w.workspace=Workspace(tmp_path/'workspace.json');w.async_decode=False;w.video_path=path;w.index_ready(index_video(path));w.show();app.processEvents();w.image.setFocus();app.processEvents()
    seed_assignment(w);w.set_start()
    for key in (Qt.Key.Key_L,Qt.Key.Key_R,Qt.Key.Key_Q,Qt.Key.Key_W,Qt.Key.Key_C,Qt.Key.Key_V):QTest.keyClick(w,key)
    assert len(w.document()['open_events'])==6
    assert set((e['kind'],e['hand']) for e in w.document()['open_events'])=={('clip','left'),('clip','right'),('rest','left'),('rest','right'),('chalk','left'),('chalk','right')}
    assert all(b.property('role')=='stop' and w.hand_timer_cancel[k].isVisibleTo(w) for k,b in w.hand_timer_buttons.items())
    w.show_frame(5)
    for button in w.hand_timer_buttons.values():QTest.mouseClick(button,Qt.MouseButton.LeftButton)
    assert not w.document()['open_events'] and len(w.document()['events'])==6
    clips={e['hand']:e.get('clip_method') for e in w.document()['events'] if e['kind']=='clip'}
    assert clips=={'left':None,'right':None}
    assert all(b.property('role')=='start' and not w.hand_timer_cancel[k].isVisibleTo(w) for k,b in w.hand_timer_buttons.items())
    assert w.draw.value()==2 and all(e['target']==1 for e in w.document()['events'] if e['kind']=='clip')
    initial=w.theme;w.toggle_theme();assert w.theme!=initial and w.precision_scrubber.dark==(w.theme=='dark');w.toggle_theme();assert w.theme==initial
    w.toggle_events();app.processEvents();assert w.table.isVisible() and w.workspace_tabs is None
    before_name=w.climber.text();w.attempt.setFocus();w.attempt.selectAll();app.processEvents();QTest.keyClicks(w.attempt,'2');assert w.climber.text()==before_name and not w.document()['open_events']
    w.image.setFocus();app.processEvents();w.show_frame(10);monkeypatch.setattr(w,'choose_climb_outcome',lambda:'failed');w.set_failure()
    from PySide6.QtCore import QSettings
    w.settings=QSettings(str(tmp_path/'settings.ini'),QSettings.Format.IniFormat);w.frame_step.setValue(5)
    w.show_frame(0);QTest.keyClick(w,Qt.Key.Key_Right);assert w.frame_number==5
    QTest.keyClick(w,Qt.Key.Key_Right,Qt.KeyboardModifier.ShiftModifier);assert w.frame_number==6
    w.frame_step.setValue(3);QTest.keyClick(w,Qt.Key.Key_Right);assert w.frame_number==9 and w.settings.value('frame_step',type=int)==3
    w.table.selectRow(0);w.table.setFocus();app.processEvents();QTest.keyClick(w,Qt.Key.Key_Delete);assert len(w.document()['events'])==5
    w.undo();assert len(w.document()['events'])==6
    w.point_name.setText('A');w.add_point();w.points_table.selectRow(0);w.points_table.setFocus();app.processEvents();QTest.keyClick(w,Qt.Key.Key_Delete);assert not w.document()['checkpoints']
    w.undo();assert len(w.document()['checkpoints'])==1
    w.clear_boundary('start');assert w.document()['start'] is None;w.undo();assert w.document()['start'] is not None
    w.saved=w.document();w.close()


def test_playback_requests_do_not_restart_completion_timer():
    from types import SimpleNamespace
    class Timer:
        def __init__(self):self.active=False;self.starts=0
        def isActive(self):return self.active
        def start(self):self.active=True;self.starts+=1
    state=SimpleNamespace(reader=SimpleNamespace(times=list(range(100))),async_decode=True,playing=True,decode_future=None,decode_poll=Timer())
    def submit():state.decode_future=object()
    state.submit_decode=submit
    for number in range(1,50):Window.show_frame(state,number)
    assert state.decode_requested==49 and state.decode_poll.starts==1


def test_display_uses_indexed_rotation_when_cuda_drops_metadata():
    from collections import OrderedDict
    import numpy as np
    from viewer.video import VideoReader
    pixels=np.arange(18,dtype=np.uint8).reshape(2,3,3)
    class Frame:
        width=3
        height=2
        rotation=0
        def reformat(self,**kwargs):return self
        def to_ndarray(self):return pixels
    reader=object.__new__(VideoReader)
    reader.index={'rotation':-90};reader.cache=OrderedDict()
    assert np.array_equal(reader.display_pixels(Frame(),0),np.rot90(pixels,k=-1))
