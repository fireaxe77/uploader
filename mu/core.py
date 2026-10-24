"""One drop = check the file, find song + game, write title / description / 3 thumbnails, upload private, set thumbnail #1."""
import datetime
from pathlib import Path

from . import describe, montager, thumbs
from .config import HISTORY, LOG_DIR, MEMORY, load_json, save_json, thumb_dir

VIDEO_OK = {".mp4"}
VIDEO_MAYBE = {".mov", ".mkv", ".m4v", ".webm"}


def log_line(text):
    """App log (logs\\uploader.log). Only status text goes here: never tokens or client secrets."""
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_DIR / "uploader.log", "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}  {text}\n")
    except OSError:
        pass


def check_video(path):
    """Plain-language problem with the dropped file, or None."""
    p = Path(path)
    if not p.exists():
        return f"File not found: {p}"
    if p.is_dir():
        return "That is a folder. Drop one finished montage .mp4 file."
    suf = p.suffix.lower()
    if p.name.lower().endswith(".part.mp4"):
        return "That is an unfinished Montager render (.part.mp4). Wait until Montager has finished and drop the final .mp4."
    if suf not in VIDEO_OK | VIDEO_MAYBE:
        return f"'{p.name}' is not a video. Drop the finished montage .mp4."
    if p.stat().st_size < 100 * 1024:
        return f"'{p.name}' is too small to be a finished montage."
    try:
        info = thumbs.probe(p)
    except ValueError as ex:
        return f"'{p.name}' cannot be read as a video ({ex}). Is it still being written?"
    if info["dur"] < 3:
        return f"'{p.name}' is only {info['dur']:.1f} s long."
    return None


def remembered(video):
    return load_json(MEMORY, {}).get(Path(video).name)


def remember(video, song, game, artists=""):
    m = load_json(MEMORY, {})
    m[Path(video).name] = {"song": song, "game": game, "artists": artists}
    save_json(MEMORY, m)


def resolve(cfg, video, ask=None):
    """{song, artists, game, source, plan}. Order: a choice typed earlier for this file, Montager's data, then ask once (and remember)."""
    mem = remembered(video)
    found = None
    try:
        found = montager.lookup(cfg.get("montager_data_dir"), video)
    except Exception as ex:                              # noqa: BLE001 - unreadable Montager data: fall back to asking
        log_line(f"Montager lookup failed: {type(ex).__name__}: {ex}")
    if mem:
        plan = found.get("plan") if found else None
        if not plan:
            plan, _ = montager.find_plan(cfg.get("montager_data_dir"), video)
        return {"song": mem["song"], "artists": mem.get("artists") or (found or {}).get("artists", ""), "game": mem["game"],
                "source": "typed earlier", "plan": plan}
    if found:
        return found
    if ask is None:
        raise LookupError("song / game not found in Montager's data")
    ans = ask(montager.game_from_name(video))
    if not ans:
        raise LookupError("cancelled: no song name given")
    song, game = ans[0].strip(), ans[1]
    artists = ans[2].strip() if len(ans) > 2 and ans[2] else ""
    remember(video, song, game, artists)
    return {"song": song, "artists": artists, "game": game, "source": "typed by hand", "plan": None}


def prepare(cfg, video, ask=None, log=lambda s: None):
    """Everything before the upload. Returns {video, song, artists, game, source, title, description, tags, thumbs:{paths, ...}}."""
    video = Path(video)
    bad = check_video(video)
    if bad:
        raise ValueError(bad)
    log("Finding the song in Montager's data...")
    info = resolve(cfg, video, ask)
    meta = describe.make_text(info["song"], info["artists"], info["game"], cfg["description_template"])
    log(f"Title: {meta['title']}")
    log("Saving the thumbnails from the intro...")
    th = thumbs.make_thumbnails(video, thumb_dir(cfg, video), info.get("plan"), log=log)
    return {"video": video, **{k: v for k, v in info.items() if k != "plan"}, **meta, "thumbs": th}


def already_uploaded(video):
    return load_json(HISTORY, {}).get(Path(video).name)


def record_upload(video, vid, title):
    h = load_json(HISTORY, {})
    h[Path(video).name] = {"id": vid, "title": title, "date": f"{datetime.datetime.now():%Y-%m-%d %H:%M}"}
    save_json(HISTORY, h)


def watch_url(vid):
    return f"https://youtu.be/{vid}"


def studio_url(vid):
    return f"https://studio.youtube.com/video/{vid}/edit"
