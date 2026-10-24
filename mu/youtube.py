"""YouTube Data API v3: OAuth for my own channel, resumable videos.insert, thumbnails.set. Credentials stay in secrets\\ and are never printed."""
import http.client
import random
import socket
import time

from .config import CLIENT_SECRET, TOKEN

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]       # enough for videos.insert + thumbnails.set
CHUNK = 8 * 1024 * 1024
RETRY_STATUS = {500, 502, 503, 504}
RETRY_EXC = (http.client.HTTPException, ConnectionError, socket.timeout, TimeoutError, OSError)
MAX_RETRIES = 12


class UploadError(Exception):
    """An error with a plain-language message."""


def _imports():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError, ResumableUploadError
        from googleapiclient.http import MediaFileUpload
    except ImportError as ex:
        raise UploadError("The Google packages are missing. Run Install.bat (or: python -m pip install --user -r requirements.txt).") from ex
    return Request, Credentials, InstalledAppFlow, build, HttpError, ResumableUploadError, MediaFileUpload


def _reason(ex):
    try:
        import json
        j = json.loads(ex.content.decode("utf-8", "replace"))
        errs = j.get("error", {}).get("errors") or [{}]
        return errs[0].get("reason") or j.get("error", {}).get("status") or "", j.get("error", {}).get("message") or ""
    except Exception:                                   # noqa: BLE001
        return "", ""


def plain(ex):
    """A Google API error in plain words."""
    status = getattr(getattr(ex, "resp", None), "status", None)
    reason, msg = _reason(ex)
    if reason in ("quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"):
        return "YouTube's daily upload quota for this Google Cloud project is used up. Try again tomorrow (the quota resets at midnight Pacific time)."
    if reason == "uploadLimitExceeded":
        return "Your channel reached YouTube's upload limit for today. Try again in 24 hours."
    if reason in ("invalidTitle",):
        return "YouTube rejected the title. Check the title for odd characters."
    if reason in ("invalidDescription",):
        return "YouTube rejected the description. Check description_template.txt for < or > characters."
    if reason in ("youtubeSignupRequired",):
        return "This Google account has no YouTube channel yet. Create the channel on youtube.com first."
    if status == 401 or reason in ("authError", "unauthorized"):
        return "The YouTube login expired. Drop the file again and log in once more in the browser."
    if status == 403 and reason in ("accessNotConfigured", "SERVICE_DISABLED"):
        return "The YouTube Data API v3 is not enabled in your Google Cloud project. Enable it (see README, step 2)."
    if status == 403:
        return f"YouTube refused the request ({reason or 'forbidden'}): {msg}"
    return f"YouTube error {status or ''} {reason}: {msg}".strip()


def get_service(log=lambda s: None):
    Request, Credentials, InstalledAppFlow, build, *_ = _imports()
    if not CLIENT_SECRET.is_file():
        raise UploadError(f"client_secret.json is missing. Put the file you downloaded from Google Cloud here: {CLIENT_SECRET}")
    creds = None
    if TOKEN.is_file():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
        except (ValueError, OSError):
            creds = None
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:                               # noqa: BLE001 - revoked / expired refresh token: log in again
            creds = None
    if not creds or not creds.valid:
        log("Opening the Google login in your browser (one time)...")
        try:
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
        except ValueError as ex:
            raise UploadError("client_secret.json is not an OAuth 'Desktop app' client file. Download it again (README, step 3).") from ex
        creds = flow.run_local_server(port=0, open_browser=True, prompt="consent",
                                      success_message="Montage Uploader is logged in. You can close this tab.")
        TOKEN.parent.mkdir(parents=True, exist_ok=True)
        TOKEN.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload(video, meta, privacy="private", category="20", kids=False, progress=lambda f: None, log=lambda s: None):
    """Resumable upload. Retries network drops / 5xx with backoff (the upload resumes where it stopped). Returns the video id."""
    _, _, _, _, HttpError, ResumableUploadError, MediaFileUpload = _imports()
    yt = get_service(log)
    body = {"snippet": {"title": meta["title"], "description": meta["description"], "tags": meta.get("tags") or [], "categoryId": str(category)},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": bool(kids)}}
    media = MediaFileUpload(str(video), mimetype="video/mp4", chunksize=CHUNK, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media, notifySubscribers=False)
    resp, tries = None, 0
    while resp is None:
        try:
            status, resp = req.next_chunk()
            tries = 0
            if status:
                progress(status.progress())
        except (HttpError, ResumableUploadError) as ex:
            st = getattr(getattr(ex, "resp", None), "status", None)
            if st in RETRY_STATUS and tries < MAX_RETRIES:
                tries += 1
                wait = min(64, 2 ** tries) + random.random()
                log(f"YouTube server hiccup ({st}); retrying in {wait:.0f} s (try {tries} of {MAX_RETRIES})")
                time.sleep(wait)
                continue
            raise UploadError(plain(ex)) from ex
        except RETRY_EXC as ex:
            if tries >= MAX_RETRIES:
                raise UploadError("The internet connection dropped and did not come back. Drop the file again to retry.") from ex
            tries += 1
            wait = min(64, 2 ** tries) + random.random()
            log(f"Connection lost ({type(ex).__name__}); resuming in {wait:.0f} s (try {tries} of {MAX_RETRIES})")
            time.sleep(wait)
    progress(1.0)
    if "id" not in resp:
        raise UploadError("YouTube did not return a video id; check YouTube Studio before uploading again.")
    return resp["id"]


def set_thumbnail(video_id, jpg, log=lambda s: None):
    """(ok, message). A channel without phone verification cannot have custom thumbnails: that is reported, never raised."""
    _, _, _, _, HttpError, _, MediaFileUpload = _imports()
    yt = get_service(log)
    try:
        yt.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(jpg), mimetype="image/jpeg")).execute()
        return True, "Thumbnail set."
    except HttpError as ex:
        st = getattr(getattr(ex, "resp", None), "status", None)
        reason, _ = _reason(ex)
        if st == 403 or reason == "forbidden":
            return False, ("YouTube did not accept the custom thumbnail. Usually that means the channel is not phone-verified yet: "
                           "verify it at youtube.com/verify, then click 'Use #1' below (the thumbnail files are kept).")
        if reason == "mediaBodyTooLarge" or st == 413:
            return False, "The thumbnail file is too large for YouTube (over 2 MB)."
        return False, "The thumbnail was not set: " + plain(ex)
    except RETRY_EXC:
        return False, "The connection dropped while setting the thumbnail. Click 'Use #1' to try again."
