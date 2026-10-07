"""Synthetic regressions for event selection, synchronisation and accessible graphs."""
import copy
from PySide6.QtCore import QPoint,QPointF,Qt,QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog,QTreeWidget,QCheckBox
from viewer.test_rebuild import window
from viewer.test_sync_view import synthetic
from viewer.test_playback import wait_until
from viewer.labels import empty_labels,make_event
from viewer.compare_scope import identity


def loaded(tmp_path,monkeypatch):
    app,w=window(tmp_path,monkeypatch);path=tmp_path/'synthetic.mkv';index=synthetic(path,40);w.video_path=path;w.index_ready(index)
    d=copy.deepcopy(w.document());d['start']=w.reader.point(0);d['end']=w.reader.point(39);d['outcome']='completed'
    for kind,hand,frame,note in [('clip','left',2,'roof'),('rest','right',8,'stance'),('chalk','left',15,'roof')]:
        d['events'].append(make_event(dict(kind=kind,hand=hand,target=1 if kind=='clip' else None,start=w.reader.point(frame),confidence=1,notes=note),w.reader.point(frame+2)))
    assert w.commit(d)
    return app,w


def test_filtered_event_actions_preserve_identity_and_reports(tmp_path,monkeypatch):
    app,w=loaded(tmp_path,monkeypatch);before=copy.deepcopy(w.document())
    w.event_kind.setCurrentIndex(w.event_kind.findData('chalk'));w.event_hand.setCurrentIndex(w.event_hand.findData('left'));w.event_search.setText('roof')
    assert len(w.visible_events)==1 and w.visible_events[0]['kind']=='chalk' and w.document()==before
    chalk_id=w.visible_events[0]['id'];w.table.selectRow(0);w.delete_event()
    assert [e['kind'] for e in w.document()['events']]==['clip','rest'];w.undo();assert w.document()==before
    # A timer's edit action must reveal the intended event even if current filters hide it.
    clip_id=before['events'][0]['id'];w.select_timeline_event(clip_id)
    assert w.visible_events[w.table.currentRow()]['id']==clip_id and w.event_search.text()==''
    assert chalk_id in {e['id'] for e in w.document()['events']}
    w.close()


def test_completeness_has_explicit_scope_and_cancel_is_safe(tmp_path,monkeypatch):
    app,w=loaded(tmp_path,monkeypatch);before=copy.deepcopy(w.document())
    def cancel():
        dialog=app.activeModalWidget();assert isinstance(dialog,QDialog)
        assert not any(c.isVisible() for c in w.review.values())
        for c in dialog.findChildren(QCheckBox):c.setChecked(True)
        dialog.reject()
    QTimer.singleShot(0,cancel);w.check_completeness();assert w.document()==before
    def accept():
        dialog=app.activeModalWidget()
        for c in dialog.findChildren(QCheckBox):c.setChecked(True)
        dialog.accept()
    w.clip_review.answer('direct')
    answered=copy.deepcopy(w.document())
    QTimer.singleShot(0,accept);w.check_completeness();assert all(w.document()['reviewed'].values())
    w.undo();assert w.document()==answered;w.undo();assert w.document()==before;w.close()


def test_exact_athlete_selection_and_shared_read_only_timelines(tmp_path,monkeypatch):
    app,w=loaded(tmp_path,monkeypatch)
    for name,start in [('Second',4),('Third',7)]:
        path=tmp_path/(name+'.mkv');index=synthetic(path,40);d=empty_labels(index['source']);d['climber']=name;
        from viewer import identity as ids
        data=w.workspace.organisation;a=ids.athlete(data,name);ids.assign(d,data,a['id'],data['sessions'][0]['id'],data['routes'][0]['id']);d['start']={'frame':start,'pts':index['pts'][start],'seconds':start/10};w.workspace.remember(path,d)
    w.refresh_collection();w.compare_scope.intent.setCurrentIndex(1);w.compare_scope.set_selection([identity(d) for d in w.workspace.documents()]);w.refresh_comparison();w.show_view(w.sync_view);wait_until(app,lambda:len(w.sync_view.tiles)==3)
    excluded=w.compare_scope.reference.currentData();w.sync_view.seek(.6)
    def select():
        dialog=app.activeModalWidget();listing=dialog.findChild(QTreeWidget)
        for i in range(listing.topLevelItemCount()):
            parent=listing.topLevelItem(i)
            for j in range(parent.childCount()):
                item=parent.child(j);item.setCheckState(0,Qt.CheckState.Unchecked if item.data(0,Qt.ItemDataRole.UserRole)==excluded else Qt.CheckState.Checked)
        dialog.accept()
    QTimer.singleShot(0,select);w.compare_scope.choose_subjects()
    assert len(w.sync_view.tiles)==2 and excluded not in {identity(t.document) for t in w.sync_view.tiles}
    assert w.compare_scope.reference.currentData()!=excluded and abs(w.sync_view.t-.6)<1e-8
    snapshots=[copy.deepcopy(t.document) for t in w.sync_view.tiles];signals=[]
    for tile in w.sync_view.tiles:
        tile.timeline.seek.connect(signals.append);tile.timeline.observationSelected.connect(signals.append)
        assert tile.timeline.read_only
        QTest.mouseClick(tile.timeline,Qt.MouseButton.LeftButton,pos=QPoint(60,52))
    assert signals==[] and [t.document for t in w.sync_view.tiles]==snapshots and abs(w.sync_view.t-.6)<1e-8
    w.sync_view.slider.setValue(900);wait_until(app,lambda:all(t.shown==t.wanted for t in w.sync_view.tiles))
    assert all(abs(t.timeline.position-t.reader.times[t.shown])<1e-8 for t in w.sync_view.tiles)
    assert all(abs(t.timeline.bounds()[0]-t.anchor-w.sync_view.lo)<1e-8 for t in w.sync_view.tiles)
    def clear():
        dialog=app.activeModalWidget();listing=dialog.findChild(QTreeWidget)
        for i in range(listing.topLevelItemCount()):listing.topLevelItem(i).setCheckState(0,Qt.CheckState.Unchecked)
        dialog.accept()
    QTimer.singleShot(0,clear);w.compare_scope.choose_subjects()
    assert w.sync_view.tiles==[] and w.compare_scope.chosen()==[]
    w.close()


def test_missing_comparison_video_fails_once_until_retry(tmp_path,monkeypatch):
    app,w=window(tmp_path,monkeypatch);path=tmp_path/'missing.mkv';index=synthetic(path);d=empty_labels(index['source']);d['start']={'frame':0,'pts':index['pts'][0],'seconds':0.};w.workspace.remember(path,d);path.unlink()
    w.show_view(w.sync_view);wait_until(app,lambda:str(path) in w.sync_view.index_errors and not w.sync_view.worker.isRunning())
    app.processEvents();assert 'Cannot open: missing.mkv' in w.sync_view.note.text()
    worker=w.sync_view.worker;w.sync_view.load();assert w.sync_view.worker is worker
    w.close()


def test_graph_and_timeline_hovers_identify_data_without_colour(tmp_path,monkeypatch):
    from viewer.charts import ResponsiveChart
    from viewer.dashboard import AllocationChart
    app,w=loaded(tmp_path,monkeypatch);w.show_frame(10);app.processEvents();scrubber=w.precision_scrubber;scrubber.grab()
    assert 'Current video time' in scrubber.hover_text(scrubber.playhead_rect.center())
    clip_rect,clip=scrubber.event_hits[0];tip=scrubber.hover_text(clip_rect.center())
    assert 'Left' in tip and 'Clip' in tip and '0.200 s' in tip
    w.show_view(w.comparison_charts);app.processEvents();chart=w.comparison_charts.findChildren(ResponsiveChart)[0]
    scale=min(chart.width()/600,chart.height()/chart.base_height);y=(chart.height()-chart.base_height*scale)/2+25*scale
    assert 'Ref · ' in chart.hover_text(y) and 'Arrival at' in chart.hover_text(y)
    assert 'Ref · ' in chart.accessibleDescription()
    w.show_view(w.pattern_dashboard);w.pattern_dashboard.tabs.setCurrentIndex(5);app.processEvents();allocation=w.pattern_dashboard.chart;allocation.grab()
    assert isinstance(allocation,AllocationChart) and allocation.hits
    rect,_=next((r,t) for r,t in allocation.hits if 'rest:' in t)
    assert 'rest: 0.200 s' in allocation.hover_text(rect.center())
    w.close()
