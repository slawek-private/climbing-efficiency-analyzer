import copy
import pytest
from viewer.labels import empty_labels
from viewer.test_manual import source,point,event
from viewer.comparison import export_comparison
from viewer.report_cli import build_report,main

def documents():
    a=empty_labels(source());a.update(climber='Athlete A',start=point(1),end=point(11),outcome='failed')
    a['checkpoints']=[{'id':'p','name':'REST','point':point(5),'comment':'<private comment>'}]
    a['events']=[event('clip','left',2,3,1),event('clip','right',7,8,2),event('rest','left',4,6)]
    b=copy.deepcopy(a);b['climber']='Athlete B';b['attempt']='2';b['events'][1]['start']=point(8);b['events'][1]['end']=point(9)
    return [a,b]

def test_reproducible_html_source_and_pdf(tmp_path):
    source=export_comparison(documents(),tmp_path/'source.html');original=source.read_bytes()
    assert main(['--source',str(source),'--output',str(tmp_path/'report.html'),'--focus','Athlete A','--pdf',str(tmp_path/'report.pdf')])==0
    html=(tmp_path/'report.html').read_text(encoding='utf-8')
    assert 'Athlete A: gaps minus marked recovery' in html and '&lt;private comment&gt;' in html
    assert '20.00%' in html and source.read_bytes()==original
    assert (tmp_path/'report.pdf').read_bytes().startswith(b'%PDF-')
    assert (tmp_path/'report.json').exists()
    assert (tmp_path/'report-focus-gaps.csv').exists()

def test_source_overwrite_rejected(tmp_path):
    source=export_comparison(documents(),tmp_path/'source.html')
    with pytest.raises(ValueError,match='differ'):build_report(source,source)

def test_live_charts_svg_valid_and_updates():
    from PySide6.QtWidgets import QApplication
    from viewer.charts import ComparisonCharts
    app=QApplication.instance() or QApplication([])
    w=ComparisonCharts();w.set_documents(documents());w.show();app.processEvents()
    from PySide6.QtSvgWidgets import QSvgWidget
    widgets=w.findChildren(QSvgWidget)
    assert widgets and all(svg.renderer().isValid() for svg in widgets)
    w.checkpoint='REST';w.redraw();app.processEvents()
    from PySide6.QtWidgets import QLabel
    assert any(label.text()=='Arrival at REST' for label in w.findChildren(QLabel))
    w.close()
