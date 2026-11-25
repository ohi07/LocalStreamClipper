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


## Quality and portrait clips (Final release)

The default input quality is **1080p preferred**: choose the highest source stream at or below 1080p when available; if only a higher-resolution source can be obtained it falls back to the highest available. A lower-resolution source cannot be genuinely upgraded to native 1080p. The **Best available** option may download 1440p/4K/8K and use substantially more disk space. Input quality is different from output resolution; the output remains a 9:16 portrait video at 1080×1920 on sufficiently capable machines. Low-RAM machines can automatically use lower-resolution output for stability.

The blur renderer explicitly normalizes both video branches to yuv420p, composites them with overlay, and writes portrait H.264; use **Center crop** if the blurred background is undesirable. Video encoding is hardware-tested and CPU fallback is available. Captions are burned into the final video.

If CUDA transcription fails because cuBLAS/cuDNN is unavailable, the transcription engine attempts to restart the stage on CPU. This is slower but should preserve downloads, audio files, and checkpoints.

Live and expired sources may not support resumption; only videos you are authorized to use should be processed. YouTube publishing requires separate OAuth authorization.


## 2026 update: time-window downloads, previews and caption styles

- **No subtitles by default:** deselect *Burn subtitles*. Transcription still runs for selecting highlights; it simply does not burn text into the video.
- **Title suggestions:** the downloader reads the title and uploader from provider metadata when available. Generated clip titles are suggestions; edit them before publishing. These suggestions do not claim unverified events.
- **Time-window mode:** enter start and end times in HH:MM:SS (maximum 12 hours per job). Example: `08:00:00` to `08:30:00` downloads the selected 30-minute segment from a 24-hour completed VOD, when supported by that provider. Video clip timestamps on the results page show their positions in the original source.
- yt-dlp uses FFmpeg for `--download-sections`; sections may start on nearby keyframes, and interruptions may require restarting the *section*, unlike ordinary full-video resumable downloads. Expired livestream fragments may not be accessible. This mode is not supported by the optional MDM adapter.
- **Preview:** uses browser-native H.264 MP4 previews via HTTP Range-capable FileResponse, with an error message and manual Download fallback when the browser cannot decode a clip. This is not a guarantee that all browser/codec versions will play.
- **Captions:** clean, bold Pop, minimal; captions are optional. These are static style effects, not word-by-word animation. Blur-mode captions are positioned lower, outside the main horizontal gameplay strip where space permits.
- **No re-download of old jobs:** installed upgrades do not automatically migrate a previous project's `data` directory. Preserve it separately.

**Karaoke effect:** an animated ASS word-highlight style is available. Requires Whisper word timestamps and FFmpeg with libass support; absent word timings result in no generated karaoke captions.

### Caption controls

Optional burn-in subtitles now have font, size, position presets (auto/below gameplay/bottom/center/top/custom), custom vertical position and four effects. Choose font installed on your OS. Read `docs/USER_MANUAL.md`.
