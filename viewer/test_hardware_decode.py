import sys
import av,numpy as np,pytest
from viewer.video import index_video,VideoReader

pytestmark=pytest.mark.skipif(sys.platform!='darwin',reason='VideoToolbox is macOS only')

def h264(path,frames=60):
    codec=next((c for c in ('libx264','h264_videotoolbox') if c in av.codecs_available),None)
    if codec is None:pytest.skip('no H.264 encoder')
    with av.open(str(path),'w') as out:
        stream=out.add_stream(codec,rate=30);stream.width=320;stream.height=240;stream.pix_fmt='yuv420p' if codec=='libx264' else 'nv12';stream.gop_size=12
        for n in range(frames):
            pixels=np.zeros((240,320,3),dtype=np.uint8);pixels[:,:n*5+5]=200
            for packet in stream.encode(av.VideoFrame.from_ndarray(pixels,format='rgb24')):out.mux(packet)
        for packet in stream.encode():out.mux(packet)

def test_videotoolbox_returns_the_same_indexed_frames_as_cpu(tmp_path):
    path=tmp_path/'clip.mp4';h264(path);index=index_video(path)
    try:gpu=VideoReader(path,index,'videotoolbox');gpu.frame(0)
    except Exception as error:pytest.skip(f'VideoToolbox unavailable here: {error}')
    cpu=VideoReader(path,index,'cpu');auto=VideoReader(path,index,'auto')
    assert gpu.backend=='videotoolbox' and auto.backend=='videotoolbox'
    for n in (0,37,5,59,24,25,1):
        a,b=gpu.frame(n).astype(int),cpu.frame(n).astype(int)
        assert a.shape==b.shape and np.abs(a-b).mean()<3, n
        cpu.cache.clear();gpu.cache.clear();cpu.raw_cache.clear();gpu.raw_cache.clear()
    for reader in (gpu,cpu,auto):reader.close()
