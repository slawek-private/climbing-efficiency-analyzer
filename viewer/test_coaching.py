"""Synthetic regression checks for reviewed footwork, media provenance and coaching exports."""
import copy,json
from pathlib import Path
from fractions import Fraction
from uuid import uuid4
import av,numpy as np,pytest
from viewer.labels import empty_labels,validate,load,save
from viewer.footwork import enable,metrics
from viewer.coaching_report import export_report,write_clip
from viewer.test_rebuild import window
from viewer.test_sync_view import synthetic


def fixture():
    source={'file':'fictional.mkv','sha256':'a'*64,'time_base':'1/10','first_pts':0,'frame_count':601}
    d=empty_labels(source);point=lambda s:{'frame':round(s*10),'pts':round(s*10),'seconds':s}
    d.update(start=point(0),end=point(60),outcome='completed');t=enable(d)
    for a,b in [(0,10),(16,60)]:t['coverage'].append({'id':uuid4().hex,'start':point(a),'end':point(b),'state':'reviewed'})
    t['coverage'].append({'id':uuid4().hex,'start':point(10),'end':point(16),'state':'obscured'})
    for s,limb,status,intent in [(18.2,'left','confirmed','unplanned'),(43.4,'right','confirmed','unplanned'),(12.3,'uncertain','uncertain','uncertain')]:
        t['events'].append(dict(id=uuid4().hex,kind='slip',limb=limb,start=point(s),end=None,intent=intent,status=status,observation='Visible release',interpretation='',action=''))
    for a,b,intent in [(27,28.6,'intentional'),(43.4,44.2,'unplanned')]:t['events'].append(dict(id=uuid4().hex,kind='both_off',limb='both',start=point(a),end=point(b),intent=intent,status='confirmed',observation='',interpretation='',action=''))
    validate(d);return d,point


def test_coverage_denominators_unknowns_and_fall_flight():
    d,point=fixture();m=metrics(d);assert m['confirmed_slips']==2 and m['candidate_slips']==1
    assert m['reviewed_seconds']==54 and m['coverage_share']==.9 and m['both_off_seconds']==pytest.approx(2.4) and m['both_off_share']==pytest.approx(2.4/54)
    assert m['intentional_seconds']==pytest.approx(1.6) and m['unplanned_seconds']==pytest.approx(.8)
    d['footwork']['coverage']=[];assert metrics(d)['confirmed_slips'] is None and metrics(d)['both_off_share'] is None
    d,point=fixture();d['outcome']='failed';assert metrics(d)['fall_review_needed'] and metrics(d)['both_off_seconds'] is None
    d['footwork']['fall_onset']=point(43.7);assert metrics(d)['unplanned_seconds']==pytest.approx(.3)
    # An interval crossing occlusion is intersected with reviewed coverage, not bridged.
    d,point=fixture();d['footwork']['events']=[dict(d['footwork']['events'][-1],start=point(8),end=point(18))];assert metrics(d)['both_off_seconds']==4
    # Nothing marked in explicitly reviewed coverage is a reviewed zero.
    d['footwork']['events']=[];assert metrics(d)['confirmed_slips']==0 and metrics(d)['both_off_seconds']==0
    d['footwork']['pending']={'start':point(18),'intent':'uncertain'};assert metrics(d)['both_off_seconds'] is None
    d,point=fixture();d['footwork']['events'][-1]['status']='candidate';assert metrics(d)['both_off_seconds'] is None


def test_identity_validation_migration_and_backups(tmp_path):
    d,point=fixture();old=empty_labels(d['source']);path=tmp_path/'attempt.labels.json';save(old,path);original=path.read_bytes();save(d,path)
    assert load(path)==d and path.with_name('attempt.labels.pre-coaching-backup.json').read_bytes()==original
    bad=copy.deepcopy(d);bad['footwork']['events'][0]['start']['pts']+=1
    with pytest.raises(ValueError,match='Timestamp'):validate(bad)
    bad=copy.deepcopy(d);bad['footwork']['coverage'][0]['end']=point(17)
    with pytest.raises(ValueError,match='overlap'):validate(bad)
    bad=copy.deepcopy(d);bad['footwork']['events'][-1]['start']=point(28)
    with pytest.raises(ValueError,match='overlap'):validate(bad)
    assert d['source']==old['source']


def test_html_pdf_escaping_anonymity_and_missing_media(tmp_path):
    d,_=fixture();d['climber']='Private fictional name';d['coaching']={'goal':'<script>alert(1)</script>','reflection':'=A1','action':'Review right foot','retest':'Repeat matched section'}
    path=tmp_path/'review.html';export_report([d],path,anonymous=True,pdf=True)
    html=path.read_text();assert '<script>alert(1)</script>' not in html and '&lt;script&gt;' in html and 'Private fictional name' not in html
    provenance=json.loads(path.with_suffix('.json').read_text());assert provenance['events'][0]['source_sha256']==d['source']['sha256']
    assert path.with_suffix('.pdf').read_bytes().startswith(b'%PDF') and 'data-replay' not in html.split('<script id="reportData"')[0]
    original=path.read_bytes()
    with pytest.raises(ValueError,match='Locate'):export_report([d],path,media='clips')
    assert path.read_bytes()==original and not list(tmp_path.glob('.climb-report-*'))


def test_vfr_portable_clip_keeps_all_source_frames_and_pts(tmp_path):
    from viewer.video import index_video,VideoReader
    source=tmp_path/'vfr.mkv';timestamps=[0,40,95,170,300,450,610,800]
    with av.open(str(source),'w') as c:
        stream=c.add_stream('ffv1',rate=30);stream.width=64;stream.height=48;stream.pix_fmt='yuv420p'
        for pts in timestamps:
            frame=av.VideoFrame.from_ndarray(np.full((48,64,3),pts//4,dtype=np.uint8),format='rgb24');frame.pts=pts;frame.time_base=Fraction(1,1000)
            for packet in stream.encode(frame):c.mux(packet)
        for packet in stream.encode():c.mux(packet)
    index=index_video(source);reader=VideoReader(source,index,'cpu');d=empty_labels(index['source']);t=enable(d);event=dict(id=uuid4().hex,kind='slip',limb='left',start=reader.point(3),end=None,intent='unplanned',status='confirmed',observation='',interpretation='',action='');t['events']=[event]
    try:
        clip=tmp_path/'clip.mp4';mapping=write_clip(reader,event,clip)
        with av.open(str(clip)) as c:frames=list(c.decode(video=0));times=[float(f.pts*f.time_base) for f in frames]
        assert len(frames)==len(index['pts']);assert times==pytest.approx(reader.times,abs=.0001);assert mapping['source_pts']==index['pts']
        report=tmp_path/'with-video.html';export_report([d],report,sources={d['attempt_id']:source},media='clips',pdf=True)
        html=report.read_text();assert 'Replay event' in html and '<img ' in html and list(tmp_path.glob('with-video-media-*/*.mp4'))
        assert '<script id="reportData"' in html
    finally:reader.close()


def test_footwork_gui_persistence_undo_replay_and_compact_themes(tmp_path,monkeypatch):
    from PySide6.QtTest import QTest
    from viewer.design import apply_theme
    app,w=window(tmp_path,monkeypatch);path=tmp_path/'a.mkv';index=synthetic(path,80);w.video_path=path;w.index_ready(index);w.show_frame(2);w.set_start()
    panel=w.footwork_panel;panel.toggle.setChecked(True);panel.toggle_both();assert w.document()['footwork']['pending']['start']==w.reader.point(2)
    assert w.autosave() and load(w.label_path)['footwork']['pending']
    panel.cancel_timer();assert not w.document()['footwork']['pending'];w.undo();assert w.document()['footwork']['pending'];w.redo()
    e={'start':w.reader.point(20),'end':w.reader.point(25)};w.replay_observation(e);assert w.replay_range and w.playing;w.pause();assert w.replay_range is None
    for theme in ('light','dark','system'):
        apply_theme(w,theme);QTest.qWait(50);w.resize(1024,768);app.processEvents();assert w.width()==1024 and w.position.visibleRegion().boundingRect().width()>=w.position.sizeHint().width()
    w.close()


def test_checkpoint_reference_missing_repeated_and_different_route():
    from viewer.coaching_report import section_comparison
    first,p=fixture();first['climber']='A';first['start']=p(1);first['checkpoints']=[dict(id='roof',name='Roof',point=p(20))]
    second=copy.deepcopy(first);second['climber']='B';second['checkpoints'][0]['point']=p(23)
    rows=section_comparison([first,second]);assert rows[1][3:6]==['22 s','19 s','3 s']
    second['checkpoints'].append(dict(id='roof2',name='Roof',point=p(26)))
    assert section_comparison([first,second])[1][-1]=='Ambiguous / missing'
    second['checkpoints'].pop();second['route']='Another route'
    assert section_comparison([first,second])[1][4:]==['Not reviewed','Not reviewed','Different route / round']


def test_export_rollback_cancel_and_labels_collision(tmp_path,monkeypatch):
    d,_=fixture();path=tmp_path/'report.html';export_report([d],path,pdf=True)
    originals={p:p.read_bytes() for p in tmp_path.iterdir()}
    replace=Path.replace
    def fail_html(self,target):
        if self.name=='report.html' and self.parent.name.startswith('.climb-report-'):raise OSError('Synthetic publishing failure')
        return replace(self,target)
    with monkeypatch.context() as m:
        m.setattr(Path,'replace',fail_html)
        with pytest.raises(OSError,match='publishing'):export_report([d],path,pdf=True)
    assert {p:p.read_bytes() for p in tmp_path.iterdir()}==originals
    with pytest.raises(InterruptedError):export_report([d],path,cancelled=lambda:True)
    assert {p:p.read_bytes() for p in tmp_path.iterdir()}==originals
    path.with_suffix('.json').write_text(json.dumps(d))
    with pytest.raises(ValueError,match='labels file'):export_report([d],path)


def test_cli_measurements_and_preview_reuse(tmp_path,monkeypatch):
    from viewer.coaching_report import main
    from viewer.video import VideoReader
    from viewer.preview_cache import build_preview
    from viewer.storage import folders
    path=tmp_path/'original.mkv';index=synthetic(path,30);reader=VideoReader(path,index,'cpu');d=empty_labels(index['source']);t=enable(d)
    t['events']=[dict(id='foot',kind='slip',limb='right',start=reader.point(10),end=None,intent='unplanned',status='confirmed',observation='',interpretation='',action='')];reader.close()
    labels=tmp_path/'original.labels.json';save(d,labels)
    assert main(['--labels',str(labels),'--output',str(tmp_path/'cli.html'),'--pdf'])==0
    cache=tmp_path/'cache';build_preview(path,index,folders(cache)[0])
    def no_original(*args,**kwargs):raise AssertionError('Prepared preview must be preferred')
    monkeypatch.setattr('viewer.video.VideoReader',no_original)
    export_report([d],tmp_path/'preview.html',sources={d['attempt_id']:path},media='clips',cache_root=cache)
    wrong=copy.deepcopy(d);wrong['source']['sha256']='b'*64
    with pytest.raises(ValueError,match='identity'):export_report([wrong],tmp_path/'wrong.html',sources={wrong['attempt_id']:path},media='clips')


def test_project_video_landing_navigation_and_coaching_hand_timers(tmp_path,monkeypatch):
    from viewer.projects import create
    from viewer.workspace import Workspace
    from viewer.test_playback import wait_until
    app,w=window(tmp_path,monkeypatch);project=create(tmp_path,'Fictional route');paths=[]
    for name in ('front.mkv','side.mkv'):
        p=tmp_path/name;synthetic(p,40);paths.append(p)
    workspace=Workspace(project.workspace_file)
    for p in paths:workspace.add(p)
    workspace.save();assert w.open_project(project)
    assert w.main_tabs.currentWidget() is w.library and w.video_path is None and '2 videos' in w.library.heading.text()
    w.library.open_row(0,0);wait_until(app,lambda:w.reader is not None and not w.worker.isRunning())
    assert w.main_tabs.currentWidget() is w.measure_page and w.video_navigation.buttons[0].isChecked() and w.video_count.text()=='Viewing 1/2'
    d=copy.deepcopy(w.document());enable(d);w.commit(d);w.show_frame(5);w.toggle_hand_timer('chalk','left');w.show_frame(8);w.toggle_hand_timer('chalk','left')
    assert w.document()['schema_version']=='1.4.0' and w.document()['events'][-1]['kind']=='chalk' and w.autosave()
    w.video_navigation.buttons[1].click();wait_until(app,lambda:w.video_path==paths[1] and w.reader is not None and not w.worker.isRunning())
    assert w.video_navigation.buttons[1].isChecked() and not w.video_navigation.buttons[0].isChecked() and w.video_count.text()=='Viewing 2/2'
    w.show_view(w.library);assert 'Open now: side.mkv' in w.library.open_now.text()
    assert w.open_project(project) and w.main_tabs.currentWidget() is w.library
    w.close()
