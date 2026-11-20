# User manual — Local Stream Clipper

## 1. Launch
Install once using your OS guide; run the `start_...` script whenever you want to use the app. Browse to http://127.0.0.1:8501. This is a localhost dashboard, without registration, trackers or external ad scripts.

## 2. Create a project
- **Video URL**: paste a publicly accessible or authorized YouTube, Twitch or Facebook video/VOD URL. Some websites require a cookie file exported from your own browser session; configure `YTDLP_COOKIES_FILE` in `.env` only if you have permission.
- **Local path**: enter an absolute filesystem path available **on the computer running the app**; no duplicate copy is needed.
- **Quality**: 480/720/1080/best; choosing best can download tens of gigabytes.
- **Clips**: choose number, length, burned-in subtitles and blurred or center framing.
- **Encoder**: Auto is recommended. Hardware acceleration is probed; CPU is the portable fallback.
- **Downloader**: `yt-dlp` recommended for video sites. MDM CLI support is an optional experimental external integration, **not packaged**.

## 3. Watch progress
The dashboard shows the **current stage** (download → audio → transcribe → analysis → render), the stage percentage if known, downloaded bytes, transfer speed/ETA (if provider reports these), drive free space, and actual workspace usage. Peak disk use is a **rough estimate**, not a guaranteed cap. Network speeds and ETAs often show unknown during extraction/merging.

## 4. Pause / resume / outages
Click **Pause** to retain partial files and completed checkpoints. Click **Resume** to schedule retry. If an internet error is classified as transient, the job waits and retries with increasing intervals (up to 15 minutes). Closing the app pauses active jobs; after reopening, click Resume. Finished source video, transcript and individual valid clips are reused. An interrupted **transcription stage may restart**, as Whisper cannot resume in the middle of a model call. Some VODs / segmented downloads do not support byte-accurate resumes; live fragments can disappear.

## 5. Clip review / publishing
Play output clips in the browser, download MP4s. YouTube upload is **optional and initiated manually per clip** using OAuth configured in `.env` and a Google Cloud OAuth client secrets file. Default upload privacy is private. You must have permission to reuse the source content. Instagram and TikTok direct upload are **not implemented**.

## 6. Disk storage
Job files are under `data/<jobid>/` (downloaded source, checkpoints, clips). **Never delete partial files while a job is running**. To reclaim space, stop the app or pause the job before manually removing an old job folder; deleted jobs cannot resume. Reserve plenty of disk space; a source can consume 40 GiB plus transcoded audio (about 115 MiB/hour), outputs and temp files.

## 7. Privacy and security
Video transcription and local analysis run on your PC. Ollama runs locally when installed. First-time installations and model downloads require internet. `yt-dlp` sends requests to the source provider; optional YouTube publishing sends approved clips to YouTube. The web app has **no authentication**, so keep it bound to `127.0.0.1` and do not forward its port to untrusted networks.

## 8. Common errors
- `Video unavailable / 403`: update yt-dlp (`.venv/bin/python -m pip install -U yt-dlp`, Windows equivalent), ensure authorized access, or try a completed VOD rather than live stream.
- Missing subtitles filter: install an FFmpeg build with libass/subtitles support.
- `No working H.264 encoder`: install a full FFmpeg build with libx264.
- CUDA / cuDNN error: set `WHISPER_DEVICE=cpu`.
- Video crop cuts speaker: choose blurred background instead of center crop.
- Slow transcribe: set `WHISPER_MODEL=tiny` or `base`.
- Stuck waiting for internet: choose Resume to try immediately; check provider website availability.
- Stale job after a sudden shutdown: reopen and Resume. It may redo the interrupted stage.
