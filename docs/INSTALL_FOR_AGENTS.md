# Installation handoff for other coding models

End users can install from GitHub Releases (macOS `.dmg`, Windows `setup.exe`).
This guide covers the runnable source checkout. Installers are built only by
`packaging/build.py` and the release workflow; do not invent other packaging
commands. The manual viewer requires
no model weights, CUDA, WSL, cloud service or API key.

## 1. Inspect before executing

Read `AGENTS.md`. Confirm the operating system and CPU architecture, whether
Git and uv are available, and whether the user already has a checkout.
Reuse an existing checkout rather than cloning another copy unnecessarily.
On macOS, require native arm64 Terminal for Apple Silicon; on Windows use native
PowerShell. Never paste secrets into commands or logs.

The repository is:

```text
https://github.com/slawek-private/climbing-efficiency-analyzer.git
```

If GitHub authentication is needed, let the user sign in through the normal Git
credential flow. Do not ask them to put a token into the repository URL.

## 2. Bootstrap pinned tooling

Install uv **0.8.22** from its official release if missing:
https://github.com/astral-sh/uv/releases/tag/0.8.22
Use the architecture-specific archive; keep the executable on PATH. See
[Windows setup](SETUP.md) or [Mac setup](SETUP_MACOS.md) for platform details.

From the repository root:

```sh
uv python install 3.12.11
uv sync --locked
uv run --no-sync python -c "import av, PySide6, reportlab; print('Viewer dependencies OK')"
```

`uv sync --locked` may download Python wheels at setup time. After setup,
`uv run --no-sync` launches without dependency resolution or network access.
Never use `pip install -U` or remove pins to resolve an install error. Capture the
package/platform error and propose the smallest supported fix.

## 3. Launch and verify

```sh
uv run --no-sync python -m viewer
uv run --no-sync python -m pytest viewer -q
```

Optional video: `uv run --no-sync python -m viewer --video "/path/to/video.MOV"`.
Windows users can double-click `tools/windows/start_manual_viewer.cmd`.
Mac users can double-click `tools/macos/start_manual_viewer.command`.

Check playback/pause, both directions of frame stepping, rotation, marking climb
end as fall/top, save/reload, live charts and HTML/PDF export. Prefer generated
fixtures until the user supplies local footage. For slow 4K video, choose
**Prepare smooth preview**; this caches independent frames while preserving
original frame identities and times. Apple GPU telemetry currently displays
unavailable; do not claim it is zero or that MPS inference was exercised.

For headless synthetic UI checks, set `QT_QPA_PLATFORM=offscreen` for that command
only. Remove it before a normal launch; otherwise the app window will not appear.
An existing `.venv` copied from another OS must be recreated with `uv sync`;
copy videos and labels separately, never the Windows virtual environment to Mac.

## 4. Recreate reports

```sh
uv run --no-sync python -m viewer.report_cli --labels videos --output artifacts/reports/comparison.html --focus "Athlete A" --pdf output/pdf/comparison.pdf
```

Alternatively use `--source exported-report.html` instead of `--labels`.
Focus must identify one athlete/attempt; omit it for an overall report.
Keep outputs private. [Report definitions and precision](REPORTS.md).

## 5. Recreate safe documentation screenshots

```sh
uv run --no-sync python -m tools.capture_screenshots
```

The generator creates a temporary video from coloured rectangles and fictional
labels, using isolated workspace/settings paths. It never reads private footage
or labels. Review the four PNGs under `docs/screenshots` before staging them.
Only those synthetic documentation PNGs are allowed through the image ignore rule.

## Completion evidence

Report the installed version, exact launch/test commands, tests passed, and
hardware actually exercised. Windows tests and Apple Silicon wheel availability
are not evidence of real M3 Pro interactive performance. CI checks synthetic
fixtures on Windows and macOS; no footage or generated private reports belong in CI.
