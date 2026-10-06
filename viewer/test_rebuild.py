import copy
from pathlib import Path
from PySide6.QtCore import QMimeData,QPointF,QSettings,QUrl,Qt
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QApplication
from viewer.labels import empty_labels,load
from viewer.test_playback import wait_until
from viewer.test_sync_view import synthetic
from viewer.video import index_video
from viewer.workspace import Workspace

def window(tmp_path,monkeypatch):
    import viewer.simple as simple,viewer.sync_view as sync
    monkeypatch.setattr(simple,'ROOT',tmp_path);monkeypatch.setattr(sync,'ROOT',tmp_path)
    settings=QSettings(str(tmp_path/'settings.ini'),QSettings.Format.IniFormat);monkeypatch.setattr(simple,'QSettings',lambda *a:settings)
    app=QApplication.instance() or QApplication([]);w=simple.Window();w.workspace=Workspace(tmp_path/'workspace.json');w.async_decode=False;w.resize(1300,900);w.show();app.processEvents()
    return app,w

def test_empty_state_then_loaded_video_and_autosave_without_dialog(tmp_path,monkeypatch):
    app,w=window(tmp_path,monkeypatch)
    assert w.empty_hint.isVisible() and not w.image.isVisible() and not w.transport.isVisible() and w.empty_panel.isVisible() and w.save_state.text()==''
    path=tmp_path/'anna.mkv';index=synthetic(path,40);w.video_path=path;w.index_ready(index);app.processEvents()
    assert not w.empty_hint.isVisible() and w.image.isVisible() and w.transport.isVisible() and w.boundary_box.isVisible() and not w.empty_panel.isVisible()
    w.show_frame(5);w.set_start();assert w.start_button.text()=='Start · 0.500 s' and w.start_clear.isVisible() and '00:00.500<' in w.position.text() and 'frame 5<' in w.position.text()
    assert w.save_state.text()=='Saving…'
    wait_until(app,lambda:not w.autosave_timer.isActive())
    saved=load(w.label_path);assert saved['start']['frame']==5 and w.label_path.parent==w.project.labels and w.save_state.text()=='✓ Saved' and not w.dirty()
    w.show_frame(9);w.set_start();assert w.flush_autosave() and load(w.label_path)['start']['frame']==9  # switching videos flushes at once
    w.close()

def test_drop_adds_videos_and_routes_project_files(tmp_path,monkeypatch):
    app,w=window(tmp_path,monkeypatch);added=[];projects=[]
    monkeypatch.setattr(w,'add_videos',lambda paths:added.extend(paths));monkeypatch.setattr(w,'show_projects',lambda action=None:projects.append(action))
    data=QMimeData();data.setUrls([QUrl.fromLocalFile(str(tmp_path/'a.MOV')),QUrl.fromLocalFile(str(tmp_path/'notes.txt')),QUrl.fromLocalFile(str(tmp_path/'event.climbproject'))])
    event=QDropEvent(QPointF(10,10),Qt.DropAction.CopyAction,data,Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier);w.dropEvent(event)
    assert added==[str(tmp_path/'a.MOV')] and projects==[('import_path',tmp_path/'event.climbproject')] and w.settings.value('videos_folder')==str(tmp_path)
    w.close()

def test_leaderboard_gaps_sorting_and_detail(tmp_path,monkeypatch):
    app,w=window(tmp_path,monkeypatch);index=synthetic(tmp_path/'v.mkv',80);times=[n/10 for n in range(80)]
    def point(frame):return {'frame':frame,'pts':index['pts'][frame],'seconds':times[frame]}
    for name,arrival,outcome in (('Anna',30,'completed'),('Ben',20,'failed'),('Cleo',25,'failed')):
        path=tmp_path/f'{name}.mkv';path.write_bytes((tmp_path/'v.mkv').read_bytes())
        d=empty_labels({**index['source'],'file':path.name});d.update(climber=name,start=point(0),end=point(70),outcome=outcome)
        d['checkpoints']=[{'id':name,'name':'Roof','point':point(arrival)}]
        d['events']=[{'id':name+'c','kind':'clip','hand':'left','target':1,'start':point(5),'end':point(8),'confidence':1,'notes':'','clip_method':'mouth'}]
        if name!='Anna':d['events'].append({'id':name+'r','kind':'rest','hand':'right','target':None,'start':point(30),'end':point(30+arrival//5),'confidence':1,'notes':''})
        w.workspace.remember(path,d)
    w.refresh_collection();t=w.comparison_table
    headers=[t.horizontalHeaderItem(c).text() for c in range(t.columnCount())]
    assert headers==['Athlete','Result','Climb','Recovery','Clips','Clip method','Roof']
    cells={t.item(r,0).text():[t.item(r,c).text() for c in range(t.columnCount())] for r in range(t.rowCount())}
    assert cells['Ben'][6]=='2.0 s · fastest' and cells['Anna'][6]=='3.0 s · +1.0' and cells['Cleo'][4]=='1 · 0.3 s avg' and cells['Cleo'][5]=='1 mouth' and cells['Anna'][3]=='—' and cells['Ben'][3]=='5.7 %'
    t.sortItems(6);assert [t.item(r,0).text() for r in range(3)]==['Ben','Cleo','Anna']
    assert w.comparison_summary(0)['athlete']=='Ben'
    t.selectRow(2);assert w.comparison_activity_table.rowCount()==1 and w.comparison_activity_table.item(0,3).text()=='Rope to mouth' and 'Anna' in w.comparison_detail_title.text()
    w.show_view(w.comparison_charts);app.processEvents()
    from PySide6.QtSvgWidgets import QSvgWidget
    svgs=w.comparison_charts.scroll.widget().findChildren(QSvgWidget);assert svgs and all(s.width()<=600 for s in svgs)
    w.close()

def test_side_by_side_frame_step_and_library_button(tmp_path,monkeypatch):
    app,w=window(tmp_path,monkeypatch)
    for name,start in (('a.mkv',3),('b.mkv',7)):
        path=tmp_path/name;index=synthetic(path);d=empty_labels(index['source']);d['start']={'frame':start,'pts':index['pts'][start],'seconds':start/10};w.workspace.remember(path,d)
    w.show_view(w.sync_view);wait_until(app,lambda:len(w.sync_view.tiles)==2)
    assert abs(w.sync_view.frame_seconds()-.1)<1e-9;w.sync_view.step_frames(2);assert [t.wanted for t in w.sync_view.tiles]==[5,9]
    w.show_view(w.library);wait_until(app,lambda:len(w.library.meta)==2)
    assert not w.library.buttons['recommended'].isEnabled() and w.library.buttons['recommended'].text()=='Nothing to prepare'
    w.close()
