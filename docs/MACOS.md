# macOS installation (Apple Silicon M1/M2/M3/M4/M5; Intel Mac)

## Compatibility
macOS 12+ recommended. Apple Silicon or Intel. Python **3.11 or 3.12**. Intel Macs use CPU transcription; Apple Silicon also uses CPU transcription in this stable release (optimized native Accelerate may help). The app checks actual **VideoToolbox** encoding availability and falls back to `libx264`.

## One-time setup
1. Install Apple Command Line Tools: `xcode-select --install`.
2. Install Homebrew from https://brew.sh (follow its architecture-specific PATH guidance).
3. In Terminal:

```bash
brew install python@3.11 ffmpeg
python3.11 --version
```

4. Extract the ZIP, navigate into its root directory (drag the folder into Terminal after `cd `).
5. Create the environment, ensuring Python 3.11 is selected. For Homebrew installations where `python3` points to a different version, do:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
cp -n .env.example .env
mkdir -p data
```

Or run `./setup_macos.sh` when `python3 --version` already reports 3.11 or 3.12.

6. Start:

```bash
chmod +x start_macos.sh
./start_macos.sh
```

7. Open `http://127.0.0.1:8501`.

## Apple hardware notes
- FFmpeg must have both `subtitles` and `h264_videotoolbox`. VideoToolbox may be available yet not work on a particular device or permissions setup: app probes functionality before auto-selecting it.
- The stable AI engine is `faster-whisper` with CPU fallback; this is **not an MLX GPU-accelerated release**. Ollama can optionally leverage Metal for text ranking if its own runtime supports it.
- If no GPU encoder works, choose CPU; it is slower but compatible.
- Prevent sleep for long sessions using your Energy settings; pausing jobs before shutdown is safer. On recent macOS systems you can run `caffeinate -i ./start_macos.sh` to discourage idle sleep while running.

## Troubleshooting
- `python` version incompatible: run the explicit `python3.11 -m venv .venv` commands above.
- `Operation not permitted`: move folder out of Downloads/iCloud if needed and allow access to the folder; do not disable Gatekeeper system-wide.
- `no module named ...`: run `./setup_macos.sh` again in that folder.
- CPU is slow: reduce clip resolution using fewer system resources and use `WHISPER_MODEL=tiny` in `.env`.
