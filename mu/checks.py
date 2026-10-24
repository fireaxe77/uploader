"""First-run check: what is missing, in plain words. Returns [(level, text)], level = 'ok' | 'warn' | 'missing'."""
import importlib.util
import shutil
import sys
from pathlib import Path

from .config import CLIENT_SECRET, TOKEN

PACKAGES = [("googleapiclient", "google-api-python-client", True), ("google_auth_oauthlib", "google-auth-oauthlib", True),
            ("PIL", "Pillow", True), ("numpy", "numpy", True), ("tkinterdnd2", "tkinterdnd2 (drag and drop onto the window)", False)]


def run(cfg):
    res = []
    v = sys.version_info
    res.append(("ok" if v >= (3, 9) else "missing", f"Python {v.major}.{v.minor}" + ("" if v >= (3, 9) else " is too old: install Python 3.12 from python.org")))
    miss = [pip for mod, pip, need in PACKAGES if need and importlib.util.find_spec(mod) is None]
    res.append(("missing", "Python packages missing: " + ", ".join(miss) + ". Double-click Install.bat.") if miss else ("ok", "Python packages"))
    if importlib.util.find_spec("tkinterdnd2") is None:
        res.append(("warn", "tkinterdnd2 is missing: dropping onto the window is off (Install.bat fixes it). Dropping onto 'Montage Uploader.bat' still works."))
    for tool in ("ffmpeg", "ffprobe"):
        res.append(("ok", tool) if shutil.which(tool) else ("missing", f"{tool} not found. Install it: winget install --id Gyan.FFmpeg -e --scope user (then open a new window)."))
    if CLIENT_SECRET.is_file():
        res.append(("ok", "Google OAuth client (client_secret.json)"))
    else:
        res.append(("missing", f"client_secret.json is missing. Follow README 'One-time Google setup' and save the file as {CLIENT_SECRET}"))
    res.append(("ok", "YouTube login saved") if TOKEN.is_file() else ("warn", "Not logged in to YouTube yet: the first upload opens the Google login in your browser."))
    d = Path(cfg.get("montager_data_dir") or "")
    if d.is_dir():
        res.append(("ok" if (d / "config.json").is_file() else "warn",
                    f"Montager data folder {d}" + ("" if (d / "config.json").is_file() else " (no config.json in it: is this the montage_data folder?)")))
    else:
        res.append(("warn", f"Montager data folder not found: {d}. Set montager_data_dir in settings.json (song names will be asked by hand until then)."))
    return res


def blocking(res):
    return [t for lv, t in res if lv == "missing"]
