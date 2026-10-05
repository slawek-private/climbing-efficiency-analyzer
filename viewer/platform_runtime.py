"""Platform-specific subprocess flags and hardware video decoder choice."""
import sys,subprocess

def hidden_process_options():
    return {'creationflags':subprocess.CREATE_NO_WINDOW} if sys.platform=='win32' else {}

# Hardware decoder reached through FFmpeg: Apple media engine on macOS, NVIDIA CUDA elsewhere.
GPU_BACKEND='videotoolbox' if sys.platform=='darwin' else 'cuda'
GPU_LABEL='Apple GPU · VideoToolbox' if GPU_BACKEND=='videotoolbox' else 'NVIDIA GPU · CUDA'

def gpu_candidate(codec,width,height):
    """Whether auto mode should try the hardware decoder before the CPU."""
    if GPU_BACKEND=='videotoolbox':return codec in ('h264','hevc')
    return max(width,height)>=3840 and codec in ('hevc','h264')
