import numpy as np
from blue_route import select_blue_route


def scene(xs=(100,)):
    rgb = np.zeros((1000, 600, 3), dtype=np.uint8)
    detections = []
    for x in xs:
        for y in (100, 220, 340, 460):
            rgb[y:y+20,x:x+20] = (0,0,255)
            detections.append({"box": [x,y,x+20,y+20], "score": 0.5, "label": "a blue climbing hold"})
    return rgb, detections


def test_reject_nonblue_holds():
    rgb, detections = scene()
    rgb[:] = (255,0,0)
    assert select_blue_route(rgb,detections)["person_box"] is None
    assert select_blue_route(rgb,detections)["accepted_holds"] == []


def test_exclude_bystander():
    rgb, detections = scene()
    detections.append({"box": [400,100,550,500],"score":0.9,"label":"a person"})
    result = select_blue_route(rgb,detections)
    assert len(result["accepted_holds"]) == 4
    assert result["person_box"] is None


def test_select_route_person():
    rgb, detections = scene()
    box = [60,80,170,500]
    detections.append({"box":box,"score":0.3,"label":"a person"})
    result = select_blue_route(rgb,detections)
    assert result["person_box"] == box
    assert result["identity_verified"] is False


def test_abstain_multiple_blue_routes():
    rgb, detections = scene((100,450))
    assert select_blue_route(rgb,detections)["status"] == "ambiguous_blue_routes"


def test_abstain_multiple_route_people():
    rgb, detections = scene()
    detections.extend({"box":b,"score":0.4,"label":"a person"} for b in ([60,80,170,500],[75,90,185,510]))
    assert select_blue_route(rgb,detections)["status"] == "ambiguous_route_people"
