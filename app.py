"""Montage Uploader: drop one finished montage .mp4 -> title, description, 3 thumbnails, private YouTube upload, thumbnail #1, the link.

    python app.py                      the window (drop a file on it)
    python app.py <video.mp4>          the window, starts with that file (this is what 'Montage Uploader.bat' does)
    python app.py --dry-run <video>    everything except the upload (title, description, thumbnails)
    python app.py --prepare <video>    the same without a window: prints title + description, writes the thumbnails
    python app.py --check              the first-run check
"""
import argparse
import os
import queue
import sys
import threading
import traceback
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mu import checks, core                                    # noqa: E402
from mu.config import load_settings                            # noqa: E402
from mu.montager import GAME_NAMES                             # noqa: E402

APP = "Montage Uploader"


def cli_check():
    cfg = load_settings()
    for lv, t in checks.run(cfg):
        print({"ok": "OK     ", "warn": "NOTE   ", "missing": "MISSING"}[lv], t)
    return 1 if checks.blocking(checks.run(cfg)) else 0


def cli_prepare(path):
    cfg = load_settings()

    def ask(game):
        song = input("Song not found in Montager's data. Song name: ").strip()
        g = input(f"Game (cs2 / valorant / r6s) [{game or 'cs2'}]: ").strip().lower() or game or "cs2"
        return (song, g) if song else None
    r = core.prepare(cfg, path, ask, log=print)
    print("\nTITLE\n" + r["title"] + "\n\nDESCRIPTION\n" + r["description"] + "\n\nTAGS\n" + ", ".join(r["tags"]))
    print(f"\nsong source: {r['source']}   thumbnail frames at {r['thumbs']['times']} s")
    for p in r["thumbs"]["paths"]:
        print("thumbnail:", p)
    return 0


# ------------------------------------------------------------------ window
def run_gui(first=None, dry=False):
    import tkinter as tk
    from tkinter import ttk
    try:
        from tkinterdnd2 import DND_FILES, TkinterDnD
        root = TkinterDnD.Tk()
        dnd = True
    except Exception:                                          # noqa: BLE001 - no tkinterdnd2: the .bat drop and the file chooser still work
        root = tk.Tk()
        dnd = False
    from PIL import Image, ImageTk

    cfg = load_settings()
    root.title(APP + (" (dry run: no upload)" if dry else ""))
    root.geometry("860x640")
    root.minsize(720, 520)
    ico = Path(__file__).with_name("icon.png")
    if ico.is_file():
        try:
            root.iconphoto(True, tk.PhotoImage(file=str(ico)))
        except tk.TclError:
            pass
    BG, FG, DIM, ACC = "#16181d", "#e8e8ea", "#9aa0aa", "#5b8def"
    root.configure(bg=BG)
    st = ttk.Style()
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass
    st.configure("TProgressbar", troughcolor="#262a33", background=ACC, bordercolor=BG, lightcolor=ACC, darkcolor=ACC)
    st.configure("TButton", padding=6)

    q = queue.Queue()
    state = {"busy": False, "vid": None, "thumbs": [], "imgs": []}

    checks_txt = tk.Label(root, bg=BG, fg="#f0b46a", justify="left", anchor="w", wraplength=820, font=("Segoe UI", 9))
    checks_txt.pack(fill="x", padx=16, pady=(10, 0))
    drop = tk.Label(root, text="Drop a finished montage .mp4 here\n(or click to choose a file)", bg="#1f232b", fg=FG,
                    font=("Segoe UI", 15), relief="groove", bd=2, height=5, cursor="hand2")
    drop.pack(fill="x", padx=16, pady=12)
    status = tk.Label(root, text="Ready.", bg=BG, fg=FG, justify="left", anchor="w", wraplength=820, font=("Segoe UI", 10))
    status.pack(fill="x", padx=16)
    bar = ttk.Progressbar(root, mode="determinate", maximum=100)
    bar.pack(fill="x", padx=16, pady=8)
    title_l = tk.Label(root, text="", bg=BG, fg=FG, anchor="w", font=("Segoe UI", 12, "bold"), wraplength=820, justify="left")
    title_l.pack(fill="x", padx=16)
    link = tk.Label(root, text="", bg=BG, fg=ACC, anchor="w", font=("Segoe UI", 12, "underline"), cursor="hand2")
    link.pack(fill="x", padx=16, pady=(2, 0))
    note = tk.Label(root, text="", bg=BG, fg="#f0b46a", anchor="w", justify="left", wraplength=820, font=("Segoe UI", 10))
    note.pack(fill="x", padx=16, pady=(4, 0))
    thumbs_f = tk.Frame(root, bg=BG)
    thumbs_f.pack(fill="x", padx=16, pady=10)
    btns = tk.Frame(root, bg=BG)
    btns.pack(fill="x", padx=16)

    def show_checks():
        res = checks.run(cfg)
        bad = [t for lv, t in res if lv != "ok"]
        checks_txt.config(text="\n".join("• " + t for t in bad))
    show_checks()

    def post(kind, *a):
        q.put((kind, a))

    def ask_song(game):
        """Runs in the worker: shows the small dialog on the main thread and waits for it."""
        ev, box = threading.Event(), {}
        post("ask", game, ev, box)
        ev.wait()
        return box.get("ans")

    def dialog(game, ev, box):
        d = tk.Toplevel(root, bg=BG)
        d.title("Song and game")
        d.transient(root)
        d.grab_set()
        tk.Label(d, text="The song was not found in Montager's data.\nType it once; it is remembered for this file.", bg=BG, fg=FG,
                 justify="left").grid(row=0, column=0, columnspan=2, padx=12, pady=(12, 6), sticky="w")
        tk.Label(d, text="Song", bg=BG, fg=FG).grid(row=1, column=0, padx=12, sticky="w")
        e = tk.Entry(d, width=40)
        e.grid(row=1, column=1, padx=12, pady=4)
        tk.Label(d, text="Artist (optional)", bg=BG, fg=FG).grid(row=2, column=0, padx=12, sticky="w")
        ea = tk.Entry(d, width=40)
        ea.grid(row=2, column=1, padx=12, pady=4)
        tk.Label(d, text="Game", bg=BG, fg=FG).grid(row=3, column=0, padx=12, sticky="w")
        names = list(GAME_NAMES.values())
        gv = tk.StringVar(value=GAME_NAMES.get(game or "cs2", "CS2"))
        ttk.Combobox(d, textvariable=gv, values=names, state="readonly", width=37).grid(row=3, column=1, padx=12, pady=4)

        def ok(*_):
            if e.get().strip():
                box["ans"] = (e.get().strip(), {v: k for k, v in GAME_NAMES.items()}[gv.get()], ea.get().strip())
                d.destroy()
                ev.set()

        def cancel(*_):
            d.destroy()
            ev.set()
        ttk.Button(d, text="OK", command=ok).grid(row=4, column=1, sticky="e", padx=12, pady=12)
        d.bind("<Return>", ok)
        d.protocol("WM_DELETE_WINDOW", cancel)
        e.focus_set()

    def clear_result():
        title_l.config(text="")
        link.config(text="")
        note.config(text="")
        for w in list(thumbs_f.winfo_children()) + list(btns.winfo_children()):
            w.destroy()
        state["imgs"].clear()

    def show_thumbs(paths, active=0, can_switch=False):
        for w in thumbs_f.winfo_children():
            w.destroy()
        state["imgs"].clear()
        for i, p in enumerate(paths):
            col = tk.Frame(thumbs_f, bg=BG)
            col.pack(side="left", padx=(0, 12))
            im = Image.open(p)
            im.thumbnail((256, 144))
            ph = ImageTk.PhotoImage(im)
            state["imgs"].append(ph)
            tk.Label(col, image=ph, bg=ACC if i == active else BG, bd=0, padx=3, pady=3).pack()
            if i == active:
                tk.Label(col, text=f"#{i + 1} in use" if can_switch else f"#{i + 1} (used first)", bg=BG, fg=FG).pack(pady=4)
            elif can_switch:
                ttk.Button(col, text=f"Use #{i + 1} instead", command=lambda i=i: switch_thumb(i)).pack(pady=4)
            else:
                tk.Label(col, text=f"#{i + 1}", bg=BG, fg=DIM).pack(pady=4)

    def switch_thumb(i):
        if state["busy"] or not state["vid"]:
            return
        state["busy"] = True
        status.config(text=f"Setting thumbnail #{i + 1}...")

        def work():
            from mu import youtube
            try:
                ok, msg = youtube.set_thumbnail(state["vid"], state["thumbs"][i], log=lambda s: post("status", s))
            except Exception as ex:                    # noqa: BLE001
                ok, msg = False, str(ex)
            post("thumb_done", i, ok, msg)
        threading.Thread(target=work, daemon=True).start()

    def start(path):
        if state["busy"]:
            return
        state["busy"] = True
        clear_result()
        bar.config(value=0)
        status.config(text=f"Working on {Path(path).name} ...")
        core.log_line(f"drop: {path}")

        def work():
            try:
                r = core.prepare(cfg, path, ask_song, log=lambda s: post("status", s))
                post("prepared", r)
                if dry:
                    post("done_dry", r)
                    return
                prev = core.already_uploaded(path)
                if prev:
                    ev, box = threading.Event(), {}
                    post("confirm", prev, ev, box)
                    ev.wait()
                    if not box.get("yes"):
                        post("stopped", "Not uploaded again.")
                        return
                from mu import youtube
                post("status", "Uploading to YouTube as " + cfg.get("privacy", "private").upper() + " ...")
                vid = youtube.upload(path, r, privacy=cfg.get("privacy", "private"), category=cfg.get("category_id", "20"),
                                     kids=cfg.get("made_for_kids", False), progress=lambda f: post("progress", f), log=lambda s: post("status", s))
                core.record_upload(path, vid, r["title"])
                core.log_line(f"uploaded {Path(path).name} -> {vid}")
                post("status", "Setting thumbnail #1 ...")
                ok, msg = youtube.set_thumbnail(vid, r["thumbs"]["paths"][0], log=lambda s: post("status", s))
                post("uploaded", r, vid, ok, msg)
            except Exception as ex:                    # noqa: BLE001 - every error ends as plain text in the window
                core.log_line("error: " + "".join(traceback.format_exception_only(type(ex), ex)).strip())
                post("error", ex)
        threading.Thread(target=work, daemon=True).start()

    def poll():
        try:
            while True:
                kind, a = q.get_nowait()
                if kind == "status":
                    status.config(text=a[0])
                elif kind == "progress":
                    bar.config(value=round(a[0] * 100))
                    status.config(text=f"Uploading... {a[0] * 100:.0f} %")
                elif kind == "ask":
                    dialog(*a)
                elif kind == "confirm":
                    from tkinter import messagebox
                    prev, ev, box = a
                    box["yes"] = messagebox.askyesno(APP, f"This file was already uploaded on {prev['date']}:\n{core.watch_url(prev['id'])}\n\nUpload it again?")
                    ev.set()
                elif kind == "prepared":
                    r = a[0]
                    state["thumbs"] = r["thumbs"]["paths"]
                    title_l.config(text=r["title"])
                    show_thumbs(r["thumbs"]["paths"])
                elif kind == "done_dry":
                    r = a[0]
                    state["busy"] = False
                    status.config(text=f"Dry run finished (nothing uploaded). Song from: {r['source']}. Thumbnails: {r['thumbs']['paths'][0].parent}")
                    ttk.Button(btns, text="Open thumbnails folder", command=lambda p=r["thumbs"]["paths"][0].parent: open_path(p)).pack(side="left")
                elif kind == "uploaded":
                    r, vid, ok, msg = a
                    state.update(busy=False, vid=vid)
                    bar.config(value=100)
                    status.config(text="Uploaded as PRIVATE. " + msg)
                    link.config(text=core.watch_url(vid))
                    link.bind("<Button-1>", lambda e, u=core.watch_url(vid): webbrowser.open(u))
                    if not ok:
                        note.config(text=msg)
                    show_thumbs(r["thumbs"]["paths"], active=0 if ok else -1, can_switch=True)
                    ttk.Button(btns, text="Open in YouTube Studio", command=lambda: webbrowser.open(core.studio_url(vid))).pack(side="left")
                    ttk.Button(btns, text="Copy link", command=lambda: (root.clipboard_clear(), root.clipboard_append(core.watch_url(vid)))).pack(side="left", padx=8)
                    ttk.Button(btns, text="Open thumbnails folder", command=lambda p=r["thumbs"]["paths"][0].parent: open_path(p)).pack(side="left")
                elif kind == "thumb_done":
                    i, ok, msg = a
                    state["busy"] = False
                    status.config(text=msg)
                    note.config(text="" if ok else msg)
                    if ok:
                        show_thumbs(state["thumbs"], active=i, can_switch=True)
                elif kind == "stopped":
                    state["busy"] = False
                    status.config(text=a[0])
                elif kind == "error":
                    state["busy"] = False
                    status.config(text="Stopped: " + str(a[0]))
                    bar.config(value=0)
        except queue.Empty:
            pass
        root.after(100, poll)

    def open_path(p):
        try:
            os.startfile(str(p))                       # Windows
        except AttributeError:
            webbrowser.open(Path(p).as_uri())

    def choose(_=None):
        from tkinter import filedialog
        p = filedialog.askopenfilename(title="Choose the montage", filetypes=[("Videos", "*.mp4 *.mov *.mkv"), ("All files", "*.*")])
        if p:
            start(p)
    drop.bind("<Button-1>", choose)
    if dnd:
        def on_drop(e):
            files = root.tk.splitlist(e.data)
            if files:
                start(files[0])
        drop.drop_target_register(DND_FILES)
        drop.dnd_bind("<<Drop>>", on_drop)
    root.after(100, poll)
    if first:
        root.after(300, lambda: start(first))
    root.mainloop()


def main():
    ap = argparse.ArgumentParser(prog="app.py", description=APP)
    ap.add_argument("video", nargs="?")
    ap.add_argument("--dry-run", action="store_true", help="everything except the upload")
    ap.add_argument("--prepare", action="store_true", help="no window: print title / description, write thumbnails")
    ap.add_argument("--check", action="store_true", help="first-run check")
    a = ap.parse_args()
    if a.check:
        return cli_check()
    if a.prepare:
        if not a.video:
            ap.error("--prepare needs a video file")
        try:
            return cli_prepare(a.video)
        except (ValueError, LookupError) as ex:
            print("Stopped:", ex)
            return 1
    run_gui(a.video, dry=a.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
