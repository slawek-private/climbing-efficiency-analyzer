"""Offline, sampled M0 benchmark; not a contact-analysis pipeline.

Usage: python tools/m0_spike.py sample|detector|base|large
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

from local_runtime import configure
configure()

import av
import cv2
import numpy as np
from blue_route import select_blue_route
import torch
from PIL import Image
from transformers import AutoImageProcessor, Owlv2Processor, Owlv2ForObjectDetection, VitPoseForPoseEstimation

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "m0"
SAMPLES = 36
PROMPTS = ["a person", "a blue climbing hold", "a climbing quickdraw"]


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def video_identity(video):
    digest = hashlib.sha256()
    with video.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return {"file": video.name, "sha256": digest.hexdigest(), "samples": SAMPLES}


def validate_cache(folder):
    identity_path = folder / "source_identity.json"
    if not identity_path.exists():
        raise RuntimeError(f"Unverified old sample cache: {folder.name}. Run the sample stage again.")
    identity = json.loads(identity_path.read_text())
    if identity != video_identity(ROOT / "videos" / identity["file"]):
        raise RuntimeError(f"Video changed: {folder.name}. Run the sample stage again.")


def samples():
    for video in sorted((ROOT / "videos").glob("*")):
        if video.suffix.lower() not in {".mp4", ".mov"}:
            continue
        dest = OUT / video.stem
        identity = video_identity(video)
        identity_path = dest / "source_identity.json"
        if (dest / "samples.json").exists() and identity_path.exists():
            if json.loads(identity_path.read_text()) == identity:
                continue
        dest.mkdir(parents=True, exist_ok=True)
        records = []
        with av.open(str(video)) as container:
            stream = container.streams.video[0]
            duration = float(stream.duration * stream.time_base)
            start = float((stream.start_time or 0) * stream.time_base)
            for index, target in enumerate(np.linspace(start + 0.5, start + duration - 0.5, SAMPLES)):
                container.seek(int(target / float(stream.time_base)), stream=stream, backward=True)
                for frame in container.decode(stream):
                    if frame.pts is None:
                        raise RuntimeError("Missing PTS")
                    actual = float(frame.pts * frame.time_base)
                    if actual < target:
                        continue
                    rotation = frame.rotation
                    if rotation % 90:
                        raise RuntimeError(f"Unsupported rotation: {rotation}")
                    rgb = np.ascontiguousarray(np.rot90(frame.to_ndarray(format="rgb24"), k=rotation // 90))
                    filename = f"frame_{index:03}.png"
                    cv2.imwrite(str(dest / filename), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
                    records.append({"file": filename, "pts": frame.pts, "time_base": str(frame.time_base),
                                    "seconds": actual, "rotation": rotation,
                                    "width": rgb.shape[1], "height": rgb.shape[0]})
                    break
                else:
                    raise RuntimeError(f"No frame at target {target}")
        write_json(dest / "samples.json", records)
        write_json(identity_path, identity)
        print(f"Sampled {video.name}: {len(records)} exact PTS frames", flush=True)


def verified_folder(name):
    from download_m0_models import digest
    manifest = json.loads((ROOT / "models" / "manifest.json").read_text())
    repo = next(key for key in manifest if key.split("/")[-1] == name)
    folder = ROOT / "models" / name
    for file in manifest[repo]["files"]:
        if digest(folder / file["name"]) != file["sha256"]:
            raise RuntimeError(f"Model checksum mismatch: {file['name']}")
    return folder


def inference_time(call):
    torch.cuda.synchronize()
    start = time.perf_counter()
    result = call()
    torch.cuda.synchronize()
    return result, time.perf_counter() - start


def detector():
    folder = verified_folder("owlv2-base-patch16-ensemble")
    processor = Owlv2Processor.from_pretrained(folder, local_files_only=True)
    model = Owlv2ForObjectDetection.from_pretrained(folder, local_files_only=True).to("cuda").eval()
    warmed = False
    for listing in sorted(OUT.glob("*/samples.json")):
        validate_cache(listing.parent)
        records = json.loads(listing.read_text())
        results = []
        torch.cuda.reset_peak_memory_stats()
        for record in records:
            image = Image.open(listing.parent / record["file"]).convert("RGB")
            def run():
                inputs = processor(text=[PROMPTS], images=image, return_tensors="pt").to("cuda")
                with torch.inference_mode():
                    outputs = model(**inputs)
                return processor.post_process_object_detection(outputs, threshold=0.10,
                         target_sizes=torch.tensor([[image.height, image.width]], device="cuda"))[0]
            if not warmed:
                run()
                torch.cuda.synchronize()
                warmed = True
            result, elapsed = inference_time(run)
            boxes = result["boxes"].cpu().tolist()
            scores = result["scores"].cpu().tolist()
            labels = result["labels"].cpu().tolist()
            detections = [{"box": box, "score": score, "label": PROMPTS[label]}
                          for box, score, label in zip(boxes, scores, labels)]
            route = select_blue_route(np.array(image), detections)
            results.append({**record, "seconds_processing": elapsed, "detections": detections,
                            "person_box": route["person_box"], "blue_route": route,
                            "identity_verified": False})
            if len(results) in {1, 18, 36}:
                overlay = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                if route["route_box"] is not None:
                    a,b,c,d = map(int,route["route_box"])
                    cv2.rectangle(overlay,(a,b),(c,d),(255,0,0),3)
                for detection in route["accepted_holds"]:
                    x1, y1, x2, y2 = map(int, detection["box"])
                    cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 255, 255), 2)
                    cv2.putText(overlay, f"{detection['label']} {detection['score']:.2f}",
                                (x1, max(y1, 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
                cv2.putText(overlay, route["status"],(15,30),cv2.FONT_HERSHEY_SIMPLEX,0.7,(255,255,255),2)
                cv2.imwrite(str(listing.parent / f"blue_detector_{len(results):03}.png"), overlay)
        write_json(listing.parent / "blue_detector.json", {"source_identity": json.loads((listing.parent / "source_identity.json").read_text()), "target_route": "blue", "records": results,
                   "peak_allocated_mib": torch.cuda.max_memory_allocated() / 2**20,
                   "peak_reserved_mib": torch.cuda.max_memory_reserved() / 2**20})
        print(f"Detector {listing.parent.name}: {len(results)/sum(r['seconds_processing'] for r in results):.2f} FPS", flush=True)


def pose(which):
    name = "vitpose-base-simple" if which == "base" else "vitpose-plus-large"
    folder = verified_folder(name)
    processor = AutoImageProcessor.from_pretrained(folder, local_files_only=True, use_fast=False)
    model = VitPoseForPoseEstimation.from_pretrained(folder, local_files_only=True).to("cuda").eval()
    warmed = False
    for listing in sorted(OUT.glob("*/blue_detector.json")):
        validate_cache(listing.parent)
        detector_data = json.loads(listing.read_text())
        source_identity = json.loads((listing.parent / "source_identity.json").read_text())
        if detector_data.get("source_identity") != source_identity:
            raise RuntimeError(f"Stale detector cache: {listing.parent.name}. Run detector again.")
        detected = detector_data["records"]
        results = []
        torch.cuda.reset_peak_memory_stats()
        for record in detected:
            if record["person_box"] is None:
                results.append({"pts": record["pts"], "seconds": record["seconds"], "pose": None,
                                "reason": "No person crop"})
                continue
            image = Image.open(listing.parent / record["file"]).convert("RGB")
            x1, y1, x2, y2 = record["person_box"]
            box = np.array([[x1, y1, x2 - x1, y2 - y1]], dtype=np.float32)
            def run():
                inputs = processor(image, boxes=[box], return_tensors="pt").to("cuda")
                if which == "large":
                    inputs["dataset_index"] = torch.tensor([0], device="cuda")
                with torch.inference_mode():
                    output = model(**inputs)
                return processor.post_process_pose_estimation(output, boxes=[box])[0][0]
            if not warmed:
                run()
                torch.cuda.synchronize()
                warmed = True
            result, elapsed = inference_time(run)
            points = result["keypoints"].cpu().tolist()
            scores = result["scores"].cpu().tolist()
            results.append({"file": record["file"], "pts": record["pts"], "seconds": record["seconds"],
                            "seconds_processing": elapsed, "pose": points, "scores": scores,
                            "person_box": record["person_box"], "target_route": "blue", "identity_verified": False})
            if len(results) in {1, 18, 36}:
                overlay = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                for a, b in model.config.edges:
                    if scores[a] >= 0.3 and scores[b] >= 0.3:
                        cv2.line(overlay, tuple(map(int, points[a])), tuple(map(int, points[b])), (0, 255, 0), 2)
                for index, (point, score) in enumerate(zip(points, scores)):
                    color = (0, 0, 255) if score < 0.3 else (255, 100, 0)
                    cv2.circle(overlay, tuple(map(int, point)), 4, color, -1)
                    if index in {9, 10}:
                        cv2.putText(overlay, f"{'L' if index == 9 else 'R'} wrist {score:.2f}",
                                    tuple(map(int, point)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                cv2.putText(overlay, f"{name} PTS {record['seconds']:.3f}s | identity unverified",
                            (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
                cv2.imwrite(str(listing.parent / f"blue_{which}_{len(results):03}.png"), overlay)
        times = [r["seconds_processing"] for r in results if r["pose"] is not None]
        write_json(listing.parent / f"blue_{which}.json", {"source_identity": source_identity, "target_route": "blue", "model": name, "records": results,
                   "fps": len(times) / sum(times) if times else None,
                   "peak_allocated_mib": torch.cuda.max_memory_allocated() / 2**20,
                   "peak_reserved_mib": torch.cuda.max_memory_reserved() / 2**20})
        print(f"{name} {listing.parent.name}: {len(times)} successful crops, {len(times)/sum(times) if times else 0:.2f} FPS", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["sample", "detector", "base", "large"])
    args = parser.parse_args()
    if args.stage == "sample":
        samples()
    elif args.stage == "detector":
        detector()
    else:
        pose(args.stage)
