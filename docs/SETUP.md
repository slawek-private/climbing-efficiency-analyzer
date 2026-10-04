# Native Windows M0 environment

This is the feasibility environment, not a completed pipeline. All processing is local.

## Versions and environment choice

Use uv 0.8.22 and CPython 3.12.11. Direct dependencies are pinned in
`pyproject.toml`; `uv.lock` pins transitive dependencies and package hashes.
uv provides one environment for PyTorch, video decoding and the Qt viewer,
without needing conda or a separately installed CUDA toolkit. This is a
deliberately selected version set, not a claim that these are the newest versions.

PyTorch 2.8.0 and torchvision 0.23.0 use the official CUDA 12.8 wheel index.
The NVIDIA driver's reported CUDA version is its supported runtime ceiling,
not the version of a locally installed toolkit.

## Clean Windows installation

1. Install Windows 11 updates. Download a driver supporting RTX 5070 Ti
   from https://www.nvidia.com/Download/index.aspx and install it; restart
   if requested. Run `nvidia-smi` to verify the card, driver and memory.
   This workstation already has driver 596.49 and 16,303 MiB reported VRAM;
   retain that working driver when the CUDA check below passes.
2. Enable long paths from an **Administrator PowerShell**:

   ```powershell
   Set-ItemProperty -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -Name LongPathsEnabled -Value 1
   ```

   Restart Windows if needed for applications to pick up the policy.
   The automated attempt on this workstation was denied registry access;
   this step remains outstanding. A short checkout path is an alternative
   if installation encounters path-length failures.
3. Obtain Git for Windows from https://git-scm.com/downloads/win.
   This workstation uses portable MinGit under
   `%LOCALAPPDATA%\CodexTools\MinGit`; it was added to the user PATH.
4. Download `uv-x86_64-pc-windows-msvc.zip` and its `.sha256` file from
   https://github.com/astral-sh/uv/releases/tag/0.8.22.
   Compare `Get-FileHash -Algorithm SHA256` with the supplied hash before
   extraction. Extract to `%LOCALAPPDATA%\CodexTools\uv-0.8.22` and add
   that directory to the user PATH. Open a new terminal.
5. Clone the repository, enter it, and run:

   ```powershell
   uv python install 3.12.11
   uv sync --locked --extra analysis
   ```

   No activation is required. Run commands using `uv run --locked` or
   `.\.venv\Scripts\python.exe`. Never replace the locked CUDA build with
   an unspecified `pip install torch`.
6. Verify imports, a real CUDA matrix operation, Qt creation and local video
   decoding using presentation timestamps:

   ```powershell
   .\.venv\Scripts\python.exe tools/check_environment.py
   ```

   Place MP4/MOV footage under `videos` first. The check writes a local
   report under `artifacts/m0`; it does not download model weights.

## Privacy and weights

`videos`, `models`, `artifacts`, `.venv` and environment secret files are
ignored by Git. Do not put footage or image outputs elsewhere in the repository.
`tools/local_runtime.py` configures offline mode and disables optional analytics
and integrations before the check imports model libraries. Future M0 scripts
must call this configuration before those imports and load verified weights
from local paths. Model downloads must have an approved
source and licence and a recorded, verified upstream checksum; hashing a file
after downloading alone does not verify its origin. Subsequent inference must
use offline mode. M0 downloaded and verified the three models listed in
`MODELS.md`; immutable revisions and hashes are in `M0_MODEL_MANIFEST.json`.
No public dataset media was downloaded. The inference socket guard blocks
Python network connections in addition to the library offline settings.

Run the sampled benchmark and regenerate its report with the commands in
`M0_REPORT.md`, using `tools/blue_route_report.py` for the current blue-route
report. See `M0_BLUE_ROUTE_REPORT.md`. This is an M0 harness, not the production
`analyse` command.

## References

- uv: https://docs.astral.sh/uv/
- PyTorch version-specific wheels: https://docs.pytorch.org/get-started/previous-versions/

For the manual viewer alone, use `uv sync --locked`. The optional `analysis` extra installs the pinned native Windows CUDA feasibility stack. See [macOS setup](SETUP_MACOS.md) for Apple Silicon.
