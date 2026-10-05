"""Plain manual measurements and one offline comparison document."""
import csv
from pathlib import Path
from .labels import validate, load, length, union, rest_breakdown
from .report import esc
from .version import APP_NAME,__version__


def rows(documents):
    overview, points, holds = [], [], []
    for d in documents:
        validate(d)
        identity = dict(athlete=d['climber'], attempt=d['attempt'], video=d['source']['file'])
        start = d['start']['seconds'] if d['start'] else None
        end = d['end']['seconds'] if d['end'] else None
        contacts = [e for e in d['events'] if e['kind']=='contact']
        totals = {hand: sum(max(0,min(e['end']['seconds'],end)-max(e['start']['seconds'],start)) for e in contacts if e['hand']==hand) if start is not None and end is not None and any(e['hand']==hand for e in contacts) else None for hand in ('left','right')}
        overview.append({**identity,'outcome':{'failed':'Fell / failed','completed':'Topped'}.get(d['outcome'],d['outcome']),'climb_seconds':end-start if start is not None and end is not None else None,'start_video_seconds':start,'end_video_seconds':end,'left_marked_hold_seconds':totals['left'],'right_marked_hold_seconds':totals['right'],'closed_hold_intervals':len(contacts),'unfinished_intervals':len(d['open_events']),'status':'unfinished holds' if d['open_events'] else 'boundaries missing' if start is None or end is None else 'marked measurements'})
        summary=overview[-1]
        for kind in ("rest","clip","chalk"):
            intervals=[(max(start,e["start"]["seconds"]),min(end,e["end"]["seconds"])) for e in d["events"] if e["kind"]==kind and e["end"]["seconds"]>start and e["start"]["seconds"]<end] if start is not None and end is not None else []
            marked=any(e["kind"]==kind for e in d["events"])
            total=length(intervals) if marked and start is not None and end is not None else None
            summary[kind+"_marked_seconds"]=total
            summary[kind+"_marked_count"]=len(union(intervals)) if kind=="rest" and total is not None else len(intervals) if total is not None else None
        climb_clips=[e for e in d["events"] if e["kind"]=="clip" and start is not None and end is not None and e["end"]["seconds"]>start and e["start"]["seconds"]<end]
        methods=[e.get("clip_method") for e in climb_clips]
        for method in ("mouth","direct"):summary["clip_"+method+"_count"]=methods.count(method) if any(methods) else None
        summary["marked_rest_share"]=summary["rest_marked_seconds"]/summary["climb_seconds"] if summary["rest_marked_seconds"] is not None else None
        summary["seconds_outside_marked_rests"]=summary["climb_seconds"]-summary["rest_marked_seconds"] if summary["rest_marked_seconds"] is not None else None
        for kind in ('rest','clip','chalk'):
            for hand in ('left','right'):
                hand_events=[e for e in d['events'] if e['kind']==kind and e['hand']==hand]
                hand_intervals=[(max(start,e['start']['seconds']),min(end,e['end']['seconds'])) for e in hand_events if e['end']['seconds']>start and e['start']['seconds']<end] if start is not None and end is not None else []
                summary[hand+'_'+kind+'_marked_seconds']=length(hand_intervals) if hand_events and start is not None and end is not None else None
        summary.update(rest_breakdown(d))
        summary["seconds_outside_marked_rests"]=summary["climb_seconds"]-summary["total_rest_marked_seconds"] if summary["total_rest_marked_seconds"] is not None else None
        previous = start
        for p in sorted(d.get('checkpoints',[]),key=lambda p:p['point']['seconds']):
            t=p['point']['seconds']
            inside=start is not None and t>=start and (end is None or t<=end)
            points.append({**identity,'point':p['name'],'comment':p.get('comment',''),'arrival_video_seconds':t,'arrival_frame':p['point']['frame'],'seconds_from_climb_start':t-start if inside else None,'seconds_from_previous_point':t-previous if inside and previous is not None else None,'seconds_from_point_to_climb_end':end-t if inside and end is not None else None,'status':'marked' if inside else 'outside climb or start missing'})
            if inside: previous=t
        for e in contacts:
            a,b=e['start']['seconds'],e['end']['seconds']
            holds.append({**identity,'hand':e['hand'],'hold':e['target'],'grab_video_seconds':a,'release_video_seconds':b,'duration_seconds':b-a,'grab_from_climb_start_seconds':a-start if start is not None else None,'grab_frame':e['start']['frame'],'release_frame':e['end']['frame'],'status':'closed'})
        for e in d['open_events']:
            if e['kind']=='contact':
                holds.append({**identity,'hand':e['hand'],'hold':e['target'],'grab_video_seconds':e['start']['seconds'],'release_video_seconds':None,'duration_seconds':None,'grab_from_climb_start_seconds':e['start']['seconds']-start if start is not None else None,'grab_frame':e['start']['frame'],'release_frame':None,'status':'unfinished'})
    return overview,points,holds


def export_comparison(documents,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    from .analytics import patterns,matched_clips,between_clips
    hand_rows=[patterns(d) for d in documents]
    for row in hand_rows:
        allocation=row.pop('allocation')
        row.update({k+'_allocation_seconds':allocation[k] if allocation and (k not in ('clip','rest','chalk') or row[k+'_labelled']) else None for k in ('clip','rest','chalk','overlap','unclassified')})
    splits=between_clips(documents)
    matched=matched_clips(documents)
    for suffix,data,defaults in [('hand-patterns',hand_rows,['athlete','clip_sequence']),('matched-clips',matched,['athlete','quickdraw','hand','duration_seconds']),('between-clips',splits,['athlete','from_quickdraw','to_quickdraw','gap_seconds'])]:
        with path.with_name(path.stem+'-'+suffix+'.csv').open('w',newline='',encoding='utf-8-sig') as target:
            writer=csv.DictWriter(target,fieldnames=list(data[0]) if data else defaults);writer.writeheader();writer.writerows(data)
    groups=list(rows(documents))
    activities=[]
    for d in documents:
        for e in d['events']+d['open_events']:
            if e['kind'] not in ('rest','clip','chalk'):continue
            end=e.get('end');start=e['start'];climb_start=d['start']['seconds'] if d['start'] else None
            activities.append(dict(athlete=d['climber'],attempt=d['attempt'],video=d['source']['file'],activity=e['kind'],hand=e['hand'],quickdraw=e['target'],clip_method=e.get('clip_method') if e['kind']=='clip' else None,start_from_climb_seconds=start['seconds']-climb_start if climb_start is not None else None,end_from_climb_seconds=end['seconds']-climb_start if end and climb_start is not None else None,start_video_seconds=start['seconds'],end_video_seconds=end['seconds'] if end else None,duration_seconds=end['seconds']-start['seconds'] if end else None,start_frame=start['frame'],end_frame=end['frame'] if end else None,status='closed' if end else 'unfinished'))
    groups.append(activities)
    headings=('Athlete overview','Arrival at named points','Every hand / hold interval','Rest, clipping and chalking intervals')
    defaults=(['athlete','attempt','climb_seconds'],['athlete','point','seconds_from_climb_start'],['athlete','hand','hold','duration_seconds'],['athlete','activity','duration_seconds'])
    sections=[]
    for title,data,fields,suffix in zip(headings,groups,defaults,('overview','points','holds','activities')):
        fields=list(data[0]) if data else fields
        with path.with_name(path.stem+'-'+suffix+'.csv').open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(data)
        def value(v): return 'Unmarked' if v is None else f'{v:.3f}' if isinstance(v,float) else str(v)
        body=''.join('<tr>'+''.join('<td>'+esc(value(row.get(k)))+'</td>' for k in fields)+'</tr>' for row in data)
        sections.append('<section><h2>'+title+'</h2><div class="scroll"><table><thead><tr>'+''.join('<th>'+esc(k.replace('_',' '))+'</th>' for k in fields)+'</tr></thead><tbody>'+body+'</tbody></table></div></section>')
    fields=['athlete','clip_sequence','clip_hand_switches','observed_transitions','longest_same_hand_clip_run','left_clip_mean_seconds','right_clip_mean_seconds']
    patterns_html='<section><h2>Clipping hand patterns</h2><p>Observed hand choice depends on route geometry and stance. More alternation or less rest is not automatically better. Counts describe marked events only.</p><div class="scroll"><table><tr>'+''.join('<th>'+esc(k.replace('_',' '))+'</th>' for k in fields)+'</tr>'+''.join('<tr>'+''.join('<td>'+esc('Unmarked' if r[k] is None else f'{r[k]:.2f}' if isinstance(r[k],float) else r[k])+'</td>' for k in fields)+'</tr>' for r in hand_rows)+'</table></div></section>'
    sections.append(patterns_html)
    fields=['athlete','from_quickdraw','to_quickdraw','gap_seconds','completion_to_completion_seconds','next_clip_duration_seconds','dedicated_rest_in_gap_seconds','chalk_in_gap_seconds','total_marked_rest_in_gap_seconds','gap_outside_marked_rest_seconds','status']
    sections.append('<section><h2>Between-clip splits</h2><p>Gap = previous clip completion to next clip start. Completion split = previous clip completion to next clip completion. Combined marked rest merges dedicated rest and chalking without counting overlap twice. Time outside marked rest is unclassified, not measured movement time. Zero rest in a gap means no marked rest there, not verified absence.</p><div class="scroll"><table><tr>'+''.join('<th>'+esc(k.replace('_',' '))+'</th>' for k in fields)+'</tr>'+''.join('<tr>'+''.join('<td>'+esc('Unavailable' if r[k] is None else f'{r[k]:.2f}' if isinstance(r[k],float) else r[k])+'</td>' for k in fields)+'</tr>' for r in splits)+'</table></div></section>')
    names=sorted({p['point'] for p in groups[1]})
    matrix=[]
    for summary in groups[0]:
        matching=[p for p in groups[1] if all(p[k]==summary[k] for k in ('athlete','attempt','video'))]
        matrix.append('<tr><th>'+esc(summary['athlete']+' / '+summary['attempt'])+'</th>'+''.join('<td>'+('<br>'.join(f"{p['seconds_from_climb_start']:.3f} s" for p in matching if p['point']==name and p['seconds_from_climb_start'] is not None) or 'Unmarked')+'</td>' for name in names)+'</tr>')
    matrix='<section><h2>Time to each point · seconds from climb start</h2><div class="scroll"><table><tr><th>Athlete / attempt</th>'+''.join('<th>'+esc(n)+'</th>' for n in names)+'</tr>'+''.join(matrix)+'</table></div></section>'
    path.write_text('<!doctype html><html><head><meta charset="utf-8"><title>All athletes · climbing comparison</title><style>body{font:16px system-ui;background:#edf2f8;color:#172b46;margin:32px}section{background:white;padding:24px;margin:24px 0;border-radius:12px}.scroll{overflow:auto}table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:12px;border-bottom:1px solid #dce4ef;white-space:nowrap}th{background:#eaf0fa}h1{font-size:32px}</style></head><body><h1>All athletes · blue route</h1><p>Human-marked measurements. Climb starts at first grip and ends at the marked fall or top. Hold, rest, clip and chalk totals include only marked intervals within the climb; unmarked time is unknown. Total rest includes dedicated rest and chalking, merged across hands and activities. Dedicated rest and chalk subtotals remain separate; their sum can exceed total rest when they overlap. Total chalking time merges overlapping hands; per-hand chalking durations remain separate. Chalking, clipping and resting may overlap and are reported separately. Time outside marked rests includes clipping and any unmarked rests; it is not a measurement of movement time. Use the same point names across athletes. Repeated arrivals are shown separately.</p>'+f'<p>Generated with {APP_NAME} v{__version__}</p>'+sections[0]+matrix+''.join(sections[1:])+'</body></html>',encoding='utf-8')
    from .report_visuals import charts,STYLE
    def headings_as_spaces(data):return [{k.replace('_',' '):v for k,v in row.items()} for row in data]
    def chart_table(headers,data):
        def display(value):return 'Unmarked' if value is None else f'{value:.2f}' if isinstance(value,float) else str(value)
        return '<div class="scroll"><table><tr>'+''.join('<th>'+esc(h)+'</th>' for h in headers)+'</tr>'+''.join('<tr>'+''.join('<td>'+esc(display(v))+'</td>' for v in row)+'</tr>' for row in data)+'</table></div>'
    graph_sections=charts(headings_as_spaces(groups[0]),headings_as_spaces(groups[1]),headings_as_spaces(activities),lambda title,body:'<section><h2>'+esc(title)+'</h2>'+body+'</section>',chart_table)
    html=path.read_text(encoding='utf-8');html=html.replace('<section>',graph_sections+'<section>',1)
    start=html.index('<style>');stop=html.index('</style>',start)
    html=html[:start]+'<style>'+STYLE+html[stop:];path.write_text(html,encoding='utf-8')
    return path


def load_collection(folder,current=None):
    documents=[load(p) for p in sorted(Path(folder).glob('*.labels.json'))]
    if current:
        documents=[d for d in documents if not (d['source']['sha256']==current['source']['sha256'] and d['attempt']==current['attempt'])]
        documents.append(current)
    return documents
