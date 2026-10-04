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

class Donuts(Flowable):
    def __init__(self,rows,focus,width):super().__init__();self.rows=rows;self.focus=focus;self.width=width;self.height=145
    def draw(self):
        c=self.canv;cell=self.width/len(self.rows)
        for i,row in enumerate(self.rows):
            x=(i+.5)*cell;y=82;r=36;duration=number(row['climb seconds']);rest=number(row['total rest marked seconds']);pct=100*rest/duration if rest is not None else None
            c.setFillColor(PALE);c.circle(x,y,r,stroke=0,fill=1)
            if pct is not None:
                c.setFillColor(ORANGE if row['athlete']==self.focus else GREEN);c.wedge(x-r,y-r,x+r,y+r,90,-3.6*pct,stroke=0,fill=1)
            c.setFillColor(colors.white);c.circle(x,y,r*.73,stroke=0,fill=1)
            c.setFillColor(INK);c.setFont('Helvetica-Bold',13);c.drawCentredString(x,y-4,f'{pct:.2f}%' if pct is not None else 'Unknown')
            c.setFont('Helvetica-Bold',10);c.drawCentredString(x,129,row['athlete'])
            c.setFont('Helvetica',8);c.drawCentredString(x,24,f'{rest:.2f}s / {duration:.2f}s' if rest is not None else 'Recovery unmarked')

class Bars(Flowable):
    def __init__(self,items,width,focus,unit='s'):super().__init__();self.items=items;self.width=width;self.height=len(items)*26+12;self.focus=focus;self.unit=unit
    def draw(self):
        c=self.canv;maximum=max((v for _,v in self.items),default=1) or 1
        for i,(name,value) in enumerate(self.items):
            y=self.height-26*(i+1);c.setFont('Helvetica',9);c.setFillColor(INK);c.drawString(0,y+5,name)
            w=value/maximum*(self.width-180);c.setFillColor(ORANGE if name==self.focus else BLUE);c.roundRect(95,y,w,17,3,stroke=0,fill=1)
            c.setFillColor(INK);c.drawString(103+w,y+5,f'{value:.2f}{self.unit}')

def export_pdf(source,output,focus=None,route=''):
    import hashlib
    source=Path(source);output=Path(output)
    if output.resolve()==source.resolve():raise ValueError('PDF output must differ from source')
    _,overview,points,activities,splits=parse_export(source)
    output.parent.mkdir(parents=True,exist_ok=True)
    styles=getSampleStyleSheet();styles.add(ParagraphStyle(name='Cell',fontName='Helvetica',fontSize=8,leading=11,textColor=INK));styles.add(ParagraphStyle(name='SmallNote',fontSize=9,leading=13,textColor=INK))
    styles['Title'].textColor=INK;styles['Heading1'].textColor=INK
    story=[];width=landscape(A4)[0]-84
    def paragraph(value,style='SmallNote'):story.append(Paragraph(value,styles[style]));story.append(Spacer(1,10))
    def heading(value):paragraph(text(value),'Heading1')
    def grid(headers,rows,widths=None):
        data=[[Paragraph(text(h),styles['Cell']) for h in headers]]+[[Paragraph(text(v),styles['Cell']) for v in row] for row in rows]
        t=Table(data,colWidths=widths or [width/len(headers)]*len(headers),repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),PALE),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f7f9fc')]),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor('#b5c8df')),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]));story.append(t);story.append(Spacer(1,12))
    paragraph('Climbing performance &amp; efficiency','Title');paragraph(text(route or source.stem))
    paragraph('Human-marked measurements. Recovery merges dedicated rest and chalking across hands; overlapping intervals count once. Time outside marked recovery is not measured active climbing. Missing activity is unknown, not zero. No age component is included.')
    heading('Recovery as a percentage of the climb')
    valid=[s for s in overview if number(s['climb seconds']) is not None]
    for start in range(0,len(valid),4):story.append(Donuts(valid[start:start+4],focus,width))
    paragraph('Coloured sectors: combined marked recovery. Grey: time outside marked recovery, including clipping and unclassified activities. Percentages use duration totals, not the rounded ratio column.')
    story.append(PageBreak());heading('Athlete overview')
    summary=[]
    for s in overview:
        duration=number(s['climb seconds']);rest=number(s['total rest marked seconds'])
        summary.append([s['athlete'],duration,s.get('outcome','Not present in export'),s['clip marked count'],number(s['clip marked seconds']),number(s['rest marked seconds']),number(s['chalk marked seconds']),rest,100*rest/duration if rest is not None and duration is not None else None])
    grid(['Athlete','Climb s','Outcome','Clips','Clip time s','Dedicated rest s','Chalk s','Recovery s','Recovery %'],summary)
    heading('Combined recovery share')
    story.append(Bars(sorted([(s['athlete'],100*number(s['total rest marked seconds'])/number(s['climb seconds'])) for s in valid if number(s['total rest marked seconds']) is not None],key=lambda x:x[1]),width,focus,'%'))
    story.append(PageBreak());heading('Shared point arrivals')
    grid(['Athlete','Point','Arrival from start s','Point to climb end s','Comment'],[[p['athlete'],p['point'],number(p['seconds from climb start']),number(p['seconds from point to climb end']),p.get('comment','')] for p in points])
    arrivals=sorted([(p['athlete'],number(p['seconds from climb start'])) for p in points if p['point']=='REST' and number(p['seconds from climb start']) is not None],key=lambda x:x[1])
    if arrivals:heading('REST arrival');story.append(Bars(arrivals,width,focus))
    if focus:
        own=[a for a in activities if a['athlete']==focus and a['activity']=='clip' and a['status']=='closed']
        story.append(PageBreak());heading(f'{focus}: clips compared with peers')
        cliprows=[]
        for a in own:
            peers=[number(p['duration seconds']) for p in activities if p['athlete']!=focus and p['activity']=='clip' and p['status']=='closed' and p['quickdraw']==a['quickdraw']]
            duration=number(a['duration seconds']);med=median(peers) if peers else None
            cliprows.append([a['quickdraw'],a['hand'],duration,med,duration-med if med is not None else None,1+sum(x<duration for x in peers),len(peers)+1])
        grid(['Draw','Hand','Focus duration s','Peer median s','Difference s','Rank, shortest first','Athletes'],cliprows)
        paragraph('Ranks compare recorded operations, not climbing ability. More hand alternation or less rest is not automatically better. Review the same stance and quickdraw before interpreting a time difference.')
        heading('Gaps between clips after removing recovery')
        gaps=[]
        for s in splits:
            if s['athlete']!=focus:continue
            peers=[number(p['gap outside marked rest seconds']) for p in splits if p['athlete']!=focus and p['from quickdraw']==s['from quickdraw'] and p['to quickdraw']==s['to quickdraw'] and number(p['gap outside marked rest seconds']) is not None]
            residual=number(s['gap outside marked rest seconds']);med=median(peers) if peers else None
            delta=residual-med if residual is not None and med is not None else None
            gaps.append([s['from quickdraw']+' -> '+s['to quickdraw'],number(s['gap seconds']),number(s['total marked rest in gap seconds']),residual,med,delta,'Longer' if delta is not None and delta>0 else 'Shorter' if delta is not None and delta<0 else 'Equal / unknown'])
        grid(['Split','Raw gap s','Recovery removed s','Outside recovery s','Peer median s','Difference s','Flag'],gaps)
        paragraph('Recovery removed includes chalking and dedicated rest, merged within the gap. Overlaps are subtracted once. The remainder can include movement, route reading or unmarked rest. Timing alone cannot establish why an athlete fell.')
    story.append(PageBreak());heading('Every completed clip')
    grid(['Athlete','Draw','Hand','Start from climb s','Completed from climb s','Duration s'],[[a['athlete'],a['quickdraw'],a['hand'],number(a['start from climb seconds']),number(a['end from climb seconds']),number(a['duration seconds'])] for a in activities if a['activity']=='clip' and a['status']=='closed'])
    story.append(PageBreak());heading('Every between-clip split')
    grid(['Athlete','Draw split','Gap s','Completion split s','Recovery removed s','Outside recovery s'],[[s['athlete'],s['from quickdraw']+' -> '+s['to quickdraw'],number(s['gap seconds']),number(s['completion to completion seconds']),number(s['total marked rest in gap seconds']),number(s['gap outside marked rest seconds'])] for s in splits])
    story.append(PageBreak());heading('Rest and chalking activity log')
    grid(['Athlete','Activity','Hand','Start from climb s','End from climb s','Duration s','Status'],[[a['athlete'],a['activity'],a['hand'],number(a['start from climb seconds']),number(a['end from climb seconds']),number(a['duration seconds']),a['status']] for a in activities if a['activity'] in ('rest','chalk')])
    heading('Source and limits')
    paragraph('Source: '+text(source.name)+'<br/>SHA256: '+hashlib.sha256(source.read_bytes()).hexdigest())
    paragraph('All values derive solely from this HTML snapshot. Three-decimal or two-decimal values retain source rounding. Missing outcomes cannot be recovered from older exports. No footage, labels or telemetry are uploaded by this generator. No physiological recovery or fatigue is measured. Equal clip counts do not establish equal final holds; compare matched progress before attempt duration.')
    def footer(canvas,doc):
        canvas.setFont('Helvetica',8);canvas.setFillColor(INK);canvas.drawString(42,22,'Climbing comparison / private local report');canvas.drawRightString(landscape(A4)[0]-42,22,f'Page {doc.page}')
    doc=SimpleDocTemplate(str(output),pagesize=landscape(A4),leftMargin=42,rightMargin=42,topMargin=38,bottomMargin=38,title='Climbing performance and efficiency',author='Climb Studio')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return output
