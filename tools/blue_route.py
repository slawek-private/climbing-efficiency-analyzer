"""Conservative M0 blue-hold filtering and route-local person selection.

These rules propose a route, not a calibrated identity or route classifier.
Multiple plausible blue hold groups cause abstention.
"""
import cv2
import numpy as np


def select_blue_route(rgb, detections):
    height, width = rgb.shape[:2]
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    blue = cv2.inRange(hsv, (90, 70, 35), (135, 255, 255))
    holds = []
    for detection in detections:
        if "climbing hold" not in detection["label"]:
            continue
        x1, y1, x2, y2 = detection["box"]
        xa, ya = max(0, int(x1)), max(0, int(y1))
        xb, yb = min(width, int(x2)), min(height, int(y2))
        area = (xb - xa) * (yb - ya)
        if area <= 0 or area > width * height * 0.03:
            continue
        pixels = np.count_nonzero(blue[ya:yb, xa:xb])
        fraction = pixels / area
        if pixels >= 16 and fraction >= 0.15:
            # De-duplicate highly overlapping boxes from the same prompt.
            duplicate = False
            for previous in holds:
                a, b, c, d = previous["box"]
                overlap = max(0, min(x2, c) - max(x1, a)) * max(0, min(y2, d) - max(y1, b))
                union = (x2-x1)*(y2-y1) + (c-a)*(d-b) - overlap
                if union > 0 and overlap / union > 0.5:
                    duplicate = True
                    break
            if not duplicate:
                holds.append({**detection, "blue_fraction": float(fraction)})
    centers = [((d["box"][0]+d["box"][2])/2, (d["box"][1]+d["box"][3])/2) for d in holds]
    # Group by lateral proximity; this initial rule assumes one blue route.
    remaining = set(range(len(holds)))
    groups = []
    while remaining:
        group = {min(remaining)}
        remaining -= group
        while True:
            additions = {j for j in remaining if any(abs(centers[i][0]-centers[j][0]) < width*0.18 for i in group)}
            if not additions:
                break
            group |= additions
            remaining -= additions
        groups.append(sorted(group))
    groups.sort(key=lambda g: (-len(g), g[0]))
    result = {"target": "blue", "accepted_holds": [], "route_box": None,
              "person_box": None, "status": "insufficient_blue_holds",
              "identity_verified": False, "candidate_blue_holds": len(holds)}
    if not groups or len(groups[0]) < 4:
        return result
    if len(groups) > 1 and len(groups[1]) >= max(3, len(groups[0])*0.6):
        result["status"] = "ambiguous_blue_routes"
        return result
    selected = [holds[i] for i in groups[0]]
    xs = [centers[i][0] for i in groups[0]]
    ys = [centers[i][1] for i in groups[0]]
    if max(ys)-min(ys) < height*0.15:
        return result
    corridor = [max(0, min(xs)-width*0.12), max(0, min(ys)-height*0.08),
                min(width, max(xs)+width*0.12), min(height, max(ys)+height*0.12)]
    result.update(accepted_holds=selected, route_box=corridor, status="no_route_person")
    candidates = []
    for detection in detections:
        if detection["label"] != "a person" or detection["score"] < 0.10:
            continue
        x1, y1, x2, y2 = detection["box"]
        area = (x2-x1)*(y2-y1)
        intersection = max(0, min(x2,corridor[2])-max(x1,corridor[0])) * max(0,min(y2,corridor[3])-max(y1,corridor[1]))
        if area <= 0 or intersection/area < 0.35:
            continue
        # A route-associated climber should have holds near the upper body.
        nearby = sum(x1-width*0.04 <= x <= x2+width*0.04 and
                     y1-height*0.04 <= y <= y1+(y2-y1)*0.7 for x,y in zip(xs,ys))
        if nearby >= 2:
            candidates.append(detection)
    if len(candidates) != 1:
        result["status"] = "ambiguous_route_people" if candidates else "no_route_person"
        return result
    result.update(person_box=candidates[0]["box"], status="blue_route_candidate")
    return result
