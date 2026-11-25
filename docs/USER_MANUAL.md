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


## Quality and portrait clips (Final release)

The default input quality is **1080p preferred**: choose the highest source stream at or below 1080p when available; if only a higher-resolution source can be obtained it falls back to the highest available. A lower-resolution source cannot be genuinely upgraded to native 1080p. The **Best available** option may download 1440p/4K/8K and use substantially more disk space. Input quality is different from output resolution; the output remains a 9:16 portrait video at 1080×1920 on sufficiently capable machines. Low-RAM machines can automatically use lower-resolution output for stability.

The blur renderer explicitly normalizes both video branches to yuv420p, composites them with overlay, and writes portrait H.264; use **Center crop** if the blurred background is undesirable. Video encoding is hardware-tested and CPU fallback is available. Captions are burned into the final video.

If CUDA transcription fails because cuBLAS/cuDNN is unavailable, the transcription engine attempts to restart the stage on CPU. This is slower but should preserve downloads, audio files, and checkpoints.

Live and expired sources may not support resumption; only videos you are authorized to use should be processed. YouTube publishing requires separate OAuth authorization.


### Processing a 24-hour VOD without the full download
Enter a completed stream URL, set **Start** `13:20:00` and **End** `13:50:00`, and select **yt-dlp**. The app requests only that window. It still transcribes the selected window to score highlights. Some providers lack seekable streams; download may fail, require additional data, or refuse section retrieval. For pause/resume reliability, full VOD downloads with partial files are often more robust; a partial-section download may restart the section after a disconnect.

### Subtitles and titles
Uncheck **Burn subtitles** for no overlaid AI captions. Select Pop for bold outlined captions or Minimal for smaller text. Game subtitles already embedded in the original footage cannot be removed this way. Source metadata is retrieved to produce an editable title; review before uploading.

### Preview troubleshooting
Modern browsers support HTTP Range requests for MP4, but preview can fail with unsupported codecs or broken media. Download the clip and test it with VLC. Video outputs target H.264 / AAC / yuv420p.

**Karaoke** animates word highlighting using Whisper word-level timestamps; if transcription does not supply word timings, captions can be absent in this style.


## Caption typography and placement

Caption overlays are **off by default**. When enabled, set Caption Effect, Caption Font, Caption Position and Font Size before creating a job. Font choices: Arial, Verdana, Trebuchet MS, Impact, DejaVu Sans, Liberation Sans or Noto Sans. Fonts must be installed locally; libass may substitute when missing. No font files are bundled.

- **Auto** puts subtitles below the central widescreen gameplay with Blurred Background, and at a bottom safe area with Center Crop.
- **Below gameplay** is best for GTA, gameplay HUDs and landscape footage with blurred fill.
- **Bottom safe zone** keeps the text above the lowest UI region, but can overlap widescreen gameplay.
- **Top/Center** are optional alternatives.
- **Custom** enables a vertical placement slider, measured from the top of the full portrait frame.
- **Font size** defaults to 48px (1080p equivalent), automatically scaled for smaller exports.

Caption settings are saved per job; re-export or start a new job to apply changes to an existing MP4. Captions baked into the source video cannot be removed using this setting. For an accurate local preview, render a short test clip first.
