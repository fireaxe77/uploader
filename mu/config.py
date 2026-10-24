"""Settings, paths and small JSON helpers. settings.json is created on first run next to app.py and is the one file to edit."""
import json
import os
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SETTINGS_PATH = Path(os.environ.get("MU_SETTINGS") or (HERE / "settings.json"))
SECRETS = HERE / "secrets"                       # client_secret.json + token.json (git-ignored, never logged, never uploaded)
CLIENT_SECRET = SECRETS / "client_secret.json"
TOKEN = SECRETS / "token.json"
MEMORY = HERE / "memory.json"                    # song / game typed by hand, remembered per video file name
HISTORY = HERE / "uploads.json"                  # what was uploaded (file name -> video id), so a second drop of the same file warns
LOG_DIR = HERE / "logs"
TEMPLATE_DEFAULT = HERE / "templates" / "description_default.txt"

DEFAULTS = {
    "montager_data_dir": r"C:\Users\fireaxe\Desktop\CLAUDECODE\montager\montage_data",
    "description_template": str(HERE / "description_template.txt"),
    "privacy": "private",
    "thumbnail_folder_name": "thumbnails",       # the 3 candidates go to <video folder>\thumbnails\<video name>_1.jpg .. _3.jpg
    "thumbnail_output_dir": "",                  # set a full path to put every video's thumbnails there instead
    "category_id": "20",                         # YouTube category 20 = Gaming
    "made_for_kids": False,
}


def load_json(p, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(p, data):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


def load_settings():
    """settings.json merged over the defaults; written back on first run (and when a new setting was added) so it is easy to find and edit."""
    cur = load_json(SETTINGS_PATH, None)
    cfg = dict(DEFAULTS)
    if isinstance(cur, dict):
        cfg.update(cur)
    if cur != cfg:
        try:
            save_json(SETTINGS_PATH, cfg)
        except OSError:
            pass
    tpl = Path(cfg["description_template"])
    if not tpl.exists() and TEMPLATE_DEFAULT.exists():
        try:
            tpl.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(TEMPLATE_DEFAULT, tpl)
        except OSError:
            pass
    return cfg


def thumb_dir(cfg, video):
    video = Path(video)
    if cfg.get("thumbnail_output_dir"):
        return Path(cfg["thumbnail_output_dir"])
    return video.parent / (cfg.get("thumbnail_folder_name") or "thumbnails")
