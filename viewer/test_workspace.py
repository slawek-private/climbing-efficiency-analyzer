from viewer.workspace import Workspace
from viewer.test_manual import source,point
from viewer.labels import empty_labels

def test_workspace_drafts_survive_switch_and_restart(tmp_path):
    a=tmp_path/'a.mov';b=tmp_path/'b.mov';a.touch();b.touch()
    workspace=Workspace(tmp_path/'workspace.json');workspace.add(a);workspace.add(b);workspace.add(a)
    d=empty_labels(source());d['start']=point(1);d['checkpoints']=[{'id':'a','name':'A','point':point(5)}]
    workspace.remember(a,d,frame=50);workspace.save()
    restored=Workspace(workspace.path)
    assert len(restored.videos)==2 and len(restored.documents())==1
    assert restored.states[str(a.resolve())]['frame']==50
    assert restored.documents()[0]['checkpoints'][0]['name']=='A'


def test_exact_index_cache_reuses_hash_and_accepts_rename(tmp_path):
    import av,numpy as np
    from fractions import Fraction
    from viewer.video import index_video
    first=tmp_path/'first.mkv'
    with av.open(str(first),'w') as out:
        stream=out.add_stream('ffv1',rate=25);stream.width=32;stream.height=32;stream.pix_fmt='yuv420p'
        for n in range(3):
            f=av.VideoFrame.from_ndarray(np.full((32,32,3),n*60,dtype=np.uint8),format='rgb24');f.pts=n*40;f.time_base=Fraction(1,1000)
            for packet in stream.encode(f):out.mux(packet)
        for packet in stream.encode():out.mux(packet)
    original=index_video(first,cache_dir=tmp_path/'cache')
    renamed=tmp_path/'renamed.mkv';renamed.write_bytes(first.read_bytes())
    cached=index_video(renamed,cache_dir=tmp_path/'cache')
    assert cached['pts']==original['pts'] and cached['source']['sha256']==original['source']['sha256']
    assert cached['source']['file']=='renamed.mkv' and len(list((tmp_path/'cache').glob('*.json')))==1


def test_shared_point_names_persist_without_arrivals(tmp_path):
    w=Workspace(tmp_path/'project.json');assert w.add_point_name('REST')=='REST'
    assert w.add_point_name('rest')=='REST';w.save();restored=Workspace(w.path)
    assert restored.shared_points()==['REST'] and restored.documents()==[]
