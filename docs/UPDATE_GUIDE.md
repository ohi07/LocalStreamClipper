# Updating from an earlier version

1. Stop the old server with Ctrl+C and preserve the entire old `LocalStreamClipper/data` folder. Do not delete it.
2. Extract this ZIP to a **different folder**. The package is source code, not an in-place patch.
3. Run the OS-specific setup script once; then run the launch script. Open http://127.0.0.1:8501.
4. Existing projects are **not automatically imported**. For an existing completed source video, create a new project using **Local video path** pointing to the old job's `source.mp4` (or `source.mkv`), as long as that original file is complete. Do not use an incomplete `.part` file.
5. Leave **Burn subtitles** unchecked to export without newly generated captions. AI transcription still runs to find highlights.
6. For a long completed online VOD, use **Download time window**. Example `12:10:00`–`12:35:00`. Source time offsets are shown for completed clips.

## Preview diagnostic

The Clip Library includes an embedded MP4 player and an **Open clip in new tab** link. It serves videos with standard HTTP byte-range support. If the preview still won't play, download the MP4 and test it in VLC; unsupported video profiles, bad media, and old browser caches are still possible. Reopen the browser tab or hard refresh if the UI is cached. The exporter writes H.264/AAC MP4 with `+faststart` for browser streaming.

## What window downloading cannot promise

- Section downloads depend on provider support, and may start at nearby keyframes.
- If a section download is interrupted, it may have to restart *the selected section*; `yt-dlp` cannot guarantee byte-accurate resume here.
- Expired stream fragments, private VODs, and ongoing live streams can fail.
- For multiple noncontiguous windows, make separate jobs. Each job accepts one window up to 12 hours, and the recommended size is 10–60 minutes.

## Publishing titles

A clip gets an editable suggestion built from the remote source title and its highlight number. The tool does not automatically invent the scene's story or promise engagement; review it before you publish.

## Caption styles

- Off (default): no generated subtitle layer.
- Clean: standard white subtitles.
- Pop: bold outlined subtitles.
- Minimal: smaller white subtitles.
- Karaoke: animated word highlighting; requires Whisper word timestamps and FFmpeg libass. No animation if word timings are absent.

Game subtitles and watermarks baked into the original pixels are unaffected by these toggles.
