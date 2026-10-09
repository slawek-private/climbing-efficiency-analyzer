"""Entry point for installed builds (PyInstaller needs an absolute-import script)."""
import argparse
import sys

parser = argparse.ArgumentParser(description="Climb Studio · local manual climbing-video measurements")
parser.add_argument("--video", help="Optional video to open")
parser.add_argument("--self-check", action="store_true", help="Verify the installed bundle and exit")
args, _ = parser.parse_known_args()  # macOS may pass -psn_* arguments to app bundles
if args.self_check:
    from viewer.selfcheck import run
    sys.exit(run())
from viewer.launch import main
sys.exit(main(args.video))
