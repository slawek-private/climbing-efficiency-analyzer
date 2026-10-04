import copy
from fractions import Fraction

import av
import numpy as np
import pytest
from jsonschema import Draft202012Validator

from viewer.labels import SCHEMA,History,empty_labels,make_event,metrics,validate,save,load
from viewer.video import index_video,VideoReader
from viewer.report import export_html,export_csv


def source():
    return {"file":"synthetic.mkv","sha256":"a"*64,"time_base":"1/1000","first_pts":500,"frame_count":1000}


def point(seconds):
    return {"frame":int(seconds*10),"pts":500+int(seconds*1000),"seconds":float(seconds)}


def event(kind,hand,start,end,target=None):
    return make_event({"kind":kind,"hand":hand,"target":target,"start":point(start),"confidence":.8,"notes":""},point(end))


def test_schema_and_reviewed_metrics():
    Draft202012Validator.check_schema(SCHEMA)
    doc=empty_labels(source());doc.update(start=point(1),end=point(11),outcome="failed")
    doc["events"]=[event("contact","left",1,5,1),event("contact","right",2,6,2),event("contact","left",6,11,2),
                   event("rest","none",3,7),event("rest","none",6,8),event("offwall","left",5,6),event("clip","right",8,9,1)]
    assert metrics(doc)["climb_seconds"] is None
    doc["reviewed"]={k:True for k in doc["reviewed"]};result=metrics(doc)
    assert result["climb_seconds"]==10
    assert result["rest_seconds"]==5 and result["rest_count"]==1
    assert result["rest_share"]==.5
    assert result["unique_holds"]==2 and result["furthest_hold"]==2
    assert result["left_contact_seconds"]==9
    assert result["left_offwall_during_rests"]==1
    assert result["clip_seconds"]==1


def test_no_offwall_inferred_from_missing_contacts():
    doc=empty_labels(source());doc.update(start=point(1),end=point(11),outcome="failed")
    doc["events"]=[event("rest","none",3,7)]
    for key in ("boundaries","rests","left_contacts"):doc["reviewed"][key]=True
    assert metrics(doc)["left_offwall_during_rests"] is None


def test_hand_switches_and_attempt_clipping():
    doc=empty_labels(source());doc.update(start=point(2),end=point(10),outcome="failed")
    doc["events"]=[event("rest","none",1,12),event("offwall","left",3,4),event("offwall","right",5,6)]
    for key in ("boundaries","rests","left_offwall","right_offwall"):doc["reviewed"][key]=True
    result=metrics(doc)
    assert result["rest_seconds"]==8 and result["rest_share"]==1
    assert result["rest_hand_switches"]==1
    doc["reviewed"]["right_offwall"]=False
    assert metrics(doc)["rest_hand_switches"] is None


def test_reject_impossible_labels():
    doc=empty_labels(source());doc["events"]=[event("contact","left",1,5,1),event("contact","left",4,6,2)]
    with pytest.raises(ValueError,match="Overlapping"):validate(doc)
    doc["events"]=[event("contact","left",1,5,1),event("offwall","left",4,6)]
    with pytest.raises(ValueError,match="simultaneously"):validate(doc)
    doc["events"]=[event("rest","none",2,2)]
    with pytest.raises(ValueError,match="end after"):validate(doc)


def test_drafts_history_and_roundtrip(tmp_path):
    doc=empty_labels(source());history=History(doc)
    opened={"kind":"contact","hand":"left","target":1,"start":point(1),"confidence":1,"notes":""}
    changed=copy.deepcopy(doc);changed["open_events"]=[opened];history.apply(changed)
    history.undo();assert not history.document["open_events"]
    history.redo();assert history.document["open_events"]
    path=tmp_path/"sample.labels.json";save(history.document,path);assert load(path)==history.document
    bad=copy.deepcopy(history.document);bad["reviewed"]["rests"]=True
    with pytest.raises(ValueError,match="Close all"):validate(bad)


def test_report_escapes_and_exports(tmp_path):
    doc=empty_labels(source());doc["climber"]="<script>alert(1)</script>"
    doc.update(start=point(1),end=point(3),outcome="failed");doc["reviewed"]["boundaries"]=True
    doc["events"]=[event("clip","right",1,2,1)]
    path=export_html([doc],tmp_path/"report.html");text=path.read_text()
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in text
    assert "<script>alert(1)</script>" not in text
    assert "Not reviewed" in text and "connect-src 'none'" in text
    export_csv(doc,tmp_path/"events.csv");assert (tmp_path/"events-summary.csv").exists()


def test_variable_frame_rate_exact_seek(tmp_path):
    path=tmp_path/"variable.mkv"
    with av.open(str(path),"w") as output:
        stream=output.add_stream("ffv1",rate=25);stream.width=64;stream.height=48;stream.pix_fmt="bgr0";stream.time_base=Fraction(1,1000)
        stream.codec_context.time_base=Fraction(1,1000)
        for i,pts in enumerate((0,40,120,160,280)):
            image=np.full((48,64,3),i*40,dtype=np.uint8);frame=av.VideoFrame.from_ndarray(image,format="rgb24");frame.pts=pts;frame.time_base=Fraction(1,1000)
            for packet in stream.encode(frame):output.mux(packet)
        for packet in stream.encode():output.mux(packet)
    index=index_video(path);reader=VideoReader(path,index)
    assert len(index["pts"])==5
    assert len(set(np.diff(index["pts"])))>1
    for number in (4,0,3,2,1,4):
        image=reader.frame(number)
        assert abs(int(image[0,0,0])-number*40)<=1
        assert reader.point(number)["pts"]==index["pts"][number]
    reader.close()
