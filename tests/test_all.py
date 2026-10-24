"""Montage Uploader tests (no network, no Google account). Run: python tests/test_all.py [<montager repo>]
Builds a test montage from Montager's own frames (read-only) when a Montager repo path is given or found next to this repo."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp(prefix="mu_test_"))
os.environ["MU_SETTINGS"] = str(TMP / "settings.json")

from mu import config, core, describe, montager, thumbs, youtube  # noqa: E402

config.MEMORY = core.MEMORY = TMP / "memory.json"
config.HISTORY = core.HISTORY = TMP / "uploads.json"
core.LOG_DIR = TMP / "logs"
FAILS = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  ({detail})" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def t_clean():
    ct = montager.clean_title
    cases = {("Azure Lane (feat. Someone) [Radio Edit]", ""): "Azure Lane", ("Kanaria - Azure Lane (Official Video)", "Kanaria"): "Azure Lane",
             ("Song ft. X", ""): "Song", ("Dance With Me", ""): "Dance With Me", ("Track - Radio Edit", ""): "Track",
             ("01. Night Drive - Official Music Video", ""): "Night Drive", ("Title (with Friend)", ""): "Title", ("Song - with Friend", ""): "Song"}
    for (raw, art), want in cases.items():
        check(f"clean_title {raw!r}", ct(raw, art) == want, ct(raw, art))
    check("clean_artists", montager.clean_artists("Kanaria;Someone - Topic, Kanaria") == "Kanaria, Someone")
    check("game from name", montager.game_from_name("LM_CS2_V9.0_2026-10-24.mp4") == "cs2" and montager.game_from_name("X_VAL_V9.0_2026-10-24_2.mp4") == "valorant"
          and montager.game_from_name("X_R6S_V9_2026.mp4") == "r6s" and montager.game_from_name("clip.mp4") is None)


def t_text():
    check("title format", describe.make_title("Azure Lane", "cs2") == "Azure Lane | CS2 Montage")
    check("title r6s", describe.make_title("Song", "r6s") == "Song | Rainbow Six Siege Montage")
    check("title length", len(describe.make_title("x" * 200, "valorant")) <= 100)
    d = describe.make_text("Azure Lane", "Kanaria", "valorant", ROOT / "templates" / "description_default.txt")
    lines = d["description"].splitlines()
    check("description line 1", lines[0] == "Valorant montage.", lines[0])
    check("description song line", "Song: Azure Lane by Kanaria" in d["description"])
    check("description rights line", "I do not own the rights to this song. All rights belong to the original artist and label." in d["description"])
    check("description blurb", "Valorant is a tactical team shooter by Riot Games." in d["description"])
    check("no links", "http" not in d["description"] and "www." not in d["description"])
    check("no template comments", "Placeholders" not in d["description"] and "[blurb" not in d["description"])
    check("tags", d["tags"] == ["Valorant", "Valorant montage", "montage", "kill montage", "Azure Lane"], d["tags"])
    d2 = describe.make_text("Song", "", "cs2", ROOT / "templates" / "description_default.txt")
    check("no artist -> no 'by'", "Song: Song\n" in d2["description"] + "\n" and " by " not in d2["description"].splitlines()[2])


def t_lookup(fx):
    data = fx / "montage_data"
    vid = fx / "Montages" / "CS2" / "AL_CS2_V9.0.1_2026-10-24.mp4"
    r = montager.lookup(data, vid)
    check("lookup via plan.json", r and r["song"] == "Azure Lane" and r["game"] == "cs2" and r["artists"] == "Kanaria, Someone", r and {k: r[k] for k in ("song", "game", "artists")})
    # montage.log path (no plan next to the video)
    v2 = fx / "Montages" / "CS2" / "NS_CS2_V9.0.1_2026-10-23.mp4"
    (data / "logs" / "montage.log").write_text("2026-10-23 PICK  song: Night Sky (Official Video)  style: hype  (picked by auto)\n"
                                              f"rendered {v2}\n", encoding="utf-8")
    r = montager.lookup(data, v2)
    check("lookup via montage.log", r and r["song"] == "Night Sky" and r["game"] == "cs2", r)
    # used_clips / used_songs path
    v3 = fx / "Montages" / "Valorant" / "OS_VAL_V9.0.1_2026-10-22.mp4"
    json.dump({"valorant": [{"date": "2026-10-22", "title": "OS_VAL_V9.0.1_2026-10-22"}]}, open(data / "used_clips.json", "w"))
    json.dump({"valorant": [{"date": "2026-10-22", "path": r"C:\Music\Nobody - Other Song (Lyrics).mp3"}]}, open(data / "used_songs.json", "w"))
    r = montager.lookup(data, v3)
    check("lookup via used_songs.json + CSV", r and r["song"] == "Other Song" and r["artists"] == "Nobody" and r["game"] == "valorant", r)
    check("unknown -> None", montager.lookup(data, fx / "XX_CS2_V9_2026-01-01.mp4") is None)
    check("missing data folder -> None", montager.lookup(fx / "nope", fx / "XX_CS2_V9_2026-01-01.mp4") is None)
    # ask once + remember
    cfg = config.load_settings()
    cfg["montager_data_dir"] = str(fx / "nope")
    asked = []
    (fx / "loose").mkdir(exist_ok=True)
    unk = fx / "loose" / "ZZ_CS2_V9.0.1_2026-10-24.mp4"           # no plan next to it, no Montager data
    shutil.copyfile(fx / "Montages" / "CS2" / "AL_CS2_V9.0.1_2026-10-24.mp4", unk)
    r = core.resolve(cfg, unk, ask=lambda g: asked.append(g) or ("Typed Song", "cs2"))
    r2 = core.resolve(cfg, unk, ask=lambda g: asked.append(g) or ("Other", "cs2"))
    check("ask once, then remembered", len(asked) == 1 and r2["song"] == "Typed Song" and asked[0] == "cs2", (asked, r2["song"]))


def t_files(fx):
    check("wrong file: text", "not a video" in (core.check_video(Path(__file__)) or ""))
    check("wrong file: missing", "not found" in (core.check_video(fx / "missing.mp4") or ""))
    part = fx / "x.part.mp4"
    part.write_bytes(b"0" * 200000)
    check("wrong file: part render", "unfinished" in (core.check_video(part) or ""))
    junk = fx / "junk.mp4"
    junk.write_bytes(b"0" * 200000)
    check("wrong file: broken mp4", "cannot be read" in (core.check_video(junk) or ""))


def t_thumbs(fx):
    vid = fx / "Montages" / "CS2" / "AL_CS2_V9.0.1_2026-10-24.mp4"
    cfg = config.load_settings()
    cfg["montager_data_dir"] = str(fx / "montage_data")
    cfg["description_template"] = str(ROOT / "templates" / "description_default.txt")
    core.MEMORY.unlink(missing_ok=True)
    r = core.prepare(cfg, vid)
    ps = r["thumbs"]["paths"]
    from PIL import Image
    check("3 thumbnails", len(ps) == 3 and all(p.is_file() for p in ps))
    check("next to the video", all(p.parent == vid.parent / "thumbnails" for p in ps))
    check("1280x720 jpg", all(Image.open(p).size == (1280, 720) and Image.open(p).format == "JPEG" for p in ps))
    check("under 2 MB", all(p.stat().st_size < 2 * 1024 * 1024 for p in ps))
    ts = r["thumbs"]["times"]
    check("frames inside the intro, title visible", all(1.7 <= t <= 5.5 for t in ts), ts)
    blank = thumbs.sharpness(thumbs.frame_at(vid, 0.3))         # intro before the title appears: blur only
    check("#1 shows the title (sharper than the blur-only intro start)", thumbs.sharpness(Image.open(ps[0])) > blank * 2)
    check("title from Montager", r["title"] == "Azure Lane | CS2 Montage", r["title"])
    big = Image.effect_noise((1280, 720), 120).convert("RGB")
    p = thumbs.save_jpg(big, TMP / "noise.jpg")
    check("noisy thumbnail still under 2 MB", p.stat().st_size < 2 * 1024 * 1024, p.stat().st_size)
    return r


class FakeResp(dict):
    def __init__(self, status):
        super().__init__(status=str(status))
        self.status = status
        self.reason = "x"


def t_youtube(fx, prepared):
    from googleapiclient.errors import HttpError
    vid = prepared["video"]
    calls = {"chunks": 0, "body": None, "thumb": 0}

    class Status:
        def __init__(self, p):
            self._p = p

        def progress(self):
            return self._p

    class Req:
        def next_chunk(self):
            calls["chunks"] += 1
            if calls["chunks"] == 2:
                raise ConnectionError("network drop")
            if calls["chunks"] == 3:
                raise HttpError(FakeResp(503), b'{"error":{"errors":[{"reason":"backendError"}]}}')
            if calls["chunks"] < 5:
                return Status(calls["chunks"] / 5), None
            return None, {"id": "abc123XYZ"}

    class Svc:
        def videos(self):
            return self

        def insert(self, part, body, media_body, notifySubscribers):
            calls["body"] = body
            return Req()

        def thumbnails(self):
            return self

        def set(self, videoId, media_body):
            calls["thumb"] += 1

            class E:
                def execute(_):
                    if calls["thumb"] == 1:
                        raise HttpError(FakeResp(403), b'{"error":{"errors":[{"reason":"forbidden"}],"message":"The authenticated user doesnt have permissions to upload and set custom video thumbnails."}}')
                    return {}
            return E()

    youtube.get_service = lambda log=None: Svc()
    youtube.time.sleep = lambda s: None
    prog = []
    vid_id = youtube.upload(vid, prepared, privacy="private", progress=prog.append)
    check("upload returns id after drop + 503", vid_id == "abc123XYZ" and calls["chunks"] == 5)
    check("privacy private + title sent", calls["body"]["status"]["privacyStatus"] == "private" and calls["body"]["snippet"]["title"] == prepared["title"])
    check("progress reaches 100 %", prog and prog[-1] == 1.0)
    ok, msg = youtube.set_thumbnail(vid_id, prepared["thumbs"]["paths"][0])
    check("unverified channel: no crash, plain message", not ok and "youtube.com/verify" in msg, msg)
    ok, msg = youtube.set_thumbnail(vid_id, prepared["thumbs"]["paths"][1])
    check("thumbnail set on retry", ok)
    q = HttpError(FakeResp(403), b'{"error":{"errors":[{"reason":"quotaExceeded"}],"message":"quota"}}')
    check("quota message", "quota" in youtube.plain(q).lower() and "tomorrow" in youtube.plain(q))


def t_secrets():
    ign = (ROOT / ".gitignore").read_text()
    check("secrets git-ignored", "secrets/" in ign and "client_secret*.json" in ign and "token*.json" in ign)
    r = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True)
    check("no credential file tracked", not any(("client_secret" in f or "token" in f.lower()) and f.endswith(".json") for f in r.stdout.splitlines()))


def main():
    mon = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not mon:
        for c in (ROOT.parent / "montager", ROOT.parent / "fireaxe77" / "montager", Path("/home/user/fireaxe77/montager")):
            if (c / "montage.py").is_file():
                mon = c
                break
    t_clean()
    t_text()
    t_secrets()
    if mon:
        fx = TMP / "fx"
        subprocess.run([sys.executable, str(ROOT / "tests" / "make_fixture.py"), str(mon), str(fx)], check=True, capture_output=True)
        t_lookup(fx)
        t_files(fx)
        r = t_thumbs(fx)
        t_youtube(fx, r)
    else:
        print("SKIP video tests: no Montager repo found (pass its path)")
    print(f"\n{'ALL PASS' if not FAILS else str(len(FAILS)) + ' FAILED: ' + ', '.join(FAILS)}   (scratch: {TMP})")
    if not FAILS and not os.environ.get("MU_KEEP"):
        shutil.rmtree(TMP, ignore_errors=True)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
