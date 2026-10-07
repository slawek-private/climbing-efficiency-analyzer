"""Local, portable identities. Names never merge people or route versions."""
import copy
from datetime import date
from uuid import uuid4


def empty():
    return {'athletes': [], 'sessions': [], 'routes': []}


def entry(data, group, identifier):
    return next((item for item in data[group] if item['id'] == identifier), None)


def add(data, group, **values):
    item = {'id': uuid4().hex, **values}
    data[group].append(item)
    return item


def athlete(data, name, label='', teams=()):
    if not name.strip():
        raise ValueError('Enter an athlete name or a descriptive anonymous label.')
    return add(data, 'athletes', name=name.strip(), label=label.strip(), teams=list(teams))


def session(data, name, kind='training', day=None, team='', event='', round_name='', goal=''):
    if not name.strip() or kind not in ('training', 'competition'):
        raise ValueError('Choose Training or Competition and enter a session name.')
    day = day or date.today().isoformat()
    date.fromisoformat(day)
    if kind == 'competition' and (not event.strip() or not round_name.strip()):
        raise ValueError('Competition needs an event and round name.')
    return add(data, 'sessions', name=name.strip(), kind=kind, date=day, team=team.strip(),
               event=event.strip(), round=round_name.strip(), goal=goal.strip())


def route(data, name, version, discipline='lead'):
    if not name.strip() or not version.strip():
        raise ValueError('Enter a route name and version, e.g. its setting date.')
    return add(data, 'routes', name=name.strip(), version=version.strip(), discipline=discipline)


def athlete_label(item):
    return item['name'] + (' · ' + item['label'] if item.get('label') else '')


def route_label(item):
    return item['name'] + ' · ' + item['version']


def session_label(item):
    return ('Competition' if item['kind'] == 'competition' else 'Training') + ' · ' + item['name'] + ' · ' + item['date']


def assigned(document):
    return bool(document and document.get('assignment'))


def assign(document, data, athlete_id, session_id, route_id):
    values = {name: entry(data, group, key) for name, group, key in
              [('athlete', 'athletes', athlete_id), ('session', 'sessions', session_id), ('route', 'routes', route_id)]}
    if not all(values.values()):
        raise ValueError('Choose an athlete, session and route version before analysis.')
    document['schema_version'] = '1.4.0'
    document['assignment'] = copy.deepcopy(values)
    if values['session']['goal'] and not document.get('coaching'):
        document['coaching']={'goal':values['session']['goal'],'reflection':'','action':'','retest':''}
    refresh(document, data)


def refresh(document, data):
    if not assigned(document):
        return
    for name, group in [('athlete', 'athletes'), ('session', 'sessions'), ('route', 'routes')]:
        stored = document['assignment'][name]
        item = entry(data, group, stored['id'])
        if item:
            document['assignment'][name] = copy.deepcopy(item)
            if name=='athlete':document['assignment'][name]['teams']=copy.deepcopy(stored['teams'])
    document['climber'] = athlete_label(document['assignment']['athlete'])
    document['route'] = route_label(document['assignment']['route'])


def register(data, document):
    """Import portable snapshots; reject conflicting context instead of merging by name."""
    if not assigned(document):
        return
    candidate = copy.deepcopy(data)
    immutable = {'athletes': (), 'sessions': ('kind', 'date', 'event', 'round'), 'routes': ('version', 'discipline')}
    for name, group in [('athlete', 'athletes'), ('session', 'sessions'), ('route', 'routes')]:
        item = document['assignment'][name]
        current = entry(candidate, group, item['id'])
        if current and any(current.get(k) != item.get(k) for k in immutable[group]):
            raise ValueError('Conflicting ' + name + ' ID in imported measurements. Import into a separate project to review it.')
        if not current:
            candidate[group].append(copy.deepcopy(item))
    data.update(candidate)


def context(document):
    if not assigned(document):
        return 'Unorganised draft · athlete, session and route need assignment'
    a = document['assignment']
    return session_label(a['session']) + ' / ' + route_label(a['route'])


def next_attempt(documents,athlete_id,session_id,route_id):
    return str(max([int(d['attempt']) for d in documents if d['attempt'].isdigit()
        and d.get('assignment',{}).get('athlete',{}).get('id')==athlete_id
        and d.get('assignment',{}).get('session',{}).get('id')==session_id
        and route_key(d)==route_id]+[0])+1)


def columns(document):
    a=document.get('assignment',{})
    return dict(attempt_id=document.get('attempt_id',''),athlete_id=a.get('athlete',{}).get('id',''),
        session_id=a.get('session',{}).get('id',''),route_id=route_key(document),comparison_scope=report_scope(document),session=context(document))


def timing_visible(document,event):
    return not (event['kind']=='clip' and event['target'] is not None and any(g['target']==event['target'] for g in document.get('clip_gaps',[])))


def route_key(document):
    return document['assignment']['route']['id'] if assigned(document) else 'legacy:' + document['route']


def report_scope(document):
    if not assigned(document):
        return 'legacy:' + document['route']
    a = document['assignment']
    # Competition rounds and training sessions never mix in an offline chooser.
    return ('training' if a['session']['kind']=='training' else a['session']['id']) + ':' + a['route']['id']


def clip_answered(event):
    method = event.get('clip_method')
    return method in ('direct', 'mouth') or (method == 'unknown' and bool(event.get('clip_reason')))


def unanswered(document):
    return [e for e in document['events'] if e['kind'] == 'clip' and not clip_answered(e)]


def review_issues(document):
    issues = []
    if not assigned(document):
        issues.append('Assign athlete, session and route version')
    if not document['start'] or not document['end'] or document['outcome'] == 'unknown':
        issues.append('Mark climb boundaries and result')
    if document['open_events'] or document.get('footwork', {}).get('pending'):
        issues.append('Stop or cancel unfinished timers')
    if unanswered(document):
        issues.append(f'{len(unanswered(document))} clip method(s) need an answer')
    if not document['reviewed'].get('clips') or not document['reviewed'].get('boundaries'):
        issues.append('Confirm boundary and clipping completeness after inspecting the footage')
    return issues


def method_counts(document):
    a = document['start']['seconds'] if document['start'] else None
    b = document['end']['seconds'] if document['end'] else None
    gaps={g['target'] for g in document.get('clip_gaps',[]) if g['target'] is not None}
    clips = [e for e in document['events'] if e['kind'] == 'clip' and e['target'] not in gaps and a is not None and b is not None
             and e['start']['seconds'] >= a and e['end']['seconds'] <= b]
    counts = {key: sum(e.get('clip_method') == key and clip_answered(e) for e in clips) for key in ('mouth', 'direct', 'unknown')}
    counts['unanswered'] = sum(not clip_answered(e) for e in clips)
    counts['classifiable'] = counts['mouth'] + counts['direct']
    counts['gaps'] = len(document.get('clip_gaps', []))
    return counts


def method_summary(document):
    c = method_counts(document)
    if not document['start'] or not document['end']:
        return 'Clip methods: climb boundaries missing'
    if not any(e['kind']=='clip' for e in document['events']) and not document['reviewed'].get('clips'):
        return f"No clips recorded · methods unknown (not evidence of zero clips). Visibility gaps: {c['gaps']} (no duration)."
    return (f"Clips inside climb: {c['direct']} direct · {c['mouth']} two-stage · "
            f"{c['unknown']} cannot tell · {c['unanswered']} answer needed. "
            f"Classifiable-method denominator: {c['classifiable']}. Visibility gaps: {c['gaps']} (no duration).")
