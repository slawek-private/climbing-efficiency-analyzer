# PyInstaller spec for Climb Studio. Build with: uv run --no-sync python packaging/build.py
import re
import sys
from PyInstaller.utils.hooks import collect_data_files
from pathlib import Path

ROOT = Path(SPECPATH).parent
VERSION = re.search(r"__version__ = '([^']+)'", (ROOT/'viewer'/'version.py').read_text(encoding='utf-8')).group(1)

a = Analysis([str(ROOT/'packaging'/'climb_studio.py')], pathex=[str(ROOT)],
             datas=[(str(ROOT/'schema'/'labels-v1.schema.json'), 'schema'), (str(ROOT/'viewer'/'assets'/'icon.png'), 'viewer/assets'), (str(ROOT/'viewer'/'assets'/'icons'), 'viewer/assets/icons')]+collect_data_files('reportlab',includes=['fonts/*.ttf']),
             excludes=['pytest', 'tkinter', 'torch', 'IPython'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Climb Studio', console=False, icon=str(ROOT/'packaging'/'icon.ico'))
coll = COLLECT(exe, a.binaries, a.datas, name='Climb Studio')
if sys.platform == 'darwin':
    app = BUNDLE(coll, name='Climb Studio.app', bundle_identifier='com.slawomirbabicz.climbstudio', version=VERSION, icon=str(ROOT/'packaging'/'icon.icns'),
                 info_plist={'CFBundleShortVersionString': VERSION, 'NSHighResolutionCapable': True,
                             'LSMinimumSystemVersion': '14.0', 'NSHumanReadableCopyright': 'MIT License'})
