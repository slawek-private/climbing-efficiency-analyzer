# M0 model and dataset register

The target is the blue climbing route in the three local videos. The current
spike uses a blue-hold prompt and colour/spatial route filtering; see
M0_BLUE_ROUTE_REPORT.md. Previous gym-wide crop counts are superseded.

All inference is local. Downloads were authorised by the user's installation
approval. `models/manifest.json` records immutable source revisions, upstream
hashes, local SHA-256 values and sizes. Weights and footage are ignored by Git.
Inference verifies weights again and loads only local files.

## Models tested

| Candidate | Source and licence | Purpose and limitation |
| --- | --- | --- |
| ViTPose Base Simple | https://huggingface.co/usyd-community/vitpose-base-simple — Apache-2.0 as declared on the model card | Small plain-PyTorch pose baseline. COCO 17 points: wrists, no fingers. Not the paper's ViTPose-L COCO-25 checkpoint. |
| ViTPose+ Large | https://huggingface.co/usyd-community/vitpose-plus-large — Apache-2.0 as declared on the model card | Larger plain-PyTorch candidate; COCO expert 0, 17 points. Tests the value of increased capacity. No finger points; not Sapiens. |
| OWLv2 Base Patch16 Ensemble | https://huggingface.co/google/owlv2-base-patch16-ensemble — Apache-2.0 as declared on the model card | Trial open-vocabulary hold/person/quickdraw detector. No climbing-specific training; suitability must be measured. |

The candidate pair deliberately uses the same pose family to isolate model
capacity and avoid native extension builds. It does not compare all published
baselines. Batch size is 1, float32. Transformer processors use their checkpoint
input sizes; source frames are decoded at full resolution before person cropping.
No claim of high-resolution hand detail follows from a full-resolution source.

## Installed or considered, not benchmarked

- MediaPipe 0.10.21: native Windows imports passed. Framework code is Apache-2.0
  (https://github.com/google-ai-edge/mediapipe/blob/master/LICENSE). Separate
  weight licence verification remains outstanding; no MediaPipe weights downloaded.
- Ultralytics 8.3.199: native Windows imports passed, optional integrations and
  sync disabled. Code is AGPL-3.0 (https://github.com/ultralytics/ultralytics/blob/main/LICENSE).
  Official YOLOv8 model card also declares AGPL-3.0
  (https://huggingface.co/Ultralytics/YOLOv8). No YOLO weights downloaded or used.
- Sapiens: https://github.com/facebookresearch/sapiens/blob/main/LICENSE declares
  CC BY-NC 4.0. Not selected for this initial spike; dense finger points remain
  a useful research alternative. Windows execution and the exact checkpoint's
  licence have not been validated. No Sapiens weights downloaded.

## Published evidence

[The Way Up, 2025](https://arxiv.org/html/2505.12854v1), Table 5, confirms overall
hold-usage accuracy at any temporal overlap: ViTPose L 86.6%, MediaPipe Heavy
83.5%, YOLOv8-pose X 75.3%. These combine hands and feet. Hand-only figures are
80.1%, 76.6%, 73.9%. The experiment uses supplied hold boxes, route crops and
stabilised footage. It does not measure autonomous hold detection or clips.

[Training-Free Hold-Usage Detection, 2026](https://arxiv.org/html/2609.30026v1)
reports 90.2% **event F1**, not generic accuracy, for Sapiens-1B on held-out
videos with supplied hold boxes. It reports 83.2% at temporal IoU >= 0.5.
Its Table I reports 79.9% overall and 72.7% hand-only F1 across all 22 videos,
but Table V gives 90.0% for an apparently similar all-22 protocol. This internal
inconsistency requires clarification before reproducing or adopting the headline.
These measurements do not establish accuracy on the user's footage.

## Public dataset

The Way Up: https://doi.org/10.5281/zenodo.15196866.
The Zenodo API record declares CC BY 4.0 (verified 2026-10-04 via
https://zenodo.org/api/records/15196866). It offers a 20,889,661,515-byte archive.
Benchmarking is permitted with attribution. No dataset media has been downloaded;
the M0 spike uses only the three local videos. Public benchmarking belongs to
the subsequent contact/evaluation milestones.
