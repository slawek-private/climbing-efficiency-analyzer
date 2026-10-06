"""Capture documentation screenshots using generated pixels and fictional labels."""
import copy,shutil,tempfile,time
from fractions import Fraction
from pathlib import Path
import av,numpy as np
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from viewer.labels import empty_labels,History,make_event
from viewer.video import index_video
from viewer.footwork import enable
from viewer.coaching_report import export_report
from viewer.workspace import Workspace
import viewer.simple as simple

def main():
    repository=Path(__file__).resolve().parents[1]
    destination=repository/'docs'/'screenshots';destination.mkdir(parents=True,exist_ok=True)
    app=QApplication.instance() or QApplication([]);app.setStyle('Fusion')
    with tempfile.TemporaryDirectory(prefix='climb-studio-demo-') as directory:
        root=Path(directory).resolve();video=root/'synthetic-demo.mkv'
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
        import viewer.sync_view as sync
        sync.ROOT=root
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
            track=enable(doc);doc['coaching']={'goal':'Keep precise foot contacts through the roof','reflection':'I rushed the right-foot placement before moving','action':'Pause, choose the foothold, then commit','retest':'Repeat the roof with the same camera position'};doc['context']={'discipline':'Lead','grade':'Fictional route','wall_angle':'Overhanging','familiarity':'Practised'}
            track['coverage']=[{'id':'visible-'+str(i),'start':point(16),'end':point(55),'state':'reviewed'},{'id':'hidden-'+str(i),'start':point(10),'end':point(16),'state':'obscured'}]
            track['fall_onset']=point(59) if doc['outcome']=='failed' else None
            track['events']=[dict(id='slip-'+str(i),kind='slip',limb='right',start=point(43.4),end=None,intent='unplanned',status='confirmed',observation='Right foot visibly loses contact',interpretation='Review placement before the next reach',action='Choose the foothold before committing'),dict(id='off-'+str(i),kind='both_off',limb='both',start=point(43.4),end=point(44.2),intent='unplanned',status='confirmed',observation='Both feet visibly off the wall',interpretation='',action='')]
            doc['checkpoints']=[{'id':'rest-point','name':'REST','point':point(33+i),'comment':'Fictional demonstration'}]
            window.workspace.remember(path,doc);docs.append(doc)
        window.workspace.videos.remove(str(video));window.workspace.states.pop(str(video),None);window.video_path=root/'demo-1.mkv';window.history=History(docs[0]);window.saved=copy.deepcopy(docs[0]);window.draw.setValue(9);window.refresh();window.refresh_collection();window.show_frame(350);drain()
        window.show();
        from PySide6.QtTest import QTest
        QTest.qWait(50);window.resize(1280,800);window.precision_scrubber.set_span(15)
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
        window.events_body.show();window.events_toggle.setText('▾  Events');settle();window.measurement_scroll.verticalScrollBar().setValue(window.measurement_scroll.verticalScrollBar().maximum());settle();window.grab().save(str(destination/'workspace-events.png'));window.events_body.hide()
        window.show_view(window.library);settle(lambda:len(window.library.meta)==len(window.workspace.videos));window.grab().save(str(destination/'library.png'))
        window.compare_scope.set_selection(d['attempt_id'] for d in docs[:2])
        window.show_view(window.sync_view);settle(lambda:window.sync_view.tiles and all(t.shown is not None for t in window.sync_view.tiles))
        window.sync_view.seek(20);settle(lambda:all(t.shown==t.wanted for t in window.sync_view.tiles));window.grab().save(str(destination/'side-by-side.png'))
        apply_theme(window,'light')
        window.show_view(window.comparison_page);window.comparison_table.selectRow(0);settle();window.grab().save(str(destination/'athlete-comparison.png'))
        window.show_view(window.comparison_charts);window.compare_scope.point.setCurrentText('REST');settle();window.grab().save(str(destination/'comparison-charts.png'))
        window.show_view(window.pattern_dashboard);window.pattern_dashboard.tabs.setCurrentIndex(5);settle();window.grab().save(str(destination/'time-allocation.png'))
        window.show_view(window.measure_page);window.resize(1024,768);settle();window.measurement_scroll.verticalScrollBar().setValue(0);settle();window.grab().save(str(destination/'workspace-laptop.png'))
        window.footwork_panel.toggle.setChecked(True);settle();window.measurement_scroll.ensureWidgetVisible(window.footwork_panel.body);settle();window.grab().save(str(destination/'workspace-footwork.png'))
        window.footwork_panel.toggle.setChecked(False);window.toggle_inspector();settle();window.grab().save(str(destination/'workspace-focus.png'))
        example=copy.deepcopy(docs[0]);example['start']=point(0);example['end']=point(60);example['outcome']='completed';example['open_events']=[]
        for e in example['events']:e['notes']=''
        example['footwork']['fall_onset']=None;example['footwork']['coverage']=[{'id':'review-a','start':point(0),'end':point(10),'state':'reviewed'},{'id':'hidden','start':point(10),'end':point(16),'state':'obscured'},{'id':'review-b','start':point(16),'end':point(60),'state':'reviewed'}]
        event=example['footwork']['events'][0];example['footwork']['events'] += [dict(event,id='left-slip',limb='left',start=point(18.2),observation='Left foot visibly loses contact'),dict(event,id='uncertain-slip',limb='uncertain',start=point(12.3),status='uncertain',intent='uncertain',observation='Foot hidden by the wall',interpretation='',action=''),dict(example['footwork']['events'][1],id='intentional-off',start=point(27),end=point(28.6),intent='intentional',observation='Deliberate dynamic foot release')]
        target=repository/'artifacts'/'coaching-preview-0.22.0'/'coaching-review.html'
        export_report([example],target,sources={example['attempt_id']:root/'demo-1.mkv'},media='clips',pdf=True)
        print('Fictional coaching example:',target)
        window.saved=copy.deepcopy(window.document());window.close()
    print('Captured eleven screenshots using synthetic data only:',destination)
    return 0

if __name__=='__main__':raise SystemExit(main())
