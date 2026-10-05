"""Build the installer for this platform: macOS .dmg (Apple Silicon) or Windows setup .exe.

uv sync --locked --group build && uv run --no-sync python packaging/build.py
Output lands in build/release/. Windows also needs Inno Setup 6 (iscc) on PATH.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT/'build'
DIST = BUILD/'dist'
RELEASE = BUILD/'release'
VERSION = re.search(r"__version__ = '([^']+)'", (ROOT/'viewer'/'version.py').read_text(encoding='utf-8')).group(1)


def run(*command, **options):
    print('+', ' '.join(map(str, command)), flush=True)
    subprocess.run([str(c) for c in command], check=True, **options)


def self_check(executable):
    run(executable, '--self-check', env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'}, timeout=300)


def main():
    shutil.rmtree(BUILD, ignore_errors=True);RELEASE.mkdir(parents=True)
    run(sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--distpath', DIST, '--workpath', BUILD/'work', ROOT/'packaging'/'climb_studio.spec')
    if sys.platform == 'darwin':
        app = DIST/'Climb Studio.app';self_check(app/'Contents'/'MacOS'/'Climb Studio')
        stage = BUILD/'dmg';stage.mkdir();shutil.copytree(app, stage/app.name, symlinks=True);(stage/'Applications').symlink_to('/Applications')
        target = RELEASE/f'Climb-Studio-{VERSION}-macOS-arm64.dmg'
        run('hdiutil', 'create', '-volname', 'Climb Studio', '-srcfolder', stage, '-format', 'UDZO', '-ov', target)
    elif sys.platform == 'win32':
        folder = DIST/'Climb Studio';self_check(folder/'Climb Studio.exe')
        iscc = shutil.which('iscc') or r'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
        run(iscc, f'/DVersion={VERSION}', f'/DSource={folder}', f'/DOutput={RELEASE}', ROOT/'packaging'/'windows.iss')
        target = RELEASE/f'Climb-Studio-{VERSION}-Windows-x64-setup.exe'
    else:
        sys.exit('Installers are built on macOS or Windows.')
    print('Built', target, f'{target.stat().st_size/2**20:.0f} MB')


if __name__ == '__main__':
    main()
