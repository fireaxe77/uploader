"""Title, description and tags from the song + game and the editable template."""
import re
from pathlib import Path

from .config import TEMPLATE_DEFAULT
from .montager import GAME_NAMES

TITLE_MAX = 100                     # YouTube's title limit


def make_title(song, game):
    gname = GAME_NAMES.get(game, game)
    song = re.sub(r"[<>]", "", song).strip()                  # YouTube rejects < and > in titles
    t = f"{song} | {gname} Montage"
    if len(t) > TITLE_MAX:
        tail = f" | {gname} Montage"
        t = song[:TITLE_MAX - len(tail) - 1].rstrip() + "…" + tail
    return t


def parse_template(text):
    """(body, {game name: blurb}, tags line)."""
    body, blurbs, tags, cur = [], {}, "", None
    for line in text.splitlines():
        if re.match(r"^\s*#(\s|$)", line):                     # "# comment"; a hashtag line like "#CS2 #montage" stays
            continue
        m = re.match(r"^\[(blurb\s+(.+?)|tags)\]\s*$", line.strip(), re.I)
        if m:
            cur = ("blurb", m.group(2).strip()) if m.group(2) else ("tags", None)
            continue
        if cur is None:
            body.append(line)
        elif cur[0] == "blurb":
            if line.strip():
                blurbs[cur[1].casefold()] = (blurbs.get(cur[1].casefold(), "") + " " + line.strip()).strip()
        elif line.strip():
            tags = (tags + ", " + line.strip()).strip(", ")
    return "\n".join(body).strip("\n"), blurbs, tags


def make_text(song, artists, game, template_path):
    p = Path(template_path)
    text = p.read_text(encoding="utf-8") if p.is_file() else TEMPLATE_DEFAULT.read_text(encoding="utf-8")
    body, blurbs, tags_line = parse_template(text)
    gname = GAME_NAMES.get(game, game)
    vals = {"game": gname, "song": song, "artists": artists or "", "by_artists": f" by {artists}" if artists else "",
            "blurb": blurbs.get(gname.casefold(), "")}
    fill = lambda s: re.sub(r"\{(\w+)\}", lambda m: str(vals.get(m.group(1), m.group(0))), s)
    tags = []
    for t in fill(tags_line).split(","):
        t = re.sub(r"[<>\"]", "", t).strip()
        if t and t.casefold() not in (x.casefold() for x in tags):
            tags.append(t)
    while sum(len(t) + 1 for t in tags) > 480:                # YouTube allows ~500 characters of tags
        tags.pop()
    vals["tags_hash"] = " ".join("#" + re.sub(r"\W+", "", t) for t in tags[:3] if re.sub(r"\W+", "", t))
    desc = fill(body)
    desc = re.sub(r"[<>]", "", desc)                          # not allowed in descriptions either
    desc = re.sub(r"\n{3,}", "\n\n", desc).strip()
    return {"title": make_title(song, game), "description": desc[:4900], "tags": tags}
