"""16:9 VSL / YouTube finisher: assemble the finished timeline in DaVinci Resolve Studio and render it.
V1 A-roll (RCM S-Gamut3/S-Log3 -> DWG/Intermediate -> Rec.709 2.4), one Fusion comp per piece:
   Transform (one-pivot push/punch plan; in 'side' zones he slides left to x 620 at 1.36x for the right-hand plate)
   -> ResolveFX Contrast Pop (light midtone detail) -> ResolveFX Vignette (soft)
V2 inserts: Higgsfield stills (AE Ken Burns renders) + real client clips   V3 After Effects graphics (ProRes 4444)   V4 captions
(power-word Text+, Avenir Next; absent while any graphic is up)   V5 graphics that overlap the one before
A1 empty (source audio removed)  A2 dialogue  A3 music  A4 sound design.
python3 resolve_final.py [--no-render] [--test START END]   (--test renders only that record-time range to render/test_*.mp4)"""
import json, sys, time, functools, statistics, math
from pathlib import Path
import DaVinciResolveScript as dvr
print = functools.partial(print, flush=True)
HERE = Path(__file__).parent
import job, zooms
PROJECT = job.PROJECT; TL = f"{job.TAG} - Final"; FPS = job.FPS; SRC_FPS = job.SRC_FPS
FW, FH = job.W, job.H
CAP_LINE = getattr(job, "CAPTION_Y", 880)            # 16:9: caption line over the chest (C0027 16:9 approved y 880)
GRADE = getattr(job, "GRADE", {"NodeIndex": "1", "Slope": "1.03 1.03 1.03", "Offset": "-0.004 -0.004 -0.004", "Power": "1.0 1.0 1.0", "Saturation": "1.06"})
FX = getattr(job, "AROLL_FX", {"ContrastPop": {"MidtoneDetail": 0.12}, "Vignette": {}})
INSERTS = json.load(open(HERE / "graphics/inserts_timing.json"))
ZONES = json.load(open(HERE / "graphics/zones.json"))
FONT_POWER = ("Avenir Next Condensed", "Heavy"); FONT_SMALL = ("Avenir Next", "Demi Bold")
from PIL import ImageFont
def _pil(path, style):
    for i in range(24):
        try: f = ImageFont.truetype(path, 100, index=i)
        except Exception: break
        if f.getname()[1] == style: return f
    raise SystemExit(f"font {style} not in {path}")
PF = _pil("/System/Library/Fonts/Avenir Next Condensed.ttc", "Heavy"); SF = _pil("/System/Library/Fonts/Avenir Next.ttc", "Demi Bold")
def width_px(font, txt, px): return font.getlength(txt) * px / 100
PX_PER_SIZE = job.PX_PER_SIZE
POWER_PX, POWER_W, SMALL_PX = 104, 1000, 42
def rp(p): return job.rp(p)

def _text_line(comp, src, name, text, px, y_px, words, g, pop=False, font=None):
    size = px / PX_PER_SIZE; toks = text.split(' ')
    frs = [max(0, round((w["s"] - g["start"]) * FPS)) for w in words]
    for i in range(len(words)):
        tx = comp.AddTool("TextPlus", -32768, -32768); tx.SetAttrs({"TOOLS_Name": f"{name}{i}"})
        fam, sty = font or FONT_SMALL
        tx.SetInput("StyledText", ' '.join(toks[:i + 1])); tx.SetInput("Font", fam); tx.SetInput("Style", sty)
        for k in ("Red1", "Green1", "Blue1"): tx.SetInput(k, 1.0)
        tx.SetInput("Enabled3", 1)
        for k, v in (("Red3", 0.0), ("Green3", 0.0), ("Blue3", 0.0), ("Opacity3", 0.6), ("Softness3", 2.0)): tx.SetInput(k, v)
        tx.SetInput("Offset3", {1: 0.003, 2: -0.003, 3: 0.0})
        tx.SetInput("Center", {1: 0.5, 2: 1 - y_px / FH})
        if pop and i == 0:
            tx.Size = comp.BezierSpline({}); tx.SetInput("Size", size * 0.92, 0); tx.SetInput("Size", size * 0.92, frs[0]); tx.SetInput("Size", size, frs[0] + 3)
        else: tx.SetInput("Size", size)
        mg = comp.AddTool("Merge", -32768, -32768); mg.ConnectInput("Background", src); mg.ConnectInput("Foreground", tx)
        a, b = frs[i], (frs[i + 1] if i + 1 < len(words) else None)
        mg.Blend = comp.BezierSpline({}); mg.SetInput("Blend", 1.0 if a == 0 else 0.0, 0)   # Fusion trap: set frame 0 yourself
        if a > 1: mg.SetInput("Blend", 0.0, a - 1)
        mg.SetInput("Blend", 1.0, a)
        if b is not None and b > a: mg.SetInput("Blend", 1.0, b - 1); mg.SetInput("Blend", 0.0, b)
        elif b is not None: mg.SetInput("Blend", 0.0, a + 1)
        src = mg
    return src

def build_caption(item, g):
    comp = item.AddFusionComp(); tools = comp.GetToolList(False)
    mi = next(v for v in tools.values() if v.GetAttrs()["TOOLS_RegID"] == "MediaIn")
    mo = next(v for v in tools.values() if v.GetAttrs()["TOOLS_RegID"] == "MediaOut")
    y_c = CAP_LINE; lines = []
    if g.get("power"):
        pw = g["power"]; ptxt = ' '.join(w["w"] for w in pw)
        rows = [[w] for w in pw] if len(pw) == 2 and width_px(PF, ptxt, POWER_PX) > POWER_W else [pw]
        P = min(POWER_PX, min(POWER_W / width_px(PF, ' '.join(w["w"] for w in r), 1) for r in rows)); LH = 0.98 * P
        ys = [y_c + (k - (len(rows) - 1) / 2) * LH for k in range(len(rows))]
        if g["pre"]: lines.append(("Pre", ' '.join(w["w"] for w in g["pre"]), SMALL_PX, ys[0] - (0.45 * P + 30), g["pre"], False, None))
        for k, r in enumerate(rows): lines.append((f"Power{k}_", ' '.join(w["w"] for w in r), P, ys[k], r, True, FONT_POWER))
        if g["post"]: lines.append(("Post", ' '.join(w["w"] for w in g["post"]), SMALL_PX, ys[-1] + (0.45 * P + 26), g["post"], False, None))
    else:
        ws = g.get("pre") or g["words"]
        lines.append(("Small", ' '.join(w["w"] for w in ws), SMALL_PX, y_c, ws, False, None))
    src = mi
    for name, text, px, y, words, pop, font in lines: src = _text_line(comp, src, name, text, px, y, words, g, pop, font)
    mo.ConnectInput("Input", src)
    item.SetCDL({"NodeIndex": "1", "Slope": "1.4 1.4 1.4", "Offset": "0 0 0", "Power": "1 1 1", "Saturation": "1"})   # Fusion text lands at ~0.78 white under RCM

S_SIDE, TX_SIDE = 1.36, 620          # side zone: scale and where his face lands (timeline px x); plate covers x 1100-1920
IN_S, OUT_S = 0.45, 0.40             # must match the AE plate slide (ae/kit169.jsx plate())
def _smooth(x): x = max(0.0, min(1.0, x)); return x * x * (3 - 2 * x)
SIDES = [z for z in ZONES if z["kind"] == "side"]
def weight(T):
    w = 0.0
    for q in SIDES:
        if q["start"] <= T <= q["end"]:
            wi = 1.0 if q.get("hard_in") else _smooth((T - q["start"]) / IN_S)
            wo = 1.0 if q.get("hard_out") else _smooth((q["end"] - T) / OUT_S)
            w = max(w, min(wi, wo))
    return w
def add_aroll(item, z, it):
    """Fusion comp on an A-roll piece (comp = SOURCE 3840x2160 at 50 fps, frame 0 = clip start). Transform math in source px,
    top-down: out = P + s*(in - P) + D, D = (Center - 0.5) * size. One pivot (zooms.PIVOT) and one face (zooms.FACE) for the video."""
    comp = item.AddFusionComp(); T = comp.GetToolList(False)
    mi = next(v for v in T.values() if v.GetAttrs()["TOOLS_RegID"] == "MediaIn")
    mo = next(v for v in T.values() if v.GetAttrs()["TOOLS_RegID"] == "MediaOut")
    xf = comp.AddTool("Transform", -32768, -32768); xf.SetAttrs({"TOOLS_Name": "Zoom"})
    px, py = z["pivot"]; xf.SetInput("Pivot", {1: px, 2: py})
    P = (px * 3840, (1 - py) * 2160); F = (zooms.FACE["cx"] * 2, zooms.FACE["cy"] * 2)
    keys = z["keys"]; r0 = it["rec_in"]; dur = it["rec_out"] - it["rec_in"]
    def plan_s(t):
        if t <= keys[0][0]: return keys[0][1]
        for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
            if t <= t1: return v0 + (v1 - v0) * (t - t0) / max(1e-6, t1 - t0)
        return keys[-1][1]
    times = {round(k * 0.5, 3) for k in range(int(dur / 0.5) + 1)} | {0.0, round(dur, 3)}
    for q in SIDES:
        if q["end"] > r0 and q["start"] < r0 + dur:
            for base, sp in ((q["start"], IN_S), (q["end"] - OUT_S, OUT_S)):
                for k in range(10):
                    tt = base + sp * k / 9 - r0
                    if 0 <= tt <= dur: times.add(round(tt, 3))
            for tt in (q["start"] - r0, q["end"] - r0):
                if 0 <= tt <= dur: times.add(round(tt, 3))
    xf.Size = comp.BezierSpline({}); xf.Center = comp.XYPath({})
    tgt_side = (TX_SIDE * 2, P[1] + S_SIDE * (F[1] - P[1]))
    for t in sorted(times):
        s = plan_s(t); w = weight(r0 + t); sb = (1 - w) * s + w * S_SIDE
        fn = (P[0] + s * (F[0] - P[0]), P[1] + s * (F[1] - P[1]))
        tgt = (fn[0] + w * (tgt_side[0] - fn[0]), fn[1] + w * (tgt_side[1] - fn[1]))
        D = (tgt[0] - (P[0] + sb * (F[0] - P[0])), tgt[1] - (P[1] + sb * (F[1] - P[1])))
        fr = round(t * SRC_FPS)
        xf.SetInput("Size", sb, fr); xf.SetInput("Center", {1: 0.5 + D[0] / 3840, 2: 0.5 - D[1] / 2160}, fr)
    xf.ConnectInput("Input", mi); last = xf
    for name, params in FX.items():
        fx = comp.AddTool("ofx.com.blackmagicdesign.resolvefx." + name, -32768, -32768)
        if not fx: print("ResolveFX missing:", name); continue
        for k, v in params.items(): fx.SetInput(k, v)
        fx.ConnectInput("Source", last); last = fx
    mo.ConnectInput("Input", last)

def main(render=True, test=None):
    r = dvr.scriptapp("Resolve"); pm = r.GetProjectManager(); proj = pm.GetCurrentProject()
    if proj.GetName() != PROJECT: proj = pm.LoadProject(PROJECT)
    mp = proj.GetMediaPool(); r.OpenPage("edit")
    for k, v in (("useInverseDRT", "1"), ("disableFusionToneMapping", "1"), ("graphicsWhiteLevel", "100")): proj.SetSetting(k, v)
    E = json.loads((HERE / "edl.json").read_text()); G = json.loads((HERE / "graphics/graphics_timing.json").read_text())
    C = json.loads((HERE / "captions.json").read_text())
    have = {}
    def walk(f):
        for c in f.GetClipList() or []: have[c.GetClipProperty("File Path")] = c
        for s in f.GetSubFolderList() or []: walk(s)
    walk(mp.GetRootFolder())
    stale = [c for pth, c in have.items() if pth.startswith(rp(HERE) + "/") and any(s in pth for s in ("/graphics/", "/audio/stem_", "/carriers/", "/tclips/"))]
    car_path = HERE / "carriers/caption_carrier.mov"
    if not car_path.exists():
        import subprocess, imageio_ffmpeg
        car_path.parent.mkdir(exist_ok=True)
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=black@0.0:s={FW}x{FH}:r={FPS},format=yuva444p12le",
                        "-t", "60", "-c:v", "prores_ks", "-profile:v", "4", "-pix_fmt", "yuva444p12le", str(car_path)], check=True)
    for t in [proj.GetTimelineByIndex(i) for i in range(1, (proj.GetTimelineCount() or 0) + 1)]:
        if t and t.GetName() == TL: mp.DeleteTimelines([t])
    if stale: mp.DeleteClips(stale); have = {k: v for k, v in have.items() if v not in stale}
    need = [HERE / i["file"] for i in INSERTS] + [HERE / f"graphics/{g['id']}.mov" for g in G] + [car_path] + \
           [HERE / f"audio/stem_{s}.wav" for s in ("dialogue", "music", "sfx")]
    new = [rp(p) for p in need if rp(p) not in have]
    got = mp.ImportMedia(new) or [] if new else []
    for c in got: have[c.GetClipProperty("File Path")] = c
    missing = [p for p in need if rp(p) not in have]
    if missing: sys.exit(f"ABORT import failed for {len(missing)}: {[str(m) for m in missing[:5]]}")
    M = lambda p: have[rp(HERE / p)]
    for p in [i["file"] for i in INSERTS] + [f"graphics/{g['id']}.mov" for g in G] + ["carriers/caption_carrier.mov"]:
        c = M(p); c.SetClipProperty("Input Color Space", "Rec.709 Gamma 2.4")
        if c.GetClipProperty("FPS") not in ("25", "25.0", 25, 25.0): c.SetClipProperty("FPS", str(FPS))
    SRC = have[str(job.SRC)]; assert SRC.GetClipProperty("Input Color Space") == job.IDT
    tl = mp.CreateEmptyTimeline(TL); proj.SetCurrentTimeline(tl); st = tl.GetStartFrame()
    for _ in range(4): tl.AddTrack("video")
    for _ in range(3): tl.AddTrack("audio", "stereo")
    for k, v in {1: "A-roll", 2: "Inserts + client clips", 3: "Graphics (AE)", 4: "Captions", 5: "Graphics (AE, overlap)"}.items(): tl.SetTrackName("video", k, v)
    for k, v in {1: "Source (unused)", 2: "Dialogue (enhanced)", 3: "Music", 4: "Sound design"}.items(): tl.SetTrackName("audio", k, v)
    A = [it for it in E["items"] if it["kind"] == "a"]
    ent = [{"mediaPoolItem": SRC, "startFrame": round(it["src_in"] * SRC_FPS), "endFrame": round(it["src_out"] * SRC_FPS), "trackIndex": 1,
            "recordFrame": st + round(it["rec_in"] * FPS)} for it in A]
    v1 = mp.AppendToTimeline(ent) or []; assert len(v1) == len(ent), f"V1 {len(v1)}/{len(ent)}"
    a1 = tl.GetItemListInTrack("audio", 1)
    if a1: tl.DeleteClips(a1, False)
    ZP = {z["piece"]: z for z in zooms.plan()}
    for vi, it in zip(v1, A):
        i = E["items"].index(it); vi.SetCDL(GRADE); add_aroll(vi, ZP[i], it)
    ins = [{"mediaPoolItem": M(i["file"]), "startFrame": 0, "endFrame": round((i["end"] - i["start"]) * FPS), "trackIndex": 2,
            "recordFrame": st + round(i["start"] * FPS), "mediaType": 1} for i in INSERTS]
    assert len(mp.AppendToTimeline(ins) or []) == len(ins), "inserts"
    gr, last_end = [], -1
    for g in sorted(G, key=lambda g: g["start"]):
        f0, f1 = round(g["start"] * FPS), round(g["end"] * FPS); trk = 3 if f0 >= last_end else 5
        if trk == 3: last_end = f1
        gr.append({"mediaPoolItem": M(f"graphics/{g['id']}.mov"), "startFrame": 0, "endFrame": f1 - f0, "trackIndex": trk, "recordFrame": st + f0, "mediaType": 1})
    assert len(mp.AppendToTimeline(gr) or []) == len(gr), "graphics"
    au = [{"mediaPoolItem": M(f"audio/stem_{s}.wav"), "startFrame": 0, "endFrame": round(E["duration"] * FPS), "trackIndex": k, "recordFrame": st, "mediaType": 2}
          for k, s in ((2, "dialogue"), (3, "music"), (4, "sfx"))]
    print("audio stems placed:", len(mp.AppendToTimeline(au) or []))
    car = M("carriers/caption_carrier.mov"); cap_ent = []; endf = round(E["duration"] * FPS)
    for g in C:
        f0 = round(g["start"] * FPS); f1 = min(endf, max(f0 + 3, round(g["end"] * FPS)))   # clamp to the picture's last frame (IMG3543 trap)
        cap_ent.append({"mediaPoolItem": car, "startFrame": 0, "endFrame": f1 - f0, "trackIndex": 4, "recordFrame": st + f0, "mediaType": 1})
    caps = mp.AppendToTimeline(cap_ent) or []; assert len(caps) == len(C), f"captions {len(caps)}/{len(C)}"
    bad = []
    for ci, (item, g) in enumerate(zip(caps, C)):
        try: build_caption(item, g)
        except AttributeError: bad.append((ci, g["start"]))
    if bad: print("CAPTION BUILD FAILED:", len(bad), bad[:8])
    # every V1 join must be gap 0 (a clip read at the wrong fps leaves a hidden one-frame black at each cut)
    v1i = tl.GetItemListInTrack("video", 1); gaps = [(a.GetEnd(), b.GetStart()) for a, b in zip(v1i, v1i[1:]) if b.GetStart() != a.GetEnd()]
    tset = {(round(i["rec_in"] * FPS), round(i["rec_out"] * FPS)) for i in E["items"] if i["kind"] == "t"}
    real = [g for g in gaps if (g[0] - st, g[1] - st) not in tset]
    total = (tl.GetEndFrame() - st) / FPS
    print(f"timeline {TL}: {total:.2f}s | V1 {len(v1i)} (unexpected gaps {len(real)}) V2 {len(tl.GetItemListInTrack('video',2))} "
          f"V3 {len(tl.GetItemListInTrack('video',3))} V4 {len(tl.GetItemListInTrack('video',4))} V5 {len(tl.GetItemListInTrack('video',5) or [])}")
    if real: print("GAPS:", real[:10])
    pm.SaveProject()
    if not render: return
    r.OpenPage("deliver"); proj.DeleteAllRenderJobs(); proj.SetCurrentTimeline(tl)
    proj.SetCurrentRenderFormatAndCodec("mp4", "H264")
    name = f"{job.OUT_NAME}_final" if not test else f"test_{int(test[0])}_{int(test[1])}"
    s = {"SelectAllFrames": not test, "TargetDir": str(HERE / "render"), "CustomName": name, "FormatWidth": FW, "FormatHeight": FH,
         "ExportVideo": True, "ExportAudio": True, "AudioSampleRate": 48000, "AudioCodec": "aac", "AudioBitDepth": 16, "VideoQuality": 0}
    if test: s.update({"MarkIn": st + round(test[0] * FPS), "MarkOut": st + round(test[1] * FPS)})
    (HERE / "render").mkdir(exist_ok=True); proj.SetRenderSettings(s); jid = proj.AddRenderJob()
    proj.StartRendering([jid], False); t0 = time.time()
    while proj.IsRenderingInProgress() and time.time() - t0 < 5400: time.sleep(5)
    print("render", proj.GetRenderJobStatus(jid), round(time.time() - t0), "s")
    r.OpenPage("edit"); pm.SaveProject()

if __name__ == "__main__":
    test = None
    if "--test" in sys.argv: k = sys.argv.index("--test"); test = (float(sys.argv[k + 1]), float(sys.argv[k + 2]))
    main(render="--no-render" not in sys.argv, test=test)
