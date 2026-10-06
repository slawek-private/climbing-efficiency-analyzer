"""Offline evidence-first coaching reports with explicitly selected local video sections."""
import bisect,copy,csv,json,shutil,tempfile
from fractions import Fraction
from html import escape
from pathlib import Path
from uuid import uuid4
from urllib.parse import quote
from .labels import validate
from .footwork import metrics,observations
from .version import __version__

CSS='''
:root{color-scheme:light dark;--bg:#f4f5f6;--panel:#fff;--ink:#20252b;--muted:#59616b;--line:#8b939d;--soft:#e5e7eb;--accent:#245fc4}
@media(prefers-color-scheme:dark){:root{--bg:#151719;--panel:#202326;--ink:#f3f4f5;--muted:#b2b8bf;--line:#727c87;--soft:#383e45;--accent:#78adff}}
*{box-sizing:border-box}body{font:16px/1.6 system-ui,sans-serif;margin:0;background:var(--bg);color:var(--ink)}main{max-width:1150px;margin:auto;padding:36px 24px}h1{font-size:36px;line-height:1.2;letter-spacing:-.03em}h2{font-size:25px;margin-top:0}h3{font-size:19px;margin:20px 0 8px}section{background:var(--panel);border-radius:8px;padding:28px;margin:24px 0}p{max-width:900px}.muted,small{color:var(--muted);font-size:13px}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;border-top:1px solid var(--soft);border-bottom:1px solid var(--soft);padding:20px 0}.stats strong{display:block;font-size:30px}.evidence{border-top:1px solid var(--soft);padding:20px 0}.notes{white-space:pre-wrap}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid var(--soft)}th{background:var(--bg)}button{font:inherit;font-size:14px;min-height:36px;padding:7px 12px;border:1px solid var(--line);border-radius:5px;background:var(--panel);color:var(--ink);cursor:pointer}button:hover{background:var(--bg)}button:focus-visible{outline:3px solid var(--accent);outline-offset:2px}button:disabled{cursor:default;color:var(--muted)}video{width:100%;max-height:65vh;background:#101214;display:block;border-radius:6px;margin:16px 0}.player{position:sticky;top:8px;z-index:2;border:1px solid var(--line);box-shadow:0 8px 20px #0002}.player[hidden]{display:none}.tag{font-size:12px;color:var(--muted)}.actions{display:flex;gap:10px;flex-wrap:wrap}a{color:var(--accent)}code{overflow-wrap:anywhere;font-size:12px}.coverage{height:12px;background:var(--soft);margin:14px 0}.coverage span{display:block;height:12px;background:var(--accent)}.goal{font-size:20px}details{padding:12px 0;border-top:1px solid var(--soft)}summary{cursor:pointer}summary:focus-visible{outline:3px solid var(--accent)}.print-note{display:none}
@media(max-width:650px){main{padding:16px}section{padding:18px}.stats{grid-template-columns:1fr}h1{font-size:28px}.player{position:static}}
@media print{:root{color-scheme:light;--bg:white;--panel:white;--ink:#20252b;--muted:#59616b;--line:#8b939d;--soft:#d6d8d9}body{font-size:11pt}main{padding:0;max-width:none}button,video,.player{display:none!important}.print-note{display:block}section{padding:12px 0;break-before:page}header+section{break-before:auto}.evidence{break-inside:avoid}thead{display:table-header-group}h2,h3{break-after:avoid}.scroll{overflow:visible}details>div{display:block!important}}
'''
SCRIPT='''
let printedDetails=[];window.addEventListener('beforeprint',()=>{printedDetails=[...document.querySelectorAll('details')].map(d=>[d,d.open]);printedDetails.forEach(([d])=>d.open=true);});window.addEventListener('afterprint',()=>printedDetails.forEach(([d,open])=>d.open=open));
const data=JSON.parse(document.getElementById('reportData').textContent),player=document.getElementById('player'),video=document.getElementById('video'),status=document.getElementById('playStatus');let bounds=null;
function playEvent(key,context){const e=data[key],m=e.media;if(!m){status.textContent='No video included for this observation.';return;}player.hidden=false;document.getElementById('playTitle').textContent=e.label+' · original frame '+e.frame;status.textContent=m.kind==='link'?'Original video link; it must remain at its exported location.':'Portable review clip; measurements retain original frame and PTS identity.';const start=Math.max(0,e.start-m.offset-(context?2:0)),end=e.end-m.offset+(context?2:0);bounds=[start,Math.max(start+.1,end)];const run=()=>{if(Number.isFinite(video.duration))bounds[1]=Math.min(bounds[1],video.duration);video.currentTime=Math.min(start,video.duration||start);video.play().catch(()=>status.textContent='Use Play. If this video format cannot play here, export portable H.264 sections.');};if(video.dataset.key!==key){video.dataset.key=key;video.src=m.url;video.load();video.onloadedmetadata=run;}else run();player.scrollIntoView({block:'start',behavior:'smooth'});}
video.addEventListener('timeupdate',()=>{if(bounds&&!video.paused&&video.currentTime>=bounds[1])video.currentTime=bounds[0];});video.addEventListener('ended',()=>{if(bounds){video.currentTime=bounds[0];video.play().catch(()=>{});}});video.addEventListener('error',()=>status.textContent='Video unavailable. Original links work only on this computer and depend on browser codec support. Export portable sections for sharing.');document.getElementById('closePlayer').onclick=()=>{video.pause();bounds=null;player.hidden=true;};document.querySelectorAll('[data-replay]').forEach(b=>b.onclick=()=>playEvent(b.dataset.replay,b.dataset.context==='true'));
'''

def display(value,unit=''):
    return 'Not reviewed' if value is None else f'{value:.1f}{unit}' if isinstance(value,float) else str(value)+unit

def table(headers,rows):
    return '<div class="scroll"><table><thead><tr>'+''.join('<th scope="col">'+escape(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'

def section_comparison(documents,anonymous=False):
    if len(documents)<2:return []
    reference=documents[0];names=sorted({p['name'] for d in documents for p in d.get('checkpoints',[])})
    def arrival(d,name):
        matches=[p for p in d.get('checkpoints',[]) if p['name']==name and d['start'] and p['point']['seconds']>=d['start']['seconds'] and (not d['end'] or p['point']['seconds']<=d['end']['seconds'])]
        return matches[0]['point']['seconds']-d['start']['seconds'] if len(matches)==1 else None
    rows=[]
    for i,d in enumerate(documents):
        for name in names:
            own=arrival(d,name);ref=arrival(reference,name) if d['route']==reference['route'] else None
            delta=own-ref if own is not None and ref is not None else None
            rows.append([f'Athlete {i+1}' if anonymous else d['climber'],d['attempt'],name,display(own,' s'),display(ref,' s'),display(delta,' s'),'Different route' if d['route']!=reference['route'] else 'Ambiguous / missing' if own is None or ref is None else 'Marked arrival'])
    return rows

def clip_window(event,times):
    start=max(0,event['start']['seconds']-2);end=min(times[-1],(event.get('end') or event['start'])['seconds']+2)
    first=max(0,bisect.bisect_right(times,start)-1);last=min(len(times)-1,bisect.bisect_left(times,end))
    return first,last

def write_clip(reader,event,path,cancelled=lambda:False):
    """Every source frame in the selected window; native PTS spacing, no FPS equalization."""
    import av
    first,last=clip_window(event,reader.times);base=Fraction(reader.index['source']['time_base']);pts=reader.index['pts'];path=Path(path)
    rgb=reader.frame(first);height,width=rgb.shape[:2];width-=width%2;height-=height%2
    if not width or not height:raise ValueError('Video is too small to export')
    with av.open(str(path),'w',format='mp4') as output:
        stream=output.add_stream('libx264',rate=30);stream.width=width;stream.height=height;stream.pix_fmt='yuv420p';stream.time_base=base;stream.codec_context.time_base=base;stream.codec_context.max_b_frames=0;stream.options={'crf':'23','preset':'fast'}
        for number in range(first,last+1):
            if cancelled():raise InterruptedError('Report export cancelled')
            if number%30==0 and shutil.disk_usage(path.parent).free<512*1024**2:raise OSError('Report export stopped: less than 512 MB free')
            frame=av.VideoFrame.from_ndarray(reader.frame(number)[:height,:width],format='rgb24');frame.pts=pts[number]-pts[first];frame.time_base=base
            for packet in stream.encode(frame):output.mux(packet)
        for packet in stream.encode():output.mux(packet)
    return {'offset':reader.times[first],'first_source_frame':first,'last_source_frame':last,'source_pts':pts[first:last+1],'source_time_base':str(base),'kind':'clip'}

def export_report(documents,path,*,sources=None,media='none',include_hands=False,anonymous=False,cache_root=None,pdf=False,progress=lambda value:None,cancelled=lambda:False):
    """Stage all output locally; leave the previous report intact on failure/cancellation."""
    if media not in ('none','links','clips'):raise ValueError('Unknown media mode')
    path=Path(path).resolve();sources=sources or {};documents=copy.deepcopy(list(documents))
    if not documents:raise ValueError('Choose at least one attempt')
    for d in documents:validate(d)
    if path in [Path(p).resolve() for p in sources.values()]:raise ValueError('Report must not overwrite a source video')
    sidecar=path.with_suffix('.json')
    if sidecar.exists():
        try:previous=json.loads(sidecar.read_text(encoding='utf-8'))
        except (ValueError,OSError):previous={}
        if isinstance(previous,dict) and 'schema_version' in previous and 'source' in previous:raise ValueError('Report sidecar would overwrite a labels file; choose another name')
    path.parent.mkdir(parents=True,exist_ok=True);parts=[];payload={};records=[];summaries=[];stills={};media_folder=path.stem+'-media-'+uuid4().hex[:8]
    with tempfile.TemporaryDirectory(prefix='.climb-report-',dir=path.parent) as temp:
        stage=Path(temp);assets=stage/media_folder;assets.mkdir();counter=0
        for n,d in enumerate(documents):
            if cancelled():raise InterruptedError('Report export cancelled')
            name=f'Athlete {n+1}' if anonymous else d['climber'];label=name+' · attempt '+d['attempt'];m=metrics(d);events=observations(d);coach=d.get('coaching',{});context=d.get('context',{});media_map={};reader=None
            identity=d.get('attempt_id') or d['source']['sha256'];source=sources.get(identity) or sources.get(d['source']['sha256'])
            selected=[e for e in events if include_hands or e['kind'] in ('slip','both_off','foot_release') or e.get('observation') or e.get('interpretation')]
            if media!='none' and selected:
                if source is None or not Path(source).is_file():raise ValueError('Locate original video for '+label+' before including media')
                from .video import index_video,VideoReader
                progress('Verifying original checksum and frame timestamps · '+label)
                index=index_video(source,cancelled=cancelled)
                if any(index['source'][k]!=d['source'][k] for k in ('sha256','time_base','first_pts','frame_count')):raise ValueError('Video identity does not match measurements for '+label)
                from .footwork import validate_track
                points=validate_track(d)+[p for p in (d['start'],d['end']) if p]+[p['point'] for p in d.get('checkpoints',[])]
                points += [e['start'] for e in d['open_events']]
                for point in points:
                    if index['pts'][point['frame']]!=point['pts']:raise ValueError('Measurement does not match the source frame')
                for e in events:
                    for point in (e['start'],e.get('end')):
                        if point and index['pts'][point['frame']]!=point['pts']:raise ValueError('Observation does not match the source frame')
                if media=='clips':
                    from .preview_cache import open_preview
                    from .storage import folders
                    reader=open_preview(folders(cache_root)[0],index) if cache_root else None
                    reader=reader or VideoReader(source,index,'cpu')
                try:
                    for e in selected:
                        counter+=1;progress(f'Preparing {label} · section {counter}')
                        if cancelled():raise InterruptedError('Report export cancelled')
                        if media=='links':media_map[e['id']]={'url':Path(source).resolve().as_uri(),'offset':0,'kind':'link'}
                        else:
                            filename=f'section-{counter}.mp4';entry=write_clip(reader,e,assets/filename,cancelled);entry['url']=quote(media_folder+'/'+filename);
                            from PIL import Image
                            poster=filename.replace('.mp4','.png');Image.fromarray(reader.frame(e['start']['frame'])).save(assets/poster);entry['poster']=quote(media_folder+'/'+poster);stills.setdefault(identity,{})[e['id']]=assets/poster;media_map[e['id']]=entry
                finally:
                    if reader:reader.close()
            goal=coach.get('goal') or 'No session goal recorded';facts=[('Confirmed foot slips',display(m['confirmed_slips']),f"{m['candidate_slips']} candidates / uncertain observations"),('Unplanned both-feet-off',display(m['unplanned_seconds'],' s'),'Intentional '+display(m['intentional_seconds'],' s')+' shown separately'),('Footwork coverage',display(m['coverage_share']*100 if m['coverage_share'] is not None else None,'%'),display(m['reviewed_seconds'],' s')+' visible and reviewed')]
            body='<h2>'+escape(label)+'</h2><p class="muted">'+escape(d['route']+' · '+d['outcome']+' · '+' · '.join(v for v in context.values() if v))+'</p><p class="goal">'+escape(goal)+'</p><div class="stats">'+''.join('<div><strong>'+escape(value)+'</strong><span>'+escape(title)+'</span><br><small>'+escape(note)+'</small></div>' for title,value,note in facts)+'</div>'
            if m['coverage_share'] is not None:body+=f'<div class="coverage" aria-label="{m["coverage_share"]:.0%} reviewed coverage"><span style="width:{100*m["coverage_share"]:.3f}%"></span></div>'
            if m['pending']:body+='<p><strong>Unfinished feet-off timer:</strong> totals stay unknown until it is closed and reviewed.</p>'
            if m['fall_review_needed']:body+='<p><strong>Fall start not marked:</strong> footwork totals remain unknown because time in the air after the fall cannot yet be excluded.</p>'
            body+='<p class="muted">Both feet off: '+escape(display(m['both_off_seconds'],' s'))+' / '+escape(display(m['reviewed_seconds'],' s'))+' = '+escape(display(m['both_off_share']*100 if m['both_off_share'] is not None else None,'%'))+' of observable reviewed time. This is a description, not a quality rating. Occluded and unreviewed footage is excluded.</p>'
            cards=[];event_rows=[]
            highlighted=sorted(events,key=lambda e:(not bool(e.get('action') or e.get('interpretation')),e.get('status')!='confirmed',e['start']['seconds']))[:3]
            for i,e in enumerate(events):
                key=f'a{n}-e{i}';point=e['start'];end=e.get('end') or point;media_entry=media_map.get(e['id']);payload[key]={'label':e['label'],'frame':point['frame'],'start':point['seconds'],'end':end['seconds'],'media':media_entry}
                controls='<span class="muted">Video not included for this event</span>' if not media_entry else f'<div class="actions"><button data-replay="{key}" data-context="false">Replay event</button><button data-replay="{key}" data-context="true">Replay with context</button></div>'
                card='<article class="evidence"><span class="tag">'+escape(e['status']+' · '+e['intent'])+'</span><h3>'+escape(e['label']+' · '+e['limb'])+'</h3><p class="muted">Original frame '+str(point['frame'])+' · '+f'{point["seconds"]:.3f} s · PTS {point["pts"]}'+'</p>'
                for field,title in [('observation','Observed'),('interpretation','Coach interpretation'),('action','Agreed action')]:
                    if e.get(field):card+='<p class="notes"><strong>'+title+':</strong> '+escape(e[field])+'</p>'
                if media_entry and media_entry.get('poster'):card+='<figure><img style="max-width:100%;max-height:300px" src="'+escape(media_entry['poster'],quote=True)+'" alt="Evidence at original frame '+str(point['frame'])+'"><figcaption class="muted">Original frame '+str(point['frame'])+' · review copy</figcaption></figure>'
                card+=controls+'</article>'
                cards.append(card)
                event_rows.append([e['label'],e['limb'],e['intent'],e['status'],f'{point["seconds"]:.3f}',point['frame'],point['pts'],f'{end["seconds"]-point["seconds"]:.3f}' if e['end'] else 'Point event'])
                records.append({'athlete':name,'attempt':d['attempt'],'route':d['route'],'event_id':e['id'],'kind':e['kind'],'limb':e['limb'],'intent':e['intent'],'review_state':e['status'],'start_frame':point['frame'],'start_pts':point['pts'],'start_seconds':point['seconds'],'end_frame':end['frame'] if e['end'] else None,'end_pts':end['pts'] if e['end'] else None,'end_seconds':end['seconds'] if e['end'] else None,'source_sha256':d['source']['sha256'],'observation':e.get('observation',''),'interpretation':e.get('interpretation',''),'action':e.get('action','')})
            if cards:body+='<h3>Review these moments first</h3>'+''.join(cards[events.index(e)] for e in highlighted)
            for field,title in [('reflection','Athlete reflection'),('action','Agreed next action'),('retest','Next-session check')]:body+='<h3>'+title+'</h3><p class="notes">'+escape(coach.get(field) or 'Not recorded')+'</p>'
            body+='<details><summary>Full evidence index and timing appendix</summary><div>'+table(['Observation','Limb','Intent','Review','Video s','Frame','PTS','Length s'],event_rows)+''.join(cards)+'</div></details>'
            body+='<details><summary>Coverage and provenance</summary><div>'+table(['Coverage','Start frame','End frame','Start s','End s'],[[c['state'],c['start']['frame'],c['end']['frame'],c['start']['seconds'],c['end']['seconds']] for c in d.get('footwork',{}).get('coverage',[])])+f'<p class="muted">Source SHA256 <code>{d["source"]["sha256"]}</code><br>Time base {escape(d["source"]["time_base"])} · first PTS {d["source"]["first_pts"]} · schema {escape(d["schema_version"])} · definition 1.0.0 · app {escape(__version__)}<br>Unfinished hand timers: {len(d["open_events"])}; unfinished foot interval: {bool(d.get("footwork",{}).get("pending"))}. These are excluded.</p></div></details>'
            parts.append('<section>'+body+'</section>');summaries.append(dict(athlete=name,attempt=d['attempt'],route=d['route'],**m))
        comparison=section_comparison(documents,anonymous)
        if comparison:parts.append('<section><h2>Matched checkpoints · reference is the first selected attempt</h2><p>Arrival times are relative to each climb start. Differences describe timing, not climbing ability; repeated or missing arrivals remain unknown. Compare camera coverage and route context before interpreting a difference.</p>'+table(['Athlete','Attempt','Checkpoint','Arrival','Reference','Difference','State'],comparison)+'</section>')
        report_data=json.dumps(payload,ensure_ascii=True).replace('<','\\u003c');html='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Climb Studio · Coaching review</title><style>'+CSS+'</style></head><body><main><header><p class="muted">Climb Studio · Local coaching review</p><h1>Observe the moment. Agree the next step.</h1><p>Human-marked observations with explicit review states and coach interpretations. Video timing does not measure force, fatigue, energy expenditure or the cause of a fall.</p><p class="print-note">Video replay is available in the interactive HTML. This printed copy retains original frame numbers and timestamps.</p></header><section id="player" class="player" hidden><div class="actions"><strong id="playTitle"></strong><button id="closePlayer">Close replay</button></div><video id="video" controls playsinline preload="metadata"></video><p id="playStatus" class="muted" aria-live="polite"></p></section>'+''.join(parts)+'<footer><p class="muted">No network assets or uploads. Media mode: '+media+'. Share accompanying media folders with this HTML when using portable sections. Original-video links depend on this computer and browser codec support. Replay pixels may be compressed; source frame and PTS identity remain in the measurements.</p></footer></main><script id="reportData" type="application/json">'+report_data+'</script><script>'+SCRIPT+'</script></body></html>'
        (stage/path.name).write_text(html,encoding='utf-8')
        (stage/(path.stem+'.json')).write_text(json.dumps({'app_version':__version__,'definition_version':'1.0.0','media_mode':media,'summaries':summaries,'events':records,'attempts':[dict(d,climber=f'Athlete {i+1}' if anonymous else d['climber']) for i,d in enumerate(documents)],'replay':payload},indent=2),encoding='utf-8')
        for suffix,rows in [('events',records),('summary',summaries)]:
            with (stage/(path.stem+'-'+suffix+'.csv')).open('w',newline='',encoding='utf-8-sig') as f:
                writer=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['athlete','attempt']);writer.writeheader()
                writer.writerows({k:("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v) for k,v in row.items()} for row in rows)
        if pdf:progress('Building printable PDF');export_pdf(documents,stage/(path.stem+'.pdf'),anonymous,stills)
        if cancelled():raise InterruptedError('Report export cancelled')
        published=[];media_target=path.parent/media_folder
        try:
            if media=='clips' and any(assets.iterdir()):assets.replace(media_target)
            files=[f for f in stage.iterdir() if f.is_file() and f.name!=path.name]+[stage/path.name]
            for file in files:
                target=path.parent/file.name;backup=stage/('backup-'+uuid4().hex) if target.exists() else None
                if backup:shutil.copy2(target,backup)
                published.append((target,backup));file.replace(target)
        except Exception:
            for target,backup in reversed(published):
                if backup:backup.replace(target)
                elif target.exists():target.unlink()
            if media_target.exists():shutil.rmtree(media_target)
            raise
    progress('Report ready');return path


def export_pdf(documents,path,anonymous=False,stills=None):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,LongTable,PageBreak,Image,KeepTogether
    import reportlab
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    fonts=Path(reportlab.__file__).parent/'fonts'
    for name,file in [('Review','Vera.ttf'),('ReviewBold','VeraBd.ttf'),('ReviewItalic','VeraIt.ttf'),('ReviewBoldItalic','VeraBI.ttf')]:
        if name not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont(name,str(fonts/file)))
    pdfmetrics.registerFontFamily('Review',normal='Review',bold='ReviewBold',italic='ReviewItalic',boldItalic='ReviewBoldItalic')
    styles=getSampleStyleSheet()
    for style in styles.byName.values():
        if hasattr(style,'fontName'):style.fontName='ReviewBold' if style.fontName.endswith('Bold') else 'Review'
    styles.add(ParagraphStyle(name='Cell',fontName='Review',fontSize=8,leading=11));story=[];width=A4[0]-80
    def para(value,style='BodyText'):return Paragraph(escape(str(value)).replace('\n','<br/>'),styles[style])
    def add(value,style='BodyText'):story.extend((para(value,style),Spacer(1,10)))
    def grid(headers,rows):
        data=[[para(x,'Cell') for x in headers]]+[[para(x,'Cell') for x in row] for row in rows]
        t=LongTable(data,colWidths=[width/len(headers)]*len(headers),repeatRows=1,splitInRow=1);t.setStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e5e7eb')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),8)]);story.extend((t,Spacer(1,12)))
    for i,d in enumerate(documents):
        if i:story.append(PageBreak())
        name=f'Athlete {i+1}' if anonymous else d['climber'];m=metrics(d);c=d.get('coaching',{});add(name+' · attempt '+d['attempt'],'Title');add(d['route']+' · '+d['outcome']+' · '+' · '.join(v for v in d.get('context',{}).values() if v));add(c.get('goal') or 'No session goal recorded','Heading2')
        grid(['Confirmed slips','Unplanned both feet off','Footwork coverage'],[[display(m['confirmed_slips']),display(m['unplanned_seconds'],' s'),display(m['coverage_share']*100 if m['coverage_share'] is not None else None,'%')]])
        add(f"Candidates: {m['candidate_slips']}. Intentional feet off: {display(m['intentional_seconds'],' s')}. Total feet off {display(m['both_off_seconds'],' s')} / reviewed {display(m['reviewed_seconds'],' s')}. This is a description, not a quality score.")
        if m['fall_review_needed']:add('Fall start not marked: totals unknown until time after the fall can be excluded.')
        for key,title in [('reflection','Athlete reflection'),('action','Agreed next action'),('retest','Next-session check')]:
            story.extend((KeepTogether([para(title,'Heading3'),Spacer(1,6),para(c.get(key) or 'Not recorded')]),Spacer(1,12)))
        events=observations(d)
        if events:story.append(PageBreak());add('Review these moments first','Heading1')
        images=(stills or {}).get(d.get('attempt_id') or d['source']['sha256'],{})
        for e in sorted(events,key=lambda e:(not bool(e.get('action') or e.get('interpretation')),e.get('status')!='confirmed',e['start']['seconds']))[:3]:
            card_start=len(story)
            add(e['label']+' · '+e['limb']+' · '+e['status'],'Heading3');add(f"Original frame {e['start']['frame']} · PTS {e['start']['pts']} · video {e['start']['seconds']:.3f} s · intent {e['intent']}")
            if e['id'] in images:
                image=Image(str(images[e['id']]));scale=min(width/image.imageWidth,110/image.imageHeight);image.drawWidth=image.imageWidth*scale;image.drawHeight=image.imageHeight*scale;story.extend((image,Spacer(1,10)))
            for key,title in [('observation','Observed'),('interpretation','Coach interpretation'),('action','Agreed action')]:
                if e.get(key):add(title+': '+e[key])
            card=story[card_start:];del story[card_start:];story.append(KeepTogether(card))
        story.append(PageBreak());add('Evidence and timing appendix','Heading1');grid(['Event / limb','Review / intent','Original frame / PTS','Video seconds','Length s'],[[e['label']+' / '+e['limb'],e['status']+' / '+e['intent'],str(e['start']['frame'])+' / '+str(e['start']['pts']),f"{e['start']['seconds']:.3f}",f"{e['end']['seconds']-e['start']['seconds']:.3f}" if e['end'] else 'Point event'] for e in events])
        for e in events:
            if any(e.get(k) for k in ('observation','interpretation','action')):
                add(e['label']+f" · {e['start']['seconds']:.3f} s",'Heading3')
                for k,title in [('observation','Observed'),('interpretation','Interpretation'),('action','Action')]:
                    if e.get(k):add(title+': '+e[k])
        add('Coverage and provenance','Heading2');grid(['Coverage','Start frame / s','End frame / s'],[[x['state'],f"{x['start']['frame']} / {x['start']['seconds']:.3f}",f"{x['end']['frame']} / {x['end']['seconds']:.3f}"] for x in d.get('footwork',{}).get('coverage',[])])
        add('Source SHA256: '+d['source']['sha256']);add('Time base: '+d['source']['time_base']+' · schema '+d['schema_version']+' · definition 1.0.0 · app '+__version__);add('Occluded and unreviewed footage is unknown. Draft timers are excluded. Timing does not establish fatigue, force or causes of falls. Replay is available in the HTML report.')
    comparison=section_comparison(documents,anonymous)
    if comparison:
        story.append(PageBreak());add('Matched checkpoints: first attempt is the reference','Heading1');grid(['Athlete','Attempt','Point','Arrival','Reference','Difference','State'],comparison);add('Different routes and repeated or missing arrivals are unavailable. Differences describe marked timing, not climbing ability.')
    def footer(canvas,doc):canvas.setFont('Review',8);canvas.drawString(40,24,'Climb Studio · Manual coaching observations');canvas.drawRightString(A4[0]-40,24,str(doc.page))
    SimpleDocTemplate(str(path),pagesize=A4,rightMargin=40,leftMargin=40,topMargin=40,bottomMargin=40,title='Climb Studio coaching review').build(story,onFirstPage=footer,onLaterPages=footer)
    return Path(path)


def main(argv=None):
    import argparse
    from .labels import load
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--labels',type=Path,nargs='+',required=True,help='Label files or folders of *.labels.json')
    parser.add_argument('--output',type=Path,required=True,help='Local HTML destination')
    parser.add_argument('--media',choices=('none','links','clips'),default='none')
    parser.add_argument('--video-dir',type=Path,help='Folder containing the original files named in the labels')
    parser.add_argument('--cache-root',type=Path,help='App data root containing prepared previews')
    parser.add_argument('--pdf',action='store_true');parser.add_argument('--anonymous',action='store_true');parser.add_argument('--include-hands',action='store_true')
    args=parser.parse_args(argv)
    try:
        files=[f for p in args.labels for f in (sorted(p.glob('*.labels.json')) if p.is_dir() else [p])]
        if not files:raise ValueError('No label files found')
        targets={args.output.resolve(),args.output.with_suffix('.json').resolve(),args.output.with_suffix('.pdf').resolve()}
        if any(p.resolve() in targets for p in files):raise ValueError('Output must differ from label files')
        documents=[load(p) for p in files];sources={}
        if args.video_dir:
            root=args.video_dir.resolve()
            for d in documents:
                source=(root/d['source']['file']).resolve()
                if not source.is_relative_to(root):raise ValueError('Video filename must stay inside the video directory')
                sources[d.get('attempt_id') or d['source']['sha256']]=source
        print(export_report(documents,args.output,sources=sources,media=args.media,cache_root=args.cache_root,pdf=args.pdf,anonymous=args.anonymous,include_hands=args.include_hands,progress=print))
    except (OSError,ValueError,KeyError,TypeError) as e:parser.exit(2,f'Coaching report failed: {e}\n')
    return 0

if __name__=='__main__':raise SystemExit(main())
