import copy
from viewer.labels import empty_labels,save
from viewer.discovery import matching_labels
from viewer.test_manual import source

def test_find_by_hash_ignores_filename_and_wrong_video(tmp_path):
    d=empty_labels(source());d['source']['file']='original-name.mov';save(d,tmp_path/'custom-name.labels.json')
    other=copy.deepcopy(d);other['source']['sha256']='b'*64;save(other,tmp_path/'wrong.labels.json')
    (tmp_path/'broken.labels.json').write_text('broken')
    found=matching_labels('a'*64,[tmp_path,tmp_path])
    assert len(found)==1 and found[0][0].name=='custom-name.labels.json'
