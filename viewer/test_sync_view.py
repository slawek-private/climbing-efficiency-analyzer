import av,numpy as np
from PySide6.QtWidgets import QApplication
from viewer.labels import empty_labels
from viewer.simple import Window
from viewer.sync_view import frame_at,anchor_seconds
from viewer.test_playback import wait_until
from viewer.video import index_video
from viewer.workspace import Workspace

def synthetic(path,frames=25):
    with av.open(str(path),'w') as out:
        stream=out.add_stream('ffv1',rate=10);stream.width=32;stream.height=32;stream.pix_fmt='yuv420p'
        for n in range(frames):
            for packet in stream.encode(av.VideoFrame.from_ndarray(np.full((32,32,3),n*9,dtype=np.uint8),format='rgb24')):out.mux(packet)
        for packet in stream.encode():out.mux(packet)
    return index_video(path)

def test_frame_and_anchor_helpers():
    assert [frame_at([0,.1,.2],s) for s in (-1,0,.15,.2,9)]==[0,0,1,2,2]
    d={'start':{'seconds':2.},'checkpoints':[{'name':'Rest','point':{'seconds':5.}},{'name':'rest','point':{'seconds':4.}}]}
    assert anchor_seconds(d,'start')==2 and anchor_seconds(d,'REST')==4 and anchor_seconds(d,'roof') is None

def test_videos_align_at_climb_start(tmp_path,monkeypatch):
    import viewer.simple as simple,viewer.sync_view as sync
    monkeypatch.setattr(simple,'ROOT',tmp_path);monkeypatch.setattr(sync,'ROOT',tmp_path)
    app=QApplication.instance() or QApplication([]);w=Window();w.workspace=Workspace(tmp_path/'workspace.json')
    for name,start in (('a.mkv',3),('b.mkv',7),('c.mkv',None)):
        path=tmp_path/name;index=synthetic(path);reader_times=[n/10 for n in range(25)]
        d=empty_labels(index['source']);d['climber']=name[0].upper()
        if start is not None:d['start']={'frame':start,'pts':index['pts'][start],'seconds':reader_times[start]}
        w.workspace.remember(path,d)
    w.show_view(w.sync_view);wait_until(app,lambda:len(w.sync_view.tiles)==2)
    view=w.sync_view;assert 'not marked: C' in view.note.text()
    assert [t.wanted for t in view.tiles]==[3,7]
    view.step(.5);assert [t.wanted for t in view.tiles]==[8,12]
    view.seek(-1);assert [t.wanted for t in view.tiles]==[0,0] and 'not started' in view.tiles[0].status.text()
    wait_until(app,lambda:all(t.shown==t.wanted for t in view.tiles))
    view.seek(0);view.toggle_play();wait_until(app,lambda:view.t>.2);view.pause()
    assert all(t.wanted==frame_at(t.reader.times,t.anchor+view.t) for t in view.tiles)
    w.main_tabs.setCurrentIndex(0);assert not view.timer.isActive()
    w.close()
