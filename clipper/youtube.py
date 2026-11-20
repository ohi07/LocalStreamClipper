"""Optional official YouTube uploader. Never uploads without explicit user action."""
import json
import os
from pathlib import Path

from .core import ROOT, config

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def upload_video(path, title, description="", privacy=None):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    secrets = Path(config("YOUTUBE_CLIENT_SECRETS", "client_secrets.json"))
    if not secrets.is_absolute():
        secrets = ROOT / secrets
    if not secrets.is_file():
        raise RuntimeError("YouTube credentials not configured: add client_secrets.json from Google Cloud Console.")
    token_path = ROOT / "youtube_token.json"
    creds = None
    if token_path.is_file():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets), SCOPES)
            creds = flow.run_local_server(port=0, open_browser=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    api = build("youtube", "v3", credentials=creds, cache_discovery=False)
    level = privacy or config("YOUTUBE_PRIVACY", "private")
    if level not in ("private", "public", "unlisted"):
        raise ValueError("Invalid privacy level")
    req = api.videos().insert(
        part="snippet,status",
        body={"snippet": {"title": title[:100], "description": description[:5000], "categoryId": "22"},
              "status": {"privacyStatus": level, "selfDeclaredMadeForKids": False}},
        media_body=MediaFileUpload(str(path), chunksize=8 * 1024 * 1024, resumable=True, mimetype="video/mp4"),
    )
    response = None
    while response is None:
        _, response = req.next_chunk()
    return response["id"]
