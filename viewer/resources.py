"""Nonblocking local process and GPU-device resource monitoring."""
import os,subprocess,shutil
import psutil
from PySide6.QtCore import QThread,Signal
from .platform_runtime import hidden_process_options


def gpu_snapshot(pid):
    executable=shutil.which('nvidia-smi')
    if not executable:return {'gpu_percent':None,'device_vram_mb':None,'total_vram_mb':None,'app_vram_mb':None}
    common=dict(capture_output=True,text=True,timeout=3,**hidden_process_options())
    try:
        out=subprocess.run([executable,'--query-gpu=utilization.gpu,memory.used,memory.total','--format=csv,noheader,nounits'],**common)
        fields=out.stdout.strip().splitlines()[0].split(',');result=dict(zip(('gpu_percent','device_vram_mb','total_vram_mb'),[float(v.strip()) for v in fields]));result['app_vram_mb']=None
        apps=subprocess.run([executable,'--query-compute-apps=pid,used_gpu_memory','--format=csv,noheader,nounits'],**common)
        for line in apps.stdout.splitlines():
            values=line.split(',')
            if len(values)==2 and values[0].strip()==str(pid):
                try:result['app_vram_mb']=float(values[1].strip())
                except ValueError:pass
        return result
    except (OSError,ValueError,IndexError,subprocess.TimeoutExpired):return dict(gpu_percent=None,device_vram_mb=None,total_vram_mb=None,app_vram_mb=None)

class ResourceMonitor(QThread):
    sampled=Signal(object)
    def run(self):
        process=psutil.Process(os.getpid());logical=psutil.cpu_count() or 1;process.cpu_percent()
        while not self.isInterruptionRequested():
            cpu=process.cpu_percent();data=dict(cpu_percent=cpu/logical,core_equivalents=cpu/100,logical_cores=logical,ram_mb=process.memory_info().rss/1024**2,**gpu_snapshot(process.pid));self.sampled.emit(data)
            for _ in range(20):
                if self.isInterruptionRequested():return
                self.msleep(100)

def format_usage(data):
    def value(key):return 'n/a' if data.get(key) is None else f'{data[key]:.0f}'
    return f"App CPU {data['cpu_percent']:.1f}% · {data['core_equivalents']:.1f}/{data['logical_cores']} core equivalents · App RAM {data['ram_mb']/1024:.2f} GB · GPU device {value('gpu_percent')}% · App VRAM {value('app_vram_mb')} MB · Device VRAM {value('device_vram_mb')}/{value('total_vram_mb')} MB"
