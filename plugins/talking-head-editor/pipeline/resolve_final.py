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
# caption line: y 1280 of 1920 (approved). job.AD_SAFE = True lifts it to 1150 so Meta's ad UI (bottom 35%, below y 1248)
# never covers it; job.CAPTION_Y overrides both. Fusion y runs bottom-up.
CAP_LINE = getattr(job, "CAPTION_Y", 1150 if getattr(job, "AD_SAFE", False) else 1280)
CAP_Y = 1 - CAP_LINE / 1920
CAP_SIZE = 0.17; GRADE = {"NodeIndex": "1", "Slope": "1.03 1.03 1.03", "Offset": "-0.004 -0.004 -0.004", "Power": "1.0 1.0 1.0", "Saturation": "1.06"}
GRADE = getattr(job, "GRADE", GRADE)  # per-job grade override (job.py)
INSERTS = [(i["file"], i["start"], i["end"], i["src_off"]) for i in json.load(open(Path(__file__).parent / "graphics/inserts_timing.json"))]
import zooms  # face-anchored push/punch/snap plan

ZONES = json.loads((Path(__file__).parent / "graphics/zones.json").read_text()) if (Path(__file__).parent / "graphics/zones.json").exists() else []
def cap_y(t):  # captions sit on the lower-third line, but move clear of split panels (y 1130) and full-screen explainers (y 1640)
    for z in ZONES:
        if z["start"] - 0.05 <= t < z["end"]: return 1 - {"split": 1130, "full": 1640, "lift": 1190}.get(z["kind"], 1640) / 1920
    return CAP_Y

# fonts (Harsh, 27 Sep: "use better fonts"): condensed heavy for power words, Avenir Next Demi Bold for small words
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
HEAD_TOP = getattr(job, "HEAD_TOP", 340)   # y of the top of his hair (tools/matte/headtop.py) for hero words behind the head
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
def build_power_caption(item, g):
    """Power-word caption (Harsh's reference, 27 Sep): the power word big and UPPERCASE on the caption line, small lead-in words
    on the line above, small follow-on words on the line below, each word appearing as it is spoken. No power word = small words
    on the caption line."""
    comp = item.AddFusionComp(); tools = comp.GetToolList(False)
    mi = next(v for v in tools.values() if v.GetAttrs()["TOOLS_RegID"] == "MediaIn")
    mo = next(v for v in tools.values() if v.GetAttrs()["TOOLS_RegID"] == "MediaOut")
    tm = (g["start"] + g["end"]) / 2   # zone at the group's midpoint (a group straddling a scene change follows the longer side)
    y_c = (1 - (cap_y(tm) if "cap_y" in globals() else CAP_Y)) * 1920
    lines = []
    if g.get("layout") == "hero":   # the word alone, huge, just above his head
        ptxt = g["power"][0]["w"]; P = min(HERO_PX, HERO_W / width_px(PF, ptxt, 1))
        P = min(P, 270); lines.append(("Hero", ptxt, P, max(215, HEAD_TOP - 0.45 * P), g["power"], True, FONT_POWER))   # clear ABOVE his head (no cut-out: see SKILL.md)
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

def build_caption(item, g):
    if "layout" in g: return build_power_caption(item, g)   # power_captions.py output (the default style since 27 Sep)
    comp = item.AddFusionComp(); tools = comp.GetToolList(False)
    mi = next(v for v in tools.values() if v.GetAttrs()["TOOLS_RegID"] == "MediaIn")
    mo = next(v for v in tools.values() if v.GetAttrs()["TOOLS_RegID"] == "MediaOut")
    tx = comp.AddTool("TextPlus", -32768, -32768); mg = comp.AddTool("Merge", -32768, -32768)
    tx.SetAttrs({"TOOLS_Name": "Caption"})
    tx.SetInput("StyledText", g["text"]); tx.SetInput("Font", "Inter SemiBold"); tx.SetInput("Style", "Regular")
    tx.SetInput("Size", CAP_SIZE * (getattr(job, "CAPTION_KEYWORD_SCALE", 1.5) if g.get("big") else 1.0)); tx.SetInput("Red1", 1.0); tx.SetInput("Green1", 1.0); tx.SetInput("Blue1", 1.0)
    tx.SetInput("Enabled3", 1)
    for k, v in (("Red3", 0.0), ("Green3", 0.0), ("Blue3", 0.0), ("Opacity3", 0.5), ("Softness3", 2.0)): tx.SetInput(k, v)
    tx.SetInput("Offset3", {1: 0.004, 2: -0.004, 3: 0.0})
    # rise 11 px over 3 frames, then hold
    cy = cap_y(g["start"]) if "cap_y" in globals() else CAP_Y
    tx.Center = comp.XYPath({}); tx.SetInput("Center", {1: 0.5, 2: cy - 0.0057}, 0); tx.SetInput("Center", {1: 0.5, 2: cy}, 3)
    # word write-on: step keys at each word onset
    text = g["text"]; n = len(text); tx.End = comp.BezierSpline({}); pos = 0; prev = None
    for wi, w in enumerate(g["words"]):
        pos = text.find(w["w"], pos) + len(w["w"]); val = pos / n if wi < len(g["words"]) - 1 else 1.0
        fr = max(0, round((w["s"] - g["start"]) * FPS))
        if prev is not None and fr > 0: tx.SetInput("End", prev, fr - 1)
        tx.SetInput("End", val, fr); prev = val
    mg.ConnectInput("Background", mi); mg.ConnectInput("Foreground", tx); mo.ConnectInput("Input", mg)
    # Fusion output lands in the managed timeline at ~0.78 of display white; a clip-level slope restores true white
    item.SetCDL({"NodeIndex": "1", "Slope": "1.4 1.4 1.4", "Offset": "0 0 0", "Power": "1 1 1", "Saturation": "1"})

def add_zoom(item, z):
    """Fusion Transform on an A-roll clip: scale about the face. Comp time runs at the SOURCE rate (job.SRC_FPS), 0 = clip start."""
    comp = item.AddFusionComp(); T = comp.GetToolList(False)
    mi = next(v for v in T.values() if v.GetAttrs()["TOOLS_RegID"] == "MediaIn")
    mo = next(v for v in T.values() if v.GetAttrs()["TOOLS_RegID"] == "MediaOut")
    xf = comp.AddTool("Transform", -32768, -32768); xf.SetAttrs({"TOOLS_Name": "Zoom"})
    px, py = z["pivot"]; xf.SetInput("Pivot", {1: px, 2: py})  # Center stays 0.5: Center places the image, Pivot is the scale point
    xf.Size = comp.BezierSpline({})
    for t, v in z["keys"]: xf.SetInput("Size", v, round(t * SRC_FPS))
    if getattr(job, "TOP_DARKEN", False):  # soft darkening of a bright ceiling (iPhone selfie footage)
        bc = comp.AddTool("BrightnessContrast", -32768, -32768); bc.SetInput("Gain", 0.78); bc.SetInput("Saturation", 0.9)
        rm = comp.AddTool("RectangleMask", -32768, -32768); rm.SetInput("Center", {1: 0.5, 2: 0.97}); rm.SetInput("Width", 1.4); rm.SetInput("Height", 0.42); rm.SetInput("SoftEdge", 0.18)
        bc.ConnectInput("EffectMask", rm); xf.ConnectInput("Input", mi); bc.ConnectInput("Input", xf); mo.ConnectInput("Input", bc)
    else:
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
    SRCS = {k: have[str(job.source(k)["video"])] for k in {it.get("clip") for it in E["items"]}}
    for k, c in SRCS.items(): assert c.GetClipProperty("Input Color Space") == job.IDT, (k, c.GetClipProperty("Input Color Space"))
    for i in range(1, (proj.GetTimelineCount() or 0) + 1):
        t = proj.GetTimelineByIndex(i)
        if t.GetName() == TL: mp.DeleteTimelines([t]); break
    tl = mp.CreateEmptyTimeline(TL); proj.SetCurrentTimeline(tl); st = tl.GetStartFrame()
    for _ in range(3): tl.AddTrack("video")
    for _ in range(3): tl.AddTrack("audio", "stereo")
    names = {1: "A-roll", 2: "Inserts", 3: "Graphics (AE)", 4: "Captions"}
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
        vi.SetCDL(GRADE); add_zoom(vi, z)
    # V2 inserts
    ins = [{"mediaPoolItem": M(p), "startFrame": round(off * FPS), "endFrame": round(off * FPS) + round((b - a) * FPS), "trackIndex": 2,
            "recordFrame": st + round(a * FPS), "mediaType": 1} for p, a, b, off in INSERTS]
    assert len(mp.AppendToTimeline(ins) or []) == len(ins)
    # V3 graphics
    # a graphic that overlaps the one before it (e.g. price card held under the CTA) goes to its own track (V5),
    # otherwise AppendToTimeline silently overwrites it
    gr, last_end, extra = [], -1, False
    for g in sorted(G, key=lambda g: g["start"]):
        f0, f1 = round(g["start"] * FPS), round(g["end"] * FPS)
        trk = 3 if f0 >= last_end else 5
        if trk == 3: last_end = f1
        else: extra = True
        gr.append({"mediaPoolItem": M(f"graphics/{g['id']}.mov"), "startFrame": 0, "endFrame": f1 - f0, "trackIndex": trk,
                   "recordFrame": st + f0, "mediaType": 1})
    if extra and tl.GetTrackCount("video") < 5:
        tl.AddTrack("video"); tl.SetTrackName("video", 5, "Graphics (AE, overlap)")
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
    total = (tl.GetEndFrame() - st) / FPS
    print(f"timeline {TL}: {total:.2f}s | V1 {len(tl.GetItemListInTrack('video',1))} V2 {len(tl.GetItemListInTrack('video',2))} "
          f"V3 {len(tl.GetItemListInTrack('video',3))} V4 {len(tl.GetItemListInTrack('video',4))} V5 {len(tl.GetItemListInTrack('video',5) or [])} | A1 {len(tl.GetItemListInTrack('audio',1))} "
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
