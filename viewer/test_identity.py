"""Synthetic acceptance checks for the approved athlete and clipping flows."""
import copy,json
import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog,QApplication
from viewer import identity
from viewer.labels import empty_labels,validate,save,load,make_event
from viewer.workspace import Workspace
from viewer.test_manual import source,point
from viewer.test_rebuild import window
from viewer.test_sync_view import synthetic


def collection():
    data=identity.empty();a=identity.athlete(data,'Alex','Alpine',['Alpine']);b=identity.athlete(data,'Alex','Valley',['Valley'])
    training=identity.session(data,'Practice',day='2026-10-07',team='Alpine');older=identity.session(data,'Practice',day='2026-10-01')
    event=identity.session(data,'Qualifier','competition','2026-10-03',event='Autumn Open',round_name='Qualifier')
    route=identity.route(data,'Blue','set 2026-09-25');reset=identity.route(data,'Blue','set 2026-09-25')
    docs=[]
    for athlete,session,r in [(a,training,route),(a,older,route),(b,training,route),(a,event,route),(a,training,reset)]:
        d=empty_labels(source());identity.assign(d,data,athlete['id'],session['id'],r['id']);d.update(start=point(1),end=point(11),outcome='completed');docs.append(d)
    return data,docs


def test_identity_does_not_merge_names_or_route_versions_and_import_conflicts():
    data,docs=collection();assert docs[0]['assignment']['athlete']['id']!=docs[2]['assignment']['athlete']['id']
    assert identity.route_key(docs[0])!=identity.route_key(docs[4]);before=copy.deepcopy(docs[0]['source'])
    data['athletes'][0]['name']='Alex renamed';identity.refresh(docs[0],data);assert docs[0]['climber']=='Alex renamed · Alpine' and docs[0]['source']==before
    other=identity.empty();identity.register(other,docs[0]);assert other['athletes'][0]['id']==data['athletes'][0]['id']
    bad=copy.deepcopy(docs[0]);bad['assignment']['route']['version']='different reset'
    with pytest.raises(ValueError,match='Conflicting route'):identity.register(other,bad)


def test_session_scope_reference_and_explicit_team_selection():
    from viewer.compare_scope import CompareScope,identity as key
    app=QApplication.instance() or QApplication([]);data,docs=collection();scope=CompareScope()
    scope.set_context(data,data['sessions'][0]['id'],docs[0]);scope.set_documents(docs)
    assert [key(d) for d in scope.chosen()]==[key(docs[0])]
    scope.history.setChecked(True);assert {key(d) for d in scope.chosen()}=={key(docs[0]),key(docs[1])}
    scope.intent.setCurrentIndex(1);assert not scope.chosen();scope.set_selection([key(docs[0]),key(docs[2])]);assert len(scope.chosen())==2
    scope.reference.setCurrentIndex(1);assert key(scope.chosen()[0])==key(docs[2])
    scope.team.setCurrentIndex(scope.team.findData('Valley'));assert not scope.chosen();assert scope.candidates()==[docs[2]]
    scope.set_selection([key(docs[0]),key(docs[2])]);assert scope.chosen()==[docs[2]]
    scope.set_context(data,data['sessions'][2]['id'],docs[3]);scope.set_documents(docs);assert not scope.chosen()
    scope.set_selection([key(docs[3])]);assert scope.chosen()==[docs[3]];scope.close()


def test_old_work_migration_backup_and_identity_round_trip(tmp_path):
    file=tmp_path/'workspace.json';d=empty_labels(source());old={'version':2,'videos':[str(tmp_path/'a.mov')],'states':{str(tmp_path/'a.mov'):{'document':d,'frame':3,'label_path':None}}}
    file.write_text(json.dumps(old));original=file.read_bytes();w=Workspace(file);assert not identity.assigned(w.documents()[0]);w.save()
    assert file.with_suffix('.v2-backup.json').read_bytes()==original
    data,docs=collection();label=tmp_path/'a.labels.json';save(d,label);before=label.read_bytes();identity.assign(d,data,data['athletes'][0]['id'],data['sessions'][0]['id'],data['routes'][0]['id']);save(d,label)
    assert label.with_name(label.stem+'.pre-identity-backup.json').read_bytes()==before
    w.remember(tmp_path/'a.mov',d,label);w.save();restored=Workspace(file);assert restored.documents()[0]['assignment']==load(label)['assignment'] and restored.documents()[0]['source']==old['states'][str(tmp_path/'a.mov')]['document']['source']


def test_methods_unknown_unanswered_and_gaps_are_distinct(tmp_path):
    data,docs=collection();d=docs[0]
    d['events']=[make_event(dict(kind='clip',hand='left',target=i,start=point(i+1),confidence=1,notes=''),point(i+2)) for i in range(1,5)]
    d['events'][0]['clip_method']='mouth';d['events'][1]['clip_method']='direct';d['events'][2].update(clip_method='unknown',clip_reason='hidden');validate(d)
    assert len(identity.unanswered(d))==1 and identity.method_counts(d)['classifiable']==2
    d['clip_gaps']=[dict(id='gap',target=2,point=point(7),visibility='partial',notes='Beginning is off camera')];validate(d)
    assert identity.method_counts(d)['classifiable']==1
    from viewer.comparison import rows
    summary=rows([d])[0][0];assert summary['clip_direct_count']==0 and summary['clip_mouth_count']==1 and summary['clip_classifiable_count']==1
    from viewer.reporting import records,context_html
    assert records([d])[0]['clips']['2'] is None and 'DRAFT' in context_html([d]) and 'Visibility gaps: 1' in context_html([d])
    from viewer.comparison import export_comparison
    export_comparison([d],tmp_path/'draft.html');assert 'Cannot tell' in (tmp_path/'draft.html').read_text() or 'cannot tell' in (tmp_path/'draft.html').read_text()


def test_new_analysis_requires_assignment_but_old_timer_can_stop(tmp_path,monkeypatch):
    app,w=window(tmp_path,monkeypatch,assigned=False);p=tmp_path/'unassigned.mkv';w.video_path=p;w.index_ready(synthetic(p,40));w.show_frame(1);w.set_start();assert w.document()['start'] is None
    d=copy.deepcopy(w.document());d['open_events']=[dict(kind='clip',hand='left',target=1,start=w.reader.point(0),confidence=1,notes='')];w.commit(d);w.toggle_hand_timer('clip','left');assert len(w.document()['events'])==1 and not w.document()['open_events']
    assert w.autosave();w.close()


def test_intake_bulk_assignment_and_concurrent_clip_decisions(tmp_path,monkeypatch):
    from viewer.context_ui import AssignmentDialog
    app,w=window(tmp_path,monkeypatch);p=tmp_path/'a.mkv';w.video_path=p;w.index_ready(synthetic(p,40));data=w.workspace.organisation
    dialog=AssignmentDialog(w,[(str(p),None),(str(tmp_path/'b.mkv'),None)])
    assert not dialog.save_button.isEnabled();dialog.bulk.setCurrentIndex(1);dialog.bulk_assign();assert not dialog.save_button.isEnabled()
    for r in dialog.routes:r.setCurrentIndex(1)
    assert dialog.save_button.isEnabled();dialog.accept_assignments();assert len(dialog.result_assignments)==2;dialog.close()
    w.show_frame(1);w.toggle_hand_timer('clip','left');w.draw.setValue(2);w.toggle_hand_timer('clip','right');w.show_frame(5);w.toggle_hand_timer('clip','left');w.toggle_hand_timer('clip','right')
    assert len(identity.unanswered(w.document()))==2
    first,second=w.document()['events'];w.clip_review.event_id=first['id'];w.clip_review.answer('mouth');assert w.clip_review.buttons['mouth'].isChecked()
    w.clip_review.event_id=second['id'];w.clip_review.refresh(w.document());assert not any(b.isChecked() for b in w.clip_review.buttons.values());w.clip_review.answer('unknown')
    assert len(identity.unanswered(w.document()))==1
    w.clip_review.reason.setCurrentIndex(w.clip_review.reason.findData('hidden'));assert not identity.unanswered(w.document())
    assert w.document()['events'][0]['clip_method']=='mouth' and w.document()['events'][1]['clip_method']=='unknown';w.undo();assert len(identity.unanswered(w.document()))==1;w.redo();assert not identity.unanswered(w.document());assert w.autosave();w.close()


def test_new_attempt_confirms_identity_and_preserves_one_recording_history(tmp_path,monkeypatch):
    from viewer.context_ui import AssignmentDialog
    app,w=window(tmp_path,monkeypatch);p=tmp_path/'long.mkv';index=synthetic(p,40);w.video_path=p;w.index_ready(index);first=w.document()['attempt_id'];before=copy.deepcopy(w.document()['source'])
    b=identity.athlete(w.workspace.organisation,'Nina')
    def confirm():
        dialog=app.activeModalWidget();assert isinstance(dialog,AssignmentDialog);dialog.athletes[0].setCurrentIndex(dialog.athletes[0].findData(b['id']));dialog.accept_assignments()
    QTimer.singleShot(0,confirm);w.new_attempt();assert w.document()['attempt_id']!=first and w.document()['climber']=='Nina' and w.document()['source']==before
    assert len(w.workspace.documents())==2 and len(w.workspace.videos)==1
    assert w.autosave();w.reader.close();w.reader=None;w.session_histories={};w.workspace=Workspace(w.workspace.path);w.index_ready(index)
    assert w.document()['climber']=='Nina' and len(w.workspace.documents())==2;w.close()


def test_selected_import_identity_is_not_overridden_by_discovered_labels(tmp_path,monkeypatch):
    from viewer.test_playback import wait_until
    app,w=window(tmp_path,monkeypatch,assigned=False);p=tmp_path/'source.mkv';index=synthetic(p,40)
    data=w.workspace.organisation;a=identity.athlete(data,'First');b=identity.athlete(data,'Second');s=identity.session(data,'Training',day='2026-10-07');r=identity.route(data,'Route','version 1')
    old=empty_labels(index['source']);identity.assign(old,data,a['id'],s['id'],r['id']);old['start']={'frame':1,'pts':index['pts'][1],'seconds':.1}
    label=w.project.labels/'old.labels.json';save(old,label);original=label.read_bytes()
    w.workspace.assignments[str(p.resolve())]={'athlete':b['id'],'session':s['id'],'route':r['id']};w.video_path=p;w.index_ready(index)
    assert w.document()['climber']=='Second' and w.document()['start'] is None and w.document()['attempt_id']!=old['attempt_id']
    assert w.workspace.attempts[0]['state']['document']['climber']=='First' and label.read_bytes()==original
    assert str(p.resolve()) not in w.workspace.assignments
    other=tmp_path/'other.mkv';other.write_bytes(p.read_bytes());w.workspace.assignments[str(other.resolve())]={'athlete':b['id'],'session':s['id'],'route':r['id']}
    monkeypatch.setattr('viewer.simple.matching_labels',lambda *args:[]);w.autosave();w.begin_video(other);wait_until(app,lambda:w.reader is not None and not w.worker.isRunning())
    assert w.document()['attempt']=='2';w.close()


def test_portable_project_keeps_ids_and_queued_assignments(tmp_path):
    from viewer import projects
    data,docs=collection();project=projects.create(tmp_path/'root','Synthetic project');video=tmp_path/'source.mov';video.write_bytes(b'synthetic placeholder')
    ws=Workspace(project.workspace_file);ws.organisation=data;ws.remember(video,docs[0]);ws.assignments[str(video.resolve())]={'athlete':data['athletes'][0]['id'],'session':data['sessions'][0]['id'],'route':data['routes'][0]['id']};ws.session_id=data['sessions'][0]['id'];ws.save()
    archive=projects.export_project(project,tmp_path/'project.climbproject');restored=Workspace(projects.import_project(tmp_path/'other',archive).workspace_file)
    assert restored.organisation==data and restored.session_id==ws.session_id and restored.documents()[0]['assignment']==docs[0]['assignment']
    assert list(restored.assignments)==restored.videos and not restored.load_error


def test_library_assigns_open_unassigned_video_with_one_confirmation(tmp_path,monkeypatch):
    from viewer.context_ui import AssignmentDialog
    app,w=window(tmp_path,monkeypatch,assigned=False);p=tmp_path/'queued.mkv';w.workspace.add(p);w.video_path=p;w.index_ready(synthetic(p,40));original=copy.deepcopy(w.document()['source'])
    data=w.workspace.organisation;a=identity.athlete(data,'Nina');s=identity.session(data,'Practice',day='2026-10-07');r=identity.route(data,'Blue','set October')
    w.library.render();w.library.table.selectRow(0)
    def confirm():
        dialog=app.activeModalWidget();assert isinstance(dialog,AssignmentDialog)
        for field,key in [(dialog.session,s['id']),(dialog.athletes[0],a['id']),(dialog.routes[0],r['id'])]:field.setCurrentIndex(field.findData(key))
        dialog.accept_assignments()
    QTimer.singleShot(0,confirm);w.library.assign_selected()
    assert w.document()['climber']=='Nina' and w.workspace.session_id==s['id'] and w.document()['source']==original
    assert not w.workspace.assignments;assert w.autosave();w.close()


def test_session_creation_intake_and_review_dialog_gates(tmp_path,monkeypatch):
    from viewer.context_ui import create_session,intake,AssignmentDialog,report_permission
    from PySide6.QtWidgets import QLineEdit,QDialogButtonBox
    app,w=window(tmp_path,monkeypatch,assigned=False)
    def setup():
        dialog=app.activeModalWidget();fields=dialog.findChildren(QLineEdit);fields[0].setText('Clipping practice');dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save).click()
    QTimer.singleShot(0,setup);assert create_session(w);data=w.workspace.organisation;a=identity.athlete(data,'Anonymous · blue shirt');r=identity.route(data,'Route','set 1 Oct')
    def assign_rows():
        dialog=app.activeModalWidget();assert isinstance(dialog,AssignmentDialog);dialog.bulk.setCurrentIndex(1);dialog.bulk_assign()
        for field in dialog.routes:field.setCurrentIndex(1)
        dialog.accept_assignments()
    paths=[tmp_path/'one.mov',tmp_path/'two.mov'];QTimer.singleShot(0,assign_rows);assert intake(w,paths)
    assert len(w.workspace.assignments)==2 and all(v['athlete']==a['id'] for v in w.workspace.assignments.values())
    d=empty_labels(source());QTimer.singleShot(0,lambda:app.activeModalWidget().reject());assert not report_permission(w,[d])
    QTimer.singleShot(0,lambda:app.activeModalWidget().accept());assert report_permission(w,[d]);w.close()
