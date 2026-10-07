"""Descriptive hand patterns and time allocation from explicit annotations."""
from statistics import mean,median
from .labels import validate,length,rest_breakdown
from . import identity


def patterns(document):
    validate(document);a=document['start']['seconds'] if document['start'] else None;b=document['end']['seconds'] if document['end'] else None
    events=sorted([e for e in document['events'] if e['kind'] in ('clip','rest','chalk') and identity.timing_visible(document,e) and (a is None or e['end']['seconds']>a) and (b is None or e['start']['seconds']<b)],key=lambda e:e['start']['seconds'])
    clips=[e for e in events if e['kind']=='clip'];sequence=[e['hand'] for e in clips];switches=sum(x!=y for x,y in zip(sequence,sequence[1:]));longest=0;run=0;previous=None
    for hand in sequence:
        run=run+1 if hand==previous else 1;longest=max(longest,run);previous=hand
    result={'athlete':document['climber'],'attempt':document['attempt'],'video':document['source']['file'],'clip_sequence':' → '.join('L' if h=='left' else 'R' for h in sequence) or None,'clip_hand_switches':switches if clips else None,'observed_transitions':max(0,len(clips)-1) if clips else None,'longest_same_hand_clip_run':longest if clips else None,'unfinished_timers':len(document['open_events'])}
    for kind in ('clip','rest','chalk'):
        group=[e for e in events if e['kind']==kind]
        result[kind+'_labelled']=bool(group)
        for hand in ('left','right'):
            marked=[e for e in group if e['hand']==hand];durations=[min(b,e['end']['seconds'])-max(a,e['start']['seconds']) if a is not None and b is not None else e['end']['seconds']-e['start']['seconds'] for e in marked];prefix=hand+'_'+kind
            result[prefix+'_count']=len(marked) if group and (marked or all(e['hand']!='none' for e in group)) else None
            result[prefix+'_seconds']=sum(durations) if marked else 0 if group and all(e['hand']!='none' for e in group) else None
            result[prefix+'_mean_seconds']=mean(durations) if durations else None;result[prefix+'_median_seconds']=median(durations) if durations else None
    result.update(rest_breakdown(document));result.update(identity.columns(document))
    result['right_clip_share']=sequence.count('right')/len(sequence) if sequence else None
    allocation={key:0. for key in ('clip','rest','chalk','overlap','unclassified')}
    if a is None or b is None:result['allocation']=None
    else:
        cuts=sorted({a,b,*[max(a,min(b,e[p]['seconds'])) for e in events for p in ('start','end')]})
        for x,y in zip(cuts,cuts[1:]):
            kinds={e['kind'] for e in events if e['start']['seconds']<(x+y)/2<e['end']['seconds']}
            allocation[next(iter(kinds)) if len(kinds)==1 else 'overlap' if kinds else 'unclassified']+=y-x
        result['allocation']=allocation
    return result


def matched_clips(documents):
    output=[]
    for d in documents:
        gaps={g['target'] for g in d.get('clip_gaps',[]) if g['target'] is not None}
        base=d['start']['seconds'] if d['start'] else None
        for e in sorted(d['events'],key=lambda e:e['start']['seconds']):
            if e['kind']!='clip' or e['target'] in gaps:continue
            if base is not None and e['end']['seconds']<=base:continue
            if d['end'] and e['start']['seconds']>=d['end']['seconds']:continue
            output.append(dict(athlete=d['climber'],attempt=d['attempt'],video=d['source']['file'],quickdraw=e['target'],hand=e['hand'],clip_method=e.get('clip_method'),clip_reason=e.get('clip_reason',''),**identity.columns(d),duration_seconds=e['end']['seconds']-e['start']['seconds'],start_from_climb_seconds=e['start']['seconds']-base if base is not None else None,end_from_climb_seconds=e['end']['seconds']-base if base is not None else None))
    return output


def between_clips(documents):
    answer=[]
    for d in documents:
        validate(d);base=d['start']['seconds'] if d['start'] else None;end=d['end']['seconds'] if d['end'] else None
        clips=sorted([e for e in d['events'] if e['kind']=='clip' and identity.timing_visible(d,e) and (base is None or e['end']['seconds']>base) and (end is None or e['start']['seconds']<end)],key=lambda e:e['start']['seconds'])
        for previous,next_clip in zip(clips,clips[1:]):
            a,b=previous['end']['seconds'],next_clip['start']['seconds'];overlap=b<a
            row=dict(athlete=d['climber'],attempt=d['attempt'],video=d['source']['file'],from_quickdraw=previous['target'],to_quickdraw=next_clip['target'],previous_clip_hand=previous['hand'],next_clip_hand=next_clip['hand'],previous_completion_from_climb_seconds=a-base if base is not None else None,next_clip_start_from_climb_seconds=b-base if base is not None else None,gap_seconds=b-a if not overlap else None,completion_to_completion_seconds=next_clip['end']['seconds']-a if not overlap else None,next_clip_duration_seconds=next_clip['end']['seconds']-b,status='overlapping clips: split unavailable' if overlap else 'marked split')
            def periods(kinds):return [(max(a,e['start']['seconds']),min(b,e['end']['seconds'])) for e in d['events'] if e['kind'] in kinds and e['end']['seconds']>a and e['start']['seconds']<b]
            row.update(identity.columns(d))
            row['dedicated_rest_in_gap_seconds']=length(periods({'rest'})) if not overlap else None
            row['chalk_in_gap_seconds']=length(periods({'chalk'})) if not overlap else None
            row['total_marked_rest_in_gap_seconds']=length(periods({'rest','chalk'})) if not overlap else None
            row['gap_outside_marked_rest_seconds']=b-a-row['total_marked_rest_in_gap_seconds'] if not overlap else None
            answer.append(row)
    return answer
