from viewer.resources import format_usage,gpu_snapshot

def test_missing_process_vram_is_explicit():
    text=format_usage(dict(cpu_percent=12.5,core_equivalents=4,logical_cores=32,ram_mb=1024,gpu_percent=20,device_vram_mb=2048,total_vram_mb=16303,app_vram_mb=None))
    assert 'App CPU 12.5%' in text and 'App RAM 1.00 GB' in text and 'App VRAM n/a' in text and 'GPU device 20%' in text
