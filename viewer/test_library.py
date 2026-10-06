from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from viewer.library import probe,recommendation,notes
from viewer.sync_view import best_columns
from viewer.test_sync_view import synthetic

def test_probe_reads_metadata_and_estimates_preview(tmp_path):
    path=tmp_path/'clip.mkv';synthetic(path,30);m=probe(path)
    assert (m['codec'],m['width'],m['height'],round(m['fps']))==('ffv1',32,32,10) and m['frames']==30 and m['preview_bytes']>0
    assert recommendation(m)=='Optional' and 'below 1080p' in notes(m) and '50–60 fps recommended' in notes(m)
    assert recommendation({**m,'width':3840,'height':2160})=='Recommended' and recommendation({**m,'codec':'hevc','width':1080,'height':1920})=='Recommended'

def test_side_by_side_picks_largest_layout():
    assert best_columns(4,1600,900,9/16)==4  # portrait phone clips: one row
    assert best_columns(4,1600,900,16/9)==2  # landscape: 2 × 2
    assert best_columns(3,1600,900,16/9)==2 and best_columns(1,800,600,16/9)==1

def test_point_name_defaults_to_last_used(tmp_path,monkeypatch):
    import viewer.simple as simple
    monkeypatch.setattr(simple,'ROOT',tmp_path);settings=QSettings(str(tmp_path/'s.ini'),QSettings.Format.IniFormat);settings.setValue('last_point','Roof')
    monkeypatch.setattr(simple,'QSettings',lambda *a:settings)
    app=QApplication.instance() or QApplication([]);w=simple.Window();assert w.point_name.text()=='Roof';w.close()
