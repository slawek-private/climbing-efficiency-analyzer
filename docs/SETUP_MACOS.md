# MacBook Pro M3 Pro: native manual viewer

The viewer and report generator run without CUDA or model inference. This is
source-level macOS support with an Apple Silicon CI job; interactive behaviour
on an actual M3 Pro must still be checked. No Rosetta or Windows VM is needed.

Use macOS 14 or newer and an arm64 Terminal (`uname -m` should say `arm64`).
PySide6 6.9.2 and PyAV 15.0.0 have native macOS wheels in the shared lockfile.
H.264/HEVC videos decode on the Apple media engine through FFmpeg
VideoToolbox when no decoder preference is saved; other codecs, or files the
hardware decoder rejects, fall back to the CPU. On an M3 Pro, four synthetic 4K
H.264 streams decoded and scaled for display at 46 fps each using about 1.5 CPU
cores, against 35 fps each and 6.5 cores on the CPU. Random seeks still depend on
the file's keyframe spacing, so the same random-access preview cache as Windows
remains the fastest way to scrub. Apple GPU usage / unified-memory telemetry is not
implemented: unavailable GPU fields display n/a, rather than misleading zeros.

1. Install Git if necessary with `xcode-select --install` (follow Apple's prompt).
2. Install **uv 0.8.22** from the official release:
   https://github.com/astral-sh/uv/releases/tag/0.8.22
   Choose the Apple Silicon/aarch64 macOS archive and put `uv` on your PATH.
   Alternatively, the official uv installation documentation explains package
   manager installation: https://docs.astral.sh/uv/getting-started/installation/
3. Clone the repository and install the locked viewer environment:

   ```sh
   git clone https://github.com/slawek-private/climbing-efficiency-analyzer.git
   cd climbing-efficiency-analyzer
   uv python install 3.12.11
   uv sync --locked
   uv run --no-sync python -m viewer
   ```

   Git may ask for your GitHub authentication for a private repository. Never put
   a token in a command, video name or label file.
4. For subsequent launches, double-click
   `tools/macos/start_manual_viewer.command`, or run the command above. To open a
   particular file: `uv run --no-sync python -m viewer --video /path/to/climb.MOV`.
5. Copy your videos and saved labels to the Mac yourself. Reopen a video to match
   labels by SHA256. Machine-specific workspace paths do not transfer: add the
   Mac's video locations anew, then load their labels. Names with spaces work.
6. Choose **Prepare smooth preview** once per video for responsive scrubbing.
   Cache files remain local in ignored `artifacts/preview-cache`. They are viewing
   aids; frame numbers and measurement timestamps still refer to the original.

## Verification on the Mac

```sh
uv run --no-sync python -m pytest viewer -q
```

Then check a portrait video, playback/pause, reverse stepping, preview creation,
save/reload by video checksum, and HTML export. The existing tagging keys are
the same; Control+S/Z/Y are supported on both platforms. Measurements do not
require Apple GPU inference. Do not run the optional Windows `analysis` extra
for this setup.
