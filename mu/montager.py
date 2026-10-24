"""Read-only lookup of a montage's song + game in Montager's own data. Nothing here writes to Montager's folders.

Where Montager keeps what (montage.py V9.0.x):
  <output>\\<Game>\\logs\\<video name>.plan.json   the plan of the render: plan["song"] = {title, artist, path}, plan["game"], takes with kill times
  montage_data\\config.json                        output_root, playlist_dir (the CSV track data)
  montage_data\\logs\\montage.log                  "PICK  song: <title>" ... "rendered <path>.mp4"
  montage_data\\used_clips.json / used_songs.json  appended together per render: used_clips[game][i]["title"] = video name, used_songs[game][i]["path"] = song file
"""
import csv
import re
from pathlib import Path

from .config import load_json

GAME_CODES = {"CS2": "cs2", "VAL": "valorant", "R6S": "r6s"}
GAME_NAMES = {"cs2": "CS2", "valorant": "Valorant", "r6s": "Rainbow Six Siege"}
GAME_DIRS = {"cs2": "CS2", "valorant": "Valorant", "r6s": "R6S"}
TITLE_COLS = ["track name", "track", "title", "name", "song"]                       # Montager's HEADER_ALIASES
ARTIST_COLS = ["artist name(s)", "artist names", "artist name", "artists", "artist"]
INTRO_S = 7.0                                                                     # Montager V9.0: a plan with "intro" starts its takes this much later


# ------------------------------------------------------------------ clean song title (same rules as Montager's intro90.clean_title)
_BR = re.compile(r"\s*(\([^()]*\)|\[[^\[\]]*\]|\{[^{}]*\}|【[^】]*】|（[^）]*）)")
_TAIL = re.compile(r"\s*[-–—|:]\s*(official\b.*|radio\s+edit\b.*|extended\b.*|sped\s*up\b.*|slowed\b.*|remix\b.*|lyrics?\b.*|audio\b.*|"
                   r"topic\b.*|visuali[sz]er\b.*|music\s+video\b.*)$", re.I)
_FEAT = re.compile(r"\s+(feat\.?|ft\.?|featuring)\s+.*$|\s+[-–—]\s*with\s+.*$", re.I)       # "(with X)" goes with the brackets; a bare "with" stays ("Dance With Me")
_JUNK = re.compile(r"\s*\b(official\s+(music\s+)?(video|audio)|lyric\s+video|radio\s+edit|visuali[sz]er|vevo|hd|4k)\b\s*", re.I)


def clean_title(raw, artist=None):
    """The bare song title: no brackets, no feat. / ft. / with parts, no Radio Edit / Official Video, no artist / channel prefix or suffix, no track number."""
    t = raw or ""
    t = re.sub(r"^\s*\d{1,2}\s*[\.\)]\s+|^\s*\d{1,2}\s+-\s+", "", t)
    for _ in range(4):
        n = _BR.sub(" ", t)
        if n == t:
            break
        t = n
    if re.search(r"[\(\[\{]", t) and not re.search(r"[\)\]\}]", t):
        t = re.sub(r"[\(\[\{].*$", "", t)
    names = [x.strip().casefold() for x in re.split(r",|&| x ", artist or "") if x.strip()]
    if artist:
        for a in [artist] + [x.strip() for x in re.split(r",|&| x ", artist) if x.strip()]:
            t = re.sub(r"^\s*" + re.escape(a) + r"\s*[-–—:|]\s+", "", t, flags=re.I)
            t = re.sub(r"\s+[-–—|]\s+" + re.escape(a) + r"\s*$", "", t, flags=re.I)
    m = re.match(r"^(.{2,80}?)\s+[-–—]\s+(.+)$", t)
    if m and names and any(n in m.group(1).casefold() for n in names):
        t = m.group(2)
    for _ in range(3):
        t = re.sub(r"\s+[-–—]\s+[^-–—]*\b(remix|version|mix|edit|sped up|slowed)\s*$", "", t, flags=re.I)
        t = _TAIL.sub("", t)
        t = _FEAT.sub("", t)
    t = _JUNK.sub(" ", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" -–—|:·_")
    t = re.sub(r"\s+[’'`]+$", "", t).strip(" -–—|:·")
    return t or (raw or "").strip()


def norm(s):
    s = clean_title(s or "").casefold()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]|_", " ", s)).strip()


def clean_artists(a):
    parts = [x.strip() for x in re.split(r";|,", a or "") if x.strip()]
    out = []
    for p in parts:
        p = re.sub(r"\s*-\s*topic$|\s*vevo$|\s*official$", "", p, flags=re.I).strip()
        if p and p.casefold() not in (o.casefold() for o in out):
            out.append(p)
    return ", ".join(out)


# ------------------------------------------------------------------ helpers
def game_from_name(name):
    """LM_CS2_V9.0_2026-10-24.mp4 -> cs2 (the code between the initials and the version)."""
    m = re.search(r"_(CS2|VAL|R6S)_", Path(name).name, re.I)
    return GAME_CODES[m.group(1).upper()] if m else None


def montager_config(data_dir):
    return load_json(Path(data_dir) / "config.json", {}) if data_dir else {}


def output_roots(data_dir, video):
    roots = [Path(video).parent]
    root = montager_config(data_dir).get("output_root") or r"E:\Movies\Montages"
    for g in GAME_DIRS.values():
        roots.append(Path(root) / g)
    return roots


def find_plan(data_dir, video):
    """The plan.json Montager saved next to this render (read-only)."""
    stem = Path(video).stem
    for d in output_roots(data_dir, video):
        p = d / "logs" / (stem + ".plan.json")
        if p.is_file():
            pl = load_json(p, None)
            if isinstance(pl, dict) and pl.get("song"):
                return pl, p
    return None, None


def from_log(data_dir, video):
    """montage.log: the last 'PICK  song: X' before 'rendered ...<video name>.mp4'."""
    p = Path(data_dir) / "logs" / "montage.log"
    if not p.is_file():
        return None
    name = Path(video).name.casefold()
    pick = None
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = re.search(r"PICK\s+song:\s*(.+?)\s{2,}style:", line)
                if m:
                    pick = m.group(1).strip()
                elif "rendered " in line and line.strip().casefold().endswith(name) and pick:
                    return pick
    except OSError:
        return None
    return None


def from_history(data_dir, video, game):
    """used_clips[game][i] has title = the video name; used_songs[game][i] (written in the same call) has the song file."""
    uc = load_json(Path(data_dir) / "used_clips.json", {})
    us = load_json(Path(data_dir) / "used_songs.json", {})
    stem = Path(video).stem
    for g in ([game] if game else []) + [x for x in GAME_NAMES if x != game]:
        a, b = uc.get(g) or [], us.get(g) or []
        if len(a) != len(b):
            continue
        for i, e in enumerate(a):
            if e.get("title") == stem and b[i].get("path"):
                return g, b[i]["path"]
    return None


def read_tracks(data_dir):
    """Every row of every CSV in Montager's playlist folder: [{title, artist}]."""
    cfg = montager_config(data_dir)
    d = Path(cfg.get("playlist_dir") or (Path(data_dir) / "playlist")) if data_dir else None
    rows = []
    if not d or not d.is_dir():
        return rows
    for f in sorted(d.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(f, newline="", encoding="utf-8-sig") as fh:
                rd = csv.DictReader(fh)
                heads = {h.strip().lower(): h for h in (rd.fieldnames or [])}
                tc = next((heads[n] for n in TITLE_COLS if n in heads), None)
                ac = next((heads[n] for n in ARTIST_COLS if n in heads), None)
                if not tc:
                    continue
                for r in rd:
                    t = (r.get(tc) or "").strip()
                    if t:
                        rows.append({"title": t, "artist": (r.get(ac) or "").strip() if ac else ""})
        except (OSError, csv.Error, UnicodeDecodeError):
            continue
    return rows


def match_track(tracks, title, artist=""):
    """The CSV row of this song (title match after cleaning; the artist breaks ties)."""
    nt = norm(title)
    if not nt:
        return None
    hits = [r for r in tracks if norm(r["title"]) == nt]
    if not hits:
        hits = [r for r in tracks if nt and (nt in norm(r["title"]) or norm(r["title"]) in nt) and len(norm(r["title"])) >= 3]
    if artist and len(hits) > 1:
        a = artist.casefold()
        best = [r for r in hits if any(x.strip().casefold() in a for x in re.split(r";|,", r["artist"]) if x.strip())]
        hits = best or hits
    return hits[0] if hits else None


def song_from_file(path, tracks):
    """A song file name like 'Artist - Title (Official Video).mp3' -> (title, artist), using the CSV when it matches."""
    stem = Path(str(path).replace("\\", "/")).stem
    r = match_track(tracks, stem)
    if not r and " - " in stem:
        left, right = stem.split(" - ", 1)
        r = match_track(tracks, right, left)
        if not r:
            return right, left
    if r:
        return r["title"], r["artist"]
    return stem, ""


def lookup(data_dir, video):
    """{song, artists, game, source, plan} or None. song is cleaned; artists may be ''."""
    video = Path(video)
    game = game_from_name(video.name)
    tracks = read_tracks(data_dir) if data_dir and Path(data_dir).is_dir() else []
    plan, plan_path = find_plan(data_dir, video) if data_dir else (None, None)
    raw, artist, src = None, "", None
    if plan:
        sg = plan["song"]
        raw, artist, src = sg.get("title") or Path(str(sg.get("path", ""))).stem, sg.get("artist") or "", f"plan {plan_path.name}"
        game = plan.get("game") or game
    elif data_dir and Path(data_dir).is_dir():
        t = from_log(data_dir, video)
        if t:
            raw, src = t, "montage.log"
        else:
            h = from_history(data_dir, video, game)
            if h:
                game = game or h[0]
                raw, artist = song_from_file(h[1], tracks)
                src = "used_songs.json"
    if not raw or not game:
        return None
    r = match_track(tracks, raw, artist)
    if r:
        artist = artist or r["artist"]
        raw_csv = r["title"]
    else:
        raw_csv = raw
    song = clean_title(raw_csv, artist)
    return {"song": song, "artists": clean_artists(artist), "game": game, "source": src, "plan": plan}
