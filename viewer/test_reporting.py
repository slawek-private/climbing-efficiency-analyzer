"""Shared dashboard eligibility and export behaviour, without private footage."""
import copy,json
from pathlib import Path
from viewer.test_report_cli import documents
from viewer.test_manual import point,event
from viewer.reporting import records,chart_specs,svg_chart,read_snapshot,legacy_records,overview_html
from viewer.comparison import export_comparison
from viewer.report_cli import parse_export,build_report
from viewer.coaching_report import export_report,export_pdf
from viewer.footwork import enable


def reviewed_document():
    d=documents()[0];d['outcome']='completed'
    d['events'] += [event('chalk','right',5,7)]
    track=enable(d);track['coverage']=[dict(id='checked',start=point(1),end=point(7),state='reviewed'),dict(id='hidden',start=point(7),end=point(9),state='obscured')]
    def slip(id,t,status='confirmed'):return dict(id=id,kind='slip',limb='left',start=point(t),end=None,status=status,intent='unplanned',observation='',interpretation='',action='')
    track['events']=[slip('visible',5),slip('candidate',8,'candidate')]
    return d


def test_union_unknowns_and_coverage_share_are_identical_across_views(tmp_path):
    d=reviewed_document();r=records([d])[0]
    assert r['recovery']==3 and r['recovery_state']=='Partial annotations'
    assert (r['checked'],r['hidden'],r['unreviewed'])==(6,2,2)
    assert (r['slips'],r['candidates'],r['unplanned'],r['intentional'])==(1,1,0,0)
    no_review=documents()[1];assert records([no_review])[0]['checked'] is None and records([no_review])[0]['slips'] is None
    path=export_comparison([d,no_review],tmp_path/'comparison.html')
    assert read_snapshot(path)==[d,no_review]
    html=path.read_text();assert html.index('id="comparisonOverview"')<html.index('<details><summary>Details')
    assert '3.00 s · Partial annotations' in html and 'Footwork observations &amp; coverage' in html
    source=path.read_bytes();output=build_report(path,tmp_path/'focused.html',focus=d['climber']);assert path.read_bytes()==source
    assert json.loads(output.with_suffix('.json').read_text())['attempts'][0]==d


def test_repeated_missing_unfinished_and_outside_measurements_are_unavailable():
    d=reviewed_document();d['checkpoints'].append(dict(id='repeat',name='REST',point=point(6)))
    d['events'].append(event('clip','left',0,2,3))
    assert records([d])[0]['arrivals']['REST'] is None and records([d])[0]['clips']['3'] is None
    d['open_events']=[dict(id='open',kind='clip',hand='right',target=2,start=point(8),confidence=1,notes='')]
    assert all(value is None for value in records([d])[0]['clips'].values())
    d['open_events'][0]['kind']='rest';d['open_events'][0]['target']=None
    assert records([d])[0]['recovery'] is None
    d['outcome']='failed';assert records([d])[0]['slips'] is None and records([d])[0]['foot_state']=='Fall start missing'


def test_old_snapshots_stay_usable_without_inventing_footwork(tmp_path):
    path=export_comparison(documents(),tmp_path/'source.html');_,overview,points,activities,_=parse_export(path)
    old=path.read_text().split('<script id="measurementSnapshot"')[0]+'</body></html>';path.write_text(old)
    assert read_snapshot(path) is None
    data=legacy_records(overview,points,activities);assert all(r['slips'] is None and r['checked'] is None for r in data)
    assert build_report(path,tmp_path/'old-report.html').exists()


def test_coaching_overview_keeps_replay_provenance_and_printed_detail(tmp_path):
    d=reviewed_document();d['climber']='Żaneta <script>';d['checkpoints'][0]['comment']='</script><script>alert(1)</script>'
    path=export_report([d],tmp_path/'review.html',pdf=True);html=path.read_text()
    assert 'id="comparisonOverview"' in html and 'data-evidence-key="0"' in html and 'id="player"' in html
    assert html.index('id="comparisonOverview"')<html.index('data-evidence-key="0"')
    assert 'Żaneta &lt;script&gt;' in html and '&lt;/script&gt;&lt;script&gt;alert(1)' in html
    assert path.with_suffix('.pdf').stat().st_size>1000
    anonymous=export_report([d],tmp_path/'anonymous.html',anonymous=True)
    assert 'Żaneta' not in anonymous.read_text()


def test_bounded_draw_panels_and_svg_accessibility():
    d=reviewed_document()
    d['events'] += [event('clip','left',i,i+.1,i+2) for i in range(2,9)]
    specs=chart_specs(records([d]),'REST');assert len(specs[1])==4
    from PySide6.QtCore import QByteArray
    from PySide6.QtSvg import QSvgRenderer
    for spec in [specs[0],*specs[1],specs[2],specs[3]]:
        svg,_,_=svg_chart(spec);assert QSvgRenderer(QByteArray(svg.encode())).isValid()
        assert 'Ref · ' in svg and '<title>' in svg


def test_snapshot_detail_comparisons_exclude_ambiguous_clips_and_other_routes(tmp_path):
    from viewer.reporting import eligible_clip_rows,gap_peers
    docs=documents();other=copy.deepcopy(docs[1]);other.update(climber='Other route',route='different')
    docs.append(other);docs[0]['events'].append(event('clip','right',9,10,1))
    path=export_comparison(docs,tmp_path/'source.html');_,overview,_,activities,splits=parse_export(path)
    assert '1' not in eligible_clip_rows(activities,overview[0]) and '2' in eligible_clip_rows(activities,overview[0])
    target=next(s for s in splits if s['athlete']=='Athlete B')
    assert gap_peers(splits,target,overview)==[2.0]  # other-route 3s is excluded
