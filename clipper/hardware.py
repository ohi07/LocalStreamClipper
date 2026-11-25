"""Conservative cross-platform video encoder selection with executable smoke tests.
Only auto-enables an accelerator after a real FFmpeg encode succeeds on this machine.
"""
from __future__ import annotations
import functools, os, platform, shutil, subprocess

CANDIDATES = {
    "nvenc": "h264_nvenc", "amf": "h264_amf", "qsv": "h264_qsv",
    "videotoolbox": "h264_videotoolbox", "vaapi": "h264_vaapi", "cpu": "libx264"
}

def host_info():
    try:
        import psutil
        ram = round(psutil.virtual_memory().total / (1024 ** 3), 1)
        cores = psutil.cpu_count(logical=True) or 2
    except ImportError:
        ram, cores = None, os.cpu_count() or 2
    return {"os": platform.system(), "architecture": platform.machine(),
            "processor": platform.processor(), "ram_gib": ram, "threads": cores,
            "apple_silicon": platform.system() == "Darwin" and platform.machine() == "arm64"}

@functools.lru_cache(maxsize=1)
def available_encoders():
    if not shutil.which('ffmpeg'): return {"cpu": False}
    try:
        p = subprocess.run(['ffmpeg', '-hide_banner', '-encoders'], capture_output=True,
                           text=True, timeout=10, errors='replace')
        names = {line.split()[1] for line in p.stdout.splitlines() if len(line.split()) >= 2 and line.strip().startswith('V')}
        return {k: v in names for k, v in CANDIDATES.items()}
    except (OSError, subprocess.TimeoutExpired): return {"cpu": False}

@functools.lru_cache(maxsize=None)
def encoder_works(name):
    if name not in CANDIDATES or not available_encoders().get(name): return False
    if name == 'vaapi': return False  # Requires device upload and a configured /dev/dri device; conservative CPU fallback.
    cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
           'color=c=black:s=128x128:r=8', '-frames:v', '2', '-an', '-c:v', CANDIDATES[name]]
    if name == 'cpu': cmd.extend(['-preset','ultrafast'])
    cmd.extend(['-f','null','-'])
    try:
        return subprocess.run(cmd, capture_output=True, timeout=15).returncode == 0
    except (OSError, subprocess.TimeoutExpired): return False

def encoder_choice(requested='auto'):
    if requested not in ('auto', *CANDIDATES): raise ValueError('Invalid encoder')
    system=platform.system()
    priorities = (['videotoolbox'] if system=='Darwin' else
                  ['nvenc','qsv','amf'] if system=='Windows' else
                  ['nvenc','qsv'])
    if requested != 'auto':
        if not encoder_works(requested):
            raise RuntimeError(f"Requested {requested} encoder is not functional; choose Auto or CPU.")
        return requested
    for name in priorities:
        if encoder_works(name): return name
    if encoder_works('cpu'): return 'cpu'
    raise RuntimeError('No working H.264 encoder found. Check FFmpeg installation.')

def encode_args(name, preset):
    if name == 'cpu': return ['-c:v','libx264','-preset',preset,'-crf','19']
    if name == 'nvenc': return ['-c:v','h264_nvenc','-preset','p4','-cq','19','-b:v','0']
    if name == 'amf': return ['-c:v','h264_amf','-quality','balanced','-qp_i','19','-qp_p','19']
    if name == 'qsv': return ['-c:v','h264_qsv','-global_quality','19']
    if name == 'videotoolbox': return ['-c:v','h264_videotoolbox','-b:v','9000k']
    raise ValueError(f'Unsupported encoder: {name}')

def detect():
    info=host_info()
    enc=available_encoders()
    info['encoders'] = {k: {'listed': bool(enc.get(k)), 'working': encoder_works(k)} for k in CANDIDATES}
    try: info['selected_encoder']=encoder_choice('auto')
    except RuntimeError: info['selected_encoder']='unavailable'
    info['transcription'] = 'faster-whisper with CUDA/CPU fallback; Apple MLX optional'
    return info
