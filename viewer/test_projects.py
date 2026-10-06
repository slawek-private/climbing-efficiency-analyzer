import json,zipfile
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from viewer import projects
from viewer.labels import empty_labels,save
from viewer.test_sync_view import synthetic
from viewer.workspace import Workspace

def test_export_import_round_trip_with_videos(tmp_path):
    root=tmp_path/'data';source=projects.create(root,'SYCC Genf');assert source.slug=='sycc-genf' and projects.create(root,'SYCC Genf').name=='SYCC Genf 2'
    video=tmp_path/'clips'/'anna.mkv';video.parent.mkdir();index=synthetic(video)
    doc=empty_labels(index['source']);doc['climber']='Anna';label=source.labels/'anna.labels.json';save(doc,label)
    (source.reports).mkdir(parents=True);(source.reports/'all.html').write_text('<p>report</p>')
    ws=Workspace(source.workspace_file);ws.remember(video,doc,label);ws.save()
    archive=projects.export_project(source,tmp_path/'sycc.climbproject',include_videos=True)
    with zipfile.ZipFile(archive) as z:
        names=set(z.namelist());assert {'project.json','workspace.json','videos/anna.mkv','labels/anna.labels.json','reports/all.html'}<=names
        assert z.getinfo('videos/anna.mkv').compress_type==zipfile.ZIP_STORED
    other=tmp_path/'other';imported=projects.import_project(other,archive)
    assert imported.name=='SYCC Genf' and (imported.folder/'videos'/'anna.mkv').read_bytes()==video.read_bytes()
    data=json.loads(imported.workspace_file.read_text());path=data['videos'][0]
    assert path==str((imported.folder/'videos'/'anna.mkv').resolve()) and data['states'][path]['label_path']==str((imported.folder/'labels'/'anna.labels.json').resolve())
    loaded=Workspace(imported.workspace_file);assert loaded.videos==[path] and loaded.states[path]['document']['climber']=='Anna'
    assert [p.name for p in projects.all_projects(other)]==['My climbs','SYCC Genf']

@pytest.mark.parametrize('name',['../evil.txt','/abs.txt','labels/../../evil.txt','C:/evil.txt','unexpected/file.txt'])
def test_unsafe_archive_entries_are_rejected(tmp_path,name):
    bad=tmp_path/'bad.climbproject'
    with zipfile.ZipFile(bad,'w') as z:
        z.writestr('project.json',json.dumps({'format':1,'name':'Bad'}));z.writestr('workspace.json','{}');z.writestr(name,'x')
    with pytest.raises(ValueError):projects.import_project(tmp_path/'root',bad)
    assert not (tmp_path/'evil.txt').exists() and not (tmp_path/'root'/'projects').exists()

def test_window_switches_project_workspace_and_label_folder(tmp_path,monkeypatch):
    import viewer.simple as simple
    monkeypatch.setattr(simple,'ROOT',tmp_path)
    app=QApplication.instance() or QApplication([]);w=simple.Window();w.settings=QSettings(str(tmp_path/'s.ini'),QSettings.Format.IniFormat)
    assert w.project.legacy and w.labels_folder()==tmp_path/'artifacts'/'labels'
    target=projects.create(tmp_path,'Route B');assert w.open_project(target)
    assert w.project==target and w.workspace.path==target.workspace_file and w.labels_folder()==target.labels and 'Route B' in w.project_button.text()
    assert w.settings.value('current_project')=='route-b';w.close()
