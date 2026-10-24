"""Builds a test montage + a Montager-like data folder from real game frames (Montager's docs/fixtures, read-only).
usage: python tests/make_fixture.py <montager repo> <out dir>"""
import json, subprocess, sys
from pathlib import Path
from PIL import Image, ImageEnhance

mon, out = Path(sys.argv[1]), Path(sys.argv[2])
vid_dir = out / "Montages" / "CS2"
data = out / "montage_data"
(vid_dir / "logs").mkdir(parents=True, exist_ok=True)
(data / "playlist").mkdir(parents=True, exist_ok=True)
(data / "logs").mkdir(parents=True, exist_ok=True)

def tile(p, col=0, row=0, w=480, h=270):
    im = Image.open(mon / p).convert("RGB")
    return im.crop((col * w, row * h, col * w + w, row * h + h)).resize((1920, 1080), Image.LANCZOS)

segs = [tile("docs/proof_v844/sky_Counter-strike_2_2026.03.04_-_20.02.58.0_13.jpg", 0, 0),
        tile("docs/proof_v844/sky_Counter-strike_2_2025.02.11_-_20.21.22.0_12.jpg", 0, 0),
        tile("docs/proof_v844/sky_Counter-strike_2_2026.02.05_-_22.57.32.1_10.jpg", 0, 0),
        tile("docs/proof_v844/sky_Counter-strike_2_2026.03.04_-_20.02.58.0_13.jpg", 3, 0)]
kf = Image.open(mon / "tests/fixtures/cs2_rows/kill_row.png").convert("RGB")
kf = kf.resize((int(kf.width * 1.45), int(kf.height * 1.45)), Image.LANCZOS)
FPS, SEG, XF = 30, 4.0, 0.5
n = int(SEG * FPS * len(segs))
p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1920x1080", "-r", str(FPS), "-i", "-",
                      "-f", "lavfi", "-i", "sine=frequency=330:duration=23", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                      "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(vid_dir / "AL_CS2_V9.0.1_2026-10-24.mp4")], stdin=subprocess.PIPE)
def at(i, f):
    im = segs[i]
    z = 1.0 + 0.04 * f / (SEG * FPS)
    w, h = int(1920 / z), int(1080 / z)
    im = im.crop(((1920 - w) // 2, (1080 - h) // 2, (1920 - w) // 2 + w, (1080 - h) // 2 + h)).resize((1920, 1080))
    if i in (0, 2) and f > 1.2 * FPS:            # killfeed rows on takes 1 and 3 from 1.2 s on
        im = im.copy(); im.paste(kf, (1920 - kf.width - 20, 60))
    return im
from PIL import ImageDraw, ImageFilter, ImageFont
INTRO = 7.0                                      # Montager V9.0 intro: blurred first take + the title fading in / out
try:
    tf = ImageFont.truetype("DejaVuSans-Bold.ttf", 150)
except OSError:
    tf = ImageFont.load_default()
blur0 = segs[0].filter(ImageFilter.GaussianBlur(18))
def intro(t):
    im = blur0.copy()
    a = min(1, max(0, (t - 0.8) / 0.9)) * min(1, max(0, (6.0 - t) / 0.5))
    if a > 0:
        lay = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        d.text((960, 540), "AZURE LANE", font=tf, anchor="mm", fill=(255, 255, 255, int(255 * a)), stroke_width=4, stroke_fill=(14, 14, 22, int(255 * a)))
        im = Image.alpha_composite(im.convert("RGBA"), lay).convert("RGB")
    return im
for k in range(int(INTRO * FPS)):
    p.stdin.write(intro(k / FPS).tobytes())
for k in range(n):
    i, f = divmod(k, int(SEG * FPS))
    im = at(i, f)
    if i + 1 < len(segs) and f > (SEG - XF) * FPS:      # crossfade into the next take
        a = (f - (SEG - XF) * FPS) / (XF * FPS)
        im = Image.blend(im, at(i + 1, 0), a)
    t = k / FPS
    if t > 15.0: im = ImageEnhance.Brightness(im).enhance(max(0, (16 - t)))
    p.stdin.write(im.tobytes())
p.stdin.close(); p.wait()

plan = {"game": "cs2", "intro": {"look": "shade"}, "song": {"path": r"C:\Music\Kanaria - Azure Lane (Official Video).mp3", "artist": "", "title": "Azure Lane (feat. Someone) [Radio Edit]"},
        "takes": [{"out_start": 0.0, "rows_out": [1.3], "kills_out": [1.25], "victims": ["Pengi:3", "SuperSigma"]},
                  {"out_start": 4.0, "rows_out": [1.0], "kills_out": [1.0], "victims": ["SuperSigma"]},
                  {"out_start": 8.0, "rows_out": [1.3, 2.2], "kills_out": [1.2, 2.1], "victims": ["Pengi:3"]},
                  {"out_start": 12.0, "rows_out": [1.5], "kills_out": [1.4], "victims": []}]}
json.dump(plan, open(vid_dir / "logs" / "AL_CS2_V9.0.1_2026-10-24.plan.json", "w"))
json.dump({"output_root": str(out / "Montages"), "playlist_dir": str(data / "playlist")}, open(data / "config.json", "w"))
with open(data / "playlist" / "playlist.csv", "w", encoding="utf-8") as f:
    f.write("Track URI,Track Name,Artist Name(s),Tempo\nspotify:track:1,Azure Lane,Kanaria;Someone,128\nspotify:track:2,Other Song,Nobody,100\n")
print(vid_dir / "AL_CS2_V9.0.1_2026-10-24.mp4")
