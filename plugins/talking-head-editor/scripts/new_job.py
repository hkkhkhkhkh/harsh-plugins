#!/usr/bin/env python3
"""Start an edit job: probe the clip, copy it off the card (byte-checked), build the job folder for the format, write job.py.

  python3 new_job.py <clip> --format reel|iphone|vsl [--name slug] [--jobs-dir DIR] [--no-copy]

Personal settings (paths on YOUR machine) live in ~/.config/talking-head-editor/config.json, never in the plugin:
  {"jobs_dir": "~/Movies/edits", "footage_dir": "~/Movies/footage", "lut": "~/Movies/LUT/SL3SG3tos709.cube",
   "music": "", "dfpy": "~/.local/share/deepfilter-venv/bin/python", "sfx_house_dir": "", "sfx_library": "",
   "resolve_volume": "/Volumes/Macintosh HD", "brand": {"ink": "#10243D", "font_bold": "ArchivoEF-Bold"}}
Keep footage under ~/Movies or /Volumes: Resolve's scripting API only imports media on a mounted volume."""
import argparse, datetime, json, os, re, shutil, subprocess, sys, filecmp
from pathlib import Path
HERE = Path(__file__).resolve().parent; PIPE = HERE.parent / "pipeline"
CONF = Path("~/.config/talking-head-editor/config.json").expanduser()
BRAND = {"ink": "#10243D", "paper": "#F7F9FB", "dim": "#B9C9D8", "rule": "#CFD9E1", "red": "#BE2A1B", "green": "#10604F", "deep": "#1D3A57",
         "card": "#FFFFFF", "font_bold": "ArchivoEF-Bold", "font_semibold": "ArchivoEF-SemiBold", "font_medium": "ArchivoEF-Medium"}
FORMATS = {
    "reel":   {"W": 1080, "H": 1920, "CAPTION_Y": 1280, "PX_PER_SIZE": 700.0, "overlay": None,
               "GRADE": {"NodeIndex": "1", "Slope": "1.03 1.03 1.03", "Offset": "-0.004 -0.004 -0.004", "Power": "1.0 1.0 1.0", "Saturation": "1.06"}, "AROLL_FX": {},
               "note": "9:16 reel from a log camera (Sony FX30 S-Log3): later take wins, 0.10 s pauses cut, power-word captions, calm finish."},
    "iphone": {"W": 1080, "H": 1920, "CAPTION_Y": 1280, "PX_PER_SIZE": 700.0, "overlay": "iphone",
               "GRADE": {"NodeIndex": "1", "Slope": "1 1 1", "Offset": "0 0 0", "Power": "1 1 1", "Saturation": "1"}, "AROLL_FX": {},
               "note": "9:16 phone selfie (HDR HLG): convert with tools/tosdr.swift first, no grade on top (the phone's own look is the reference)."},
    "vsl":    {"W": 1920, "H": 1080, "CAPTION_Y": 880, "PX_PER_SIZE": round(700 * 1920 / 1080, 1), "overlay": "vsl16x9",
               "GRADE": {"NodeIndex": "1", "Slope": "1.03 1.03 1.03", "Offset": "0.008 0.008 0.008", "Power": "0.98 0.98 0.98", "Saturation": "1.06"},
               "AROLL_FX": {"ContrastPop": {"MidtoneDetail": 0.10}, "Vignette": {"size": 0.85, "softness": 0.9, "transparency": 0.65}},
               "note": "16:9 sales video / YouTube: right-hand plate graphics (he slides left), full-frame scenes, real client proof, web encode."},
}
def ff():
    try:
        import imageio_ffmpeg; return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError: return shutil.which("ffmpeg") or sys.exit("needs ffmpeg (pip install imageio-ffmpeg)")
def probe(p):
    err = subprocess.run([ff(), "-hide_banner", "-i", str(p)], capture_output=True, text=True).stderr
    v = re.search(r"Video: .*?(\d{3,4})x(\d{3,4}).*?([\d.]+) fps", err)
    w, h, fps = (int(v.group(1)), int(v.group(2)), float(v.group(3))) if v else (0, 0, 0)
    rot = re.search(r"rotation of (-?\d+)", err) or re.search(r"rotate\s*:\s*(-?\d+)", err)
    if rot and abs(int(rot.group(1))) in (90, 270): w, h = h, w
    hlg = "arib-std-b67" in err
    blob = b""
    with open(p, "rb") as f:
        blob += f.read(4_000_000); f.seek(max(0, os.path.getsize(p) - 4_000_000)); blob += f.read()
    side = next(iter(Path(p).parent.glob(Path(p).stem + "M01.XML")), None)
    if side: blob += side.read_bytes()
    gam = re.search(rb'CaptureGammaEquation" value="([^"]+)"', blob); pri = re.search(rb'CaptureColorPrimaries" value="([^"]+)"', blob)
    return {"w": w, "h": h, "fps": fps, "hlg": hlg, "gamma": gam.group(1).decode() if gam else "", "primaries": pri.group(1).decode() if pri else ""}
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("clip"); ap.add_argument("--format", required=True, choices=FORMATS)
    ap.add_argument("--name"); ap.add_argument("--jobs-dir"); ap.add_argument("--no-copy", action="store_true")
    a = ap.parse_args(); conf = json.loads(CONF.read_text()) if CONF.exists() else {}
    X = lambda k, d="": str(Path(conf[k]).expanduser()) if conf.get(k) else d
    clip = Path(a.clip).expanduser().resolve()
    if not clip.exists(): sys.exit(f"no such clip: {clip}")
    pr = probe(clip); fmt = FORMATS[a.format]
    print(f"clip {clip.name}: {pr['w']}x{pr['h']} @ {pr['fps']:g} fps, gamma {pr['gamma'] or '-'}, primaries {pr['primaries'] or '-'}, HLG {pr['hlg']}")
    # copy off the card, byte-checked (a pulled card mid-render loses the edit)
    src = clip
    if not a.no_copy and conf.get("footage_dir"):
        dst_dir = Path(X("footage_dir")) / datetime.date.today().isoformat(); dst_dir.mkdir(parents=True, exist_ok=True); src = dst_dir / clip.name
        if not (src.exists() and src.stat().st_size == clip.stat().st_size):
            print(f"copying to {src} ..."); shutil.copy2(clip, src)
        if not filecmp.cmp(clip, src, shallow=False): sys.exit("COPY MISMATCH: byte check failed")
        print("copy byte-checked")
    tag = (a.name or re.sub(r"[^A-Za-z0-9]", "", clip.stem.split("_")[-1]) or "clip").upper()
    jobs = Path(a.jobs_dir).expanduser() if a.jobs_dir else Path(X("jobs_dir", str(Path.home() / "Movies/edits")))
    J = jobs / f"{datetime.date.today().isoformat()}-{tag.lower()}-{a.format}"
    if J.exists(): sys.exit(f"job folder exists: {J}")
    shutil.copytree(PIPE, J, ignore=shutil.ignore_patterns("formats", "job_template.py", "__pycache__", "*.pyc"))
    if fmt["overlay"]:
        for f in (PIPE / "formats" / fmt["overlay"]).iterdir():
            (shutil.copytree if f.is_dir() else shutil.copy2)(f, J / f.name)
    for d in ("audio", "transcripts", "graphics", "render", "logs", "tclips/src", "inserts", "music", "carriers", "web"): (J / d).mkdir(parents=True, exist_ok=True)
    if conf.get("sfx_house_dir"):
        for w in Path(X("sfx_house_dir")).glob("*.wav"): shutil.copy2(w, J / "audio/sd" / w.name)
    # colour pipeline from the probe
    log = "s-log3" in pr["gamma"].lower()
    if a.format == "iphone" or pr["hlg"]:
        idt, prev = "Rec.709 Gamma 2.4", '"format=yuv420p"'
        sdr = J / "work" / (clip.stem + "_sdr.mov"); (J / "work").mkdir(exist_ok=True)
        print(f"HDR phone clip: convert first ->  swiftc -O {J}/tools/tosdr.swift -o {J}/tools/tosdr && {J}/tools/tosdr '{src}' '{sdr}'")
        src = sdr
    elif log:
        idt, prev = "S-Gamut3/S-Log3", "\"lut3d='{lut}'\""
        if "cine" in pr["primaries"].lower(): print("note: S-Gamut3.Cine primaries: check the IDT string Resolve accepts and set job.IDT")
    else:
        idt, prev = "Rec.709 Gamma 2.4", '"format=yuv420p"'
    src_fps = pr["fps"] or 25.0
    fps = src_fps / 2 if src_fps >= 47 else src_fps
    if abs(fps - 29.97) < 0.01: print("note: 29.97 fps: Resolve wants the STRING '29.97' as timelineFrameRate, and every clip FPS set to '29.97' after import")
    brand = {**BRAND, **conf.get("brand", {})}
    t = (PIPE / "job_template.py").read_text()
    for k, v in {"__FORMAT_NOTE__": fmt["note"], "__CLIP__": clip.name, "__SRC__": str(src), "__FORMAT__": a.format, "__IDT__": idt,
                 "__LUT__": X("lut"), "__SRC_FPS__": repr(round(src_fps, 3)), "__FPS__": repr(round(fps, 3)), "__W__": str(fmt["W"]), "__H__": str(fmt["H"]),
                 "__TAG__": tag, "__PROJECT__": f"{tag} {a.format} ({datetime.date.today().isoformat()})", "__OUT_NAME__": f"{tag}_{a.format}",
                 "__DFPY__": X("dfpy", str(Path.home() / ".local/share/deepfilter-venv/bin/python")), "__MUSIC__": X("music"),
                 "__SFX_LIBRARY__": X("sfx_library"), "__GRADE__": json.dumps(fmt["GRADE"]), "__AROLL_FX__": json.dumps(fmt["AROLL_FX"]),
                 "__PREVIEW_VF__": prev, "__CAPTION_Y__": str(fmt["CAPTION_Y"]), "__PX_PER_SIZE__": str(fmt["PX_PER_SIZE"]),
                 "__BRAND__": json.dumps(brand), "__RESOLVE_VOLUME__": conf.get("resolve_volume", "/Volumes/Macintosh HD")}.items():
        t = t.replace(k, v)
    (J / "job.py").write_text(t)
    print(f"\njob ready: {J}\n  format {a.format} ({fmt['W']}x{fmt['H']} @ {fps:g} fps from {src_fps:g}), IDT {idt}")
    if not X("lut") and log: print("  WARNING: no LUT in config: face detection and the QC colour check need the camera's log->709 LUT")
    if not X("music"): print("  no music in config: set job.MUSIC (extend a short bed with music/build_bed.py)")
    print(f"  next: cd '{J}' && python3 clean_source.py && python3 transcribe.py   (then write SPANS in keep_spans.py)")
if __name__ == "__main__": main()
