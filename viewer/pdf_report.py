"""Local vector PDF report from an HTML measurement snapshot."""
from pathlib import Path
from html import escape
from statistics import median
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape,A4
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,Flowable
from .report_cli import parse_export,number

INK=colors.HexColor('#18334f');BLUE=colors.HexColor('#4280d9');GREEN=colors.HexColor('#22a781');ORANGE=colors.HexColor('#eba442');PALE=colors.HexColor('#e8eef6')
def text(value):
    if value is None:return 'Unmarked'
    value=f'{value:.2f}' if isinstance(value,float) else str(value)
    return escape(value.replace('→','->').replace('−','-').replace('–','-').replace('—','-').replace('’',"'").replace('·',' / '))

class Bars(Flowable):
    def __init__(self,items,width,focus,unit='s'):super().__init__();self.items=items;self.width=width;self.height=len(items)*26+12;self.focus=focus;self.unit=unit
    def draw(self):
        c=self.canv;maximum=max((v for _,v in self.items),default=1) or 1
        for i,(name,value) in enumerate(self.items):
            y=self.height-26*(i+1);c.setFont('Review',9);c.setFillColor(INK);c.drawString(0,y+5,name)
            if name==self.focus:c.setFont('Review',7);c.drawString(0,y-4,'Focus athlete');c.setFont('Review',9)
            w=value/maximum*(self.width-180);c.setFillColor(ORANGE if name==self.focus else BLUE);c.roundRect(95,y,w,17,3,stroke=0,fill=1)
            c.setFillColor(INK);c.drawString(103+w,y+5,f'{value:.2f}{self.unit}')

def export_pdf(source,output,focus=None,route=''):
    import hashlib
    source=Path(source);output=Path(output)
    if output.resolve()==source.resolve():raise ValueError('PDF output must differ from source')
    _,overview,points,activities,splits=parse_export(source)
    output.parent.mkdir(parents=True,exist_ok=True)
    styles=getSampleStyleSheet();styles.add(ParagraphStyle(name='Cell',fontName='Helvetica',fontSize=8,leading=11,textColor=INK));styles.add(ParagraphStyle(name='SmallNote',fontSize=9,leading=13,textColor=INK))
    from .reporting import pdf_fonts
    pdf_fonts(styles)
    styles['Title'].textColor=INK;styles['Heading1'].textColor=INK
    story=[];width=landscape(A4)[0]-84
    def paragraph(value,style='SmallNote'):story.append(Paragraph(value,styles[style]));story.append(Spacer(1,10))
    def heading(value):paragraph(text(value),'Heading1')
    def grid(headers,rows,widths=None):
        data=[[Paragraph(text(h),styles['Cell']) for h in headers]]+[[Paragraph(text(v),styles['Cell']) for v in row] for row in rows]
        t=Table(data,splitInRow=1,colWidths=widths or [width/len(headers)]*len(headers),repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),PALE),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f7f9fc')]),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor('#b5c8df')),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]));story.append(t);story.append(Spacer(1,12))
    from .reporting import read_snapshot,records,legacy_records,pdf_overview,eligible_clip_rows,gap_peers
    documents=read_snapshot(source)
    data=records(documents) if documents is not None else legacy_records(overview,points,activities)
    if focus:data.sort(key=lambda r:not r['name'].startswith(focus+' · '))
    paragraph('Climb comparison','Title');paragraph(text(route or source.stem))
    pdf_overview(story,data,width,styles)
    story.append(PageBreak());heading('Shared point arrivals')
    grid(['Athlete','Point','Arrival from start s','Point to climb end s','Comment'],[[p['athlete'],p['point'],number(p['seconds from climb start']),number(p['seconds from point to climb end']),p.get('comment','')] for p in points])
    arrivals=sorted([(p['athlete'],number(p['seconds from climb start'])) for p in points if p['point']=='REST' and number(p['seconds from climb start']) is not None],key=lambda x:x[1])
    if arrivals:heading('REST arrival');story.append(Bars(arrivals,width,focus))
    if focus:
        targets=[s for s in overview if s['athlete']==focus]
        if len(targets)!=1:raise ValueError('Focus must identify exactly one athlete/attempt in this export')
        target=targets[0];own=list(eligible_clip_rows(activities,target).values())
        story.append(PageBreak());heading(f'{focus}: clips compared with peers')
        cliprows=[]
        for a in own:
            peers=[number(p[a['quickdraw']]['duration seconds']) for other in overview if other is not target and other.get('route')==target.get('route') and a['quickdraw'] in (p:=eligible_clip_rows(activities,other))]
            duration=number(a['duration seconds']);med=median(peers) if peers else None
            cliprows.append([a['quickdraw'],a['hand'],duration,med,duration-med if med is not None else None,len(peers)])
        grid(['Draw','Hand','Focus duration s','Peer median s','Difference s','Matched peers'],cliprows)
        paragraph('Only unique, complete clips at the same draw on the same route are compared. More hand alternation or less rest is not automatically better. Review the same stance and quickdraw before interpreting a time difference.')
        heading('Gaps between clips after removing recovery')
        gaps=[]
        for s in splits:
            if s['athlete']!=focus:continue
            peers=gap_peers(splits,s,overview)
            residual=number(s['gap outside marked rest seconds']);med=median(peers) if peers else None
            delta=residual-med if residual is not None and med is not None else None
            gaps.append([s['from quickdraw']+' -> '+s['to quickdraw'],number(s['gap seconds']),number(s['total marked rest in gap seconds']),residual,med,delta,'Longer' if delta is not None and delta>0 else 'Shorter' if delta is not None and delta<0 else 'Equal / unknown'])
        grid(['Split','Raw gap s','Recovery removed s','Outside recovery s','Peer median s','Difference s','Flag'],gaps)
        paragraph('Recovery removed includes chalking and dedicated rest, merged within the gap. Overlaps are subtracted once. The remainder can include movement, route reading or unmarked rest. Timing alone cannot establish why an athlete fell.')
    story.append(PageBreak());heading('Every completed clip')
    grid(['Athlete','Draw','Hand','Method','Start from climb s','Completed from climb s','Duration s'],[[a['athlete'],a['quickdraw'],a['hand'],a.get('clip method') or 'Unmarked',number(a['start from climb seconds']),number(a['end from climb seconds']),number(a['duration seconds'])] for a in activities if a['activity']=='clip' and a['status']=='closed'])
    story.append(PageBreak());heading('Every between-clip split')
    grid(['Athlete','Draw split','Gap s','Completion split s','Recovery removed s','Outside recovery s'],[[s['athlete'],s['from quickdraw']+' -> '+s['to quickdraw'],number(s['gap seconds']),number(s['completion to completion seconds']),number(s['total marked rest in gap seconds']),number(s['gap outside marked rest seconds'])] for s in splits])
    story.append(PageBreak());heading('Rest and chalking activity log')
    grid(['Athlete','Activity','Hand','Start from climb s','End from climb s','Duration s','Status'],[[a['athlete'],a['activity'],a['hand'],number(a['start from climb seconds']),number(a['end from climb seconds']),number(a['duration seconds']),a['status']] for a in activities if a['activity'] in ('rest','chalk')])
    if documents is not None:
        from .footwork import observations
        from .reporting import pdf_footwork_timeline
        for d in documents:
            story.append(PageBreak());heading(d['climber']+' · '+d['attempt']+' · evidence and provenance')
            coach=d.get('coaching',{})
            for key,title in [('goal','Session goal'),('reflection','Athlete reflection'),('action','Agreed action'),('retest','Next-session check')]:
                if coach.get(key):paragraph(text(title+': '+coach[key]))
            events=observations(d)
            grid(['Event / limb','Review / intent','Source frame / PTS','Video s','Length s'],[[e['label']+' / '+e['limb'],e['status']+' / '+e['intent'],str(e['start']['frame'])+' / '+str(e['start']['pts']),e['start']['seconds'],e['end']['seconds']-e['start']['seconds'] if e['end'] else None] for e in events])
            story.append(pdf_footwork_timeline(d,width));story.append(Spacer(1,12))
            for e in events:
                for key,title in [('observation','Observed'),('interpretation','Interpretation'),('action','Action')]:
                    if e.get(key):paragraph(text(e['label']+' · '+title+': '+e[key]))
            grid(['Coverage','Start frame / PTS','End frame / PTS','Start video s','End video s'],[[span['state'],str(span['start']['frame'])+' / '+str(span['start']['pts']),str(span['end']['frame'])+' / '+str(span['end']['pts']),span['start']['seconds'],span['end']['seconds']] for span in d.get('footwork',{}).get('coverage',[])])
            paragraph(text('Original SHA256: '+d['source']['sha256']+' · time base '+d['source']['time_base']+' · first PTS '+str(d['source']['first_pts'])+' · schema '+d['schema_version']))
    heading('Source and limits')
    paragraph('Source: '+text(source.name)+'<br/>SHA256: '+hashlib.sha256(source.read_bytes()).hexdigest())
    paragraph('All values derive solely from this HTML snapshot. Three-decimal or two-decimal values retain source rounding. Missing outcomes cannot be recovered from older exports. No footage, labels or telemetry are uploaded by this generator. No physiological recovery or fatigue is measured. Equal clip counts do not establish equal final holds; compare matched progress before attempt duration.')
    def footer(canvas,doc):
        canvas.setFont('Review',8);canvas.setFillColor(INK);canvas.drawString(42,22,'Climbing comparison / private local report');canvas.drawRightString(landscape(A4)[0]-42,22,f'Page {doc.page}')
    doc=SimpleDocTemplate(str(output),pagesize=landscape(A4),leftMargin=42,rightMargin=42,topMargin=38,bottomMargin=38,title='Climb comparison',author='Climb Studio')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return output
