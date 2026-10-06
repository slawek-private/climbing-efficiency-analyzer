"""Capture documentation screenshots using generated pixels and fictional labels."""
import copy,shutil,tempfile,time
from fractions import Fraction
from pathlib import Path
import av,numpy as np
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from viewer.labels import empty_labels,History,make_event
from viewer.video import index_video
from viewer.workspace import Workspace
import viewer.simple as simple

def main():
    repository=Path(__file__).resolve().parents[1]
    destination=repository/'docs'/'screenshots';destination.mkdir(parents=True,exist_ok=True)
    app=QApplication.instance() or QApplication([]);app.setStyle('Fusion')
    with tempfile.TemporaryDirectory(prefix='climb-studio-demo-') as directory:
        root=Path(directory);video=root/'synthetic-demo.mkv'
        pixels=np.full((480,320,3),[28,46,69],dtype=np.uint8)
        for x,y in [(55,425),(190,370),(95,305),(240,245),(135,180),(210,105),(70,50)]:
            pixels[y:y+16,x:x+25]=[50,132,238]
        with av.open(str(video),'w') as output:
            stream=output.add_stream('ffv1',rate=10);stream.width=320;stream.height=480;stream.pix_fmt='yuv420p'
            for number in range(640):
                frame=av.VideoFrame.from_ndarray(pixels,format='rgb24');frame.pts=number;frame.time_base=Fraction(1,10)
                for packet in stream.encode(frame):output.mux(packet)
            for packet in stream.encode():output.mux(packet)
        index=index_video(video)
        simple.ROOT=root
        original_settings=simple.QSettings
        simple.QSettings=lambda *args:original_settings(str(root/'settings.ini'),QSettings.Format.IniFormat)
        window=simple.Window();window.workspace=Workspace(root/'workspace.json');window.workspace.add(video);window.video_path=video;window.index_ready(index)
        def drain():
            end=time.monotonic()+5
            while window.decode_future is not None:
                app.processEvents();time.sleep(.005)
                if time.monotonic()>end:raise RuntimeError('Demo frame timed out')
        drain()
        def point(seconds):return window.reader.point(round(seconds*10))
        docs=[]
        for i,name in enumerate(('Athlete A','Athlete B','Athlete C')):
            path=root/f'demo-{i+1}.mkv';shutil.copyfile(video,path)
            doc=empty_labels({**index['source'],'file':path.name});doc.update(climber=name,attempt=str(i+1),start=point(1),end=point(60+i),outcome='completed' if i==1 else 'failed')
            for draw,start in enumerate((4,9,15,21,28,39,46,55),1):
                pending={'kind':'clip','hand':'left' if (draw+i)%3==0 else 'right','target':draw,'start':point(start),'confidence':1,'notes':'Synthetic demo event'}
                doc['events'].append(make_event(pending,point(start+1.5+i*.4)))
            for kind,hand,start,end in [('rest','left',34,37+i),('chalk','left',35,36),('rest','right',49,50+i)]:
                doc['events'].append(make_event({'kind':kind,'hand':hand,'target':None,'start':point(start),'confidence':1,'notes':'Synthetic demo event'},point(end)))
            doc['checkpoints']=[{'id':'rest-point','name':'REST','point':point(33+i),'comment':'Fictional demonstration'}]
            window.workspace.remember(path,doc);docs.append(doc)
        window.history=History(docs[0]);window.saved=copy.deepcopy(docs[0]);window.draw.setValue(9);window.refresh();window.refresh_collection();window.show_frame(350);drain()
        window.resize(1450,1000);window.show();window.precision_scrubber.set_span(15)
        window.position.setText('SYNTHETIC DEMO - no people, real footage or athlete telemetry')
        def settle(predicate=lambda:True,seconds=8):
            end=time.monotonic()+seconds
            while not predicate() and time.monotonic()<end:app.processEvents();time.sleep(.01)
            app.processEvents()
        from viewer.design import apply_theme
        # A running left-hand rest shows the timers' active state.
        window.history.document['open_events'].append({'kind':'rest','hand':'left','target':None,'start':window.reader.point(342),'confidence':1,'notes':''});window.refresh()
        window.autosave_timer.stop();window.saved=copy.deepcopy(window.document());window.refresh_live()
        for theme in ('light','dark'):
            apply_theme(window,theme);window.show_view(window.measure_page);settle();window.grab().save(str(destination/f'workspace-{theme}.png'))
        window.show_view(window.library);settle(lambda:len(window.library.meta)==len(window.workspace.videos));window.grab().save(str(destination/'library.png'))
        window.show_view(window.sync_view);settle(lambda:window.sync_view.tiles and all(t.shown is not None for t in window.sync_view.tiles))
        window.sync_view.seek(20);settle(lambda:all(t.shown==t.wanted for t in window.sync_view.tiles));window.grab().save(str(destination/'side-by-side.png'))
        apply_theme(window,'light')
        window.show_view(window.comparison_page);window.comparison_table.selectRow(0);settle();window.grab().save(str(destination/'athlete-comparison.png'))
        window.show_view(window.comparison_charts);window.comparison_charts.focus.setCurrentText('Athlete A');settle();window.grab().save(str(destination/'comparison-charts.png'))
        window.saved=copy.deepcopy(window.document());window.close()
    print('Captured six screenshots using synthetic data only:',destination)
    return 0

if __name__=='__main__':raise SystemExit(main())
