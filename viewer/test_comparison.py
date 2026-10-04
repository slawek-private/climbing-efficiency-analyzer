import copy
import pytest
from viewer.test_manual import source,point,event
from viewer.labels import empty_labels,save,load,validate
from viewer.comparison import rows,export_comparison,load_collection

def test_points_and_combined_export(tmp_path):
    d=empty_labels(source());d.update(start=point(1),end=point(11),outcome='failed',climber='<Alice>')
    d['checkpoints']=[{'id':'a','name':'A','point':point(4)},{'id':'b','name':'B','point':point(8)}]
    d['events']=[event('contact','left',0,5,1),event('contact','right',8,12,2)]
    overview,points,holds=rows([d])
    assert overview[0]['climb_seconds']==10
    assert overview[0]['left_marked_hold_seconds']==4
    assert overview[0]['right_marked_hold_seconds']==3
    assert [p['seconds_from_climb_start'] for p in points]==[3,7]
    assert [p['seconds_from_previous_point'] for p in points]==[3,4]
    assert holds[0]['duration_seconds']==5
    save(d,tmp_path/'alice.labels.json');assert load(tmp_path/'alice.labels.json')==d
    b=copy.deepcopy(d);b['climber']='Bob';b['attempt']='2';b['checkpoints']=[]
    save(b,tmp_path/'bob.labels.json')
    collection=load_collection(tmp_path,d);assert len(collection)==2
    target=export_comparison(collection,tmp_path/'all.html')
    html=target.read_text();assert '&lt;Alice&gt;' in html and 'Bob' in html and 'Unmarked' in html
    assert len(list(tmp_path.glob('all-*.csv')))==7
    d['checkpoints'][0]['point']['pts']+=1
    with pytest.raises(ValueError):validate(d)

def test_unfinished_is_not_duration():
    d=empty_labels(source());d['open_events']=[{'kind':'contact','hand':'left','target':1,'start':point(2),'confidence':1,'notes':''}]
    overview,points,holds=rows([d]);assert overview[0]['climb_seconds'] is None
    assert holds[0]['duration_seconds'] is None and holds[0]['status']=='unfinished'


def test_rest_clip_totals_and_unfinished_export(tmp_path):
    d=empty_labels(source());d.update(start=point(1),end=point(11),outcome='failed')
    d['events']=[event('rest','none',2,5),event('rest','none',4,7),event('clip','left',4,6,1)]
    d['open_events']=[{'kind':'clip','hand':'right','target':2,'start':point(9),'confidence':1,'notes':''}]
    summary,_,_=rows([d]);s=summary[0]
    assert s['rest_marked_seconds']==5 and s['rest_marked_count']==1
    assert s['marked_rest_share']==.5 and s['seconds_outside_marked_rests']==5
    assert s['clip_marked_seconds']==2 and s['clip_marked_count']==1
    export_comparison([d],tmp_path/'activity.html')
    import csv
    with (tmp_path/'activity-activities.csv').open(encoding='utf-8-sig',newline='') as f:activities=list(csv.DictReader(f))
    assert activities[-1]['status']=='unfinished' and activities[-1]['duration_seconds']==''
    assert activities[0]['start_from_climb_seconds']=='1.0' and activities[0]['end_from_climb_seconds']=='4.0'
    assert activities[-1]['start_from_climb_seconds']=='8.0' and activities[-1]['end_from_climb_seconds']==''


def test_per_hand_rest_overlap_and_schema_compatibility():
    from viewer.labels import validate
    d=empty_labels(source());d.update(start=point(1),end=point(11),outcome='failed')
    d['events']=[event('rest','left',2,6),event('rest','right',4,8),event('clip','left',8,9,1)]
    s=rows([d])[0][0]
    assert s['rest_marked_seconds']==6 and s['rest_marked_count']==1
    assert s['left_rest_marked_seconds']==4 and s['right_rest_marked_seconds']==4
    assert s['left_clip_marked_seconds']==1 and s['right_clip_marked_seconds'] is None
    d['schema_version']='1.0.0'
    with pytest.raises(ValueError):validate(d)
    d['events']=[event('rest','none',2,6)];validate(d)


def test_chalking_timestamps_counts_and_exports(tmp_path):
    import csv
    d=empty_labels(source());d.update(start=point(1),end=point(11),outcome='failed')
    d['events']=[event('chalk','left',2,4),event('chalk','right',3,5),event('chalk','left',7,8)]
    d['open_events']=[{'kind':'chalk','hand':'right','target':None,'start':point(9),'confidence':1,'notes':''}]
    summary=rows([d])[0][0]
    assert summary['chalk_marked_count']==3 and summary['chalk_marked_seconds']==4
    assert summary['left_chalk_marked_seconds']==3 and summary['right_chalk_marked_seconds']==2
    save(d,tmp_path/'chalk.labels.json');assert load(tmp_path/'chalk.labels.json')==d
    export_comparison([d],tmp_path/'chalk.html')
    with (tmp_path/'chalk-activities.csv').open(encoding='utf-8-sig',newline='') as f:r=list(csv.DictReader(f))
    assert r[0]['hand']=='left' and r[0]['start_from_climb_seconds']=='1.0' and r[0]['duration_seconds']=='2.0'
    assert r[-1]['status']=='unfinished' and r[-1]['duration_seconds']==''


def test_chalk_is_rest_without_double_counting():
    d=empty_labels(source());d.update(start=point(1),end=point(11))
    d['events']=[event('rest','left',2,6),event('chalk','left',4,8),event('chalk','right',5,7)]
    s=rows([d])[0][0]
    assert s['rest_marked_seconds']==4 and s['chalk_marked_seconds']==4
    assert s['total_rest_marked_seconds']==6 and s['total_rest_marked_count']==1
    assert s['total_marked_rest_share']==.6 and s['seconds_outside_marked_rests']==4
    assert s['left_total_rest_marked_seconds']==6 and s['right_total_rest_marked_seconds']==2
    d['events']=[event('chalk','left',2,4)]
    s=rows([d])[0][0];assert s['total_rest_marked_seconds']==2 and s['rest_marked_seconds'] is None


def test_timestamped_comments_roundtrip_and_export(tmp_path):
    d=empty_labels(source());d.update(start=point(1),end=point(11),outcome='failed')
    d['checkpoints']=[{'id':'note','name':'Comment','point':point(4),'comment':'Foot slipped <here>\nRetry'}]
    save(d,tmp_path/'notes.labels.json');assert load(tmp_path/'notes.labels.json')==d
    _,points,_=rows([d]);assert points[0]['comment']=='Foot slipped <here>\nRetry'
    assert points[0]['seconds_from_climb_start']==3
    html=export_comparison([d],tmp_path/'notes.html').read_text(encoding='utf-8')
    assert 'Foot slipped &lt;here&gt;' in html
    assert 'Foot slipped <here>' in (tmp_path/'notes-points.csv').read_text(encoding='utf-8-sig')
