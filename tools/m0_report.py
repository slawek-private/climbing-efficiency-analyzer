"""Create an aggregate report without including footage in the repository."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    rows = []
    proxies = []
    for folder in sorted((ROOT / "artifacts" / "m0").glob("*")):
        if not (folder / "detector.json").exists():
            continue
        detector = json.loads((folder / "detector.json").read_text())
        records = detector["records"]
        crops = sum(r["person_box"] is not None for r in records)
        fps = len(records) / sum(r["seconds_processing"] for r in records)
        rows.append(f"| {folder.name} | OWLv2 | {crops}/{len(records)} | {fps:.2f} | {detector['peak_allocated_mib']:.0f} / {detector['peak_reserved_mib']:.0f} |")
        for name in ("base", "large"):
            result = json.loads((folder / f"{name}.json").read_text())
            valid = [r for r in result["records"] if r["pose"] is not None]
            rows.append(f"| {folder.name} | {result['model']} | {len(valid)}/{len(records)} | {result['fps']:.2f} | {result['peak_allocated_mib']:.0f} / {result['peak_reserved_mib']:.0f} |")
            low = [sum(r["scores"][index] < 0.3 for r in valid) for index in (9, 10)]
            proxies.append(f"| {folder.name} | {name} | {low[0]}/{len(valid)} | {low[1]}/{len(valid)} |")
    content = """# M0 gym-wide baseline — superseded for route selection

The target is the blue route. See M0_BLUE_ROUTE_REPORT.md for the corrected
route-specific run. This original report records the gym-wide baseline only.

Date: 2026-10-04. Native Windows 11; RTX 5070 Ti, 16,303 MiB VRAM,
driver 596.49. PyTorch 2.8.0 + CUDA 12.8 passed a GPU matrix operation.
PySide6 application creation and HEVC decoding passed. uv lockfile pins the
environment. No WSL, cloud inference, upload, push or Git commit was used.

## Recommendation

**GO for native Windows development; NO-GO for autonomous measurements with
this baseline.** Missing person crops, unverified identity and wrist-only
keypoints prevent a credible contact/clip timing claim. Model capacity fits
comfortably in available GPU memory, but accuracy has not been established.
Do not generate contact durations from these sparse outputs.

The computational part of M0 is complete. The hand-quality/accuracy gate remains
open pending human ground truth and overlay review. This report does not label
the whole M0 accuracy requirement complete. Stop here for the user's review
before M1 or any production pipeline work.

## Method and measured results

36 samples per video, evenly spaced over container-reported duration; seeking
decodes forward to an actual frame with a recorded PTS and time base. Container
duration schedules sampling only. Measurements use PTS, never frame count times
nominal FPS. All three streams have -90 degree rotation; decoded frames are
rotated clockwise to 1080 x 1920. This is not a full VFR timestamp audit.

Models run separately, batch 1, float32, no compilation. One unmeasured warmup
per model process. FPS includes preprocessing, CUDA inference and model
postprocessing, excluding image read, overlays, initial model load and checksum
validation. It is **sample inference throughput**, not full-video processing FPS.
Pose throughput excludes the detector. CUDA timings synchronize the device.
Memory is PyTorch allocator peak, allocated/reserved MiB; it excludes driver,
display and non-PyTorch allocations. CUDA matrix checks are not pose accuracy tests.

| Video | Model | Person crops / samples | FPS | Peak GPU MiB allocated / reserved |
| --- | --- | --- | --- | --- |
""" + "\n".join(rows) + """

## Hand keypoint quality: not yet measured against labels

The selected COCO heads provide wrist locations, no fingertips. The larger model
has fewer low-score wrists on the available crops, but these scores are not
calibrated confidence and cannot establish correct localisation. Both models use
identical detector boxes. The heuristic selects the topmost detected person at
score >= 0.2; it does not establish that this is the climber. Missing crops count
as failures rather than silently contributing high scores to an overall average.
No ground-truth hand locations, visibility flags or hold boxes were supplied.
Hand PCK, localisation MAE, detector precision/recall and event accuracy are
therefore **unavailable**, not estimated.

Low-score wrist counts (score < 0.3, denominator is available crops only):

| Video | Model | Left | Right |
| --- | --- | --- | --- |
""" + "\n".join(proxies) + """

## Holds and quickdraws

OWLv2 uses fixed prompts: a person, a climbing hold, a climbing quickdraw.
It emits hold candidates at score >= 0.10 in every sampled frame. These are
unverified proposals; count is not accuracy. Small objects, rope occlusion and
route discrimination remain untested. No contacts, rests or clips are produced.

## Private local review artifacts

`artifacts/m0/<video>/` contains cached PNG frames, JSON predictions and overlay
PNGs: `detector_*.png`, `base_*.png`, `large_*.png`. These are ignored by Git.
Overlays mark low-score keypoints red and label identity as unverified. Pose
overlays exist only for samples with a person crop; missing outputs remain in JSON.
Review these locally; do not upload frames to a service or attach them to issues.

Representative pairs:

- [Video A — Base](../artifacts/m0/example_video_a/base_036.png), [Large](../artifacts/m0/example_video_a/large_036.png), [holds](../artifacts/m0/example_video_a/detector_036.png).
- [Video B — Base](../artifacts/m0/example_video_b/base_036.png), [Large](../artifacts/m0/example_video_b/large_036.png), [holds](../artifacts/m0/example_video_b/detector_036.png).
- [Video C — Base](../artifacts/m0/example_video_c/base_018.png), [Large](../artifacts/m0/example_video_c/large_018.png), [holds](../artifacts/m0/example_video_c/detector_018.png).

## Installation issues and next alternatives

All pinned libraries installed from wheels; no native extension compilation or
Linux workaround was needed. The long-path registry change was denied because
this session lacks administrator access; see SETUP.md. It did not prevent this
installation. MediaPipe and Ultralytics dependencies install overlapping OpenCV
distributions at the same resolved version; imports passed, but this is packaging
debt to resolve before the production environment is finalised.

At review, prioritise a stronger person detector/temporal tracker and crop identity
validation. Label a small stratified sample with left/right wrist and fingertip
locations, occlusion and hold boxes before choosing a pose model. To quantify
small-hand detail, try larger pose input resolution or a dense-hand model with
verified Windows compatibility and checkpoint licence. Sapiens is a research
alternative with noncommercial restrictions; no reason to introduce WSL yet.
If OWLv2 proposals fail review, benchmark a climbing-specific detector against
labelled holds. Both source papers use given hold boxes, so they do not settle
this detector choice. See MODELS.md for paper figures, caveats and licences.

## Reproduction

```powershell
uv sync --locked
uv run --locked python tools/download_m0_models.py
uv run --locked python tools/check_environment.py
uv run --locked python tools/m0_spike.py sample
uv run --locked python tools/m0_spike.py detector
uv run --locked python tools/m0_spike.py base
uv run --locked python tools/m0_spike.py large
uv run --locked python tools/blue_route_report.py
```

The downloader reads only public model resources. Inference runs in a separate
process with offline flags and Python socket connections denied. The socket guard
is defence in depth, not an OS-level firewall. Model revisions and hashes are
recorded in M0_MODEL_MANIFEST.json; downloads reuse verified files. Sample caches
must be removed or moved aside if the input videos change; M3 will implement
content-addressed stage caching. No GPU tests have been claimed as CI tests.
"""
    (ROOT / "docs" / "M0_REPORT.md").write_text(content, encoding="utf-8")
    print("Wrote docs/M0_REPORT.md")


if __name__ == "__main__":
    main()
