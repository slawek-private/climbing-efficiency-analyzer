"""Reproducible offline reports from saved labels or an exported HTML snapshot."""
import argparse,csv,hashlib,json,math
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from statistics import median
from .comparison import export_comparison
from .labels import load
from .report_visuals import charts,STYLE,bars

class Tables(HTMLParser):
    def __init__(self):super().__init__();self.tables=[];self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=='table':self.tables.append([])
        elif tag=='tr':self.row=[]
        elif tag in ('td','th'):self.cell=[]
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.cell is not None and self.row is not None:self.row.append(''.join(self.cell));self.cell=None
        elif tag=='tr' and self.row is not None and self.tables:self.tables[-1].append(self.row);self.row=None

def number(v):
    try:
        result=float(v)
        return result if math.isfinite(result) else None
    except (TypeError,ValueError):return None
def table(headers,data):
    def value(v):return 'Unavailable / unmarked' if v is None else f'{v:.2f}' if isinstance(v,float) else str(v)
    return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+escape(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+escape(value(v))+'</td>' for v in row)+'</tr>' for row in data)+'</tbody></table></div>'
def section(title,body):return '<section><h2>'+escape(title)+'</h2>'+body+'</section>'
def parse_export(source):
    parser=Tables();parser.feed(Path(source).read_text(encoding='utf-8-sig'))
    def find(required):
        for t in parser.tables:
            if t and required<=set(t[0]):
                if any(len(r)!=len(t[0]) for r in t[1:]):raise ValueError('Malformed source table')
                return [dict(zip(t[0],r)) for r in t[1:]]
        raise ValueError('Source is missing table columns: '+', '.join(sorted(required)))
    return parser,find({'athlete','climb seconds','total rest marked seconds'}),find({'athlete','point'}),find({'athlete','activity'}),find({'athlete','from quickdraw'})

def build_report(source,output,focus=None,route=''):
    source=Path(source);output=Path(output)
    if source.resolve()==output.resolve():raise ValueError('Output must differ from source')
    parser,overview,points,activities,splits=parse_export(source)
    output.parent.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    parts=[section('Measurement source','<p>This report uses only '+escape(source.name)+'. Values derived from an HTML snapshot inherit the source’s rounding. Missing measurements remain unknown; these are human annotations, not independently validated accuracy measurements. Combined recovery is the union of dedicated rest and chalking across hands. The remainder is not measured active movement.</p>')]
    from .reporting import read_snapshot,records,overview_html,details_html,snapshot,eligible_clip_rows,gap_peers
    documents=read_snapshot(source)
    if documents is not None:
        if focus:documents.sort(key=lambda d:d['climber']!=focus)
        parts.insert(0,overview_html(records(documents)))
    else:parts.insert(0,charts(overview,points,activities,section,table,focus=focus))
    if focus:
        targets=[s for s in overview if s['athlete']==focus]
        if len(targets)!=1:raise ValueError('Focus must identify exactly one athlete/attempt in this export')
        target=targets[0]
        def matched(row):return all(row.get(k) is None or row.get(k)==target.get(k) for k in ('athlete','attempt','video'))
        own=eligible_clip_rows(activities,target)
        comparisons=[]
        for other in overview:
            if other is target or other.get('route')!=target.get('route'):continue
            peer=eligible_clip_rows(activities,other)
            shared=sorted(set(own)&set(peer),key=lambda x:float(x))
            ours=sum(number(own[k]['duration seconds']) for k in shared) if shared else None
            theirs=sum(number(peer[k]['duration seconds']) for k in shared) if shared else None
            comparisons.append([other['athlete'],other['attempt'],', '.join(shared),ours,theirs,ours-theirs if ours is not None else None])
        parts.append(section(f'{focus}: matched clipping comparison',table(['Peer','Attempt','Shared draws','Focus clip time s','Peer clip time s','Focus − peer s'],comparisons)+'<p>Positive differences mean the focus athlete spent longer. Matching the same draws avoids comparing a five-clip attempt with an eight-clip total.</p>'))
        gap_rows=[]
        for row in splits:
            if not matched(row):continue
            residual=number(row['gap outside marked rest seconds'])
            peers=gap_peers(splits,row,overview)
            med=median(peers) if peers else None
            delta=residual-med if residual is not None and med is not None else None
            gap_rows.append([row['from quickdraw']+' → '+row['to quickdraw'],number(row['gap seconds']),number(row['total marked rest in gap seconds']),residual,med,delta,'Longer than peer median' if delta is not None and delta>0 else 'Shorter than peer median' if delta is not None and delta<0 else 'Equal / unavailable'])
        parts.append(section(f'{focus}: gaps minus marked recovery',table(['Split','Raw gap s','Recovery removed s','Unclassified s','Peer median s','Difference s','Flag'],gap_rows)+(bars('Unclassified time between clips',[(r[0],r[3]) for r in gap_rows if r[3] is not None],' s') if gap_rows else '')+'<p>Subtracts the union of marked rest and chalking within each gap. Overlaps count once. These descriptive flags are not statistical significance or a measure of movement time.</p>'))
        with output.with_name(output.stem+'-focus-gaps.csv').open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.writer(f);writer.writerow(['split','gap_seconds','recovery_removed_seconds','outside_recovery_seconds','peer_median_seconds','difference_seconds','flag']);writer.writerows(gap_rows)
    # Copy data as escaped text, never active source HTML, scripts or remote assets.
    for title,required in [('Athlete overview',{'climb seconds','athlete'}),('Point arrivals',{'point','arrival frame'}),('Hand patterns',{'clip sequence'}),('Between clips',{'from quickdraw'}),('Activity log',{'activity','start frame'})]:
        t=next((t for t in parser.tables if t and required<=set(t[0])),None)
        if t:parts.append(section(title,table(t[0],t[1:])))
    parts.append(section('Reproducibility','<p>Source SHA256: <code>'+digest+'</code>. Source file is preserved. No videos are embedded; no external fonts, scripts or services are used. End outcomes are shown only when present in the export.</p>'))
    if documents is not None:parts.append(details_html(documents))
    parts=parts[:1]+['<details><summary>Details · matched timing, full tables and provenance</summary>'+''.join(parts[1:])+'</details>']
    header='<header><div class="eyebrow">Human-assisted climbing measurements</div><h1>Climb comparison</h1><p>'+escape(route or source.stem)+'</p></header>'
    output.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Climbing comparison</title><style>'+STYLE+'</style></head><body>'+header+''.join(parts)+(snapshot(documents) if documents is not None else '')+'</body></html>',encoding='utf-8')
    output.with_suffix('.json').write_text(json.dumps({'source':source.name,'source_sha256':digest,'focus':focus,'attempts':documents,'overview':overview,'points':points,'activities':activities,'splits':splits},indent=2),encoding='utf-8')
    return output

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    inputs=parser.add_mutually_exclusive_group(required=True);inputs.add_argument('--source',type=Path,help='Existing exported HTML snapshot');inputs.add_argument('--labels',type=Path,help='Folder of saved *.labels.json or one label file')
    parser.add_argument('--pdf',type=Path,help='Also export a vector PDF locally');parser.add_argument('--output',type=Path,required=True);parser.add_argument('--focus',help='Athlete to compare with peers');parser.add_argument('--route',default='',help='Optional route description')
    args=parser.parse_args(argv)
    try:
        source=args.source
        if args.labels:
            files=sorted(args.labels.glob('*.labels.json')) if args.labels.is_dir() else [args.labels]
            if not files:raise ValueError('No label files found')
            source=args.output.with_name(args.output.stem+'-source.html')
            if any(p.resolve() in (source.resolve(),args.output.resolve()) for p in files):raise ValueError('Output must differ from labels')
            export_comparison([load(p) for p in files],source)
        print(build_report(source,args.output,args.focus,args.route))
        if args.pdf:
            from .pdf_report import export_pdf
            print(export_pdf(source,args.pdf,args.focus,args.route))
    except (OSError,ValueError,KeyError,TypeError) as error:parser.exit(2,f'Report failed: {error}\n')
    return 0

if __name__=='__main__':raise SystemExit(main())
