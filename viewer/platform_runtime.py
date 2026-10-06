"""Platform-specific subprocess flags, hardware video decoder choice and self-update installation."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

def timecode_font():
    from PySide6.QtGui import QFont,QFontDatabase
    return QFont('Consolas') if sys.platform=='win32' else QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)

def hidden_process_options():
    return {'creationflags':subprocess.CREATE_NO_WINDOW} if sys.platform=='win32' else {}

# Hardware decoder reached through FFmpeg: Apple media engine on macOS, NVIDIA CUDA elsewhere.
GPU_BACKEND='videotoolbox' if sys.platform=='darwin' else 'cuda'
GPU_LABEL='Apple GPU · VideoToolbox' if GPU_BACKEND=='videotoolbox' else 'NVIDIA GPU · CUDA'

def gpu_candidate(codec,width,height):
    """Whether auto mode should try the hardware decoder before the CPU."""
    if GPU_BACKEND=='videotoolbox':return codec in ('h264','hevc')
    return max(width,height)>=3840 and codec in ('hevc','h264')

# Waits for the running app to quit, swaps in the new bundle (restoring the old one on failure) and relaunches.
MAC_SWAP='''pid="$1"; app="$2"; incoming="$app.incoming"; previous="$app.previous"
for _ in $(seq 1 "${CLIMB_STUDIO_WAIT_STEPS:-600}"); do case "$(ps -o stat= -p "$pid" 2>/dev/null)" in ""|Z*) break;; esac; sleep 0.2; done
case "$(ps -o stat= -p "$pid" 2>/dev/null)" in ""|Z*) ;; *) exit 1;; esac
[ -d "$app" ] && [ -d "$incoming" ] && [ ! -e "$previous" ] || exit 1
# Do not remove either bundle unless the first rename has succeeded.
mv "$app" "$previous" || exit 1
if ! mv "$incoming" "$app"; then mv "$previous" "$app"; exit 1; fi
if "${CLIMB_STUDIO_OPEN:-open}" "$app"; then
    rm -rf "$previous"
else
    mv "$app" "$incoming" && mv "$previous" "$app"
    "${CLIMB_STUDIO_OPEN:-open}" "$app"
    exit 1
fi
'''

def update_target():
    import platform
    machine=platform.machine().lower()
    arch={'aarch64':'arm64','amd64':'x64','x86_64':'x64'}.get(machine,machine)
    os_version=platform.mac_ver()[0] if sys.platform=='darwin' else platform.version()
    return sys.platform,arch,tuple(int(x) for x in os_version.split('.') if x.isdigit())

def app_bundle():
    return Path(sys.executable).resolve().parents[2]

def self_update_blocker():
    """Why the running app cannot replace itself, or None."""
    if sys.platform=='darwin':
        bundle=app_bundle()
        if bundle.suffix!='.app':return 'Not running from an app bundle.'
        if '/AppTranslocation/' in str(bundle) or str(bundle).startswith('/Volumes/'):return 'Move Climb Studio to the Applications folder, then update.'
        if not (os.access(bundle,os.W_OK) and os.access(bundle.parent,os.W_OK)):return 'No permission to replace the app in its folder.'
    return None

def prepare_update(installer):
    """Stage a verified installer and return the callable that installs it once the app has quit."""
    installer=Path(installer)
    if sys.platform=='darwin':
        bundle=app_bundle();incoming=bundle.with_name(bundle.name+'.incoming');mount=Path(tempfile.mkdtemp(prefix='climb-studio-mount-'))
        subprocess.run(['hdiutil','attach','-nobrowse','-readonly','-mountpoint',str(mount),str(installer)],check=True,capture_output=True)
        try:
            subprocess.run(['rm','-rf',str(incoming)],check=True);subprocess.run(['ditto',str(mount/'Climb Studio.app'),str(incoming)],check=True)
        finally:subprocess.run(['hdiutil','detach','-quiet',str(mount)])
        script=installer.with_name('install.sh');script.write_text(MAC_SWAP,encoding='utf-8')
        return lambda:subprocess.Popen(['/bin/sh',str(script),str(os.getpid()),str(bundle)],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if sys.platform=='win32':
        # Inno Setup upgrades the same AppId in place; /relaunch=1 reopens the app when it finishes.
        flags=subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP
        return lambda:subprocess.Popen([str(installer),'/SILENT','/SUPPRESSMSGBOXES','/NORESTART','/CLOSEAPPLICATIONS','/relaunch=1'],creationflags=flags,close_fds=True)
    raise RuntimeError('Self-update is available on macOS and Windows only')
