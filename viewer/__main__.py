import argparse
from .launch import main

parser=argparse.ArgumentParser(description="Local manual climbing-video labels")
parser.add_argument("--video",help="Optional video to open")
args=parser.parse_args()
raise SystemExit(main(args.video))
