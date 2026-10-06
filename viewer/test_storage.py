import json,os
from viewer import storage

def preview(root,sha,size,used,complete=True):
    folder=root/'artifacts'/'preview-cache'/sha;folder.mkdir(parents=True);(folder/'x.jpgpack').write_bytes(b'0'*size)
    if complete:(folder/'manifest.json').write_text('{}');os.utime(folder/'manifest.json',(used,used))
    else:os.utime(folder,(used,used))

def test_limit_evicts_least_recently_used_but_keeps_protected(tmp_path):
    for sha,used in (('a',100),('b',200),('c',300)):preview(tmp_path,sha,1000,used)
    index=tmp_path/'artifacts'/'frame-indexes';index.mkdir(parents=True);(index/'b.json').write_text(json.dumps({'source':{'file':'b.mp4'}}))
    rows={r['sha256']:r for r in storage.entries(tmp_path)};assert rows['b']['file']=='b.mp4' and rows['a']['preview_bytes']>=1000
    assert storage.enforce_limit(tmp_path,2100,keep={'a'})==['b']
    assert {r['sha256'] for r in storage.entries(tmp_path) if r['preview_bytes']}=={'a','c'}
    assert storage.enforce_limit(tmp_path,10**9)==[]

def test_incomplete_previews_are_removed(tmp_path):
    preview(tmp_path,'done',10,1);preview(tmp_path,'half',10,1,complete=False)
    storage.remove_incomplete(tmp_path)
    assert [r['sha256'] for r in storage.entries(tmp_path)]==['done']
    assert storage.human(1536)=='2 KB' and storage.human(3*2**30)=='3.0 GB'
