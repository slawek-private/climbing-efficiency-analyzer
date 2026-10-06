"""Regression coverage for persisted identity, recoverability and update safety."""
import copy,json,os,subprocess,sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from viewer.test_rebuild import window
from viewer.test_sync_view import synthetic
from viewer.labels import load,empty_labels,save
from viewer.workspace import Workspace
from viewer.updater import compatibility_reason


def test_collision_rename_new_attempt_and_missing_source(tmp_path,monkeypatch):
    app,w=window(tmp_path,monkeypatch);paths=[];labels=[]
    for n in (40,50):
        folder=tmp_path/str(n);folder.mkdir();path=folder/'IMG_0001.mkv';index=synthetic(path,n);paths.append(path)
        w.video_path=path;w.label_path=None;w.index_ready(index);w.show_frame(2);w.set_start();assert w.autosave();labels.append(w.label_path)
    assert labels[0]!=labels[1] and all(load(p)['start']['frame']==2 for p in labels)
    original=w.label_path;identifier=w.document()['attempt_id'];d=copy.deepcopy(w.document());d.update(climber='Renamed athlete',attempt='99');w.commit(d);assert w.autosave()
    assert w.label_path==original and w.document()['attempt_id']==identifier
    w.new_attempt();assert w.document()['attempt_id']!=identifier and w.label_path!=original and load(original)['climber']=='Renamed athlete'
    assert len(w.workspace.documents())==3
    w.close();paths[0].unlink();reopened=Workspace(tmp_path/'workspace.json');assert len(reopened.videos)==2 and len(reopened.documents())==3
    with pytest.raises(ValueError,match='different video'):reopened.relink(paths[0],tmp_path/'replacement.mkv','0'*64)
    replacement=tmp_path/'found.mkv';digest=reopened.states[str(paths[0])]['document']['source']['sha256'];reopened.relink(paths[0],replacement,digest)
    assert str(replacement) in Workspace(tmp_path/'workspace.json').states


def test_save_failure_is_visible_retryable_and_blocks_switch(tmp_path,monkeypatch):
    import viewer.simple as simple
    app,w=window(tmp_path,monkeypatch);path=tmp_path/'a.mkv';w.video_path=path;w.index_ready(synthetic(path,40));assert w.save_state.text()=='No changes saved yet'
    w.set_start();real= simple.save
    def denied(*args):raise PermissionError('Disk is read only')
    monkeypatch.setattr(simple,'save',denied);assert not w.autosave();assert w.save_banner.isVisible() and 'read only' in w.save_detail.text() and not w.allow_change()
    monkeypatch.setattr(simple,'save',real);assert w.autosave() and not w.save_banner.isVisible();saved=w.label_path.read_bytes()
    with monkeypatch.context() as m:
        real_replace=Path.replace
        def fail_replace(path,target):
            if Path(target)==w.label_path:raise OSError('Interrupted rename')
            return real_replace(path,target)
        m.setattr(Path,'replace',fail_replace);w.show_frame(3);w.set_start();assert not w.autosave();assert w.label_path.read_bytes()==saved
    assert w.autosave();w.close()


def test_workspace_failure_does_not_claim_saved(tmp_path,monkeypatch):
    app,w=window(tmp_path,monkeypatch);path=tmp_path/'a.mkv';w.video_path=path;w.index_ready(synthetic(path));w.set_start()
    real=w.workspace.save
    def failed():raise OSError('Workspace full')
    monkeypatch.setattr(w.workspace,'save',failed);assert not w.autosave();assert 'Workspace full' in w.save_detail.text() and w.save_state.text()=='⚠ Not saved'
    monkeypatch.setattr(w.workspace,'save',real);assert w.autosave();w.close()


def test_clip_method_captured_per_pending_hand_and_interval_total(tmp_path,monkeypatch):
    app,w=window(tmp_path,monkeypatch);path=tmp_path/'a.mkv';w.video_path=path;w.index_ready(synthetic(path));w.clip_method.setCurrentIndex(w.clip_method.findData('mouth'));w.toggle_hand_timer('clip','left')
    w.clip_method.setCurrentIndex(w.clip_method.findData('direct'));w.draw.setValue(2);w.toggle_hand_timer('clip','right');w.clip_method.setCurrentIndex(0);w.show_frame(10)
    w.toggle_hand_timer('clip','left');w.toggle_hand_timer('clip','right');assert [(e['hand'],e['target'],e['clip_method']) for e in w.document()['events']]==[('left',1,'mouth'),('right',2,'direct')]
    w.show_frame(1);assert '1.0 s\nEdit interval' in w.hand_timer_buttons['clip','left'].text()
    w.close()


def manifest():
    data=json.loads((Path(__file__).resolve().parents[1]/'packaging/update.json').read_text());return {'tag_name':'v'+data['version'],'update_manifest':data}


def test_update_compatibility_fails_closed():
    release=manifest();assert compatibility_reason(release,'0.19.0',('darwin','arm64',(14,0))) is None
    for version,target in [('0.18.0',('darwin','arm64',(14,0))),('0.19.0',('darwin','x64',(14,0))),('0.19.0',('darwin','arm64',(13,0)))]:assert compatibility_reason(release,version,target)
    assert compatibility_reason({},'0.19.0',('darwin','arm64',(14,0)))
    release['update_manifest']['migration']='destructive';assert compatibility_reason(release,'0.19.0',('darwin','arm64',(14,0)))


@pytest.mark.skipif(sys.platform=='win32',reason='POSIX swap script')
@pytest.mark.parametrize('scenario',['still-running','no-incoming','old-backup','first-rename','second-rename','launch'])
def test_failed_swap_never_deletes_old_app(tmp_path,scenario):
    from viewer.platform_runtime import MAC_SWAP
    app=tmp_path/'Studio.app';app.mkdir();(app/'old').write_text('keep')
    incoming=tmp_path/'Studio.app.incoming';incoming.mkdir();(incoming/'new').write_text('new')
    script=tmp_path/'swap.sh';script.write_text(MAC_SWAP)
    env={**os.environ,'CLIMB_STUDIO_OPEN':'/usr/bin/true','CLIMB_STUDIO_WAIT_STEPS':'1'};pid='99999999'
    if scenario=='still-running':pid=str(os.getpid())
    if scenario=='no-incoming':(incoming/'new').unlink();incoming.rmdir()
    if scenario=='old-backup':(tmp_path/'Studio.app.previous').mkdir()
    if scenario=='launch':env['CLIMB_STUDIO_OPEN']='/usr/bin/false'
    if scenario in ('first-rename','second-rename'):
        bin=tmp_path/'bin';bin.mkdir();command=bin/'mv'
        fail_source=app if scenario=='first-rename' else incoming
        command.write_text('#!/bin/sh\n[ "$1" = "'+str(fail_source)+'" ] && exit 1\nexec /bin/mv "$@"\n');command.chmod(0o755);env['PATH']=str(bin)+':'+env['PATH']
    result=subprocess.run(['/bin/sh',str(script),pid,str(app)],env=env,timeout=5)
    assert result.returncode!=0 and (app/'old').read_text()=='keep'


def test_low_disk_preview_cleans_partial_file(tmp_path,monkeypatch):
    from viewer import preview_cache
    path=tmp_path/'a.mkv';index=synthetic(path);root=tmp_path/'cache'
    monkeypatch.setattr(preview_cache.shutil,'disk_usage',lambda _:SimpleNamespace(free=100))
    with pytest.raises(OSError,match='512 MB'):preview_cache.build_preview(path,index,root)
    folder=preview_cache.cache_folder(root,index);assert not list(folder.iterdir()) and path.exists()


def test_route_selection_and_laptop_layout(tmp_path,monkeypatch):
    app,w=window(tmp_path,monkeypatch);path=tmp_path/'a.mkv';index=synthetic(path);w.video_path=path;w.index_ready(index);w.set_start();w.autosave()
    other=empty_labels(index['source']);other.update(route='Other route',climber='Other');w.workspace.attempts.append({'path':str(path),'state':{'document':other,'frame':0,'label_path':None}});w.refresh_collection()
    w.compare_scope.route.setCurrentText('blue');assert all(d['route']=='blue' for d in w.comparison_documents)
    w.compare_scope.route.setCurrentText('Other route');assert len(w.comparison_documents)==1 and w.comparison_documents[0]['climber']=='Other'
    w.show_view(w.measure_page)
    from PySide6.QtTest import QTest
    QTest.qWait(50);w.resize(1024,768);app.processEvents();assert w.width()==1024
    assert w.position.visibleRegion().boundingRect().width()>=w.position.sizeHint().width()
    w.toggle_hand_timer('rest','left');w.toggle_inspector();app.processEvents();assert not w.measurement_scroll.isVisible() and w.active_timers.isVisible()
    w.close()


def test_archived_attempts_survive_project_export_import(tmp_path):
    from viewer import projects
    project=projects.create(tmp_path/'root','Session');path=tmp_path/'a.mkv';index=synthetic(path)
    ws=Workspace(project.workspace_file)
    for n in range(2):
        d=empty_labels(index['source']);d['attempt']=str(n+1);label=project.labels/(d['attempt_id']+'.labels.json');save(d,label)
        if n:ws.archive(path)
        ws.remember(path,d,label)
    ws.save();archive=projects.export_project(project,tmp_path/'session.climbproject');restored=projects.import_project(tmp_path/'other',archive);result=Workspace(restored.workspace_file)
    assert len(result.documents())==2 and len(result.attempts)==1
    entry=result.attempts[0];assert Path(entry['path']).is_file() and Path(entry['state']['label_path']).is_file() and str(restored.folder) in entry['path']


def test_comparison_selection_preserves_time_and_opens_exact_frame(tmp_path,monkeypatch):
    from viewer.test_playback import wait_until
    app,w=window(tmp_path,monkeypatch)
    for name,start in [('a',2),('b',4)]:
        path=tmp_path/(name+'.mkv');index=synthetic(path,40);doc=empty_labels(index['source']);doc['start']={'frame':start,'pts':index['pts'][start],'seconds':start/10};w.workspace.remember(path,doc)
    w.refresh_collection();w.show_view(w.sync_view);wait_until(app,lambda:len(w.sync_view.tiles)==2);w.sync_view.seek(.5)
    w.show_view(w.comparison_page);w.show_view(w.sync_view);assert abs(w.sync_view.t-.5)<1e-8
    w.compare_scope.menu.actions()[1].setChecked(False);assert len(w.sync_view.tiles)==1
    tile=w.sync_view.tiles[0];w.open_comparison_document(tile.path,tile.document,tile.wanted);wait_until(app,lambda:w.reader is not None and w.frame_number==7)
    assert w.document()['attempt_id']==tile.document['attempt_id'];w.close()
