# Local Stream Clipper — Cross-Platform Community Source Release

**Free, local-first clip generation for Windows, macOS and Linux.** No dashboard ads, account registration or tracking. Uses FFmpeg, yt-dlp, faster-whisper and optional local Ollama to produce vertical captioned clips from authorized YouTube, Twitch, Facebook VODs and local videos.

> **Status:** tested source release, **not** a guarantee of full functionality on every OS/hardware configuration. FFmpeg and Python wheels vary; hardware acceleration depends on drivers. See compatibility notes below. This is **not** a signed `.exe` / `.dmg` / AppImage.

## Quick start

| Platform | One-time | Daily use | Detailed guide |
|---|---|---|---|
| Windows 10/11 | `setup_windows.bat` | `start_windows.bat` | [Windows](docs/WINDOWS.md) |
| macOS Apple Silicon/Intel | `./setup_macos.sh` | `./start_macos.sh` | [macOS](docs/MACOS.md) |
| Linux x86-64 | `./setup_linux.sh` | `./start_linux.sh` | [Linux](docs/LINUX.md) |

**Required:** Python 3.11 (3.12 supported on Unix as dependencies allow), FFmpeg with ffprobe, internet to initially install dependencies/models. Browse to **http://127.0.0.1:8501** after launch. Windows app lives at `127.0.0.1` only.

## Manuals
- [End-user workflow, pause/resume, storage, YouTube publishing](docs/USER_MANUAL.md)
- [Windows GPU and APU setup](docs/WINDOWS.md)
- [Apple Silicon and Intel Mac setup](docs/MACOS.md)
- [Linux CPU/GPU/VAAPI notes](docs/LINUX.md)
- [Developer, architecture, tests and legal details](docs/DEVELOPER.md)

## Cross-platform support
- Windows: CPU + NVENC/Intel QSV/AMD AMF **when short encoding test succeeds**.
- macOS: CPU + VideoToolbox **when test succeeds**; Whisper CPU fallback (MLX transcription not included).
- Linux: CPU + NVENC/Intel QSV **when test succeeds**; AMD VAAPI not integrated yet.
- CPU-only, low-end APU laptops: lightweight Whisper and software H.264 encoder, slower. Some ARM platforms may require additional native package builds.

## Recovery and storage
Download retries/backoff and partial-file resume (when supported by video provider), manual Pause/Resume, persisted job checkpoints, transparent workspace size and free-disk metrics. Not guaranteed for expiring live streams or site auth failures. Source and clip files can be **very large**. Details in [manual](docs/USER_MANUAL.md).

## License
Application-authored code MIT (see LICENSE). Third-party dependencies keep their respective original licenses. Mister Download Manager is GPL-3.0-or-later and is **not bundled**; a separately installed experimental CLI bridge is available for compatible sources. yt-dlp is the default video downloader.

## Ethical use
Only download or publish videos you own or are authorized to reuse, subject to applicable law and service terms.
