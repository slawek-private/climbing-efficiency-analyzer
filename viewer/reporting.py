"""Shared presentation of recorded timing and explicitly checked footwork.

No new measurements: eligibility and labels are shared by native, HTML and PDF views.
"""
from html import escape
import json
from .labels import rest_breakdown, length
from .footwork import metrics, intersection
from . import identity

HEADERS=['Athlete / attempt','Result','Climb time','Checkpoint arrival','Recorded recovery','Footwork checked']
LIMITS='Missing is unknown. Recovery merges rest and chalking once; other time is unclassified. Footwork counts apply only to checked, visible footage. Timing does not explain a fall.'

def shown(value,unit=' s'):
    return 'Unknown' if value is None else str(value)+(unit[:-1] if value==1 and unit.strip() in ('slips','candidates','confirmed slips') else unit) if isinstance(value,int) and unit.strip() in ('slips','candidates','confirmed slips') else f'{value:.2f}{unit}'

def records(documents):
    result=[]
    for i,d in enumerate(documents):
        start,end=d['start'],d['end'];a=start['seconds'] if start else None;b=end['seconds'] if end else None
        duration=b-a if a is not None and b is not None else None
        arrivals={'Climb start':0.0 if start else None}
        for name in {p['name'] for p in d.get('checkpoints',[])}:
            hits=[p['point']['seconds']-a for p in d['checkpoints'] if p['name']==name and a is not None and p['point']['seconds']>=a and (b is None or p['point']['seconds']<=b)]
            arrivals[name]=hits[0] if len(hits)==1 else None
        pending={e['kind'] for e in d['open_events']}
        clips={}
        gaps={g['target'] for g in d.get('clip_gaps',[]) if g['target'] is not None}
        for draw in {e['target'] for e in d['events'] if e['kind']=='clip' and e['target'] is not None}:
            hits=[e for e in d['events'] if e['kind']=='clip' and e['target']==draw and a is not None and b is not None and e['start']['seconds']>=a and e['end']['seconds']<=b]
            clips[str(draw)]=hits[0]['end']['seconds']-hits[0]['start']['seconds'] if len(hits)==1 and 'clip' not in pending and draw not in gaps else None
        recovery=rest_breakdown(d)['total_rest_marked_seconds'] if not pending&{'rest','chalk'} else None
        track=d.get('footwork');m=metrics(d)
        checked=m['reviewed_seconds'] if track else None
        hidden=None;coverage=[]
        if track and a is not None and b is not None:
            stop=a+m['analysis_seconds'] if m['analysis_seconds'] is not None else b
            hidden=length(intersection([(a,stop)],[(c['start']['seconds'],c['end']['seconds']) for c in track['coverage'] if c['state']=='obscured']))
            coverage=[dict(start=max(a,c['start']['seconds'])-a,end=min(stop,c['end']['seconds'])-a,state=c['state']) for c in track['coverage'] if min(stop,c['end']['seconds'])>max(a,c['start']['seconds'])]
        result.append(dict(key=str(i),name=d['climber']+' · '+d['attempt'],route=d['route'],result={'completed':'Topped','failed':'Fell','unknown':'Unknown'}.get(d['outcome'],d['outcome']),climb=duration,arrivals=arrivals,clips=clips,recovery=recovery,recovery_state='Reviewed' if d['reviewed'].get('rests') and d['reviewed'].get('boundaries') and not pending&{'rest','chalk'} else 'Partial annotations',checked=checked,hidden=hidden,unreviewed=max(0,m['analysis_seconds']-checked-hidden) if checked is not None and hidden is not None and m['analysis_seconds'] is not None else None,slips=m['confirmed_slips'] if track else None,candidates=m['candidate_slips'] if track else None,unplanned=m['unplanned_seconds'] if track else None,intentional=m['intentional_seconds'] if track else None,coverage=coverage,analysis=m['analysis_seconds'],foot_state='Fall start missing' if track and m['fall_review_needed'] else 'Not checked' if not checked else 'Checked footage only'))
        if identity.assigned(d):
            s=d['assignment']['session'];result[-1].update(route=identity.report_scope(d),route_label='Training / '+d['route'] if s['kind']=='training' else identity.context(d))
            result[-1]['name']+=' · '+s['name']+' · '+s['date']
    return result

def context_html(documents):
    """Context and completeness are visible in every export, including legacy drafts."""
    draft=any(identity.review_issues(d) for d in documents)
    rows=[]
    for d in documents:
        status='Draft: '+', '.join(identity.review_issues(d)) if identity.review_issues(d) else 'Reviewed boundaries and clipping'
        rows.append('<tr><td>'+escape(d['climber']+' · attempt '+d['attempt'])+'</td><td>'+escape(identity.context(d))+'</td><td>'+escape(status)+'</td><td>'+escape(identity.method_summary(d))+'</td></tr>')
    gaps=''.join('<p>'+escape(d['climber']+f" · QD {g['target'] or '?'} · {g['visibility']} at source frame {g['point']['frame']} / PTS {g['point']['pts']}: "+g['notes'])+'</p>' for d in documents for g in d.get('clip_gaps',[]))
    return '<section><h2>'+('DRAFT · incomplete review' if draft else 'Reviewed boundaries & clipping')+'</h2><p>Training and competition context belongs to each attempt. Annotation timing is not an official result. Cannot tell is an explicit answer; missed clips have no invented duration.</p><div class="scroll"><table><thead><tr><th>Attempt</th><th>Session / route version</th><th>Review</th><th>Clip methods</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'+('<details><summary>Clip visibility gaps</summary>'+gaps+'</details>' if gaps else '')+'</section>'

def checkpoint_for(data):
    return next(iter(sorted({n for r in data for n in r['arrivals'] if n!='Climb start'})), 'Climb start')

def summary_cells(r,checkpoint):
    return [r['name'],r['result'],shown(r['climb']),shown(r['arrivals'].get(checkpoint)),shown(r['recovery'])+(' · '+r['recovery_state'] if r['recovery'] is not None else ''),shown(r['checked'])+(' · '+shown(100*r['checked']/r['analysis'],'%') if r['checked'] is not None and r['analysis'] else '')]

def chart_specs(data,checkpoint=None,draws=None):
    checkpoint=checkpoint or checkpoint_for(data)
    def plot(title,values,note,unit=' s'):
        return dict(title=title,unit=unit,note=note,rows=[dict(key=r['key'],name=r['name'],value=value,state=state,ref=i==0) for i,(r,(value,state)) in enumerate(zip(data,values))])
    arrival=plot('Arrival at '+checkpoint,[(r['arrivals'].get(checkpoint),'Marked arrival' if r['arrivals'].get(checkpoint) is not None else 'Missing or repeated arrival') for r in data],'Seconds from climb start. Match the same route and a unique arrival.')
    recovery=plot('Recorded recovery',[(r['recovery'],r['recovery_state']) for r in data],'Recorded seconds, not a recovery score. Rest and chalk overlaps count once.')
    targets=sorted({n for r in data for n in r['clips']},key=lambda x:float(x))
    targets=(draws if draws is not None else targets[:4])
    clips=[plot('Quickdraw '+str(draw),[(r['clips'].get(str(draw)),'One closed clip' if r['clips'].get(str(draw)) is not None else 'Missing, repeated or unfinished') for r in data],'Clip duration in seconds; complete clip inside the climb.') for draw in targets]
    foot=dict(title='Footwork observations & coverage',note='Counts apply to checked footage. Candidates and intentional releases stay separate; marked fall flight is excluded.',rows=[dict(r,ref=i==0) for i,r in enumerate(data)],kind='footwork')
    for clip in clips:clip['compact']=True
    return [arrival,clips,recovery,foot]

def row_text(row,spec):
    prefix=('Ref · ' if row.get('ref') else '')+row['name']
    if spec.get('kind')=='footwork':
        return prefix+' · '+row['foot_state']+' · '+shown(row['slips'],' confirmed slips')+' · '+shown(row['candidates'],' candidates')+' · unplanned '+shown(row['unplanned'])+' · intentional '+shown(row['intentional'])+' · checked '+shown(row['checked'])+' / hidden '+shown(row['hidden'])+' / unreviewed '+shown(row['unreviewed'])
    return prefix+' · '+spec['title']+': '+('Unknown' if row['value'] is None else f'{row["value"]:.3f}'+spec['unit'])+' · '+row['state']

def svg_chart(spec,dark=False):
    """Visible numbers and labels; coverage has redundant hatch patterns."""
    ink='#f3f4f5' if dark else '#20252b';accent='#93bcff' if dark else '#245fc4';neutral='#8b939d'
    foot=spec.get('kind')=='footwork';step=100 if foot else 34 if spec.get('compact') else 54;height=18+max(1,len(spec['rows']))*step
    maximum=max([r.get('value') or 0 for r in spec['rows']]+[1])
    out=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 {height}" role="img" aria-label="{escape(spec["title"]+'. '+'. '.join(row_text(r,spec) for r in spec['rows']),quote=True)}"><title>{escape(spec["title"]+". "+spec["note"])}</title><defs><pattern id="hidden" width="6" height="6" patternUnits="userSpaceOnUse"><path d="M0 6L6 0" stroke="{ink}" stroke-width="1"/></pattern><pattern id="unchecked" width="6" height="6" patternUnits="userSpaceOnUse"><circle cx="3" cy="3" r="1" fill="{ink}"/></pattern></defs>'
    for i,r in enumerate(spec['rows']):
        y=12+i*step;label=('Ref · ' if r.get('ref') else '')+r['name'];tip=row_text(r,spec)
        out+=f'<g><title>{escape(tip)}</title><text x="0" y="{y+16}" font-size="15" fill="{ink}">{escape((label[:38] if foot else label[:28]+('…' if len(label)>28 else '')))}</text>'
        if foot:
            out+=f'<text x="0" y="{y+37}" font-size="13" fill="{ink}">{escape(shown(r["slips"]," slips")+" · "+shown(r["candidates"]," candidates")+" · unplanned "+shown(r["unplanned"])+" · intentional "+shown(r["intentional"]))}</text>'
            total=r['analysis'] or 1;x=0
            for key,pattern in [('checked',None),('hidden','hidden'),('unreviewed','unchecked')]:
                w=600*(r[key] or 0)/total
                if w:out+=f'<rect x="{x}" y="{y+46}" width="{w}" height="10" fill="{accent if key=="checked" else neutral}"/>'+(f'<rect x="{x}" y="{y+46}" width="{w}" height="10" fill="url(#{pattern})"/>' if pattern else '')
                x+=w
            out+=f'<text x="0" y="{y+77}" font-size="13" fill="{ink}">{escape("Checked "+shown(r["checked"])+" · hidden "+shown(r["hidden"])+" · unreviewed "+shown(r["unreviewed"]))}</text>'
        else:
            value=r['value'];w=245*(value or 0)/maximum
            if value is not None:out+=f'<rect x="250" y="{y}" width="{w}" height="21" rx="2" fill="{accent if r.get("ref") else neutral}"/>'
            out+=f'<text x="505" y="{y+16}" font-size="14" fill="{ink}">{escape(shown(value,spec["unit"]))}</text>'
            if not spec.get('compact'):out+=f'<text x="0" y="{y+36}" font-size="12" fill="{ink}">{escape(r["state"])}</text>'
        out+='</g>'
    if not spec['rows']:out+=f'<text x="0" y="30" fill="{ink}" font-size="15">Choose attempts to compare.</text>'
    return out+'</svg>',height,step

def snapshot(documents):
    # Escaping '<' prevents a note from terminating an inert JSON script element.
    return '<script id="measurementSnapshot" type="application/json">'+json.dumps(documents,ensure_ascii=True).replace('<','\\u003c')+'</script>'

def read_snapshot(source):
    from html.parser import HTMLParser
    from .labels import validate
    class Snapshot(HTMLParser):
        def __init__(self):super().__init__();self.active=False;self.parts=[]
        def handle_starttag(self,tag,attrs):self.active=tag=='script' and dict(attrs).get('id')=='measurementSnapshot'
        def handle_endtag(self,tag):
            if tag=='script':self.active=False
        def handle_data(self,value):
            if self.active:self.parts.append(value)
    parser=Snapshot();parser.feed(source.read_text(encoding='utf-8-sig'))
    if not parser.parts:return None
    documents=json.loads(''.join(parser.parts))
    for d in documents:validate(d)
    return documents

OVERVIEW_CSS='''
svg text{fill:var(--ink)}.footwork-timeline .event-confirmed{fill:var(--ink);stroke:var(--ink)}.footwork-timeline .event-candidate{fill:none;stroke:var(--ink)}.footwork-timeline defs path{stroke:var(--ink)}
.chart-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}.report-overview .scope{display:flex;gap:16px;align-items:center;flex-wrap:wrap;margin:12px 0}.report-overview label{font-size:13px}.report-overview select{font:inherit;color:var(--ink);background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:7px 9px;min-height:36px;max-width:280px}.report-overview .attempt-choices{display:flex;gap:12px;flex-wrap:wrap}.report-overview .dashboard-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:24px}.report-overview article{min-width:0;border:1px solid var(--soft);border-radius:8px;padding:16px}.report-overview h3{font-size:16px;margin:0 0 6px}.report-overview svg{display:block;width:100%;height:auto;font-family:system-ui,sans-serif}.report-overview .chart-note{font-size:12px;color:var(--muted);margin:0 0 12px}.report-overview svg .athlete-label{fill:var(--ink)}.report-overview svg text{fill:var(--ink)}.report-overview svg .value-bar{fill:#8b939d}.report-overview svg .is-ref .value-bar{fill:var(--accent)}[hidden]{display:none!important}.report-overview th{position:static}.report-overview td{font-variant-numeric:tabular-nums}.report-overview .empty{padding:20px 0}
@media(max-width:760px){.report-overview .dashboard-grid,.chart-grid{grid-template-columns:1fr}}
@media print{.report-overview .scope,.report-overview .attempt-choices{display:none}.report-overview article{break-inside:avoid}.report-overview .dashboard-grid{gap:12px}.report-overview{break-before:auto}.report-overview svg{max-height:320px}.report-overview .scroll{overflow:visible}}
'''

OVERVIEW_SCRIPT=r'''
(()=>{
const root=document.getElementById('comparisonOverview');if(!root)return;
const records=JSON.parse(document.getElementById('overviewData').textContent),route=root.querySelector('[data-route]'),ref=root.querySelector('[data-reference]'),point=root.querySelector('[data-checkpoint]'),page=root.querySelector('[data-draw-page]');
const choices=[...root.querySelectorAll('[data-attempt]')],rows=[...root.querySelectorAll('tbody tr[data-key]')];
const num=(v,u=' s')=>v===null||v===undefined?'Unknown':Number(v).toFixed(2)+u;
function update(){
 const chosen=records.filter(r=>r.route===route.value&&choices.find(c=>c.dataset.attempt===r.key).checked);
 if(!chosen.some(r=>r.key===ref.value)){ref.value=chosen[0]?.key||'';}
 for(const o of ref.options)o.hidden=!chosen.some(r=>r.key===o.value);
 const ordered=[...chosen].sort((a,b)=>a.key===ref.value?-1:b.key===ref.value?1:records.indexOf(a)-records.indexOf(b));
 const names=[...new Set(chosen.flatMap(r=>Object.keys(r.arrivals)))].sort();for(const o of point.options)o.hidden=!names.includes(o.value);
 if(!names.includes(point.value))point.value=names.find(n=>n!=='Climb start')||'Climb start';
 const draws=[...new Set(chosen.flatMap(r=>Object.keys(r.clips)))].sort((a,b)=>Number(a)-Number(b));
 const pages=Math.ceil(draws.length/2);const old=Number(page.value)||0;page.replaceChildren();for(let i=0;i<pages;i++){const o=document.createElement('option');o.value=String(i);o.textContent=draws.slice(i*2,i*2+2).map(d=>'Draw '+d).join(', ');page.appendChild(o);}page.value=String(Math.min(old,Math.max(0,pages-1)));page.disabled=pages<=1;
 const visibleDraws=draws.slice(Number(page.value)*2,Number(page.value)*2+2);
 root.querySelector('[data-arrival-header]').textContent=point.value+' arrival';
 for(const row of rows){const r=records.find(r=>r.key===row.dataset.key);row.hidden=!chosen.includes(r);row.cells[0].textContent=(r.key===ref.value?'Ref · ':'')+r.name;row.cells[3].textContent=num(r.arrivals[point.value]);}
 for(const r of ordered){const row=rows.find(row=>row.dataset.key===r.key);row.parentElement.appendChild(row);}
 for(const label of choices)label.parentElement.hidden=records.find(r=>r.key===label.dataset.attempt).route!==route.value;
 root.querySelector('[data-empty]').hidden=chosen.length>0;
 root.querySelector('[data-scope-label]').textContent=chosen.length+' attempts · '+(chosen[0]?.route_label||route.value)+' · reference '+(ordered[0]?.name||'none')+' · checkpoint '+point.value;
 for(const box of root.querySelectorAll('[data-chart]')){
  box.hidden=box.dataset.point!==undefined&&box.dataset.point!==point.value||box.dataset.draw!==undefined&&!visibleDraws.includes(box.dataset.draw);
  const svg=box.querySelector('svg'),step=Number(svg.dataset.step),groups=[...svg.querySelectorAll('g[data-key]')];
  const maximum=Math.max(1,...ordered.map(r=>Number(groups.find(g=>g.dataset.key===r.key)?.dataset.value)||0));
  for(const g of groups)g.style.display=chosen.some(r=>r.key===g.dataset.key)?'':'none';
  ordered.forEach((r,i)=>{const g=groups.find(g=>g.dataset.key===r.key);if(!g)return;g.setAttribute('transform','translate(0,'+(i*step-Number(g.dataset.y))+')');g.classList.toggle('is-ref',r.key===ref.value);const label=(r.key===ref.value?'Ref · ':'')+r.name;const limit=step===100?38:28;g.querySelector('.athlete-label').textContent=label.slice(0,limit)+(label.length>limit?'…':'');const title=g.querySelector('title');if(!g.dataset.tip)g.dataset.tip=title.textContent.replace(/^Ref · /,'');title.textContent=(r.key===ref.value?'Ref · ':'')+g.dataset.tip;const bar=g.querySelector('.value-bar');if(bar)bar.setAttribute('width',String(245*(Number(g.dataset.value)||0)/maximum));svg.appendChild(g);});
  svg.setAttribute('aria-label',box.querySelector('h3').textContent+'. '+ordered.map(r=>groups.find(g=>g.dataset.key===r.key)?.querySelector('title').textContent||'').join('. '));
  svg.setAttribute('viewBox','0 0 600 '+(18+Math.max(1,ordered.length)*step));
 }
 // Evidence stays coupled to the selection, without changing saved observations.
 document.querySelectorAll('[data-evidence-key]').forEach(e=>e.hidden=!chosen.some(r=>r.key===e.dataset.evidenceKey));
}
root.addEventListener('change',update);update();
window.addEventListener('beforeprint',()=>document.querySelectorAll('details').forEach(d=>{d.dataset.wasOpen=d.open?'1':'0';d.open=true;}));
window.addEventListener('afterprint',()=>document.querySelectorAll('details[data-was-open]').forEach(d=>{d.open=d.dataset.wasOpen==='1';delete d.dataset.wasOpen;}));
})();
'''

def overview_html(data,checkpoint=None):
    """Offline selection changes presentation only; measurements are computed in Python."""
    if not data:return '<section><h2>Comparison overview</h2><p>Choose attempts to compare.</p></section>'
    checkpoint=checkpoint or checkpoint_for(data)
    def options(values):return ''.join('<option value="'+escape(str(v),quote=True)+'"'+(' selected' if v==checkpoint else '')+'>'+escape(str(label))+'</option>' for v,label in values)
    choices=''.join('<label><input type="checkbox" data-attempt="'+r['key']+'" checked> '+escape(r['name'])+'</label>' for r in data)
    headers=HEADERS.copy();headers[3]=checkpoint+' arrival'
    head=''.join('<th scope="col"'+(' data-arrival-header' if i==3 else '')+'>'+escape(h)+'</th>' for i,h in enumerate(headers))
    body=''.join('<tr data-key="'+r['key']+'">'+''.join('<td>'+escape(v)+'</td>' for v in summary_cells(r,checkpoint))+'</tr>' for r in data)
    def chart(spec,attrs=''):
        svg,height,step=svg_chart(spec)
        svg=svg.replace('role="img"',f'data-step="{step}" role="img"')
        for i,r in enumerate(spec['rows']):
            svg=svg.replace('<g>',f'<g data-key="{data[i]["key"]}" data-y="{i*step}" data-value="{r.get("value") or 0}">',1)
                # Mark each row's first text, leaving the status/coverage labels intact.
        import re
        svg=re.sub(r'(<g [^>]*><title>.*?</title>)<text ',r'\1<text class="athlete-label" ',svg)
        svg=svg.replace('x="250"','class="value-bar" x="250"')
        return '<div data-chart '+attrs+'><h3>'+escape(spec['title'])+'</h3><p class="chart-note">'+escape(spec['note'])+'</p>'+svg+'</div>'
    arrival,clips,recovery,foot=chart_specs(data,checkpoint)
    arrivals=''.join(chart(chart_specs(data,n)[0],'data-point="'+escape(n,quote=True)+'"'+(' hidden' if n!=checkpoint else '')) for n in sorted({n for r in data for n in r['arrivals']}))
    targets=sorted({n for r in data for n in r['clips']},key=float)
    clip_html=''.join(chart(spec,'data-draw="'+escape(draw,quote=True)+'"'+(' hidden' if i>=2 else '')) for i,(draw,spec) in enumerate(zip(targets,chart_specs(data,checkpoint,targets)[1]))) or '<p>No matched clip annotations.</p>'
    payload=json.dumps(data,ensure_ascii=True).replace('<','\\u003c')
    return '<section id="comparisonOverview" class="report-overview"><h2>Comparison overview</h2><p class="chart-note">'+LIMITS+'</p><div class="scope"><label>Route <select data-route>'+options(list({r['route']:r.get('route_label',r['route']) for r in data}.items()))+'</select></label><label>Reference <select data-reference>'+options([(r['key'],r['name']) for r in data])+'</select></label><label>Checkpoint <select data-checkpoint>'+options([(n,n) for n in sorted({n for r in data for n in r['arrivals']})])+'</select></label></div><div class="attempt-choices">'+choices+'</div><p class="chart-note" data-scope-label aria-live="polite"></p><p class="empty" data-empty hidden>No attempts selected. Check an athlete above.</p><div class="scroll"><table><thead><tr>'+head+'</tr></thead><tbody>'+body+'</tbody></table></div><div class="dashboard-grid"><article>'+arrivals+'</article><article><label>Quickdraws <select data-draw-page><option value="0">First two draws</option></select></label>'+clip_html+'</article><article>'+chart(recovery)+'</article><article>'+chart(foot)+'</article></div></section><script id="overviewData" type="application/json">'+payload+'</script><script>'+OVERVIEW_SCRIPT+'</script>'

def legacy_records(overview,points,activities):
    """Old HTML snapshots cannot supply review flags or footwork: keep them unknown."""
    from .report_visuals import number
    result=[]
    for i,s in enumerate(overview):
        def matched(row):return all(row.get(k)==s.get(k) for k in ('athlete','attempt','video'))
        duration=number(s.get('climb seconds'));arrivals={'Climb start':0.0 if number(s.get('start video seconds')) is not None else None};clips={}
        for name in {p['point'] for p in points if matched(p)}:
            hits=[number(p.get('seconds from climb start')) for p in points if matched(p) and p['point']==name and number(p.get('seconds from climb start')) is not None]
            arrivals[name]=hits[0] if len(hits)==1 else None
        for draw in {a['quickdraw'] for a in activities if matched(a) and a['activity']=='clip'}:
            hits=[a for a in activities if matched(a) and a['activity']=='clip' and a['quickdraw']==draw]
            valid=[a for a in hits if a['status']=='closed' and number(a.get('start from climb seconds')) is not None and number(a['start from climb seconds'])>=0 and duration is not None and number(a.get('end from climb seconds')) is not None and number(a['end from climb seconds'])<=duration]
            clips[str(draw)]=number(valid[0]['duration seconds']) if len(hits)==1 and len(valid)==1 else None
        recovery=number(s.get('total rest marked seconds'))
        if any(a['activity'] in ('rest','chalk') and a['status']!='closed' for a in activities if matched(a)):recovery=None
        result.append(dict(key=str(i),name=s['athlete']+' · '+str(s.get('attempt','')),route=s.get('route') or 'Route not recorded',result=s.get('outcome','Unknown'),climb=duration,arrivals=arrivals,clips=clips,recovery=recovery,recovery_state='Review state unavailable',checked=None,hidden=None,unreviewed=None,slips=None,candidates=None,unplanned=None,intentional=None,coverage=[],analysis=None,foot_state='Not present in this snapshot'))
    return result

def footwork_timeline(document,dark=False):
    """Coverage-aware timeline in climb seconds, retaining candidates as outlines."""
    r=records([document])[0];duration=r['analysis'];ink='#f3f4f5' if dark else '#20252b';accent='#93bcff' if dark else '#245fc4'
    if not duration:return '<p>Mark climb boundaries to view the footwork timeline.</p>'
    out=f'<svg xmlns="http://www.w3.org/2000/svg" class="footwork-timeline" viewBox="0 0 900 130" role="img" aria-label="Footwork coverage and observations"><title>Footwork coverage and observations in seconds from climb start. Filled triangle: confirmed slip. Outline: candidate. Circle: intentional release. Feet-off intervals: labelled.</title><defs><pattern id="timelineHidden" width="8" height="8" patternUnits="userSpaceOnUse"><path d="M0 8L8 0" stroke="{ink}"/></pattern></defs><rect x="10" y="45" width="880" height="20" fill="#8b939d" opacity=".25"/>'
    for c in r['coverage']:
        x=10+880*c['start']/duration;w=880*(c['end']-c['start'])/duration
        out+=f'<rect x="{x}" y="45" width="{w}" height="20" fill="{accent if c["state"]=="reviewed" else "url(#timelineHidden)"}"><title>{escape(c["state"])}: {c["start"]:.3f}–{c["end"]:.3f} s from climb start</title></rect>'
    a=document['start']['seconds']
    for e in document.get('footwork',{}).get('events',[]):
        t=e['start']['seconds']-a
        if not 0<=t<duration:continue
        x=10+880*t/duration;fill=ink if e['status']=='confirmed' else 'none'
        cls='event-confirmed' if e['status']=='confirmed' else 'event-candidate'
        label=f'{e["kind"]} · {e["status"]} · {e["intent"]} · {t:.3f} s · original frame {e["start"]["frame"]}'
        if e['kind']=='both_off':
            stop=min(duration,e['end']['seconds']-a);w=880*(stop-t)/duration
            out+=f'<g><title>{escape(label)}</title><rect class="{cls}" x="{x}" y="10" width="{w}" height="12" fill="{fill}" stroke="{ink}"/><text x="{x}" y="38" font-size="12" fill="{ink}">{escape(e["intent"])} feet off</text></g>'
        elif e['kind']=='foot_release':out+=f'<circle class="{cls}" cx="{x}" cy="75" r="5" fill="{fill}" stroke="{ink}"><title>{escape(label)}</title></circle>'
        else:out+=f'<path class="{cls}" d="M{x-5} 80 L{x} 70 L{x+5} 80 Z" fill="{fill}" stroke="{ink}"><title>{escape(label)}</title></path>'
    out+=f'<text x="10" y="105" font-size="14" fill="{ink}">0 s</text><text x="890" y="105" text-anchor="end" font-size="14" fill="{ink}">{duration:.2f} s</text><text x="10" y="125" font-size="12" fill="{ink}">Solid: checked · diagonal hatch: hidden · pale: unreviewed · filled: confirmed · outline: candidate · circle: intentional</text>'
    return out+'</svg>'

def split_specs(documents):
    from .analytics import between_clips
    result=[]
    for d in documents:
        rows=[]
        for r in between_clips([d]):
            label=f'{r["from_quickdraw"]} → {r["to_quickdraw"]}'
            rows.append(dict(name=label,value=r['gap_seconds'],state='Recorded recovery '+shown(r['total_marked_rest_in_gap_seconds'])+' · unclassified '+shown(r['gap_outside_marked_rest_seconds']),ref=False))
        result.append(dict(title=d['climber']+' · '+d['attempt']+' · between-clip gaps',unit=' s',note='Previous clip end to next clip start. Time outside marked recovery is unclassified.',rows=rows))
    return result

def details_html(documents):
    """Pair detailed tables with bounded charts; raw activity logs need no duplicate plot."""
    from .analytics import between_clips
    from .coaching_report import table
    data=records(documents);parts=[]
    for route in dict.fromkeys(r['route'] for r in data):
        chosen=[r for r in data if r['route']==route]
        names=sorted({n for r in chosen for n in r['arrivals'] if n!='Climb start'})
        body=''
        for name in names:
            spec=chart_specs(chosen,name)[0]
            body+='<h3>'+escape(name)+'</h3>'+table(['Athlete / attempt','Arrival s','State'],[[r['name'],shown(r['value']),r['state']] for r in spec['rows']])+svg_chart(spec)[0]
        parts.append('<section><h2>Checkpoint timing · '+escape(chosen[0].get('route_label',route))+'</h2>'+body+'</section>')
    for route in dict.fromkeys(r['route'] for r in data):
        chosen=[r for r in data if r['route']==route];draws=sorted({n for r in chosen for n in r['clips']},key=float)
        for offset in range(0,len(draws),4):
            selected=draws[offset:offset+4];panels=''
            for spec in chart_specs(chosen,draws=selected)[1]:
                panels+='<article><h3>'+escape(spec['title'])+'</h3>'+table(['Athlete / attempt','Clip s','State'],[[r['name'],shown(r['value']),r['state']] for r in spec['rows']])+svg_chart(spec)[0]+'</article>'
            parts.append('<details><summary>Matched clips · '+escape(chosen[0].get('route_label',route))+' · draws '+', '.join(selected)+'</summary><section><div class="chart-grid">'+panels+'</div></section></details>')
    for d in documents:
        specs=split_specs([d]);splits=between_clips([d])
        body=table(['Split','Gap s','Recovery s','Unclassified s'],[[str(r['from_quickdraw'])+' → '+str(r['to_quickdraw']),shown(r['gap_seconds']),shown(r['total_marked_rest_in_gap_seconds']),shown(r['gap_outside_marked_rest_seconds'])] for r in splits])+svg_chart(specs[0])[0]
        parts.append('<section><h2>'+escape(d['climber']+' · '+d['attempt'])+' · splits</h2>'+body+'</section>')
    return ''.join(parts)

def pdf_overview(story,data,width,styles):
    """Printed numbers and coverage states, with vector graphics and no hover dependency."""
    from reportlab.platypus import Paragraph,Spacer,LongTable,Flowable,Table
    from reportlab.lib import colors
    cell_style=styles['Cell'];font=cell_style.fontName
    def para(value):return Paragraph(escape(str(value)),cell_style)
    class Chart(Flowable):
        def __init__(self,spec):super().__init__();self.spec=spec;self.width=(width-20)/2;self.height=20+len(spec['rows'])*(82 if spec.get('kind')=='footwork' else 26 if spec.get('compact') else 44)
        def draw(self):
            c=self.canv;spec=self.spec;maximum=max([r.get('value') or 0 for r in spec['rows']]+[1]);foot=spec.get('kind')=='footwork';step=82 if foot else 26 if spec.get('compact') else 44
            for i,r in enumerate(spec['rows']):
                y=self.height-20-i*step;name=('Ref · ' if r.get('ref') else '')+r['name'];p=para(name);_,h=p.wrap(self.width,28);p.drawOn(c,0,y-h)
                c.setFillColor(colors.HexColor('#245fc4' if r.get('ref') else '#8b939d'))
                if foot:
                    line=shown(r['slips'],' slips')+' · '+shown(r['candidates'],' candidates')+' · '+r['foot_state']
                    for k,value in enumerate([line,'Unplanned '+shown(r['unplanned'])+' · intentional '+shown(r['intentional']),'Checked '+shown(r['checked'])+' · hidden '+shown(r['hidden'])+' · unreviewed '+shown(r['unreviewed'])]):
                        p=para(value);_,h=p.wrap(self.width,24);p.drawOn(c,0,y-18-k*16-h)
                    total=r['analysis'] or 1;x=0
                    for key in ('checked','hidden','unreviewed'):
                        w=self.width*(r[key] or 0)/total
                        if not w:continue
                        c.setFillColor(colors.HexColor('#245fc4' if key=='checked' else '#b4bbc3'));c.rect(x,y-76,w,6,fill=1,stroke=0)
                        if key!='checked':
                            c.setStrokeColor(colors.HexColor('#20252b'));c.setLineWidth(.4)
                            for dx in range(0,int(w),5):
                                if key=='hidden':c.line(x+dx,y-76,x+min(dx+4,w),y-70)
                                else:c.circle(x+dx,y-73,.5,fill=0,stroke=1)
                        x+=w
                else:

                    if r['value']:c.rect(0,y-25,(self.width-78)*r['value']/maximum,7,fill=1,stroke=0)
                    c.setFillColor(colors.HexColor('#20252b'));c.setFont(font,8);c.drawRightString(self.width,y-25,shown(r['value'],spec['unit']));
                    if not spec.get('compact'):p=para(r['state']);_,h=p.wrap(self.width,14);p.drawOn(c,0,y-28-h)
    checkpoint=checkpoint_for(data)
    story.extend([Paragraph('Comparison overview',styles['Heading1']),para(LIMITS),Spacer(1,10)])
    headers=HEADERS.copy();headers[3]=checkpoint+' arrival'
    summary=LongTable([[para(h) for h in headers]]+[[para(v) for v in summary_cells(r,checkpoint)] for r in data],colWidths=[width/6]*6,repeatRows=1,splitInRow=1)
    summary.setStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e5e7eb')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),7)]);story.extend([summary,Spacer(1,14)])
    for route in dict.fromkeys(r['route'] for r in data):
        chosen=[r for r in data if r['route']==route]
        # Printed panels paginate in groups of three; the full tables follow in the appendix.
        for start in range(0,len(chosen),3):
            batch=chosen[start:start+3];arrival,clips,recovery,foot=chart_specs(batch,checkpoint_for(chosen))
            for spec in [arrival,*clips,recovery,foot]:
                for r in spec['rows']:r['ref']=r['key']==chosen[0]['key']
            def panel(spec):return [Paragraph(escape(spec['title']),styles['Heading3'])]+([] if spec.get('compact') else [para(spec['note'])])+[Chart(spec)]
            clip_panel=[para('Matching quickdraws · seconds. Missing, repeated or unfinished clips are unknown.')]
            for clip in clips[:2]:clip_panel+=panel(clip)
            if not clips:clip_panel=[para('No complete clip annotations.')]
            grid=Table([[panel(arrival),clip_panel],[panel(recovery),panel(foot)]],colWidths=[width/2]*2,hAlign='LEFT');grid.setStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),12),('BOTTOMPADDING',(0,0),(-1,-1),12)])
            story.extend([para(chosen[0].get('route_label',route)+' · reference '+chosen[0]['name']),grid,Spacer(1,12)])

def pdf_footwork_timeline(document,width):
    from reportlab.platypus import Flowable
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    class Timeline(Flowable):
        def __init__(self):super().__init__();self.width=width;self.height=84
        def draw(self):
            r=records([document])[0];c=self.canv;c.setFont('Review' if 'Review' in pdfmetrics.getRegisteredFontNames() else 'Helvetica',8)
            if not r['analysis']:c.drawString(0,40,'Climb boundaries missing; footwork timeline unavailable.');return
            total=r['analysis'];c.setFillColor(colors.HexColor('#e5e7eb'));c.rect(0,28,width,10,fill=1,stroke=0)
            for span in r['coverage']:
                x=width*span['start']/total;w=width*(span['end']-span['start'])/total;c.setFillColor(colors.HexColor('#245fc4' if span['state']=='reviewed' else '#b4bbc3'));c.rect(x,28,w,10,fill=1,stroke=0)
                if span['state']=='obscured':
                    c.setLineWidth(.4);c.setStrokeColor(colors.HexColor('#20252b'))
                    for dx in range(0,int(w),5):c.line(x+dx,28,x+min(dx+5,w),38)
            c.setFillColor(colors.HexColor('#20252b'));c.setStrokeColor(colors.HexColor('#20252b'))
            for e in document.get('footwork',{}).get('events',[]):
                t=e['start']['seconds']-document['start']['seconds']
                if not 0<=t<total:continue
                x=width*t/total;filled=e['status']=='confirmed'
                if e['kind']=='both_off':c.rect(x,49,width*(min(total,e['end']['seconds']-document['start']['seconds'])-t)/total,5,fill=filled,stroke=1)
                elif e['kind']=='foot_release':c.circle(x,20,3,fill=filled,stroke=1)
                else:
                    p=c.beginPath();p.moveTo(x-3,16);p.lineTo(x,23);p.lineTo(x+3,16);p.close();c.drawPath(p,fill=filled,stroke=1)
            c.drawString(0,5,'0 s');c.drawRightString(width,5,f'{total:.2f} s from climb start');c.drawString(0,72,'Solid: checked / hatch: hidden / pale: unreviewed. Filled: confirmed / outline: candidate.')
    return Timeline()


def pdf_fonts(styles):
    """Use the already bundled Unicode fonts for both printable report formats."""
    import reportlab
    from pathlib import Path
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    fonts=Path(reportlab.__file__).parent/'fonts'
    for name,file in [('Review','Vera.ttf'),('ReviewBold','VeraBd.ttf'),('ReviewItalic','VeraIt.ttf'),('ReviewBoldItalic','VeraBI.ttf')]:
        if name not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont(name,str(fonts/file)))
    pdfmetrics.registerFontFamily('Review',normal='Review',bold='ReviewBold',italic='ReviewItalic',boldItalic='ReviewBoldItalic')
    for style in styles.byName.values():
        if hasattr(style,'fontName'):style.fontName='ReviewBold' if style.fontName.endswith('Bold') else 'Review'

def eligible_clip_rows(activities,summary):
    """Use the same closed, unique, bounded clips in older snapshot detail tables."""
    from .report_visuals import number
    own=[a for a in activities if a['activity']=='clip' and all(a.get(k)==summary.get(k) for k in ('athlete','attempt','video','attempt id'))]
    duration=number(summary.get('climb seconds'))
    if duration is None or any(a['status']=='unfinished' for a in own):return {}
    own=[a for a in own if a['status']=='closed']
    result={}
    for draw in {a['quickdraw'] for a in own}:
        hits=[a for a in own if a['quickdraw']==draw];a=hits[0]
        start,end=number(a.get('start from climb seconds')),number(a.get('end from climb seconds'))
        if len(hits)==1 and start is not None and end is not None and 0<=start<=end<=duration and number(a.get('duration seconds')) is not None:result[draw]=a
    return result


def gap_peers(splits,row,overview):
    from .report_visuals import number
    identity=lambda r:tuple(r.get(k) for k in ('athlete','attempt','video','attempt id'))
    def route_for(r):
        matches=[s for s in overview if all(r.get(k) is None or r.get(k)==s.get(k) for k in ('athlete','attempt','video','attempt id'))]
        return matches[0].get('comparison scope',matches[0].get('route')) if len(matches)==1 else None
    route=route_for(row)
    if route is None:return []
    own=[s for s in splits if identity(s)==identity(row) and s['from quickdraw']==row['from quickdraw'] and s['to quickdraw']==row['to quickdraw']]
    if len(own)!=1:return []
    peers=[s for s in splits if identity(s)!=identity(row) and route_for(s)==route and s['from quickdraw']==row['from quickdraw'] and s['to quickdraw']==row['to quickdraw']]
    return [number(p['gap outside marked rest seconds']) for p in peers if sum(identity(q)==identity(p) for q in peers)==1 and number(p['gap outside marked rest seconds']) is not None]
