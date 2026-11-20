# Windows installation (Intel, AMD, NVIDIA, APU)

## Supported baseline
- Windows 10/11 x64 recommended. Windows ARM64 is experimental: some Python libraries lack native wheels.
- Python **3.11**; FFmpeg with `libx264`, `subtitles` filter and `ffprobe`.
- At least 8 GB RAM recommended (4 GB with Whisper tiny can work slowly); 5 GB free for the application/model plus **additional space for your video**. Large 40 GB VODs may require 60+ GB free.

## One-time setup
1. Extract the project ZIP into an ordinary writable folder, e.g. `D:\Clipper` (avoid OneDrive-managed folders for large jobs).
2. Open PowerShell, run:

```powershell
winget install Python.Python.3.11
winget install Gyan.FFmpeg
```

3. **Close and reopen PowerShell** and navigate into the extracted folder:

```powershell
cd "D:\Clipper"
.\setup_windows.bat
```

4. Start the app (every later use):

```powershell
.\start_windows.bat
```

5. Open `http://127.0.0.1:8501` in a browser. **Keep the terminal open.**

## Optional AI highlight ranking
Install Ollama from https://ollama.com/download and run `ollama pull qwen2.5:7b`. The app's default `.env` disables Ollama; set `OLLAMA_ENABLED=true` to enable it. Set `OLLAMA_ENABLED=false` to skip it and use transcript heuristics only. For small PCs, use a smaller Ollama model or disable it.

## NVIDIA RTX/GTX
NVIDIA NVENC is used **only after an actual FFmpeg test succeeds**. For GPU Whisper, install compatible NVIDIA drivers plus CUDA/cuDNN libraries required by your installed faster-whisper/CTranslate2 versions; otherwise CPU fallback applies. NVENC accelerates rendering, not necessarily speech transcription.

## AMD/Intel/APU
The app probes AMF (AMD) and Quick Sync (Intel), as available from your FFmpeg build and drivers. Otherwise the app uses `libx264` CPU encoding. AMD or Intel GPU inference for Whisper is **not included**.

## Common fixes
- `ffmpeg not found`: restart your terminal; run `ffmpeg -version` and `ffmpeg -filters | findstr subtitles`.
- Port busy: exit older v2/v3 instance (Ctrl+C). Or set `PORT=8502` before running startup if the launcher supports it.
- Download stalls: wait for automatic retry; pause and resume from the job panel; do not delete `.part` files.
- Permission errors: move the extracted project to an ordinary writable folder.
- GPU crashes: set Video encoder to **CPU** in the dashboard and `WHISPER_DEVICE=cpu` in `.env`.
- Device not recognized: update graphics drivers/FFmpeg; CPU mode is always the compatibility option.
