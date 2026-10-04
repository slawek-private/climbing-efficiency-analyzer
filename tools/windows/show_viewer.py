"""Windows-only launch helper: show an existing viewer without losing edits."""
import argparse
import ctypes
from ctypes import wintypes

parser=argparse.ArgumentParser()
parser.add_argument("pid",type=int)
args=parser.parse_args()
user32=ctypes.WinDLL("user32",use_last_error=True)
callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
user32.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
user32.ShowWindow.argtypes=[wintypes.HWND,ctypes.c_int]
user32.SetForegroundWindow.argtypes=[wintypes.HWND]
shown=[]

@callback_type
def visit(hwnd,parameter):
    pid=wintypes.DWORD();user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
    if pid.value==args.pid:
        title=ctypes.create_unicode_buffer(512);user32.GetWindowTextW(hwnd,title,512)
        if title.value.startswith("Blue route"):
            user32.ShowWindow(hwnd,9);user32.SetForegroundWindow(hwnd);shown.append(title.value)
    return True

user32.EnumWindows(visit,0)
if not shown:
    raise SystemExit("Viewer window has not appeared")
print("Viewer shown:",shown[0])
