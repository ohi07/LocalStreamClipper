from __future__ import annotations
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
load_dotenv(ROOT / ".env")


def config(name, default):
    return os.getenv(name, str(default))


def run(command, cwd=None):
    result = subprocess.run([str(x) for x in command], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError(f"Command failed: {' '.join(map(str, command[:3]))}\n{result.stderr[-3500:]}")
    return result.stdout


def need_binaries():
    missing = [name for name in ("ffmpeg", "ffprobe") if not shutil.which(name)]
    if missing:
        raise RuntimeError("Missing programs in PATH: " + ", ".join(missing) + ". Install FFmpeg and restart terminal.")


def validate_url(url):
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("https", "http") or not parsed.hostname:
        raise ValueError("Use a valid HTTP(S) video URL.")
    host = parsed.hostname.lower().rstrip(".")
    allowed = ("youtube.com", "youtu.be", "twitch.tv", "facebook.com", "fb.watch", "m.facebook.com", "youtube-nocookie.com")
    if not any(host == h or host.endswith("." + h) for h in allowed):
        raise ValueError("Only YouTube, Twitch and Facebook video URLs are accepted.")
    return url.strip()


def duration(path):
    result = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)])
    value = float(result.strip())
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Invalid video duration")
    return value


def download(url, workspace, progress):
    from yt_dlp import YoutubeDL
    url = validate_url(url)
    progress("Downloading source video", stage="download", percent=0)
    output = str(workspace / "source.%(ext)s")
    last_emit = [0.0]
    def hook(d):
        now = time.monotonic()
        if d.get("status") == "downloading" and now - last_emit[0] < 0.8:
            return
        last_emit[0] = now
        downloaded = d.get("downloaded_bytes") or 0
        size = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        p = round(100 * downloaded / size, 1) if size else None
        progress("Downloading video" if d.get("status") != "finished" else "Download complete; merging streams", stage="download",
                 percent=p, downloaded_bytes=downloaded, source_total_bytes=size or None,
                 speed_bps=d.get("speed"), eta_seconds=d.get("eta"))
    opts = {"format": "bv*+ba/b", "outtmpl": output, "noplaylist": True,
            "merge_output_format": "mp4", "quiet": True, "no_warnings": True,
            "retries": 5, "fragment_retries": 5, "ignoreerrors": False,
            "progress_hooks": [hook]}
    cookie_path = config("YTDLP_COOKIES_FILE", "").strip()
    if cookie_path:
        cookie = Path(cookie_path).expanduser()
        if not cookie.is_file():
            raise FileNotFoundError("YTDLP_COOKIES_FILE does not exist")
        opts["cookiefile"] = str(cookie)
    with YoutubeDL(opts) as ydl:
        ydl.download([url])
    candidates = [p for p in workspace.glob("source.*") if p.suffix.lower() in (".mp4", ".mkv", ".webm", ".mov")]
    if not candidates:
        raise RuntimeError("Download did not produce a video. Check video access or update yt-dlp.")
    file = max(candidates, key=lambda p: p.stat().st_size)
    progress("Source downloaded", stage="download", percent=100, downloaded_bytes=file.stat().st_size, source_total_bytes=file.stat().st_size)
    return file


def ffmpeg_with_progress(command, seconds, callback, cwd=None):
    command = [command[0], "-nostats", "-progress", "pipe:1", *command[1:]]
    proc = subprocess.Popen([str(x) for x in command], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace", cwd=cwd)
    # Read progress key=value lines. ffmpeg typically emits every 0.5 s.
    last_sent = -1.0
    for line in proc.stdout:
        if line.startswith("out_time="):
            clock = line.strip().split("=", 1)[1]
            try:
                h, m, sec = clock.split(":")
                value = 3600 * float(h) + 60 * float(m) + float(sec)
                percent = min(99.9, max(0, 100 * value / seconds)) if seconds else None
                if percent is not None and percent - last_sent >= 0.5:
                    callback(round(percent, 1))
                    last_sent = percent
            except (ValueError, ZeroDivisionError):
                pass
    err = proc.stderr.read()[-4000:]
    if proc.wait():
        raise RuntimeError(f"FFmpeg failed: {err}")
    callback(100)


def extract_audio(video, output, seconds=None, on_progress=None):
    cmd = ["ffmpeg", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(output)]
    if on_progress:
        ffmpeg_with_progress(cmd, seconds, on_progress)
    else:
        run(cmd)


def transcribe(audio, progress, on_progress=None):
    from faster_whisper import WhisperModel
    model_name = config("WHISPER_MODEL", "auto")
    if model_name.lower() == "auto":
        try:
            import psutil
            ram = psutil.virtual_memory().total / (1024 ** 3)
        except ImportError:
            ram = 8
        model_name = "tiny" if ram < 6 else "base" if ram < 12 else "small"
    device = config("WHISPER_DEVICE", "auto")
    compute = config("WHISPER_COMPUTE_TYPE", "auto")
    progress(f"Loading Whisper {model_name} ({device})...")
    try:
        model = WhisperModel(model_name, device=device, compute_type=compute)
    except Exception as error:
        if device == "cpu":
            raise
        progress(f"GPU unavailable ({type(error).__name__}); trying CPU...")
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
    progress("Transcribing audio (first run downloads the free model)...")
    def iterate_whisper(active_model):
        # CTranslate2 may load cuBLAS lazily at iteration rather than on model init.
        result, info = active_model.transcribe(str(audio), beam_size=5, vad_filter=True, word_timestamps=True)
        for segment in result:
            yield segment
    segments = []
    audio_length = duration(audio)
    last_update = -1
    def consume(active_model):
        nonlocal last_update
        for seg in iterate_whisper(active_model):
            if on_progress and int(seg.end * 100 / max(1, audio_length)) > last_update:
                last_update = int(seg.end * 100 / max(1, audio_length))
                on_progress(min(99.9, last_update))
            segments.append({"start": float(seg.start), "end": float(seg.end), "text": seg.text.strip(),
                             "words": [{"start": float(w.start), "end": float(w.end), "word": w.word} for w in (seg.words or [])]})
    try:
        consume(model)
    except (RuntimeError, OSError) as error:
        if device == 'cpu' or not any(x in str(error).lower() for x in ('cublas', 'cudnn', 'cuda', 'cudart')):
            raise
        progress(f'CUDA transcription failed ({type(error).__name__}); restarting transcription on CPU')
        segments.clear()
        last_update = -1
        consume(WhisperModel(model_name, device='cpu', compute_type='int8'))
    if on_progress:
        on_progress(100)
    return segments


def make_windows(segments, length, total):
    """Generate speech-aligned candidates from the entire transcript."""
    if not segments:
        # Can still clip music/gameplay, but highlights are evenly spaced rather than AI-selected.
        return [{"start": max(0., i * max(1., total - length) / 6), "end": min(total, i * max(1., total - length) / 6 + length), "text": "", "score": 0.0} for i in range(7)]
    windows = []
    stride = max(8, length / 2)
    t = 0.
    while t < total:
        nearby = [s for s in segments if s["end"] > t and s["start"] < t + length]
        if nearby:
            start = max(0, nearby[0]["start"] - 1.5)
            end = min(total, start + length)
            if end - start >= 8:
                text = " ".join(s["text"] for s in nearby)
                word_count = len(text.split())
                richness = min(word_count / max(length * 2, 1), 1.0)
                reactions = len(re.findall(r"\b(wow|omg|amazing|crazy|insane|wait|what|no way|laugh|funny|unbelievable|win|lost|best|secret|important|why|how|never|finally)\b|[!?]", text.lower()))
                score = richness * 2 + min(reactions, 10) * .35
                windows.append({"start": round(start, 2), "end": round(end, 2), "text": text[:2500], "score": round(score, 3)})
        t += stride
    return windows


def ollama_rank(candidates, progress):
    if config("OLLAMA_ENABLED", "true").lower() not in ("1", "true", "yes") or not candidates:
        return candidates
    progress("Ranking candidate moments with optional Ollama...")
    # Chunk to stay within context and prevent very long streams from overwhelming the LLM.
    url = config("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/") + "/api/generate"
    model = config("OLLAMA_MODEL", "qwen2.5:7b")
    for pos in range(0, len(candidates), 20):
        block = candidates[pos:pos + 20]
        items = [{"id": idx, "transcript": c["text"][:420]} for idx, c in enumerate(block)]
        prompt = ("You are selecting engaging short-form video highlights. Rank each candidate based only on its transcript, "
                  "favoring coherent hooks, payoff, surprising insights, useful explanations or funny reactions. "
                  "Return ONLY a valid JSON array of objects with integer id and numerical score from 0 to 10. "
                  "No markdown or extra explanation. Candidates: " + json.dumps(items, ensure_ascii=False))
        try:
            response = requests.post(url, json={"model": model, "prompt": prompt, "stream": False, "format": "json", "options": {"temperature": 0.1}}, timeout=150)
            response.raise_for_status()
            parsed = json.loads(response.json()["response"])
            if isinstance(parsed, dict):
                parsed = parsed.get("scores", parsed.get("results", []))
            for item in parsed:
                idx = item.get("id")
                score = float(item.get("score", 0))
                if isinstance(idx, int) and 0 <= idx < len(block):
                    block[idx]["score"] += max(0., min(10., score)) * .6
        except Exception as error:
            progress(f"Ollama unavailable for one batch ({type(error).__name__}); using transcript scoring.")
            break
    return candidates


def select_highlights(candidates, count):
    picked = []
    for item in sorted(candidates, key=lambda x: x["score"], reverse=True):
        if all(min(item["end"], p["end"]) - max(item["start"], p["start"]) <= 0.1 * (item["end"] - item["start"]) for p in picked):
            picked.append(item)
        if len(picked) >= count:
            break
    return sorted(picked, key=lambda x: x["start"])


def srt_timestamp(seconds):
    ms = max(0, round(float(seconds) * 1000))
    h, remainder = divmod(ms, 3600000)
    m, remainder = divmod(remainder, 60000)
    s, milliseconds = divmod(remainder, 1000)
    return f"{h:02}:{m:02}:{s:02},{milliseconds:03}"


def write_srt(segments, start, end, path):
    cues = []
    for seg in segments:
        for word in seg.get("words") or []:
            a = max(0., word["start"] - start)
            b = min(end - start, word["end"] - start)
            if b > a:
                cues.append((a, b, word["word"].strip()))
    # Group up to 5 words while maintaining per-phrase timestamps.
    lines = []
    for i in range(0, len(cues), 5):
        group = cues[i:i + 5]
        if group:
            lines.append(f"{len(lines)+1}\n{srt_timestamp(group[0][0])} --> {srt_timestamp(group[-1][1])}\n{' '.join(w[2] for w in group)}\n")
    if not lines:
        for seg in segments:
            a, b = max(0., seg["start"] - start), min(end-start, seg["end"] - start)
            if b > a:
                lines.append(f"{len(lines)+1}\n{srt_timestamp(a)} --> {srt_timestamp(b)}\n{seg['text']}\n")
    path.write_text("\n".join(lines), encoding="utf-8")
    return bool(lines)


def write_karaoke_ass(segments, start, end, path, width=1080, height=1920, crop_mode='blur', caption_font='Arial', caption_size=48, caption_position='auto', caption_y=72):
    """Word-highlight karaoke subtitles using libass; returns False for silent clips."""
    def clock(sec):
        cs=max(0,int(round(sec*100)))
        h, r=divmod(cs,360000);m,r=divmod(r,6000);t,c=divmod(r,100)
        return f'{h}:{m:02}:{t:02}.{c:02}'
    words=[]
    for seg in segments:
        for word in seg.get('words') or []:
            a=max(0.,float(word['start'])-start);b=min(end-start,float(word['end'])-start)
            if b>a:
                txt=str(word.get('word','')).strip().replace('\\','').replace('{','(').replace('}',')').replace('\n',' ')
                if txt: words.append((a,b,txt))
    if not words:return False
    fontsize=scaled_caption_size(width, caption_size)
    margin=caption_margin(width, height, crop_mode, caption_position, caption_y)
    hdr=(f'[Script Info]\nScriptType: v4.00+\nPlayResX: {width}\nPlayResY: {height}\nWrapStyle: 0\n'
         '[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n'
         f'Style: Karaoke,{caption_font},{fontsize},&H00FFFFFF,&H0000D0FF,&H00000000,&H70000000,-1,0,0,0,100,100,0,0,1,3,1,2,70,70,{margin},1\n'
         '[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n')
    lines=[]
    for index in range(0,len(words),5):
        grp=words[index:index+5]
        a=grp[0][0];b=grp[-1][1]
        pieces=[]; last=a
        for wa,wb,txt in grp:
            # Include inter-word gaps in karaoke duration.
            dur=max(1,round((wb-last)*100))
            pieces.append(r'{\kf'+str(dur)+'}'+txt)
            last=wb
        lines.append(f'Dialogue: 0,{clock(a)},{clock(b)},Karaoke,,0,0,0,,{{\fad(120,120)}}'+' '.join(pieces))
    path.write_text(hdr+'\n'.join(lines)+'\n',encoding='utf-8')
    return True


CAPTION_FONTS = ('Arial', 'Verdana', 'Trebuchet MS', 'Impact', 'DejaVu Sans', 'Liberation Sans', 'Noto Sans')
CAPTION_POSITIONS = ('auto', 'below', 'bottom', 'center', 'top', 'custom')


def scaled_caption_size(width, caption_size):
    if not isinstance(caption_size, int) or not (24 <= caption_size <= 80):
        raise ValueError('Caption font size must be between 24 and 80 at 1080p')
    return max(12, round(caption_size * width / 1080))


def caption_margin(width, height, crop_mode='blur', caption_position='auto', caption_y=72):
    if caption_position not in CAPTION_POSITIONS:
        raise ValueError('Invalid caption positioning preset')
    if not isinstance(caption_y, int) or not 10 <= caption_y <= 90:
        raise ValueError('Custom vertical position must be 10–90%')
    effective = ('below' if crop_mode == 'blur' else 'bottom') if caption_position == 'auto' else caption_position
    if effective == 'below':
        # Source 16:9 frame is centered in a portrait output; place captions
        # just underneath it. 16:9 footage is approximately width*9/16 tall.
        content_bottom = (height + min(height, width * 9 / 16)) / 2
        baseline = content_bottom + height * .065
    elif effective == 'bottom':
        baseline = height * .82
    elif effective == 'center':
        baseline = height * .53
    elif effective == 'top':
        baseline = height * .21
    else:
        baseline = height * caption_y / 100
    # libass Alignment=2: margin measures baseline offset from bottom.
    return max(round(height * .07), min(round(height * .88), round(height - baseline)))


def vertical_filtergraph(width, height, crop_mode='blur', has_subs=False, caption_style='clean', caption_font='Arial', caption_size=48, caption_position='auto', caption_y=72):
    """Correctly composite portrait H.264 frames, with explicit pixel formats.

    Explicit yuv420p before and after overlay avoids mismatched pixel format
    negotiation which can produce green artifacts on some FFmpeg builds.
    """
    if width <= 0 or height <= 0 or width % 2 or height % 2:
        raise ValueError('Output dimensions must be positive even integers')
    if crop_mode == 'center':
        graph=(f'[0:v]scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,'
               f'crop={width}:{height},setsar=1,format=yuv420p[vbase]')
    elif crop_mode == 'blur':
        graph=(f'[0:v]format=yuv420p,setsar=1,split=2[bg][fg];'
               f'[bg]scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,'
               f'crop={width}:{height},setsar=1,boxblur=luma_radius=30:luma_power=2:'
               f'chroma_radius=15:chroma_power=2,format=yuv420p[back];'
               f'[fg]scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos,'
               f'pad=ceil(iw/2)*2:ceil(ih/2)*2,setsar=1,format=yuv420p[front];'
               f'[back][front]overlay=x=(W-w)/2:y=(H-h)/2:format=yuv420:shortest=1,'
               f'format=yuv420p[vbase]')
    else:
        raise ValueError('Unknown framing mode')
    if has_subs:
        # ASS-style captions: font scales with original script canvas. The margin
        # places text below the central 16:9 gameplay band in blurred mode.
        # We use 2-line SRT cues; the styling is conservative and readable.
        if caption_style not in ('clean','pop','minimal','karaoke'):
            raise ValueError('Invalid caption style')
        if caption_font not in CAPTION_FONTS:
            raise ValueError('Unsupported caption font')
        font_size = scaled_caption_size(width, caption_size)
        if caption_style == 'minimal': font_size = max(12, round(font_size * .83))
        margin = caption_margin(width, height, crop_mode, caption_position, caption_y)
        outline = 3 if caption_style == 'pop' else 2
        bold = 1 if caption_style == 'pop' else 0
        shadow = 1 if caption_style == 'pop' else 0
        subtitle_file = 'captions.ass' if caption_style == 'karaoke' else 'captions.srt'
        graph+=(f";[vbase]subtitles={subtitle_file}:force_style='FontName={caption_font},FontSize={font_size},"
                f"Bold={bold},Alignment=2,MarginV={margin},MarginL=70,MarginR=70,"
                f"Outline={outline},Shadow={shadow},PrimaryColour=&H00FFFFFF,"
                "OutlineColour=&H00000000'[captioned];[captioned]format=yuv420p[vout]")
    else:
        graph+=';[vbase]null[vout]'
    return graph


def render(video, start, end, target, segments, captions, crop_mode, width, height, preset, on_progress=None):
    # Using a temporary ASCII-only filter_script avoids Windows path escaping bugs.
    with tempfile.TemporaryDirectory(prefix="cliprender_") as tmp:
        tmp = Path(tmp)
        subs = tmp / "captions.srt"
        has_subs = write_srt(segments, start, end, subs) if captions else False
        filtergraph = vertical_filtergraph(width, height, crop_mode, has_subs)
        (tmp / "filters.txt").write_text(filtergraph, encoding="utf-8")
        cmd = ["ffmpeg", "-y", "-ss", str(start), "-i", str(video), "-t", str(end-start),
               "-filter_complex_script", "filters.txt", "-map", "[vout]", "-map", "0:a?",
               "-c:v", "libx264", "-preset", preset, "-crf", "19", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(target)]
        if on_progress:
            # Filter script needs to resolve relative to its temporary directory.
            cmd[cmd.index("filters.txt")] = str(tmp / "filters.txt")
            # Subtitle filter also needs the temp working directory.
            ffmpeg_with_progress(cmd, end-start, on_progress, cwd=tmp)
        else:
            run(cmd, cwd=tmp)


def job_path(job_id):
    if not re.fullmatch(r"[a-f0-9]{12}", str(job_id)):
        raise ValueError("Invalid job id")
    return DATA / str(job_id)


def save_status(directory, data):
    tmp = directory / "status.tmp"
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(directory / "status.json")


def load_status(directory):
    try:
        return json.loads((directory / "status.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


STAGE_PROGRESS = {"queued": 0, "prepare": 2, "download": 12, "audio": 47,
                  "transcribe": 55, "analysis": 72, "render": 80, "done": 100}


def process(job_id, *, url=None, uploaded=None, count=5, seconds=45, captions=True, crop="blur", publish=False):
    workspace = job_path(job_id)
    def progress(message, *, stage=None, percent=None, **fields):
        state = load_status(workspace)
        state["message"] = message
        state["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        if stage is not None and stage != state.get("stage"):
            state["stage"] = stage
            state["stage_percent"] = None
        if percent is not None:
            state["stage_percent"] = percent
        for key, value in fields.items():
            state[key] = value
        state["workspace_bytes"] = sum(p.stat().st_size for p in workspace.rglob("*") if p.is_file())
        save_status(workspace, state)
    try:
        need_binaries()
        progress("Preparing input", stage="prepare", percent=0)
        if url:
            video = download(url, workspace, progress)
        elif uploaded:
            video = Path(uploaded)
            if not video.is_file() or workspace not in video.parents:
                raise ValueError("Invalid local upload")
        else:
            raise ValueError("Supply a video URL or local upload")
        total = duration(video)
        if total < 10:
            raise ValueError("Video must be at least 10 seconds long.")
        seconds = min(float(seconds), total)
        source_bytes = video.stat().st_size
        # 16-kHz mono WAV = 32,000 bytes per second; encoded clips are variable-sized.
        audio_estimate = int(total * 32000)
        peak_estimate = source_bytes + audio_estimate + max(150_000_000, int(source_bytes * .25))
        progress("Preparing speech analysis", stage="audio", percent=0,
                 duration=total, source_bytes=source_bytes, audio_estimate_bytes=audio_estimate,
                 estimated_peak_bytes=peak_estimate)
        # Conservative check before creating the large temporary WAV file. The
        # estimate is only a heuristic; also reserve 2 GiB of drive headroom.
        free = shutil.disk_usage(workspace).free
        if free < audio_estimate + max(150_000_000, int(source_bytes * .25)) + 2 * 1024**3:
            raise RuntimeError("Insufficient disk headroom for audio and clips. Free additional space before processing; your downloaded source was kept.")
        audio = workspace / "mono.wav"
        extract_audio(video, audio, seconds=total, on_progress=lambda p: progress("Extracting audio", stage="audio", percent=p))
        progress("Audio ready", stage="audio", percent=100)
        def transcription_progress(message):
            progress(message, stage="transcribe", percent=None)
        segments = transcribe(audio, transcription_progress,
                             on_progress=lambda p: progress("Transcribing speech", stage="transcribe", percent=p))
        (workspace / "transcript.json").write_text(json.dumps(segments, indent=2, ensure_ascii=False), encoding="utf-8")
        progress("Finding highlight candidates", stage="analysis", percent=20, transcript_segments=len(segments))
        windows = make_windows(segments, seconds, total)
        picks = select_highlights(ollama_rank(windows, lambda msg: progress(msg, stage="analysis", percent=60)), count)
        if not picks:
            raise RuntimeError("No clip candidates found")
        width = int(config("VIDEO_WIDTH", 1080))
        height = int(config("VIDEO_HEIGHT", 1920))
        preset = config("EXPORT_PRESET", "veryfast")
        if preset not in ("ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow"):
            preset = "veryfast"
        clips = []
        for idx, pick in enumerate(picks, 1):
            progress(f"Rendering clip {idx} of {len(picks)}", stage="render", percent=round(100 * (idx - 1) / len(picks), 1), rendered_count=idx-1, total_clips=len(picks))
            filename = f"clip_{idx:02}.mp4"
            render(video, pick["start"], pick["end"], workspace / filename, segments, captions, crop, width, height, preset,
                   on_progress=lambda p, i=idx: progress(f"Rendering clip {i} of {len(picks)}", stage="render",
                       percent=round(100 * ((i-1)+p/100) / len(picks), 1)))
            clips.append({"file": filename, "start": pick["start"], "end": pick["end"], "score": round(pick["score"], 2),
                          "excerpt": pick["text"][:250], "published": None})
            progress(f"Rendered {idx} of {len(picks)} clips", stage="render", percent=round(100 * idx / len(picks), 1), clips=clips, rendered_count=idx)
        audio.unlink(missing_ok=True)
        state = load_status(workspace)
        state.update({"state": "done", "stage": "done", "stage_percent": 100,
                      "message": f"Generated {len(clips)} clips", "clips": clips, "source": url or "local video", "duration": total})
        save_status(workspace, state)
    except Exception as exc:
        state = load_status(workspace)
        state.update({"state": "failed", "stage": "failed", "message": f"{type(exc).__name__}: {exc}"})
        save_status(workspace, state)


def new_job(**kwargs):
    from threading import Thread
    job_id = uuid.uuid4().hex[:12]
    path = job_path(job_id)
    path.mkdir(parents=True)
    save_status(path, {"state": "running", "stage": "queued", "message": "Queued", "clips": [], "created": time.strftime("%Y-%m-%d %H:%M:%S")})
    thread = Thread(target=process, args=(job_id,), kwargs=kwargs, daemon=True)
    thread.start()
    return job_id
