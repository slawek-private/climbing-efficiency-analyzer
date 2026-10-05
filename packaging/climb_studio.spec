# PyInstaller spec for Climb Studio. Build with: uv run --no-sync python packaging/build.py
import re
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
VERSION = re.search(r"__version__ = '([^']+)'", (ROOT/'viewer'/'version.py').read_text(encoding='utf-8')).group(1)

a = Analysis([str(ROOT/'packaging'/'climb_studio.py')], pathex=[str(ROOT)],
             datas=[(str(ROOT/'schema'/'labels-v1.schema.json'), 'schema')],
             excludes=['pytest', 'tkinter', 'torch', 'IPython'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Climb Studio', console=False)
coll = COLLECT(exe, a.binaries, a.datas, name='Climb Studio')
if sys.platform == 'darwin':
    app = BUNDLE(coll, name='Climb Studio.app', bundle_identifier='com.slawomirbabicz.climbstudio', version=VERSION,
                 info_plist={'CFBundleShortVersionString': VERSION, 'NSHighResolutionCapable': True,
                             'LSMinimumSystemVersion': '14.0', 'NSHumanReadableCopyright': 'MIT License'})
