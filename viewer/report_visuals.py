"""Self-contained SVG charts from the selected export's rounded measurements."""
from html import escape
import math

def number(v):
    try:return float(v)
    except (ValueError,TypeError):return None

def bars(title,items,unit='',maximum=None,highlight=None):
    maximum=maximum or max((v for _,v in items),default=1)*1.12 or 1
    height=55+len(items)*45
    out=f'<svg viewBox="0 0 700 {height}" role="img" aria-label="{escape(title)}">'
    for i,(name,v) in enumerate(items):
        y=25+i*45;w=max(0,v/maximum*460);color='#f0a340' if name==highlight else '#4784df'
        if name==highlight:out+=f'<text x="0" y="{y+33}" font-size="10">Focus athlete</text>'
        out+=f'<text x="0" y="{y+19}">{escape(name)}</text><rect x="105" y="{y}" width="{w:.2f}" height="27" rx="5" fill="{color}"><title>{escape(name)}: {v:.2f}{unit}</title></rect><text x="{115+w:.2f}" y="{y+19}">{v:.2f}{unit}</text>'
    return out+'</svg>'

def charts(overview,points,activities,section,table,focus=None):
    valid=[s for s in overview if number(s['climb seconds']) is not None]
    recovery=[s for s in valid if number(s['total rest marked seconds']) is not None]
    shares=sorted([(s['athlete'],100*number(s['total rest marked seconds'])/number(s['climb seconds'])) for s in recovery],key=lambda x:x[1])
    share_table=[]
    for s in recovery:
        duration=number(s['climb seconds']);r=number(s['rest marked seconds']);c=number(s['chalk marked seconds']);total=number(s['total rest marked seconds'])
        share_table.append([s['athlete'],duration,r,100*r/duration if r is not None else None,c,100*c/duration if c is not None else None,total,100*total/duration])
    cards=[]
    for s in valid:
        name=s['athlete'];duration=number(s['climb seconds']);rest=number(s['total rest marked seconds']);pct=100*rest/duration if rest is not None else None
        circle='<circle cx="105" cy="100" r="70" fill="none" stroke="#e0e7f0" stroke-width="20"/>'
        if pct is not None:
            circumference=2*math.pi*70
            circle+=f'<circle cx="105" cy="100" r="70" fill="none" stroke="{"#f0a340" if name==focus else "#20a781"}" stroke-width="20" stroke-dasharray="{circumference*pct/100:.4f} {circumference:.4f}" transform="rotate(-90 105 100)"><title>{rest:.3f} s / {duration:.3f} s = {pct:.2f}%</title></circle>'
        center=f'{pct:.2f}%' if pct is not None else 'Unknown'
        circle+=f'<text x="105" y="98" text-anchor="middle" class="donut-value">{center}</text><text x="105" y="122" text-anchor="middle" class="donut-caption">marked recovery</text>'
        caption=f'{rest:.2f} s recovery / {duration:.2f} s climb' if rest is not None else 'Rest and chalking not marked'
        cards.append('<article class="donut-card'+(' highlight' if name==focus else '')+'"><h3>'+escape(name)+(' · Focus' if name==focus else '')+'</h3><svg viewBox="0 0 210 200" role="img" aria-label="'+escape(name+' '+center+' marked recovery')+'">'+circle+'</svg><p>'+escape(caption)+'</p></article>')
    donuts=section('Recovery as a share of the climb','<p>Green/orange = combined marked recovery; grey = time outside marked recovery. Grey includes clipping and unmarked activities, so it is not measured active climbing. Dedicated rest and chalking overlap only once. Missing recovery is unknown rather than zero.</p><div class="donut-grid">'+''.join(cards)+'</div>')
    rest_chart=section('Rest percentage comparison','<p>The selected athlete is labelled Focus. Percentages are recomputed from the source durations rather than its rounded ratio column.</p>'+bars('Combined marked recovery percentage',shares,'%',highlight=focus)+table(['Athlete','Climb s','Dedicated rest s','Dedicated rest %','Chalk s','Chalk %','Combined recovery s','Combined recovery %'],share_table)+'<p>Dedicated rest % and chalk % cannot simply be added: activities may overlap. Unmarked categories remain unknown.</p>')
    panels=[]
    for name in sorted({p['point'] for p in points}):
        arrivals=[(p['athlete']+' · '+str(p.get('attempt','')),number(p['seconds from climb start'])) for p in points if p['point']==name and number(p['seconds from climb start']) is not None]
        panels.append('<article><h3>Arrival at '+escape(name)+'</h3><p>Seconds from climb start to this named point; repeated arrivals remain separate.</p>'+bars(name+' arrival',arrivals,' s')+'</article>')
    for draw in sorted({a['quickdraw'] for a in activities if a['activity']=='clip' and a.get('quickdraw') is not None},key=str):
        clips=[a for a in activities if a['activity']=='clip' and a.get('quickdraw')==draw and a.get('status')=='closed']
        items=[(a['athlete']+' · '+str(a.get('attempt','')),number(a['duration seconds'])) for a in clips if number(a.get('duration seconds')) is not None]
        panels.append('<article><h3>Quickdraw '+escape(str(draw))+'</h3><p>Recorded clip durations at the same draw; no required clip count.</p>'+bars('Quickdraw '+str(draw),items,' s')+'</article>')
    pair=section('Shared checkpoints and quickdraws','<div class="chart-grid">'+''.join(panels)+'</div>')
    by_name={s['athlete']:s for s in valid};selected=by_name.get(focus)
    if selected is None or number(selected['total rest marked seconds']) is None:return donuts+rest_chart+pair
    selected_percent=100*number(selected['total rest marked seconds'])/number(selected['climb seconds'])
    hypothesis=section('Recovery interpretation','<div class="interpretation"><h3>Recorded recovery</h3><p>'+escape(focus)+ ' has <strong>'+f"{number(selected['total rest marked seconds']):.2f} s ({selected_percent:.2f}%)"+'</strong> combined marked recovery. Timers describe recorded time, not physiological recovery.</p><p>Very little rest may motivate a coaching question, but the annotations do not establish that insufficient rest caused a fall. Review grip, foot placement, movement errors and available rest stances. More rest is not automatically beneficial.</p></div>')
    return donuts+rest_chart+pair+hypothesis

STYLE='''
:root{--ink:#17304c;--muted:#65758a;--line:#dfe7f0}
body{font:15px/1.6 "Segoe UI",Arial,sans-serif;color:var(--ink);background:#eef3f8;max-width:1440px;margin:0 auto;padding:30px 24px 70px}
h1{font-size:40px;letter-spacing:-1.2px;line-height:1.15;margin:0 0 12px}h2{font-size:25px;letter-spacing:-.4px;margin:0 0 15px}h3{font-size:18px;margin:12px 0}
section{background:#fff;padding:30px;border:1px solid #e0e8f1;border-radius:18px;margin:24px 0;box-shadow:0 6px 22px #163a6010}
p{max-width:1100px;color:#4a6077}.scroll{overflow-x:auto;max-height:650px;border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:12px 14px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}th{background:#eaf1f8;color:#456079;font-size:12px;position:sticky;top:0;z-index:1}tbody tr:nth-child(even){background:#f8fafd}tbody tr:hover{background:#edf4ff}
li{margin:14px 0;padding-left:5px}svg{width:100%;font:15px "Segoe UI",sans-serif;fill:#34516f}
.donut-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:14px}.donut-card{background:#f7fafd;border:1px solid #e0e8f1;border-radius:14px;padding:16px;text-align:center}.donut-card h3{margin:0}.donut-card p{font-size:12px;margin:0}.donut-card svg{max-width:210px}.highlight{background:#fff8ec;border-color:#f0c987}.donut-value{font-size:25px;font-weight:700}.donut-caption{font-size:11px;fill:#6c7f93}
.chart-grid{display:grid;grid-template-columns:1fr 1fr;gap:28px}.interpretation{background:#fff8ed;border-left:4px solid #efad4c;padding:8px 24px;border-radius:8px}
code{overflow-wrap:anywhere}a{color:#2466bd}header{background:#152b46;color:#fff;padding:36px;border-radius:20px;margin-bottom:24px}header p{color:#b8cbe1}.eyebrow{text-transform:uppercase;font-size:12px;letter-spacing:2px;color:#93b6df}nav{display:flex;flex-wrap:wrap;gap:10px;margin-top:20px}nav a{color:#fff;text-decoration:none;padding:8px 15px;background:#294561;border-radius:7px}
@media(max-width:850px){body{padding:16px}section{padding:20px}.chart-grid{grid-template-columns:1fr}h1{font-size:30px}}
@media print{body{background:white;padding:0}header{background:white;color:#17304c}header p{color:#456079}nav{display:none}section{box-shadow:none;margin:12px 0;padding:18px}.scroll{max-height:none;overflow:visible}th{position:static}.donut-grid{grid-template-columns:repeat(4,1fr)}}
'''
