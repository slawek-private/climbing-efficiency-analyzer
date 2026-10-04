"""Private random-access JPEG previews, mapped 1:1 to original PTS frames."""
import io,json,hashlib
from pathlib import Path
from uuid import uuid4
from collections import OrderedDict
from PIL import Image
import numpy as np
from PySide6.QtCore import QThread,Signal
from .video import VideoReader

FORMAT=1
def fingerprint(index):
    return hashlib.sha256(json.dumps({'source':{k:v for k,v in index['source'].items() if k!='file'},'pts':index['pts'],'rotation':index.get('rotation',0)},sort_keys=True).encode()).hexdigest()
def cache_folder(root,index):return Path(root)/index['source']['sha256']

class PreviewReader:
    backend='preview'
    def __init__(self,root,index):
        folder=cache_folder(root,index);meta=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        if meta['format']!=FORMAT or meta['fingerprint']!=fingerprint(index):raise ValueError('Preview does not match original video index')
        offsets=meta['offsets'];size=(folder/meta['data']).stat().st_size
        if len(offsets)!=len(index['pts'])+1 or offsets[0]!=0 or offsets[-1]!=size or any(a>=b for a,b in zip(offsets,offsets[1:])):raise ValueError('Incomplete preview cache')
        self.index=index;self.offsets=offsets;self.file=(folder/meta['data']).open('rb');self.cache=OrderedDict()
        from fractions import Fraction
        self.times=[float((p-index['pts'][0])*Fraction(index['source']['time_base'])) for p in index['pts']]
    def point(self,number):return {'frame':number,'pts':self.index['pts'][number],'seconds':self.times[number]}
    def frame(self,number,seek_large=True):
        if number in self.cache:self.cache.move_to_end(number);return self.cache[number]
        self.file.seek(self.offsets[number]);data=self.file.read(self.offsets[number+1]-self.offsets[number])
        with Image.open(io.BytesIO(data)) as image:rgb=np.array(image.convert('RGB'))
        self.cache[number]=rgb
        while len(self.cache)>48:self.cache.popitem(last=False)
        return rgb
    def playback_frame(self,number):return self.frame(number)
    def close(self):self.file.close()

def open_preview(root,index):
    try:return PreviewReader(root,index)
    except (OSError,ValueError,KeyError,TypeError):return None

def build_preview(video,index,root,progress=lambda value:None,cancelled=lambda:False):
    existing=open_preview(root,index)
    if existing:existing.close();return cache_folder(root,index)
    folder=cache_folder(root,index);folder.mkdir(parents=True,exist_ok=True)
    token=uuid4().hex;data_path=folder/(token+'.jpgpack');manifest_tmp=folder/(token+'.json.tmp')
    reader=None
    try:
        reader=VideoReader(video,index,'auto');offsets=[0]
        with data_path.open('wb') as output:
            for number in range(len(index['pts'])):
                if cancelled():raise InterruptedError('Preview preparation cancelled')
                pixels=reader.playback_frame(number)
                Image.fromarray(pixels).save(output,format='JPEG',quality=88,subsampling=0)
                offsets.append(output.tell())
                if number%30==0:progress(int(100*(number+1)/len(index['pts'])))
        meta={'format':FORMAT,'fingerprint':fingerprint(index),'data':data_path.name,'offsets':offsets,'frame_count':len(index['pts']),'max_dimension':1280,'quality':88}
        manifest_tmp.write_text(json.dumps(meta),encoding='utf-8');manifest_tmp.replace(folder/'manifest.json');progress(100)
        return folder
    except BaseException:
        data_path.unlink(missing_ok=True);manifest_tmp.unlink(missing_ok=True);raise
    finally:
        if reader:reader.close()

class PreviewWorker(QThread):
    progress=Signal(int)
    ready=Signal(str)
    error=Signal(str)
    def __init__(self,video,index,root):
        super().__init__();self.video=Path(video);self.index=index;self.root=Path(root)
    def run(self):
        try:build_preview(self.video,self.index,self.root,self.progress.emit,self.isInterruptionRequested);self.ready.emit(self.index['source']['sha256'])
        except InterruptedError:pass
        except Exception as error:self.error.emit(str(error))
