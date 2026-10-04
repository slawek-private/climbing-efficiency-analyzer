"""Build private review overlays and a text-only blue-route M0 report."""
import json
from collections import Counter
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]


def main():
    rows, statuses, links = [], [], []
    edges = [(5,7),(7,9),(6,8),(8,10),(5,6),(5,11),(6,12),(11,12),(11,13),(13,15),(12,14),(14,16)]
    for folder in sorted((ROOT / "artifacts" / "m0").iterdir()):
        source = folder / "blue_detector.json"
        if not source.exists():
            continue
        detector = json.loads(source.read_text())
        from m0_spike import validate_cache
        validate_cache(folder)
        identity = json.loads((folder / "source_identity.json").read_text())
        if detector.get("source_identity") != identity:
            raise RuntimeError(f"Stale detector result: {folder.name}; rerun detector.")
        records = detector["records"]
        candidates = [r for r in records if r["person_box"] is not None]
        counts = Counter(r["blue_route"]["status"] for r in records)
        fps = len(records)/sum(r["seconds_processing"] for r in records)
        rows.append(f"| {folder.name} | {len(candidates)}/36 | {fps:.2f} |")
        statuses.append(f"- {folder.name}: " + ", ".join(f"{name}={count}" for name,count in sorted(counts.items())))
        indices = sorted({0,len(candidates)//2,len(candidates)-1}) if candidates else []
        for index in indices:
            record = candidates[index]
            overlay = cv2.imread(str(folder/record["file"]))
            for detection in record["blue_route"]["accepted_holds"]:
                a,b,c,d = map(int,detection["box"])
                cv2.rectangle(overlay,(a,b),(c,d),(255,0,0),2)
            a,b,c,d = map(int,record["blue_route"]["route_box"])
            cv2.rectangle(overlay,(a,b),(c,d),(255,180,0),3)
            a,b,c,d = map(int,record["person_box"])
            cv2.rectangle(overlay,(a,b),(c,d),(0,255,0),3)
            for which in ("base","large"):
                pose_data=json.loads((folder/f"blue_{which}.json").read_text())
                if pose_data.get("source_identity") != identity:
                    raise RuntimeError(f"Stale pose result: {folder.name}; rerun pose.")
                pose=next(r for r in pose_data["records"] if r["pts"]==record["pts"])
                image=overlay.copy()
                for a,b in edges:
                    if pose["scores"][a]>=.3 and pose["scores"][b]>=.3:
                        cv2.line(image,tuple(map(int,pose["pose"][a])),tuple(map(int,pose["pose"][b])),(0,255,255),2)
                for i in (9,10):
                    point=tuple(map(int,pose["pose"][i]))
                    cv2.circle(image,point,6,(0,0,255),-1)
                cv2.putText(image,f"BLUE route candidate | {which} | PTS {record['seconds']:.3f}s | unverified",
                            (10,30),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),2)
                filename=f"blue_review_{record['pts']}_{which}.png"
                cv2.imwrite(str(folder/filename),image)
                links.append(f"- [{folder.name}, {record['seconds']:.3f}s, {which}](../artifacts/m0/{folder.name}/{filename})")
    content="""# M0 correction: target the blue route

The project targets **the blue climbing route and its climber** in all current
videos. The previous gym-wide M0 report did not apply that requirement and is
superseded for route/climber selection. Its installation checks remain valid.

## Changes and measurements

The detector now uses `a blue climbing hold` rather than `a climbing hold`.
Candidate boxes must contain sufficient blue pixels (OpenCV HSV H 90–135,
S >= 70, V >= 35; at least 16 pixels and 15% of box area), and oversized boxes
are rejected. Nearby holds are grouped into a route corridor. At least four
holds and a vertical span of 15% of frame height are required. Two similarly
supported blue groups cause abstention.

Only people overlapping the corridor with at least two holds near their upper
body can feed pose estimation. More than one qualifying person causes abstention.
The person threshold is 0.10 rather than the previous 0.20; results therefore
are not an isolated comparison of route filtering alone. No identity is marked
verified. No frames are inferred from adjacent videos or silently filled in.

The scene is still scanned to locate the route; reported holds and pose crops
are restricted to the proposed blue route. This is a sampled colour/spatial
heuristic, not wall registration, temporal tracking or a validated route classifier.
Blue clothing, lighting shifts, adjacent blue routes and sparse hold detections
can still cause errors. These thresholds have not been tuned against labels.

| Video | Blue-route person candidates / samples | Detector FPS |
| --- | --- | --- |
"""+"\n".join(rows)+"""

Sample status breakdown:

"""+"\n".join(statuses)+"""

Both pose models were rerun on the new candidate crops. Predictions, timing and
memory are in private `blue_base.json` and `blue_large.json` files beside
`blue_detector.json`. Five synthetic tests passed: nonblue holds, bystander
exclusion, route-person selection, ambiguous blue routes and ambiguous people.
Those tests verify rejection behaviour, not accuracy on real footage.

## Verdict and review

**NO-GO for autonomous blue-route measurement with this baseline.** Route-local
candidate coverage is low, and identity and hand localisation remain unverified.
The previous gym-wide crop counts must not be described as blue-route results.
No hold-contact, rest or clip duration is produced. Further work needs a stronger
route detector/tracker and a labelled sample to measure accuracy.

Review the blue boxes (accepted hold candidates), cyan corridor, green person
box and yellow skeleton locally. Red wrist markers highlight the predicted wrist
positions; they do not indicate measured correctness. Images remain excluded
from Git and were not uploaded or inspected by an external vision service.

"""+"\n".join(links)+"""

The old `detector.json`, `base.json`, `large.json` and overlays are retained as
gym-wide baseline artifacts. All current spike commands use the blue route.
Run `python tools/blue_route_report.py` after rerunning the detector and pose
stages. Stop at this corrected M0 review checkpoint before M1.
"""
    (ROOT/"docs"/"M0_BLUE_ROUTE_REPORT.md").write_text(content,encoding="utf-8")
    print("Wrote docs/M0_BLUE_ROUTE_REPORT.md")


if __name__=="__main__":
    main()
