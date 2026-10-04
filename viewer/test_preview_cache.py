from fractions import Fraction
import json
import av,numpy as np
import pytest
from viewer.video import index_video
from viewer.preview_cache import build_preview,open_preview,cache_folder

def video(tmp_path):
    path=tmp_path/'vfr.mkv'
    with av.open(str(path),'w') as output:
        stream=output.add_stream('ffv1',rate=25);stream.width=64;stream.height=32;stream.pix_fmt='yuv420p'
        for n,pts in enumerate([0,40,100,180,260]):
            pixels=np.zeros((32,64,3),dtype=np.uint8);pixels[:,:32]=[n*30,100,220];pixels[:,32:]=[220,30,n*30]
            frame=av.VideoFrame.from_ndarray(pixels,format='rgb24');frame.pts=pts;frame.time_base=Fraction(1,1000)
            for packet in stream.encode(frame):output.mux(packet)
        for packet in stream.encode():output.mux(packet)
    index=index_video(path);index['rotation']=-90
    return path,index

def test_preview_exact_original_points_random_seeks_and_identity(tmp_path):
    path,index=video(tmp_path);root=tmp_path/'previews';build_preview(path,index,root)
    reader=open_preview(root,index);assert reader is not None
    for n in (4,0,3,1,2):
        assert reader.point(n)=={'frame':n,'pts':index['pts'][n],'seconds':float((index['pts'][n]-index['pts'][0])*Fraction(index['source']['time_base']))}
        assert reader.frame(n).shape==(64,32,3)
    reader.close()
    renamed=json.loads(json.dumps(index));renamed['source']['file']='renamed.mov'
    r=open_preview(root,renamed);assert r is not None;r.close()
    wrong=json.loads(json.dumps(index));wrong['pts'][1]+=1
    assert open_preview(root,wrong) is None
    meta=json.loads((cache_folder(root,index)/'manifest.json').read_text())
    data=cache_folder(root,index)/meta['data'];data.write_bytes(data.read_bytes()[:-10])
    assert open_preview(root,index) is None

def test_cancelled_preparation_does_not_publish_partial_cache(tmp_path):
    path,index=video(tmp_path);root=tmp_path/'previews'
    with pytest.raises(InterruptedError):build_preview(path,index,root,cancelled=lambda:True)
    assert open_preview(root,index) is None
    assert not list(cache_folder(root,index).iterdir())

def test_viewer_automatically_uses_prepared_preview_and_keeps_status_separate(tmp_path,monkeypatch):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QPoint
    from viewer.simple import Window
    from viewer.test_playback import wait_until
    import viewer.simple as simple
    monkeypatch.setattr(simple,'ROOT',tmp_path)
    path,index=video(tmp_path);build_preview(path,index,tmp_path/'artifacts'/'preview-cache')
    app=QApplication.instance() or QApplication([]);w=Window();w.video_path=path;w.index_ready(index);w.resize(1200,850);w.show()
    wait_until(app,lambda:w.decode_future is None)
    assert w.reader.backend=='preview' and not w.decoder_choice.isEnabled()
    w.show_frame(4);wait_until(app,lambda:w.decode_future is None)
    assert w.reader.point(w.frame_number)['pts']==index['pts'][4]
    for key,button in w.hand_timer_buttons.items():
        status=w.hand_timer_status[key]
        button_rect=button.rect();button_rect.moveTopLeft(button.mapTo(w,QPoint(0,0)))
        status_rect=status.rect();status_rect.moveTopLeft(status.mapTo(w,QPoint(0,0)))
        assert not button_rect.intersects(status_rect)
    w.saved=w.document();w.close()
