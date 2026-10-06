"""Self-contained SVG charts from the selected export's rounded measurements."""
from html import escape
from math import isfinite

def number(v):
    try:
        value=float(v);return value if isfinite(value) else None
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
    from .reporting import legacy_records,overview_html
    data=legacy_records(overview,points,activities)
    if focus:data.sort(key=lambda r:not r['name'].startswith(focus+' · '))
    return overview_html(data)

STYLE='''
:root{color-scheme:light dark;--bg:#f5f6f7;--panel:#fff;--ink:#20252b;--muted:#59616b;--line:#d1d5da;--accent:#245fc4}
@media(prefers-color-scheme:dark){:root{--bg:#151719;--panel:#202326;--ink:#f3f4f5;--muted:#b2b8bf;--line:#535c66;--accent:#8cbcff}}
*{box-sizing:border-box}body{font:15px/1.55 system-ui,sans-serif;color:var(--ink);background:var(--bg);max-width:1280px;margin:auto;padding:28px 24px 60px}h1{font-size:32px;line-height:1.2;letter-spacing:-.025em}h2{font-size:22px;margin:0 0 14px}h3{font-size:16px}section{background:var(--panel);padding:24px;border:1px solid var(--line);border-radius:6px;margin:20px 0}p{color:var(--muted)}.scroll{overflow:auto;max-height:650px}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:10px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}th{background:var(--bg)}svg text{fill:var(--ink)}svg{width:100%;font:14px system-ui,sans-serif;fill:var(--ink)}code{overflow-wrap:anywhere}a{color:var(--accent)}details{border-top:1px solid var(--line);padding:16px 0}summary{cursor:pointer;font-weight:600}summary:focus-visible,select:focus-visible,input:focus-visible{outline:3px solid var(--accent);outline-offset:3px}header p{margin:8px 0}.eyebrow{font-size:12px;color:var(--muted)}.chart-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
@media(max-width:760px){body{padding:16px}section{padding:16px}.chart-grid{grid-template-columns:1fr}}
@media print{:root{color-scheme:light;--bg:#fff;--panel:#fff;--ink:#20252b;--muted:#59616b;--line:#aeb5bd;--accent:#245fc4}body{padding:0;background:white}section{padding:12px;box-shadow:none}.scroll{max-height:none;overflow:visible}thead{display:table-header-group}h2,h3{break-after:avoid}svg{break-inside:avoid}}
'''
from .reporting import OVERVIEW_CSS
STYLE+=OVERVIEW_CSS
