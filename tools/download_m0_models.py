"""Download approved public weights; verify upstream hashes before inference.

This script never reads videos. Inference is a separate offline process.
"""
import hashlib
import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
REPOS = ["usyd-community/vitpose-base-simple", "usyd-community/vitpose-plus-large",
         "google/owlv2-base-patch16-ensemble"]


def digest(path, git_blob=False):
    h = hashlib.sha1() if git_blob else hashlib.sha256()
    if git_blob:
        h.update(f"blob {path.stat().st_size}\0".encode())
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    manifest_path = ROOT / "models" / "manifest.json"
    pinned_path = ROOT / "docs" / "M0_MODEL_MANIFEST.json"
    manifest_path.parent.mkdir(exist_ok=True)
    source_manifest = pinned_path if pinned_path.exists() else manifest_path
    manifest = json.loads(source_manifest.read_text()) if source_manifest.exists() else {}
    for repo in REPOS:
        response = requests.get(f"https://huggingface.co/api/models/{repo}",
                                params={"blobs": "true"}, timeout=60)
        response.raise_for_status()
        data = response.json()
        if data.get("cardData", {}).get("license") != "apache-2.0":
            raise RuntimeError(f"Unreviewed licence: {repo}")
        revision = manifest.get(repo, {}).get("revision", data["sha"])
        if revision != data["sha"]:
            response = requests.get(f"https://huggingface.co/api/models/{repo}/revision/{revision}",
                                    params={"blobs": "true"}, timeout=60)
            response.raise_for_status()
            data = response.json()
        folder = ROOT / "models" / repo.split("/")[-1]
        folder.mkdir(exist_ok=True)
        files = []
        for entry in data["siblings"]:
            name = entry["rfilename"]
            if not (name.endswith((".json", ".txt", ".safetensors")) or name == "README.md"):
                continue
            path = folder / name
            if not path.resolve().is_relative_to(folder.resolve()):
                raise RuntimeError("Unsafe model asset path")
            path.parent.mkdir(parents=True, exist_ok=True)
            is_lfs = "lfs" in entry
            expected = entry["lfs"]["sha256"] if is_lfs else entry["blobId"]
            url = f"https://huggingface.co/{repo}/resolve/{revision}/{name}"
            if not path.exists() or digest(path, not is_lfs) != expected:
                print(f"Downloading {repo}/{name} ({entry.get('size', 0)} bytes)", flush=True)
                temp = path.with_suffix(path.suffix + ".partial")
                with requests.get(url, stream=True, timeout=(30, 120)) as download:
                    download.raise_for_status()
                    with temp.open("wb") as target:
                        for chunk in download.iter_content(1024 * 1024):
                            target.write(chunk)
                if digest(temp, not is_lfs) != expected:
                    raise RuntimeError(f"Checksum mismatch: {repo}/{name}")
                temp.replace(path)
            files.append({"name": name, "upstream_hash": expected,
                          "hash_type": "sha256" if is_lfs else "git-blob-sha1",
                          "sha256": digest(path), "bytes": path.stat().st_size})
        manifest[repo] = {"revision": revision, "license": "apache-2.0", "files": files}
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"Verified {repo} at {revision}", flush=True)


if __name__ == "__main__":
    main()
