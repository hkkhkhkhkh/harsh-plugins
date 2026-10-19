"""Assemble the finished timeline in DaVinci Resolve and render it.
V1 graded A-roll (RCM S-Gamut3/S-Log3 -> DWG/Intermediate -> Rec.709 2.4) (face-anchored Fusion zooms)
V2 Higgsfield inserts   V3 After Effects graphics (ProRes 4444 alpha)   V4 captions: one Fusion Text+ per group, word write-on
A1 empty (A-roll source audio removed; processed dialogue lives on A2)   A2 dialogue   A3 music   A4 sfx
Placement uses AppendToTimeline recordFrame (exact frames); every item is readback-checked."""
import json, sys, time, functools
from pathlib import Path
import DaVinciResolveScript as dvr
print = functools.partial(print, flush=True)
HERE = Path(__file__).parent
import job
PROJECT = job.PROJECT; TL = f"{job.TAG} - Final"; FPS = job.FPS; SRC_FPS = job.SRC_FPS
SRC = job.SRC
CAP_Y = 1 - 1280 / 1920  # lower-third line (y 1280 of 1920); Fusion y runs bottom-up
CAP_SIZE = 0.17; GRADE = {"NodeIndex": "1", "Slope": "1.03 1.03 1.03", "Offset": "-0.004 -0.004 -0.004", "Power": "1.0 1.0 1.0", "Saturation": "1.06"}
GRADE = getattr(job, "GRADE", GRADE)  # per-job grade override
INSERTS = [(i["file"], i["start"], i["end"], i["src_off"]) for i in json.load(open(Path(__file__).parent / "graphics/inserts_timing.json"))]
import zooms  # face-anchored push/punch/snap plan

ZONES = json.loads((Path(__file__).parent / "graphics/zones.json").read_text()) if (Path(__file__).parent / "graphics/zones.json").exists() else []
FACES = {f["i"]: f for f in json.loads((Path(__file__).parent / "transcripts/faces.json").read_text())}
def cap_y(t): return CAP_Y   # v5: captions ALWAYS on the lower-third line; they are simply absent while a graphic is on screen
import math, statistics
_gf = [f for f in FACES.values() if f.get("cx") and f.get("w", 0) >= 300]
GFACE = {"cx": statistics.median(f["cx"] for f in _gf), "cy": statistics.median(f["cy"] for f in _gf)} if _gf else {"cx": 540, "cy": 900}
_ht = HERE.parent / "matte" / f"headtop_{job.CLIP.split('_')[1].split('.')[0]}.json"
HEAD_TOP = json.loads(_ht.read_text())["head_top"] if _ht.exists() else GFACE["cy"] - 330   # y of the top of his hair (1080x1920)
# fonts (Harsh, 27 Sep: "use better fonts"): condensed heavy for power words, Avenir Next Demi Bold for the small words
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
_EDL = json.loads((HERE / "edl.json").read_text())["items"]
_MATTE = HERE.parent / "matte" / f"matte_{job.CLIP.split('_')[1].split('.')[0]}.mkv"
def head_top_at(a, b):
    """Top of his hair (timeline px) across record time a..b, from the person matte, including the slow zoom (pivot = face)."""
    import subprocess, numpy as np, imageio_ffmpeg
    ys = []
    for t in (a + (b - a) * k / 4 for k in range(5)):
        it = next((i for i in _EDL if i["rec_in"] <= t < i["rec_out"]), None)
        if not it or not _MATTE.exists(): continue
        fr = round((it["src_in"] + t - it["rec_in"]) * SRC_FPS)
        r = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-nostdin", "-loglevel", "error", "-i", str(_MATTE), "-vf", f"select=eq(n\\,{fr}),format=gray",
                            "-frames:v", "1", "-f", "rawvideo", "-"], capture_output=True).stdout
        if len(r) != 1080 * 1920: continue
        m = np.frombuffer(r, np.uint8).reshape(1920, 1080)[:, 300:780] > 128; rows = np.where(m.mean(1) > 0.05)[0]
        if len(rows):
            py = GFACE["cy"]; ys.append(py - (py - rows[0]) * base_size(t))
    return min(ys) if ys else HEAD_TOP   # highest point he reaches while the word is up

def _text_line(comp, src, name, text, px, y_px, words, g, pop=False, font=None):
    """One caption line, re-centred as each word lands (the reference re-centres: "the" -> "the scientific"). One Text+ per
    word-state, each merged in only for its own frames. y_px = line centre, pixels from the top. Returns the last Merge."""
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
        tx.SetInput("Center", {1: 0.5, 2: 1 - y_px / 1920})
        if pop and i == 0:   # power word lands with a 3-frame settle (92% -> 100%)
            tx.Size = comp.BezierSpline({}); tx.SetInput("Size", size * 0.92, 0); tx.SetInput("Size", size * 0.92, frs[0]); tx.SetInput("Size", size, frs[0] + 3)
        else: tx.SetInput("Size", size)
        mg = comp.AddTool("Merge", -32768, -32768); mg.ConnectInput("Background", src); mg.ConnectInput("Foreground", tx)
        a, b = frs[i], (frs[i + 1] if i + 1 < len(words) else None)
        # animating an input drops a key at frame 0 holding its current value (Blend 1.0): overwrite it explicitly
        mg.Blend = comp.BezierSpline({}); mg.SetInput("Blend", 1.0 if a == 0 else 0.0, 0)
        if a > 1: mg.SetInput("Blend", 0.0, a - 1)
        mg.SetInput("Blend", 1.0, a)
        if b is not None and b > a: mg.SetInput("Blend", 1.0, b - 1); mg.SetInput("Blend", 0.0, b)
        elif b is not None: mg.SetInput("Blend", 0.0, a + 1)
        src = mg
    return src

PX_PER_SIZE = 700          # Text+ Size 1.0 ~ 700 px type on a 1080x1920 frame
POWER_PX, POWER_W, SMALL_PX, HERO_PX, HERO_W = 150, 880, 46, 330, 1000
def build_caption(item, g):
    """Power-word caption (Harsh's reference, 27 Sep): the power word big and UPPERCASE on the caption line, small lead-in words
    on the line above, small follow-on words on the line below, each word appearing as it is spoken. No power word = small words
    on the caption line."""
    comp = item.AddFusionComp(); tools = comp.GetToolList(False)
    mi = next(v for v in tools.values() if v.GetAttrs()["TOOLS_RegID"] == "MediaIn")
    mo = next(v for v in tools.values() if v.GetAttrs()["TOOLS_RegID"] == "MediaOut")
    tm = (g["start"] + g["end"]) / 2   # zone at the group's midpoint (a group straddling a scene change follows the longer side)
    y_c = (1 - (cap_y(tm) if "cap_y" in globals() else CAP_Y)) * 1920
    lines = []
    if g.get("layout") == "hero":   # the word alone, huge, straddling the top of his head; the cut-out on V5 puts him in front of it
        ptxt = g["power"][0]["w"]; P = min(HERO_PX, HERO_W / width_px(PF, ptxt, 1))
        # v6: no cut-out (curly hair can't be keyed cleanly from phone footage), so the word sits clear ABOVE his head
        P = min(P, 270); lines.append(("Hero", ptxt, P, max(215, head_top_at(g["start"], g["end"]) - 0.45 * P), g["power"], True, FONT_POWER))   # hair clips the bottom third only
    elif g.get("power"):
        pw = g["power"]; ptxt = ' '.join(w["w"] for w in pw)
        rows = [[w] for w in pw] if len(pw) == 2 and width_px(PF, ptxt, POWER_PX) > POWER_W else [pw]   # long 2-word phrase: stack, don't shrink
        P = min(POWER_PX, min(POWER_W / width_px(PF, ' '.join(w["w"] for w in r), 1) for r in rows)); LH = 0.98 * P
        ys = [y_c + (k - (len(rows) - 1) / 2) * LH for k in range(len(rows))]
        if g["pre"]: lines.append(("Pre", ' '.join(w["w"] for w in g["pre"]), SMALL_PX, ys[0] - (0.45 * P + 36), g["pre"], False, None))
        for k, r in enumerate(rows): lines.append((f"Power{k}_", ' '.join(w["w"] for w in r), P, ys[k], r, True, FONT_POWER))
        if g["post"]: lines.append(("Post", ' '.join(w["w"] for w in g["post"]), SMALL_PX, ys[-1] + (0.45 * P + 30), g["post"], False, None))
    else:
        ws = g.get("pre") or g["words"]
        lines.append(("Small", ' '.join(w["w"] for w in ws), SMALL_PX, y_c, ws, False, None))
    src = mi
    for name, text, px, y, words, pop, font in lines: src = _text_line(comp, src, name, text, px, y, words, g, pop, font)
    mo.ConnectInput("Input", src)
    # Fusion output lands in the managed timeline at ~0.78 of display white; a clip-level slope restores true white
    item.SetCDL({"NodeIndex": "1", "Slope": "1.4 1.4 1.4", "Offset": "0 0 0", "Power": "1 1 1", "Saturation": "1"})

BOX = {"cx": 540, "cy": 350, "size": 560}   # square split box in the upper third (y 70-630); must match WIN in ae_lib/lib.jsx
S_SPLIT = 0.60                               # clip scale inside the box
Z_AMP, Z_PERIOD = 0.045, 18.0                # v5 "visually calm": a slow breathe 1.00 -> 1.045 -> 1.00 every 18 s, continuous across cuts
def _smooth(x): x = max(0.0, min(1.0, x)); return x * x * (3 - 2 * x)
def base_size(T): return 1.0 + Z_AMP * (1 - math.cos(2 * math.pi * T / Z_PERIOD)) / 2
def add_zoom(item, z=None, it=None, face=None):
    """Fusion Transform on an A-roll (or cut-out) clip. Size and position are functions of RECORD time with one pivot for the whole
    video, so nothing jumps at a cut (v4 re-pivoted on every clip's own face = the 'zoom glitches'). In split zones the frame
    scales down so his face sits in the box centre, easing exactly with the AE plate (none on hard cuts between graphics)."""
    comp = item.AddFusionComp(); T = comp.GetToolList(False)
    mi = next(v for v in T.values() if v.GetAttrs()["TOOLS_RegID"] == "MediaIn")
    mo = next(v for v in T.values() if v.GetAttrs()["TOOLS_RegID"] == "MediaOut")
    xf = comp.AddTool("Transform", -32768, -32768); xf.SetAttrs({"TOOLS_Name": "Zoom"})
    cx, cy = GFACE["cx"], GFACE["cy"]; fx, fy = cx / 1080, 1 - cy / 1920
    xf.SetInput("Pivot", {1: fx, 2: fy})
    r0 = it["rec_in"]; dur = it["rec_out"] - it["rec_in"]
    zs = [zz for zz in ZONES if zz["kind"] == "split" and zz["end"] > r0 and zz["start"] < r0 + dur]
    def state(t):
        ta = r0 + t; w = 0.0; S = S_SPLIT * base_size(ta)
        for zz in zs:
            if zz["start"] <= ta <= zz["end"]:
                wi = 1.0 if zz.get("hard_in") else _smooth((ta - zz["start"]) / 0.55)
                wo = 1.0 if zz.get("hard_out") else _smooth((zz["end"] - ta) / 0.5)
                w = min(wi, wo)
        tx = min(max(BOX["cx"], BOX["cx"] + BOX["size"] / 2 - (1080 - cx) * S), BOX["cx"] - BOX["size"] / 2 + cx * S)
        ty = min(max(BOX["cy"], BOX["cy"] + BOX["size"] / 2 - (1920 - cy) * S), BOX["cy"] - BOX["size"] / 2 + cy * S)
        csx, csy = 0.5 + (tx / 1080 - fx), 0.5 + ((1 - ty / 1920) - fy)
        return (1 - w) * base_size(ta) + w * S, (1 - w) * 0.5 + w * csx, (1 - w) * 0.5 + w * csy
    times = {round(k * 0.25, 3) for k in range(int(dur / 0.25) + 1)} | {0.0, round(dur, 3)}
    for zz in zs:
        for base, span in ((zz["start"], 0.55), (zz["end"] - 0.5, 0.5)):
            for k in range(11):
                t = base + span * k / 10 - r0
                if 0 <= t <= dur: times.add(round(t, 3))
    xf.Size = comp.BezierSpline({}); xf.Center = comp.XYPath({})
    for t in sorted(times):
        sz, ccx, ccy = state(t); fr = round(t * SRC_FPS)
        xf.SetInput("Size", sz, fr); xf.SetInput("Center", {1: ccx, 2: ccy}, fr)
    xf.ConnectInput("Input", mi); mo.ConnectInput("Input", xf)

def main(render=True):
    r = dvr.scriptapp("Resolve"); pm = r.GetProjectManager(); proj = pm.GetCurrentProject()
    if proj.GetName() != PROJECT: proj = pm.LoadProject(PROJECT)
    mp = proj.GetMediaPool(); r.OpenPage("edit")
    # SDR inserts/graphics round-trip through the DRT unchanged; keep titles at 100-nit white
    for k, v in (("useInverseDRT", "1"), ("disableFusionToneMapping", "1"), ("graphicsWhiteLevel", "100")): proj.SetSetting(k, v)
    E = json.loads((HERE / "edl.json").read_text()); G = json.loads((HERE / "graphics/graphics_timing.json").read_text())
    C = json.loads((HERE / "captions.json").read_text())
    have = {}
    def walk(f):
        for c in f.GetClipList() or []: have[c.GetClipProperty("File Path")] = c
        for s in f.GetSubFolderList() or []: walk(s)
    walk(mp.GetRootFolder())
    # only THIS job's re-rendered files (several jobs can share one Resolve project)
    stale = [c for pth, c in have.items() if pth.startswith(str(HERE) + "/") and ("/graphics/" in pth or "/audio/stem_" in pth or "/carriers/" in pth)]
    car_path = HERE / "carriers/caption_carrier.mov"
    if not car_path.exists():  # transparent ProRes 4444 at the timeline rate (caption carrier clips are cut from it)
        import subprocess, imageio_ffmpeg
        car_path.parent.mkdir(exist_ok=True)
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=black@0.0:s=1080x1920:r={FPS},format=yuva444p12le",
                        "-t", "300", "-c:v", "prores_ks", "-profile:v", "4", "-pix_fmt", "yuva444p12le", str(car_path)], check=True)
    for i in range(1, (proj.GetTimelineCount() or 0) + 1):
        t = proj.GetTimelineByIndex(i)
        if t and t.GetName() in (TL, "TEST zoom"): mp.DeleteTimelines([t]); break
    for t in [proj.GetTimelineByIndex(i) for i in range(1, (proj.GetTimelineCount() or 0) + 1)]:
        if t and t.GetName() == "TEST zoom": mp.DeleteTimelines([t])
    if stale: mp.DeleteClips(stale); have = {k: v for k, v in have.items() if v not in stale}
    need = [HERE / p for p, *_ in INSERTS] + [HERE / f"graphics/{g['id']}.mov" for g in G] + [HERE / "carriers/caption_carrier.mov"] + \
           [HERE / f"audio/stem_{s}.wav" for s in ("dialogue", "music", "sfx")]
    new = [str(p) for p in need if str(p) not in have]
    for c in (mp.ImportMedia(new) or []) if new else []: have[c.GetClipProperty("File Path")] = c
    M = lambda p: have[str(HERE / p) if not str(p).startswith("/") else str(p)]
    for p, *_ in INSERTS: M(p).SetClipProperty("Input Color Space", "Rec.709 Gamma 2.4")
    for g in G: M(f"graphics/{g['id']}.mov").SetClipProperty("Input Color Space", "Rec.709 Gamma 2.4")
    M("carriers/caption_carrier.mov").SetClipProperty("Input Color Space", "Rec.709 Gamma 2.4")
    srcp = [str(job.source(k)["video"]) for k in {it.get("clip") for it in E["items"]}] + ([str(job.CUTOUT)] if getattr(job, "CUTOUT", None) else [])
    for c in (mp.ImportMedia([q for q in srcp if q not in have]) or []): have[c.GetClipProperty("File Path")] = c
    for q in srcp:
        have[q].SetClipProperty("Input Color Space", job.IDT)
    if getattr(job, "CUTOUT", None): have[str(job.CUTOUT)].SetClipProperty("Alpha mode", "Straight")
    SRCS = {k: have[str(job.source(k)["video"])] for k in {it.get("clip") for it in E["items"]}}
    for k, c in SRCS.items(): assert c.GetClipProperty("Input Color Space") == job.IDT, (k, c.GetClipProperty("Input Color Space"))
    for i in range(1, (proj.GetTimelineCount() or 0) + 1):
        t = proj.GetTimelineByIndex(i)
        if t.GetName() == TL: mp.DeleteTimelines([t]); break
    tl = mp.CreateEmptyTimeline(TL); proj.SetCurrentTimeline(tl); st = tl.GetStartFrame()
    for _ in range(5): tl.AddTrack("video")
    for _ in range(3): tl.AddTrack("audio", "stereo")
    names = {1: "A-roll", 2: "Inserts", 3: "Graphics (AE)", 4: "Captions", 5: "Cut-out (text behind)", 6: "Captions over cut-out"}
    for k, v in names.items(): tl.SetTrackName("video", k, v)
    for k, v in {1: "Source (unused)", 2: "Dialogue (enhanced)", 3: "Music", 4: "Sound design"}.items(): tl.SetTrackName("audio", k, v)
    # V1
    ent = []
    for it in E["items"]:
            ent.append({"mediaPoolItem": SRCS[it.get("clip")], "startFrame": round(it["src_in"] * SRC_FPS), "endFrame": round(it["src_out"] * SRC_FPS), "trackIndex": 1, "recordFrame": st + round(it["rec_in"] * FPS)})
    v1 = mp.AppendToTimeline(ent) or []
    assert len(v1) == len(ent), f"V1 {len(v1)}/{len(ent)}"
    # remove A-roll source audio from A1 (processed dialogue is on A2)
    a1 = tl.GetItemListInTrack("audio", 1)
    if a1: tl.DeleteClips(a1, False)
    for vi, it, z in zip(v1, E["items"], zooms.plan()):
        vi.SetCDL(GRADE); add_zoom(vi, z, it)
    # V2 inserts
    ins = [{"mediaPoolItem": M(p), "startFrame": round(off * FPS), "endFrame": round(off * FPS) + round((b - a) * FPS), "trackIndex": 2,
            "recordFrame": st + round(a * FPS), "mediaType": 1} for p, a, b, off in INSERTS]
    assert len(mp.AppendToTimeline(ins) or []) == len(ins)
    # V3 graphics
    gr = [{"mediaPoolItem": M(f"graphics/{g['id']}.mov"), "startFrame": 0, "endFrame": round((g["end"] - g["start"]) * FPS), "trackIndex": 3,
           "recordFrame": st + round(g["start"] * FPS), "mediaType": 1} for g in G]
    assert len(mp.AppendToTimeline(gr) or []) == len(gr)
    # A2-A4 stems
    au = [{"mediaPoolItem": M(f"audio/stem_{s}.wav"), "startFrame": 0, "endFrame": round(E["duration"] * FPS), "trackIndex": k, "recordFrame": st, "mediaType": 2}
          for k, s in ((2, "dialogue"), (3, "music"), (4, "sfx"))]
    got = mp.AppendToTimeline(au) or []; print("audio stems placed:", len(got))
    # V4 captions
    car = M("carriers/caption_carrier.mov"); cap_ent = []
    for g in C:
        f0 = round(g["start"] * FPS); f1 = max(f0 + 3, round(g["end"] * FPS))
        cap_ent.append({"mediaPoolItem": car, "startFrame": 0, "endFrame": f1 - f0, "trackIndex": 4, "recordFrame": st + f0, "mediaType": 1})
    caps = mp.AppendToTimeline(cap_ent) or []
    assert len(caps) == len(C), f"captions {len(caps)}/{len(C)}"
    for item, g in zip(caps, C): build_caption(item, g)
    H = [g for g in C if g.get("layout") == "hero"]
    if H and getattr(job, "CUTOUT", None):
        cut = have[str(job.CUTOUT)]; ce, cm = [], []
        for g in H:
            for it in E["items"]:
                a, b = max(g["start"], it["rec_in"]), min(g["end"], it["rec_out"])
                if b - a < 1 / FPS: continue
                s0 = it["src_in"] + (a - it["rec_in"])
                ce.append({"mediaPoolItem": cut, "startFrame": round(s0 * SRC_FPS), "endFrame": round((s0 + b - a) * SRC_FPS), "trackIndex": 5,
                           "recordFrame": st + round(a * FPS), "mediaType": 1}); cm.append({"rec_in": a, "rec_out": b})
        got = mp.AppendToTimeline(ce) or []; assert len(got) == len(ce), f"cut-out {len(got)}/{len(ce)}"
        for vi, m in zip(got, cm): vi.SetCDL(GRADE); add_zoom(vi, None, m)
    if H:
        small = [dict(g, layout="small", pre=g["pre"] + [dict(w, w=w["w"].lower()) for w in g["power"]] + g["post"], power=[], post=[]) for g in H if g["pre"] or g["post"]]
        se = [{"mediaPoolItem": car, "startFrame": 0, "endFrame": max(3, round(g["end"] * FPS) - round(g["start"] * FPS)), "trackIndex": 6,
               "recordFrame": st + round(g["start"] * FPS), "mediaType": 1} for g in small]
        sm = mp.AppendToTimeline(se) or []; assert len(sm) == len(se)
        for item, g in zip(sm, small): build_caption(item, g)
        print("hero words:", [g["power"][0]["w"] for g in H])
    total = (tl.GetEndFrame() - st) / FPS
    print(f"timeline {TL}: {total:.2f}s | V1 {len(tl.GetItemListInTrack('video',1))} V2 {len(tl.GetItemListInTrack('video',2))} "
          f"V3 {len(tl.GetItemListInTrack('video',3))} V4 {len(tl.GetItemListInTrack('video',4))} | A1 {len(tl.GetItemListInTrack('audio',1))} "
          f"A2 {len(tl.GetItemListInTrack('audio',2))} A3 {len(tl.GetItemListInTrack('audio',3))} A4 {len(tl.GetItemListInTrack('audio',4))}")
    pm.SaveProject()
    if not render: return
    r.OpenPage("deliver"); proj.DeleteAllRenderJobs(); proj.SetCurrentTimeline(tl)
    jobs = []
    for fmt, codec, name, extra in (("mp4", "H264", f"{job.OUT_NAME}_final", {"VideoQuality": 0, "AudioCodec": "aac", "AudioBitDepth": 16}),
                                    ("mov", "ProRes422HQ", f"{job.OUT_NAME}_master", {"AudioCodec": "lpcm", "AudioBitDepth": 24})):
        proj.SetCurrentRenderFormatAndCodec(fmt, codec)
        s = {"SelectAllFrames": True, "TargetDir": str(HERE / "render"), "CustomName": name, "FormatWidth": 1080, "FormatHeight": 1920,
             "ExportVideo": True, "ExportAudio": True, "AudioSampleRate": 48000}
        s.update(extra); proj.SetRenderSettings(s); jobs.append(proj.AddRenderJob())
    proj.StartRendering(jobs, False); t0 = time.time()
    while proj.IsRenderingInProgress() and time.time() - t0 < 3600: time.sleep(3)
    for j in jobs: print("render", proj.GetRenderJobStatus(j))
    r.OpenPage("edit"); pm.SaveProject()

if __name__ == "__main__": main(render="--no-render" not in sys.argv)
