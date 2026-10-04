"""Local M0 checks. Does not download models or transmit video data."""
import importlib.metadata
import json
from pathlib import Path

from local_runtime import configure

configure()

import av
import cv2
import mediapipe
import torch
import transformers
import ultralytics
from PySide6.QtWidgets import QApplication


def main():
    root = Path(__file__).resolve().parents[1]
    report = {"packages": {name: importlib.metadata.version(name) for name in (
        "torch", "torchvision", "av", "opencv-python", "opencv-contrib-python",
        "mediapipe", "transformers", "pyside6", "ultralytics")}}
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable")
    props = torch.cuda.get_device_properties(0)
    x = torch.randn((1024, 1024), device="cuda")
    y = x @ x
    torch.cuda.synchronize()
    assert torch.isfinite(y).all().item()
    report["gpu"] = {"name": props.name, "vram_bytes": props.total_memory,
                     "capability": list(torch.cuda.get_device_capability()),
                     "torch_cuda": torch.version.cuda, "matrix_operation": "passed"}
    app = QApplication([])
    report["qt"] = "application created"
    from ultralytics.utils import SETTINGS, ONLINE
    assert SETTINGS["sync"] is False and ONLINE is False
    report["ultralytics"] = "import passed; sync disabled; offline enabled"
    report["videos"] = []
    for path in sorted((root / "videos").iterdir()):
        if path.suffix.lower() not in {".mov", ".mp4"}:
            continue
        with av.open(str(path)) as container:
            stream = container.streams.video[0]
            frames = []
            for frame in container.decode(stream):
                if frame.pts is None:
                    raise RuntimeError(f"Missing presentation timestamp: {path.name}")
                frame.to_ndarray(format="rgb24")
                frames.append({"pts": frame.pts, "time_base": str(frame.time_base),
                               "seconds": float(frame.pts * frame.time_base)})
                if len(frames) == 3:
                    break
            report["videos"].append({"name": path.name, "width": stream.width,
                "height": stream.height, "codec": stream.codec_context.name,
                "stream_time_base": str(stream.time_base), "metadata": stream.metadata,
                "first_frames": frames})
    out = root / "artifacts" / "m0" / "environment.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
