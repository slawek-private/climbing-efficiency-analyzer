import pytest
from viewer.analytics import patterns,matched_clips
from viewer.labels import empty_labels
from viewer.test_manual import source,point,event

def test_hand_sequence_and_opportunities():
    d=empty_labels(source());d.update(start=point(1),end=point(20))
    d['events']=[event('clip',hand,2+i*2,3+i*2,i+1) for i,hand in enumerate(['right']*5+['left']*2+['right'])]
    p=patterns(d);assert p['clip_hand_switches']==2 and p['observed_transitions']==7
    assert p['longest_same_hand_clip_run']==5 and p['right_clip_count']==6 and p['left_clip_count']==2
    assert p['right_clip_share']==.75 and p['left_chalk_count'] is None
    assert matched_clips([d])[0]['end_from_climb_seconds']==2

def test_allocation_does_not_double_count_overlap():
    d=empty_labels(source());d.update(start=point(1),end=point(11));d['events']=[event('clip','left',2,6,1),event('rest','right',4,8),event('chalk','left',5,7)]
    a=patterns(d)['allocation'];assert sum(a.values())==10
    assert a==dict(clip=2,rest=1,chalk=0,overlap=3,unclassified=4)

def test_missing_boundaries_and_unassigned_hand():
    d=empty_labels(source());d['events']=[event('rest','none',2,4)]
    p=patterns(d);assert p['allocation'] is None and p['left_rest_seconds'] is None and p['left_rest_count'] is None
    assert p['clip_hand_switches'] is None


def test_between_clip_splits_and_overlapping_recovery():
    from viewer.analytics import between_clips
    d=empty_labels(source());d.update(start=point(1),end=point(20))
    d['events']=[event('clip','left',2,4,1),event('rest','left',5,10),event('chalk','left',7,9),event('clip','right',12,15,2)]
    r=between_clips([d])[0]
    assert r['gap_seconds']==8 and r['completion_to_completion_seconds']==11
    assert r['next_clip_duration_seconds']==3 and r['total_marked_rest_in_gap_seconds']==5
    assert r['chalk_in_gap_seconds']==2 and r['gap_outside_marked_rest_seconds']==3
    assert r['previous_completion_from_climb_seconds']==3
    d['events']=[event('clip','left',2,8,1),event('clip','right',6,9,2)]
    assert between_clips([d])[0]['gap_seconds'] is None
