# Climb Studio

Fully local human-assisted climbing measurements for Windows and Apple Silicon macOS.
Automatic inference remains a feasibility experiment, not a validated autonomous pipeline.

## Run the viewer

Install uv 0.8.22 and Python 3.12.11, then:

```sh
uv sync --locked
uv run --no-sync python -m viewer
```

Windows: `tools/windows/start_manual_viewer.cmd`.
Mac: `tools/macos/start_manual_viewer.command` after [macOS setup](docs/SETUP_MACOS.md).
macOS source support and an Apple Silicon CI job are provided; M3 Pro interactive validation remains required.

Mark climb start/end (fall or top), shared points, timestamped comments, and
left/right rest, clip and chalk timers. Compare multiple athletes, view live
charts, use precise frame stepping and a zoomable timeline, save/load labels
by video checksum, and export local HTML/CSV/PDF reports. Choose **Prepare
smooth preview** for direct frame access when 4K scrubbing is slow.
See [controls](docs/MANUAL_VIEWER.md) and [metric definitions](docs/COMPARISON_REQUIREMENTS.md).

## Generate reports

```sh
uv run --no-sync python -m viewer.report_cli --labels videos --output artifacts/reports/comparison.html --focus "Athlete A" --pdf artifacts/reports/comparison.pdf
```

An existing HTML snapshot is also accepted with `--source` instead of `--labels`.
[Report generation](docs/REPORTS.md) describes precision, provenance and limitations.
Combined recovery includes chalking, merging overlaps once. Missing data is
unknown. Rest percentages do not prove why an athlete fell.

## Tests and optional Windows inference

```sh
uv run --no-sync python -m pytest viewer -q
```

Windows CUDA feasibility tools require `uv sync --locked --extra analysis`.
[Windows setup](docs/SETUP.md) and [model sources/licences](docs/MODELS.md).
The manual viewer does not need model weights, CUDA or cloud APIs. CI uses
synthetic fixtures only, on Windows and macOS arm64.

## Private footage and telemetry

Videos, images, labels, athlete telemetry, caches, generated reports and
historical footage-specific M0 reports remain local and ignored by Git.
Only reusable source, schemas, synthetic tests, lockfiles and setup documentation
are committed. No telemetry, footage uploads or external assets are required.
