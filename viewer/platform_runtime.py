"""Platform-specific subprocess flags; keeps Windows helpers invisible."""
import sys,subprocess

def hidden_process_options():
    return {'creationflags':subprocess.CREATE_NO_WINDOW} if sys.platform=='win32' else {}
