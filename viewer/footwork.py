"""Reviewed observations, not inferred force, fatigue or movement quality."""
from .labels import union,length

DEFINITION_VERSION='1.0.0'
KINDS={'slip':'Foot slip','both_off':'Both feet off','foot_release':'Intentional foot release'}
INTENTS=('unplanned','intentional','uncertain')

def enable(document):
    if document['schema_version']!='1.4.0':document['schema_version']='1.3.0'
    return document.setdefault('footwork',{'definition_version':DEFINITION_VERSION,'events':[],'coverage':[],'pending':None,'fall_onset':None})

def intersection(a,b):
    return union((max(x,c),min(y,d)) for x,y in a for c,d in b if min(y,d)>max(x,c))

def validate_track(document):
    track=document.get('footwork');points=[]
    if not track:return points
    ids={e['id'] for e in document['events']}|{e['id'] for e in document.get('checkpoints',[])}
    for e in track['events']:
        if e['id'] in ids:raise ValueError('Duplicate observation ID')
        ids.add(e['id']);points.append(e['start'])
        if e['kind']=='slip' and e['intent']=='intentional':raise ValueError('Intentional foot releases are not slips; use foot_release')
        if e['kind']=='foot_release' and e['intent']!='intentional':raise ValueError('Intentional releases require intentional intent')
        if e['kind']=='both_off':
            if e['limb']!='both' or e['end'] is None:raise ValueError('Both feet off requires both feet and an end')
            if e['end']['frame']<=e['start']['frame'] or e['end']['seconds']<=e['start']['seconds']:raise ValueError('Footwork interval must end after it starts')
            points.append(e['end'])
        elif e['end'] is not None:raise ValueError('Foot slips are point observations')
    episodes=sorted((e for e in track['events'] if e['kind']=='both_off'),key=lambda e:e['start']['seconds'])
    if any(b['start']['seconds']<a['end']['seconds'] for a,b in zip(episodes,episodes[1:])):raise ValueError('Both-feet-off intervals must not overlap; edit the existing interval')
    coverage=sorted(track['coverage'],key=lambda e:e['start']['seconds'])
    for e in coverage:
        if e['end']['frame']<=e['start']['frame'] or e['end']['seconds']<=e['start']['seconds']:raise ValueError('Coverage interval must end after it starts')
        if e['id'] in ids:raise ValueError('Duplicate coverage ID')
        ids.add(e['id']);points.extend((e['start'],e['end']))
    if any(b['start']['seconds']<a['end']['seconds'] for a,b in zip(coverage,coverage[1:])):raise ValueError('Coverage intervals must not overlap')
    if track.get('pending'):points.append(track['pending']['start'])
    if track.get('fall_onset'):points.append(track['fall_onset'])
    return points

def metrics(document):
    result={k:None for k in ('analysis_seconds','reviewed_seconds','coverage_share','confirmed_slips','both_off_seconds','both_off_share','intentional_seconds','unplanned_seconds','uncertain_seconds')}
    track=document.get('footwork',{});events=track.get('events',[])
    result.update(candidate_slips=sum(e['kind']=='slip' for e in events),fall_review_needed=document['outcome']=='failed' and not track.get('fall_onset'),pending=bool(track.get('pending')))
    start,end=document['start'],document['end']
    if not start or not end:return result
    a,b=start['seconds'],end['seconds'];fall=track.get('fall_onset') if document['outcome']=='failed' else None
    if fall:b=min(b,fall['seconds'])
    if b<=a:return result
    valid=intersection([(a,b)],[(c['start']['seconds'],c['end']['seconds']) for c in track.get('coverage',[]) if c['state']=='reviewed'])
    covered=length(valid);result.update(reviewed_seconds=covered,coverage_share=covered/(b-a),analysis_seconds=b-a)
    # Without an observed fall onset, flight could pollute both the numerator and denominator.
    if not covered or result['fall_review_needed']:return result
    def visible(t):return any(x<=t<y for x,y in valid)
    slips=[e for e in events if e['kind']=='slip' and a<=e['start']['seconds']<b]
    result['confirmed_slips']=sum(e['status']=='confirmed' and e['intent']=='unplanned' and visible(e['start']['seconds']) for e in slips)
    result['candidate_slips']=sum(not (e['status']=='confirmed' and e['intent']=='unplanned' and visible(e['start']['seconds'])) for e in slips)
    reviewed=[e for e in events if e['kind']=='both_off' and e['status']=='confirmed']
    totals={intent:length(intersection(valid,[(e['start']['seconds'],e['end']['seconds']) for e in reviewed if e['intent']==intent])) for intent in INTENTS}
    pending=track.get('pending')
    unresolved=any(e['kind']=='both_off' and e['status']!='confirmed' and intersection(valid,[(e['start']['seconds'],e['end']['seconds'])]) for e in events) or bool(pending and any(y>pending['start']['seconds'] for x,y in valid))
    if unresolved:return result
    total=sum(totals.values());result.update(both_off_seconds=total,both_off_share=total/covered,**{k+'_seconds':v for k,v in totals.items()})
    return result


def observations(document):
    """A common evidence index for footwork, hand intervals and checkpoint comments."""
    result=[dict(e,label=KINDS[e['kind']]) for e in document.get('footwork',{}).get('events',[])]
    for e in document['events']:
        result.append(dict(e,label=e['kind'].capitalize(),limb=e['hand'],status='marked',intent='not reviewed',observation=e['notes'],interpretation='',action=''))
    for p in document.get('checkpoints',[]):
        result.append(dict(id=p['id'],kind='checkpoint',label=p['name'],limb='none',start=p['point'],end=None,status='marked',intent='not reviewed',observation=p.get('comment',''),interpretation='',action=''))
    return sorted(result,key=lambda e:e['start']['seconds'])
