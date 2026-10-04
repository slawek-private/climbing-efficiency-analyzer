"""Manual labels and interval metrics. No machine predictions are inferred."""
import copy
import json
from fractions import Fraction
from pathlib import Path
from uuid import uuid4

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schema" / "labels-v1.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)


def empty_labels(source):
    return {"schema_version": "1.2.0", "source": source,
            "climber": Path(source["file"]).stem.split("_final_")[0].capitalize(),
            "attempt": "1", "route": "blue", "outcome": "unknown", "start": None, "end": None,
            "checkpoints": [], "events": [], "open_events": [], "reviewed": {k: False for k in
                ("left_contacts", "right_contacts", "left_offwall", "right_offwall", "rests", "clips", "boundaries")}, "notes": ""}


def validate(document):
    VALIDATOR.validate(document)
    source = document["source"]
    base = Fraction(source["time_base"])
    if base <= 0:
        raise ValueError("Invalid time base")
    points = [p for p in (document["start"], document["end"]) if p is not None]
    ids = set()
    for checkpoint in document.get("checkpoints", []):
        if checkpoint["id"] in ids: raise ValueError("Duplicate checkpoint ID")
        ids.add(checkpoint["id"])
        points.append(checkpoint["point"])
    for event in document["events"]:
        if event["id"] in ids:
            raise ValueError("Duplicate event ID")
        ids.add(event["id"])
        if event["end"]["frame"] <= event["start"]["frame"] or event["end"]["seconds"] <= event["start"]["seconds"]:
            raise ValueError("An interval must end after it starts")
        points.extend((event["start"], event["end"]))
    for event in document["events"] + document["open_events"]:
        if event["kind"] in {"contact", "clip", "offwall", "chalk"} and event["hand"] not in {"left", "right"}:
            raise ValueError("Contact, clip and off-wall events require a hand")
        if event["kind"] == "rest" and event["hand"] != "none" and document["schema_version"] == "1.0.0":
            raise ValueError("Hand-specific rest intervals require label schema 1.1.0")
        if event["kind"] == "chalk" and document["schema_version"] != "1.2.0":raise ValueError("Chalking requires schema 1.2.0")
        if event["kind"] == "contact" and event["target"] is None:
            raise ValueError("Contact requires a blue hold number")
    keys=[(e['kind'],e['hand']) for e in document['open_events']]
    if len(keys)!=len(set(keys)):raise ValueError('Only one unfinished timer per activity and hand is allowed')
    for kind in ('rest','clip','chalk'):
        for hand in ('left','right'):
            events=sorted((e for e in document['events'] if e['kind']==kind and e['hand']==hand),key=lambda e:e['start']['seconds'])
            if any(b['start']['seconds']<a['end']['seconds'] for a,b in zip(events,events[1:])):raise ValueError('Overlapping '+hand+' '+kind+' intervals')
    points.extend(e["start"] for e in document["open_events"])
    for point in points:
        if point["frame"] >= source["frame_count"]:
            raise ValueError("Frame outside source video")
        expected = float((point["pts"] - source["first_pts"]) * base)
        if abs(expected - point["seconds"]) > 1e-6:
            raise ValueError("Timestamp does not match presentation timestamp")
    if document["start"] and document["end"] and document["end"]["seconds"] <= document["start"]["seconds"]:
        raise ValueError("Attempt end must follow start")
    for hand in ("left", "right"):
        contacts = sorted((e for e in document["events"] if e["kind"] == "contact" and e["hand"] == hand), key=lambda e: e["start"]["seconds"])
        for before, after in zip(contacts, contacts[1:]):
            if after["start"]["seconds"] < before["end"]["seconds"]:
                raise ValueError(f"Overlapping {hand} hand contacts")
        for contact in contacts:
            for off in document["events"]:
                if off["kind"] == "offwall" and off["hand"] == hand and min(contact["end"]["seconds"], off["end"]["seconds"]) > max(contact["start"]["seconds"], off["start"]["seconds"]):
                    raise ValueError(f"{hand} hand is simultaneously on and off wall")
    if any(document["reviewed"].values()) and document["open_events"]:
        raise ValueError("Close all open events before marking tracks reviewed")
    if document["reviewed"]["boundaries"] and (not document["start"] or not document["end"] or document["outcome"] == "unknown"):
        raise ValueError("Reviewed boundaries require start, end and outcome")


def make_event(open_event, end):
    return {**open_event, "id": str(uuid4()), "end": end}


def save(document, path):
    validate(document)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, indent=2), encoding="utf-8")
    temporary.replace(path)


def load(path):
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    validate(document)
    return document


def union(intervals):
    merged = []
    for start, end in sorted(intervals):
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def length(intervals):
    return sum(b-a for a,b in union(intervals))


def rest_breakdown(document):
    start,end=document['start'],document['end'];result={key:None for key in ('total_rest_marked_seconds','total_rest_marked_count','total_marked_rest_share','left_total_rest_marked_seconds','right_total_rest_marked_seconds')}
    if not start or not end:return result
    a,b=start['seconds'],end['seconds'];events=[e for e in document['events'] if e['kind'] in ('rest','chalk')]
    if not events:return result
    def intervals(group):return [(max(a,e['start']['seconds']),min(b,e['end']['seconds'])) for e in group if e['end']['seconds']>a and e['start']['seconds']<b]
    combined=union(intervals(events));result.update(total_rest_marked_seconds=length(combined),total_rest_marked_count=len(combined),total_marked_rest_share=length(combined)/(b-a))
    for hand in ('left','right'):
        group=[e for e in events if e['hand']==hand]
        if group:result[hand+'_total_rest_marked_seconds']=length(intervals(group))
    return result


def metrics(document):
    validate(document)
    start, end = document["start"], document["end"]
    result = {"dedicated_rest_seconds": None, "dedicated_rest_count": None, "chalk_seconds": None, "climb_seconds": None, "rest_count": None, "rest_seconds": None, "rest_share": None,
              "unique_holds": None, "furthest_hold": None, "left_contact_seconds": None,
              "right_contact_seconds": None, "left_offwall_during_rests": None,
              "right_offwall_during_rests": None, "rest_hand_switches": None, "clip_count": None, "clip_seconds": None}
    if not start or not end:
        return result
    a, b = start["seconds"], end["seconds"]
    def intervals(kind, hand=None):
        return [(max(a,e["start"]["seconds"]),min(b,e["end"]["seconds"])) for e in document["events"]
                if e["kind"] == kind and (hand is None or e["hand"] == hand)
                and e["end"]["seconds"] > a and e["start"]["seconds"] < b]
    boundary_ok = document["reviewed"]["boundaries"]
    if boundary_ok:
        result["climb_seconds"] = b-a
    dedicated = union(intervals("rest"))
    rests = union(intervals("rest")+intervals("chalk"))
    if boundary_ok and document["reviewed"]["rests"]:
        result.update(rest_count=len(rests), rest_seconds=length(rests), rest_share=length(rests)/(b-a),dedicated_rest_seconds=length(dedicated),dedicated_rest_count=len(dedicated),chalk_seconds=length(intervals("chalk")))
    if boundary_ok and document["reviewed"]["left_contacts"] and document["reviewed"]["right_contacts"]:
        holds = {e["target"] for e in document["events"] if e["kind"] == "contact" and e["end"]["seconds"] > a and e["start"]["seconds"] < b}
        result.update(unique_holds=len(holds), furthest_hold=max(holds) if holds else None)
    for hand in ("left", "right"):
        if boundary_ok and document["reviewed"][f"{hand}_contacts"]:
            contacts = union(intervals("contact",hand))
            result[f"{hand}_contact_seconds"] = length(contacts)
        if boundary_ok and document["reviewed"]["rests"] and document["reviewed"].get(f"{hand}_offwall",False):
            offwall = union(intervals("offwall",hand))
            result[f"{hand}_offwall_during_rests"] = length([(max(x,c),min(y,d)) for x,y in rests for c,d in offwall if min(y,d)>max(x,c)])
    if boundary_ok and document["reviewed"]["clips"]:
        clips = intervals("clip")
        result.update(clip_count=len(clips),clip_seconds=sum(y-x for x,y in clips))
    if boundary_ok and document["reviewed"]["rests"] and all(document["reviewed"].get(f"{hand}_offwall",False) for hand in ("left","right")):
        switches=0
        off={hand:union(intervals("offwall",hand)) for hand in ("left","right")}
        for x,y in rests:
            cuts=sorted({x,y,*[max(x,min(y,p)) for hand in off for interval in off[hand] for p in interval]})
            previous=None
            for c,d in zip(cuts,cuts[1:]):
                mid=(c+d)/2
                active=[hand for hand in off if any(s<=mid<t for s,t in off[hand])]
                if len(active)==2:previous=None
                elif len(active)==1:
                    if previous is not None and previous!=active[0]:switches+=1
                    previous=active[0]
        result["rest_hand_switches"]=switches
    return result


def reaches(document):
    answer = []
    for hand in ("left", "right"):
        contacts = sorted((e for e in document["events"] if e["kind"] == "contact" and e["hand"] == hand), key=lambda e:e["start"]["seconds"])
        for previous, following in zip(contacts,contacts[1:]):
            duration = following["start"]["seconds"]-previous["end"]["seconds"]
            if duration > 0:
                answer.append({"hand":hand,"from_hold":previous["target"],"to_hold":following["target"],
                               "start":previous["end"],"end":following["start"],"seconds":duration})
    return answer


class History:
    def __init__(self, document):
        self.document = copy.deepcopy(document)
        self.undo_stack, self.redo_stack = [], []

    def apply(self, document):
        validate(document)
        self.undo_stack.append(copy.deepcopy(self.document))
        self.redo_stack.clear()
        self.document = copy.deepcopy(document)

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.document)
            self.document = self.undo_stack.pop()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.document)
            self.document = self.redo_stack.pop()
