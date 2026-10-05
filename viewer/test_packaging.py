import sys
from viewer import labels
from viewer.selfcheck import run

def test_installed_app_writes_to_documents_not_its_bundle(monkeypatch):
    assert labels.data_root()==labels.RESOURCES
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    root=labels.data_root();assert root.name=='Climb Studio' and labels.RESOURCES not in root.parents

def test_self_check_used_by_installer_builds():
    assert run()==0
