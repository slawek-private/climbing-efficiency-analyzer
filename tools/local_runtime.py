"""Configure the pinned M0 libraries for local, offline use before imports."""
import json
import os
import socket
from pathlib import Path


def configure():
    root = Path(__file__).resolve().parents[1]
    config_dir = root / "artifacts" / "ultralytics"
    config_dir.mkdir(parents=True, exist_ok=True)
    os.environ.update({
        "YOLO_CONFIG_DIR": str(config_dir), "YOLO_OFFLINE": "true",
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1",
        "WANDB_MODE": "disabled", "COMET_MODE": "DISABLED",
    })
    settings = {
        "settings_version": "0.0.6",
        "datasets_dir": str(root / "artifacts" / "datasets"),
        "weights_dir": str(root / "models"),
        "runs_dir": str(root / "artifacts" / "runs"),
        "uuid": "local-only", "sync": False,
        "api_key": "", "openai_api_key": "",
    }
    for key in ("clearml", "comet", "dvc", "hub", "mlflow", "neptune",
                "raytune", "tensorboard", "wandb", "vscode_msg", "openvino_msg"):
        settings[key] = False
    settings_dir = config_dir / "Ultralytics"
    settings_dir.mkdir(parents=True, exist_ok=True)
    (settings_dir / "settings.json").write_text(json.dumps(settings, indent=2), encoding="utf-8")
    def denied(*args, **kwargs):
        raise RuntimeError("Network access is disabled during local inference")
    socket.socket.connect = denied
    socket.socket.connect_ex = denied
    socket.create_connection = denied
