# Developer and contributor guide

## Architecture
FastAPI (`server.py`) exposes a localhost REST API. Vanilla JavaScript + CSS (`web/`) provides the UI. The persistent single-worker scheduler (`clipper/jobs.py`) stores job JSON under `data/` and invokes yt-dlp/FFmpeg subprocesses; `clipper/core.py` handles Whisper transcription, transcript windowing and optional Ollama rankings. `clipper/hardware.py` detects platform and smoke-tests H.264 encoders.

## Commands
`python -m pytest -q` (after `pip install pytest`) and `python -m compileall -q .`. `python -m uvicorn server:app --host 127.0.0.1 --port 8501` runs the API.

## Design decisions
- CPU-only default is the compatibility baseline; GPU encoders are optional enhancements.
- No remote JS frameworks/CDNs, ads or telemetry.
- Restart-safe checkpoint files, no database or cloud dependency.
- yt-dlp is the default for YouTube/Twitch/Facebook. GPL-3.0-or-later Mister Download Manager is **not included**. Optional integration calls the user's separately installed CLI; its support is experimental and has not been validated on all target platforms.
- Python distribution is a **source release**, not signed OS-native installers.

## Limitations / next milestones
Additional GPU speech backends (Metal/MLX, Intel, ROCm), VAAPI, ML face tracking, advanced scene scoring, auto scheduling, platform publishing APIs, official installers, and hardware test matrix remain future work. Never promise uninterrupted 24/7 processing on sleeping laptops or live fragments that expire.

## Licensing
The original local clipper code is distributed under its included MIT LICENSE. Dependencies remain under **their own** licenses. External MDM is GPL-3.0-or-later; consult its source/project license before copying any of its code. Do not relicense external libraries as MIT.
