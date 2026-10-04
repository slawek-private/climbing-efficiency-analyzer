"""Exact PTS indexing and decoding; playback scaling changes pixels only."""
import hashlib
import json
import os
from collections import OrderedDict
from fractions import Fraction
from pathlib import Path

import av
import numpy as np


def index_video(path, progress=lambda value: None, cancelled=lambda: False, cache_dir=None):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8*1024*1024),b""):
            if cancelled():
                raise InterruptedError("Indexing cancelled")
            digest.update(chunk)
    cache_path=Path(cache_dir)/(digest.hexdigest()+'.json') if cache_dir else None
    if cache_path and cache_path.exists():
        try:
            cached=json.loads(cache_path.read_text(encoding='utf-8'));points=cached['pts'];source=cached['source']
            if source['sha256']==digest.hexdigest() and source['frame_count']==len(points) and points and all(isinstance(p,int) for p in points) and all(a<b for a,b in zip(points,points[1:])) and Fraction(source['time_base'])>0:
                source['file']=path.name;progress(100);return cached
        except (OSError,ValueError,KeyError,TypeError):pass
    pts = []
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"
        stream.codec_context.thread_count = os.cpu_count() or 1
        base = stream.time_base
        duration = float(stream.duration*base) if stream.duration else None
        rotation = 0
        for frame in container.decode(stream):
            if cancelled():
                raise InterruptedError("Indexing cancelled")
            if frame.pts is None or frame.time_base != base:
                raise ValueError("Missing or inconsistent presentation timestamps")
            if pts and frame.pts <= pts[-1]:
                raise ValueError("Non-increasing presentation timestamps; exact annotation is unsupported")
            pts.append(frame.pts)
            rotation = frame.rotation
            if rotation % 90:
                raise ValueError("Unsupported non-right-angle display rotation")
            if len(pts)%120 == 0:
                progress(min(99,int(float((pts[-1]-pts[0])*base)/duration*100)) if duration else 0)
    if not pts:
        raise ValueError("Video has no decodable frames")
    result = {"source":{"file":path.name,"sha256":digest.hexdigest(),"time_base":str(base),
                      "first_pts":pts[0],"frame_count":len(pts)},"pts":pts,"rotation":rotation}
    if cache_path:
        cache_path.parent.mkdir(parents=True,exist_ok=True);temporary=cache_path.with_suffix('.tmp');temporary.write_text(json.dumps(result),encoding='utf-8');temporary.replace(cache_path)
    return result


class VideoReader:
    def __init__(self,path,index,backend="auto"):
        if backend=='auto':
            with av.open(str(path)) as probe:
                stream=probe.streams.video[0];candidate=max(stream.codec_context.width,stream.codec_context.height)>=3840 and stream.codec_context.name in ('hevc','h264')
            if candidate:
                try:
                    self.__init__(path,index,'cuda');self.frame(0);return
                except Exception:
                    if hasattr(self,'container'):self.container.close()
            self.__init__(path,index,'cpu');return
        options={}
        if backend=="cuda":
            from av.codec.hwaccel import HWAccel
            options["hwaccel"]=HWAccel("cuda",allow_software_fallback=False)
        self.container = av.open(str(path),**options)
        self.backend=backend
        self.stream = self.container.streams.video[0]
        self.stream.thread_type = "SLICE"
        self.stream.codec_context.thread_count = min(8,os.cpu_count() or 1)
        self.index = index
        self.times = [float((p-index["pts"][0])*Fraction(index["source"]["time_base"])) for p in index["pts"]]
        self.cache = OrderedDict()
        self.raw_cache = OrderedDict()
        self.iterator = None
        self.current_pts = None

    def point(self,frame):
        return {"frame":frame,"pts":self.index["pts"][frame],"seconds":self.times[frame]}

    def display_pixels(self,frame,number):
        scale=min(1,1280/max(frame.width,frame.height));shown=frame.reformat(width=max(2,int(frame.width*scale)),height=max(2,int(frame.height*scale)),format='rgb24')
        rgb=np.ascontiguousarray(np.rot90(shown.to_ndarray(),k=self.index.get("rotation",frame.rotation)//90));self.cache[number]=rgb
        while len(self.cache)>48:self.cache.popitem(last=False)
        return rgb
    def playback_frame(self,number):return self.frame(number,seek_large=False)
    def frame(self,number,seek_large=True):
        target = self.index["pts"][number]
        if number in self.cache:
            self.cache.move_to_end(number)
            return self.cache[number]
        if target in self.raw_cache:return self.display_pixels(self.raw_cache[target],number)
        if self.iterator is None or self.current_pts is None or target <= self.current_pts or (seek_large and float((target-self.current_pts)*self.stream.time_base) > 1):
            self.container.seek(target,stream=self.stream,backward=True)
            self.iterator = iter(self.container.decode(self.stream))
        for frame in self.iterator:
            self.current_pts = frame.pts
            self.raw_cache[frame.pts]=frame
            while len(self.raw_cache)>48:self.raw_cache.popitem(last=False)
            if frame.pts is None or frame.pts < target:
                continue
            if frame.pts != target:
                raise ValueError("Seek could not locate the indexed frame")
            return self.display_pixels(frame,number)
        raise ValueError("Indexed frame is unavailable")

    def close(self):
        self.container.close()
