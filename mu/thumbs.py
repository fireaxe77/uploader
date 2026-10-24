"""Thumbnails = frames of Montager's own intro (the song title over the blurred gameplay), saved as 1280x720 JPG under 2 MB.

Montager V9.0 intro (intro90.py): the title fades in from 0.8 s, is fully visible from ~1.7 s, settles its scale by ~4 s and is gone by 6 s.
Three frames inside that window are saved; the sharpest (least mid-fade) is #1."""
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

W, H = 1280, 720
MAX_BYTES = 2 * 1024 * 1024 - 64 * 1024
INTRO_TIMES = (3.6, 3.0, 4.2)                    # inside the intro, title fully visible
NOWIN = 0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, creationflags=NOWIN)


def probe(video):
    r = _run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration", "-of", "json", str(video)])
    if r.returncode != 0:
        raise ValueError(r.stderr.decode("utf-8", "replace").strip().splitlines()[-1] if r.stderr else "ffprobe failed")
    j = json.loads(r.stdout or b"{}")
    st = (j.get("streams") or [{}])[0]
    if not st.get("width"):
        raise ValueError("the file has no video stream")
    return {"w": int(st["width"]), "h": int(st["height"]), "dur": float(j.get("format", {}).get("duration") or 0.0)}


def frame_at(video, t):
    """One RGB frame at time t, scaled (cover) to 1280x720."""
    vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    r = _run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(video), "-frames:v", "1", "-vf", vf,
              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    if r.returncode != 0 or len(r.stdout) < W * H * 3:
        return None
    return Image.frombytes("RGB", (W, H), r.stdout[:W * H * 3])


def sharpness(img):
    """Edge energy: the title's edges are sharpest when it is fully faded in (the gameplay behind it is blurred)."""
    g = np.asarray(img.convert("L").resize((640, 360)), dtype=np.float32)
    lap = g[1:-1, 1:-1] * 4 - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
    return float(lap.var())


def save_jpg(im, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    for q in (93, 88, 82, 75, 68, 60):
        im.save(path, "JPEG", quality=q, optimize=True, progressive=True)
        if path.stat().st_size <= MAX_BYTES:
            break
    return path


def make_thumbnails(video, out_dir, plan=None, log=lambda s: None):
    """Writes <out_dir>/<video name>_1.jpg .. _3.jpg (best first). Returns {paths, times, intro}."""
    info = probe(video)
    has_intro = bool((plan or {}).get("intro")) if plan else None       # None = no plan found: assume the V9 intro is there
    if has_intro is False:
        log("Note: Montager's plan says this montage has no intro; using frames from its first seconds.")
    times = [t for t in INTRO_TIMES if t < info["dur"] - 0.5] or [info["dur"] / 2]
    frames = []
    for t in times:
        im = frame_at(video, t)
        if im is not None:
            frames.append((sharpness(im), t, im))
    if not frames:
        raise ValueError("could not read a frame from the video")
    frames.sort(key=lambda f: -f[0])
    stem = Path(video).stem
    paths = [save_jpg(im, Path(out_dir) / f"{stem}_{i}.jpg") for i, (_, _, im) in enumerate(frames, 1)]
    return {"paths": paths, "times": [t for _, t, _ in frames], "intro": has_intro is not False}
