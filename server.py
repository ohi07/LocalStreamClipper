"""Local-only dashboard server. No advertisements, remote UI dependencies, or analytics."""
from __future__ import annotations
import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path
from threading import Thread
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from clipper.core import DATA, ROOT, job_path, load_status, new_job, process, save_status, validate_url
from clipper.youtube import upload_video
from clipper import jobs as manager
from clipper import hardware
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    manager.startup()
    yield
    manager.shutdown()

app = FastAPI(title="Local Stream Clipper", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
WEB = ROOT / "web"
VALID_EXT = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v", ".ts"}

class URLJob(BaseModel):
    url: str
    count: int = Field(default=5, ge=1, le=20)
    seconds: int = Field(default=45, ge=15, le=180)
    captions: bool = True
    crop: str = "blur"
    quality: str = "720"
    backend: str = "yt-dlp"
    encoder: str = "auto"

class UploadRequest(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=5000)
    privacy: str = "private"

@app.get("/", response_class=HTMLResponse)
def home():
    return (WEB / "index.html").read_text(encoding="utf-8")

@app.get("/static/{filename}")
def static(filename: str):
    if filename not in {"app.js", "style.css"}:
        raise HTTPException(404)
    return FileResponse(WEB / filename)

@app.get("/api/system")
def system():
    drive = shutil.disk_usage(DATA)
    width,height,preset=manager.get_profile()
    return {"free_bytes": drive.free, "total_bytes": drive.total, "used_bytes": drive.used,
            "data_dir": str(DATA), "profile": f"{width}×{height} · {preset}",
            "mdm_available": bool(shutil.which("misterdownloadmanager-cli")), "ffmpeg_available": bool(shutil.which("ffmpeg")),
            "hardware": hardware.detect(), "ollama_enabled": os.getenv("OLLAMA_ENABLED", "true").lower() not in {"false", "0", "no"}}

@app.get("/api/jobs")
def jobs():
    arr = []
    for folder in DATA.iterdir():
        if folder.is_dir() and re.fullmatch(r"[a-f0-9]{12}", folder.name):
            state = load_status(folder)
            if state:
                arr.append({"id": folder.name, **state})
    return sorted(arr, key=lambda x: x.get("created", ""), reverse=True)[:100]

@app.get("/api/jobs/{job_id}")
def job(job_id: str):
    try:
        folder = job_path(job_id)
    except ValueError:
        raise HTTPException(400, "Invalid job ID")
    info = load_status(folder)
    if not info:
        raise HTTPException(404, "Job not found")
    # Disk data may change while ffmpeg is writing or yt-dlp is merging.
    info["workspace_bytes"] = sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())
    return {"id": job_id, **info}

@app.post("/api/jobs/url")
def url_job(data: URLJob):
    try:
        jid = manager.create(url=data.url, count=data.count, seconds=data.seconds,
              captions=data.captions, crop=data.crop, quality=data.quality, backend=data.backend, encoder=data.encoder)
        return {"id": jid}
    except ValueError as e:
        raise HTTPException(422, str(e))

class LocalJob(URLJob):
    path: str
    url: str = ""

@app.post("/api/jobs/local")
def local_job(data: LocalJob):
    try:
        jid=manager.create(local_path=data.path,count=data.count,seconds=data.seconds,
             captions=data.captions,crop=data.crop,quality=data.quality,encoder=data.encoder)
        return {"id":jid}
    except ValueError as e:
        raise HTTPException(422, str(e))

@app.post("/api/jobs/{job_id}/control/{action}")
def job_control(job_id: str, action: str):
    try: return manager.control(job_id,action)
    except ValueError as e: raise HTTPException(400,str(e))

@app.get("/api/jobs/{job_id}/files/{name}")
def get_file(job_id: str, name: str):
    if not re.fullmatch(r"clip_\d{2}\.mp4", name):
        raise HTTPException(400, "Only rendered clips can be downloaded")
    try:
        file = job_path(job_id) / name
    except ValueError:
        raise HTTPException(400)
    if not file.is_file():
        raise HTTPException(404)
    return FileResponse(file, media_type="video/mp4", filename=name, content_disposition_type="inline")

@app.post("/api/jobs/{job_id}/publish/{name}")
def publish(job_id: str, name: str, data: UploadRequest):
    if data.privacy not in {"private", "unlisted", "public"}:
        raise HTTPException(422, "Invalid privacy setting")
    if not re.fullmatch(r"clip_\d{2}\.mp4", name):
        raise HTTPException(400)
    try:
        folder = job_path(job_id)
    except ValueError:
        raise HTTPException(400)
    state = load_status(folder)
    if state.get("state") != "done":
        raise HTTPException(409, "Job not completed")
    match = next((c for c in state.get("clips", []) if c["file"] == name), None)
    if match is None:
        raise HTTPException(404)
    if match.get("published"):
        raise HTTPException(409, "Clip already uploaded; refusing to duplicate")
    # Deliberately only run on explicit click. OAuth can require a local browser login.
    try:
        video_id = upload_video(folder / name, data.title, data.description, data.privacy)
    except Exception as e:
        raise HTTPException(502, f"Upload unsuccessful: {type(e).__name__}: {str(e)[:500]}")
    match["published"] = video_id
    save_status(folder, state)
    return {"video_id": video_id, "url": f"https://www.youtube.com/watch?v={video_id}"}
