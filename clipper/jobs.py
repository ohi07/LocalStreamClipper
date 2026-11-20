"""Durable, single-worker, local clip job orchestrator.

Pause is cooperative for Whisper and FFmpeg, and process-group termination for
video download. Persisted checkpoints make restarts idempotent. All files live
in the job directory. No cloud dependency or analytics.
"""
from __future__ import annotations
import json, os, re, shutil, signal, subprocess, sys, threading, time, uuid
from pathlib import Path
from threading import RLock
from . import core, hardware

ROOT, DATA = core.ROOT, core.DATA
_LOCK = RLock()
_RUNNING: dict[str, subprocess.Popen | None] = {}
_WORKER: threading.Thread | None = None
_STOP = threading.Event()
VIDEO_SUFFIXES = {'.mp4','.mkv','.webm','.mov','.ts','.m4v','.avi'}
STAGES = ('queued','download','audio','transcribe','analysis','render','done')


def now():
    return time.strftime('%Y-%m-%d %H:%M:%S')


def path(jid):
    return core.job_path(jid)


def state(jid):
    return core.load_status(path(jid))


def update(jid, **fields):
    with _LOCK:
        d = state(jid)
        d.update(fields)
        d['updated'] = now()
        core.save_status(path(jid), d)
        return d


def create(*, url=None, local_path=None, count=5, seconds=45, captions=True, crop='blur', quality='720', backend='yt-dlp', encoder='auto'):
    if url: core.validate_url(url)
    if local_path:
        src = Path(local_path).expanduser().resolve()
        if not src.is_file() or src.suffix.lower() not in VIDEO_SUFFIXES:
            raise ValueError('Select a valid local video file.')
    if not url and not local_path: raise ValueError('Select a video URL or local file.')
    if not 1 <= count <= 20 or not 15 <= seconds <= 180 or crop not in ('blur','center'):
        raise ValueError('Invalid clipping settings')
    if quality not in ('480','720','1080','best'): raise ValueError('Invalid source quality')
    if backend not in ('yt-dlp','mdm'): raise ValueError('Invalid downloader')
    if encoder not in ('auto', *hardware.CANDIDATES): raise ValueError('Invalid video encoder')
    jid = uuid.uuid4().hex[:12]
    dest = path(jid); dest.mkdir(parents=True)
    core.save_status(dest, {'id':jid,'state':'queued','stage':'queued', 'stage_percent':0,
      'message':'Queued for processing', 'created':now(), 'updated':now(), 'clips':[],
      'source':url or local_path, 'url':url, 'local_path':str(Path(local_path).resolve()) if local_path else None,
      'count':count,'seconds':seconds,'captions':captions,'crop':crop,'quality':quality,'backend':backend,'encoder':encoder,
      'downloaded_bytes':0,'retry_count':0,'rendered_count':0})
    return jid


def control(jid, action):
    with _LOCK:
        s=state(jid)
        if not s: raise ValueError('Unknown job')
        if action=='pause':
            if s['state'] in ('done','failed','paused','waiting_network'): return s
            update(jid,state='paused',message='Paused by user; partial data preserved')
            p=_RUNNING.get(jid)
            if p and p.poll() is None:
                stop_process(p)
        elif action=='resume':
            if s['state']=='done': return s
            if s['state']=='running': return s
            update(jid,state='queued',message='Ready to resume from saved files',next_retry_at=None)
        elif action=='retry':
            if s['state']=='done': return s
            update(jid,state='queued',message='Retry requested',next_retry_at=None)
        else: raise ValueError('Unknown action')
        return state(jid)


def stop_process(p):
    if p.poll() is not None: return
    try:
        if os.name=='nt':
            p.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            os.killpg(p.pid, signal.SIGINT)
        try: p.wait(timeout=3)
        except subprocess.TimeoutExpired: p.terminate()
    except (OSError, ValueError):
        try: p.terminate()
        except OSError: pass


def check(jid):
    s=state(jid)
    if s.get('state')=='paused': raise Paused()
    if s.get('state') not in ('running','queued'): raise Paused()
    return s


class Paused(Exception): pass
class NetworkError(Exception): pass


def command(jid,args,on_line=None,wd=None):
    """Live output, cancellable; no stdout/stderr pipe deadlock."""
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0
    p = subprocess.Popen([str(x) for x in args], cwd=wd, stdout=subprocess.PIPE,
       stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
       bufsize=1, creationflags=flags, start_new_session=os.name!='nt')
    with _LOCK: _RUNNING[jid]=p
    tail=[]
    try:
        for line in p.stdout:
            if state(jid).get('state')=='paused':
                stop_process(p);raise Paused()
            if on_line: on_line(line.rstrip())
            tail.append(line.rstrip());tail=tail[-25:]
        ret=p.wait()
        check(jid)
        if ret: raise RuntimeError('\n'.join(tail[-14:]) or f'Process returned {ret}')
        return '\n'.join(tail[-14:])
    finally:
        if p.poll() is None: stop_process(p)
        with _LOCK: _RUNNING.pop(jid,None)


def calc_usage(folder):
    try: return sum(x.stat().st_size for x in folder.rglob('*') if x.is_file())
    except OSError: return None


def source_file(folder):
    candidates=[p for p in folder.glob('source.*') if p.suffix.lower() in VIDEO_SUFFIXES and p.is_file()]
    return max(candidates,key=lambda p:p.stat().st_size) if candidates else None


def detect_quality(q):
    return 'bv*[height<=%s]+ba/b[height<=%s]/best[height<=%s]'%(q,q,q) if q!='best' else 'bv*+ba/b'


def download(jid,s):
    folder=path(jid)
    existing=source_file(folder)
    if existing and (s.get('source_ready') or s.get('local_path')) and existing.stat().st_size and core.duration(existing)>0:
        update(jid,message='Reusing previously downloaded video',source_bytes=existing.stat().st_size)
        return existing
    if s.get('local_path'):
        p=Path(s['local_path'])
        if not p.is_file(): raise FileNotFoundError('Original local video moved or deleted')
        update(jid,stage='download',stage_percent=100,source_bytes=p.stat().st_size,message='Using local file (no copy)')
        return p
    if s['backend']=='mdm':
        return download_mdm(jid,s)
    update(jid,stage='download',stage_percent=None,message='Connecting to source (resumable download)',downloaded_bytes=0)
    fmt=detect_quality(s['quality'])
    args=[sys.executable,'-m','yt_dlp','--newline','--continue','--no-overwrites',
          '--no-playlist','--retries','10','--fragment-retries','10','--extractor-retries','8',
          '--retry-sleep','http:exp=1:30','--retry-sleep','fragment:exp=1:30',
          '--socket-timeout','25','--merge-output-format','mp4',
          '--format',fmt,'--output',str(folder/'source.%(ext)s'),
          '--progress-template','download:CLIPPROGRESS %(progress.downloaded_bytes)s|%(progress.total_bytes)s|%(progress.total_bytes_estimate)s|%(progress.speed)s|%(progress.eta)s',s['url']]
    cookie=core.config('YTDLP_COOKIES_FILE','').strip()
    if cookie: args[3:3]=['--cookies',cookie]
    last=[0]
    def handle(line):
        if line.startswith('CLIPPROGRESS '):
            if time.monotonic()-last[0]<.7: return
            last[0]=time.monotonic()
            values=(line[13:].split('|')+['NA']*5)[:5]
            def num(v):
                try: return float(v) if v not in ('NA','None','') else None
                except ValueError: return None
            a,b,c,spd,eta=map(num,values)
            total=b or c
            update(jid,downloaded_bytes=int(a or 0),source_total_bytes=int(total) if total else None,
                   speed_bps=spd,eta_seconds=eta,stage_percent=round(a/total*100,1) if total else None,
                   message='Downloading video (partial files kept for resume)')
        elif line.strip().startswith('ERROR:'):
            update(jid,message=line.strip()[:400])
    try: command(jid,args,handle)
    except RuntimeError as e:
        msg=str(e)
        if any(w in msg.lower() for w in ['timed out','connection','network','temporary failure','unreachable','name resolution','reset by peer','http error 5','http error 429','unable to download','failed to resolve','no route to host','getaddrinfo','network is unreachable','connection refused','connection aborted','http error 502','http error 503','http error 504']):
            raise NetworkError(msg)
        raise
    result=source_file(folder)
    if not result: raise RuntimeError('No playable file produced. Check access and video format.')
    update(jid,stage_percent=100,source_bytes=result.stat().st_size,source_ready=True,message='Download complete')
    return result


def download_mdm(jid,s):
    """Optional GPL-licensed external MDM CLI adapter (not bundled)."""
    cli=shutil.which('misterdownloadmanager-cli')
    if not cli:
        raise RuntimeError('Mister Download Manager CLI not installed. Install MDM separately or select yt-dlp.')
    folder=path(jid)
    update(jid,stage='download',stage_percent=None,message='Mister Download Manager CLI (external) downloading video')
    # MDM CLI maintains .mdm.json partial state; reissue resume for that state.
    partial=next(iter(folder.glob('*.mdm.json')),None)
    args=[cli,'--json','resume',str(partial)] if partial else [cli,'--json','video-get',s['url'],'-o',str(folder)]
    def progress(line):
        try:
            d=json.loads(line)
            if d.get('event')=='progress':
                total=d.get('size');downloaded=d.get('downloaded')
                update(jid,downloaded_bytes=downloaded,source_total_bytes=total,speed_bps=d.get('speed'),
                       stage_percent=round(downloaded/total*100,1) if total and downloaded is not None else None)
        except (ValueError,TypeError): pass
    command(jid,args,progress)
    candidates=[p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_SUFFIXES]
    if not candidates: raise RuntimeError('MDM did not provide a video file. Use yt-dlp mode for this source.')
    video=max(candidates,key=lambda p:p.stat().st_size)
    update(jid,source_bytes=video.stat().st_size,source_ready=True,stage_percent=100)
    return video


def ffmpeg(jid,args,total,stage,base=0,span=100):
    def on_line(line):
        if line.startswith('out_time='):
            try:
                h,m,sec=line[9:].split(':'); elapsed=int(h)*3600+int(m)*60+float(sec)
                val=min(99.9,round(base+span*elapsed/max(total,.1),1))
                if val>0: update(jid,stage=stage,stage_percent=val)
            except ValueError: pass
    command(jid,['ffmpeg','-nostdin','-y','-nostats','-progress','pipe:1',*args],on_line)


def ensure_disk(jid,needed):
    free=shutil.disk_usage(path(jid)).free
    update(jid,free_bytes=free)
    if free < needed + 512*1024*1024:
        raise RuntimeError('Not enough free space. Need about %.1f GiB additional, including 512 MiB reserve. Existing files are preserved.'%((needed+512*1024*1024-free)/1024**3))


def run_job(jid):
    s=state(jid)
    update(jid,state='running',message='Checking available assets and resuming checkpoints')
    folder=path(jid)
    try:
        core.need_binaries()
        video=download(jid,s)
        check(jid)
        total=core.duration(video)
        if total<10: raise ValueError('Source must be at least 10 seconds long')
        audio=folder/'mono.wav'; transcript=folder/'transcript.json'; picks_file=folder/'highlights.json'
        audio_estimate=int(total*32000)
        source_size=video.stat().st_size
        update(jid,duration=total,source_bytes=source_size,audio_estimate_bytes=audio_estimate,
           estimated_peak_bytes=int(source_size+audio_estimate+max(150_000_000,source_size*.25)),
           stage='audio',stage_percent=0,message='Preparing audio (checkpointed)')
        if not transcript.is_file():
            if not audio.is_file() or audio.stat().st_size < max(10000,audio_estimate*.75):
                ensure_disk(jid,audio_estimate)
                partial=folder/'mono.partial.wav'
                partial.unlink(missing_ok=True)
                ffmpeg(jid,['-i',str(video),'-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',str(partial)],total,'audio')
                partial.replace(audio)
            check(jid)
            update(jid,stage='transcribe',stage_percent=0,message='Transcribing speech; may take a while')
            # Whisper loop checks pause between segments. Partial transcript is not
            # considered complete until finalized atomically.
            segments=core.transcribe(audio,lambda msg:update(jid,message=msg),
                 on_progress=lambda pct:(check(jid),update(jid,stage_percent=pct,stage='transcribe')))
            check(jid)
            tmp=folder/'transcript.partial.json'
            tmp.write_text(json.dumps(segments,ensure_ascii=False),encoding='utf-8');tmp.replace(transcript)
            audio.unlink(missing_ok=True)
        else:
            segments=json.loads(transcript.read_text(encoding='utf8'))
            update(jid,message='Reusing saved transcript',stage='transcribe',stage_percent=100)
        check(jid)
        if not picks_file.is_file():
            update(jid,stage='analysis',stage_percent=10,message='Finding highlights')
            candidates=core.make_windows(segments,min(float(s['seconds']),total),total)
            ranked=core.ollama_rank(candidates,lambda msg:update(jid,message=msg))
            check(jid)
            picks=core.select_highlights(ranked,s['count'])
            if not picks:raise RuntimeError('No highlights found')
            tmp=folder/'highlights.partial.json';tmp.write_text(json.dumps(picks,ensure_ascii=False),encoding='utf8');tmp.replace(picks_file)
        else:
            picks=json.loads(picks_file.read_text(encoding='utf8'))
        update(jid,stage='render',stage_percent=0,total_clips=len(picks),message='Rendering 9:16 clips')
        width,height,preset=get_profile()
        chosen_encoder=hardware.encoder_choice(s.get('encoder','auto'))
        update(jid,encoder_used=chosen_encoder,profile=f'{width}x{height}',message=f'Using {chosen_encoder} encoder')
        clips=[]
        for i,pick in enumerate(picks,1):
            check(jid)
            out=folder/f'clip_{i:02d}.mp4'
            # A crashed render is never mistaken for a complete output.
            if not out.is_file() or not valid_video(out):
                ensure_disk(jid,max(100_000_000,int(source_size*.05)))
                out.unlink(missing_ok=True)
                # core.render's FFmpeg progress is not pausable; custom rendering
                # calls core.filter pipeline via a cancellable Popen below.
                render_cancellable(jid,video,pick,segments,out,s,i,len(picks),width,height,preset,chosen_encoder)
            clips.append({'file':out.name,'start':pick['start'],'end':pick['end'],
                          'score':round(pick['score'],2),'excerpt':pick['text'][:250], 'published':None})
            update(jid,clips=clips,rendered_count=len(clips),stage_percent=round(i*100/len(picks),1))
        update(jid,state='done',stage='done',stage_percent=100,message=f'Generated {len(clips)} clips',clips=clips)
    except Paused:
        if state(jid).get('state')!='paused':update(jid,state='paused',message='Paused; click Resume')
    except NetworkError as e:
        attempts=int(state(jid).get('retry_count') or 0)+1
        backoff=min(900, 15*(2**min(attempts-1,6)))
        update(jid,state='waiting_network',stage='download',retry_count=attempts,
               next_retry_at=time.time()+backoff,message=f'Network unavailable; retrying in {backoff}s. Partial downloads saved. {str(e)[-170:]}')
    except Exception as e:
        # Always preserve completed artifacts; never delete input or transcript.
        update(jid,state='failed',message=f'{type(e).__name__}: {str(e)[-700:]}')


def valid_video(p):
    try: return p.stat().st_size>10000 and core.duration(p)>1
    except Exception:return False


def get_profile():
    """Conservative autoscale: choose usable encode settings without GPU requirements."""
    try:
        import psutil
        ram=psutil.virtual_memory().total/1024**3; cores=psutil.cpu_count(logical=True) or 2
    except ImportError:
        ram=8;cores=os.cpu_count() or 2
    if ram<6 or cores<=2: return 480,854,'ultrafast'
    if ram<12 or cores<=4: return 720,1280,'superfast'
    return 1080,1920,'veryfast'


def render_cancellable(jid,video,pick,segments,out,s,index,n,width,height,preset,encoder):
    # Reuse proven FFmpeg filtergraph and subtitle writer, while monitoring child
    # process for pause and preserving an atomic final export.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='lsc_v3_') as tmpdir:
        tmp=Path(tmpdir)
        subs=tmp/'captions.srt'
        has_sub=core.write_srt(segments,pick['start'],pick['end'],subs) if s['captions'] else False
        if s['crop']=='center':
            graph=(f'[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1[vbase]')
        else:
            graph=(f'[0:v]split=2[bg][fg];[bg]scale={width}:{height}:force_original_aspect_ratio=increase,'
                   f'crop={width}:{height},boxblur=30:2[b];[fg]scale={width}:{height}:force_original_aspect_ratio=decrease[front];'
                   f'[b][front]overlay=(W-w)/2:(H-h)/2,setsar=1[vbase]')
        if has_sub:
            graph+=(";[vbase]subtitles=captions.srt:force_style='FontName=Arial,FontSize=14,Alignment=2,MarginV=110,Outline=2,Shadow=1'[vout]")
        else: graph+=';[vbase]null[vout]'
        (tmp/'filters.txt').write_text(graph,encoding='utf8')
        partial=out.with_suffix('.partial.mp4')
        partial.unlink(missing_ok=True)
        seconds=pick['end']-pick['start']
        args=['-ss',str(pick['start']),'-i',str(video),'-t',str(seconds),'-filter_complex_script','filters.txt',
              '-map','[vout]','-map','0:a?',*hardware.encode_args(encoder,preset),'-pix_fmt','yuv420p',
              '-c:a','aac','-b:a','128k','-movflags','+faststart',str(partial)]
        render_command(jid,args,tmp,seconds,index,n)
        partial.replace(out)


def render_command(jid,args,tmp,seconds,index,n):
    def on_line(line):
        if line.startswith('out_time='):
            try:
                h,m,sec=line[9:].split(':');value=3600*float(h)+60*float(m)+float(sec)
                update(jid,stage='render',stage_percent=round(100*((index-1)+min(value/seconds,1))/n,1),
                       message=f'Rendering clip {index} of {n}')
            except (ValueError,ZeroDivisionError): pass
    command(jid,['ffmpeg','-nostdin','-y','-nostats','-progress','pipe:1',*args],on_line,wd=tmp)


def runner():
    while not _STOP.is_set():
        try:
            alljobs=[]
            for folder in DATA.iterdir():
                if re.fullmatch('[a-f0-9]{12}',folder.name):
                    s=state(folder.name)
                    if s:alljobs.append(s)
            for s in sorted(alljobs,key=lambda d:d.get('created','')):
                if _STOP.is_set():break
                if s.get('state')=='waiting_network' and time.time()>=float(s.get('next_retry_at') or 0):
                    update(s['id'],state='queued',message='Retrying after connection loss')
                    s=state(s['id'])
                if s.get('state')=='queued':
                    run_job(s['id']);break
        except Exception as e:
            print('Worker scheduler:',type(e).__name__,e,flush=True)
        _STOP.wait(1.5)


def startup():
    global _WORKER
    for folder in DATA.iterdir():
        if re.fullmatch('[a-f0-9]{12}',folder.name):
            s=state(folder.name)
            if s.get('state')=='running':
                update(folder.name,state='paused',message='Previous app session stopped; Resume to continue from checkpoints')
    if _WORKER is None or not _WORKER.is_alive():
        _STOP.clear();_WORKER=threading.Thread(target=runner,daemon=True,name='clip-worker');_WORKER.start()


def shutdown():
    _STOP.set()
    for jid,p in list(_RUNNING.items()):
        update(jid,state='paused',message='App closed; resume later')
        if p:stop_process(p)
