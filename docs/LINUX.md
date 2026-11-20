# Linux installation (AMD64/x86-64, ARM64 experimental)

Recommended: Ubuntu 22.04+/Debian 12+ desktop with Python **3.11 or 3.12**, FFmpeg with `subtitles` and `libx264`, and a graphical browser. Debian/Ubuntu packaged `python3` may be a different version; use an installed 3.11/3.12 interpreter explicitly if necessary. WSL2 works for localhost but is less convenient for GPU and large-file storage.

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip ffmpeg
python3 --version
```

If 3.11/3.12, extract the ZIP, `cd` into its root and run:

```bash
chmod +x setup_linux.sh start_linux.sh
./setup_linux.sh
./start_linux.sh
```

Open `http://127.0.0.1:8501`.

For another Python default version, create the environment with a Python 3.11/3.12 executable installed through your distro's supported mechanism, then install `requirements.txt` manually (the macOS guide shows the equivalent commands).

## Hardware acceleration
- NVIDIA NVENC: FFmpeg build and GPU driver must support it; `encoder auto` probes a short test encode.
- Intel QSV: available only with properly configured drivers/FFmpeg.
- AMD/Intel VAAPI: **not enabled** in this release because generic VAAPI requires a compatible graphics device path and filter-graph upload; CPU fallback is used.
- AMD/Intel GPU accelerated Whisper: **not implemented**. CPU works.
- Headless machine: access localhost via SSH port forwarding; do not expose the unauthenticated dashboard to the public internet.

## Disk/safety
Keep the `data/` directory on a disk with enough free space for source downloads, uncompressed audio and output. The application can pause and retry; it does **not** guarantee resuming expiring live streams or files from every provider.
