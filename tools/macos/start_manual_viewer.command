#!/bin/zsh
# Double-click after following docs/SETUP_MACOS.md. No network requests at launch.
set -eu
cd "$(dirname "$0")/../.."
if [[ ! -x .venv/bin/python ]]; then
  print "Run uv sync --locked from this repository first. See docs/SETUP_MACOS.md."
  read "?Press Return to close."
  exit 1
fi
exec .venv/bin/python -m viewer "$@"
