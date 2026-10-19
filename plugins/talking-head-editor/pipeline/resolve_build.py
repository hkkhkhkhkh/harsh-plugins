"""Build the job's project + cut timeline in DaVinci Resolve Studio 20 from edl.json, render the clean graded master.
Conventions proved on 20.0.1 (Reel F): AppendToTimeline start/endFrame are SOURCE frames (50p), endFrame exclusive;
RCM IDT string 'S-Gamut3/S-Log3' (no 'Sony ' prefix). Gamut read from the clip's embedded NRT XML: s-gamut3 / s-log3.
Never deletes media. Rebuilds only its own timeline (--replace)."""
import argparse, json, sys, time, functools
print = functools.partial(print, flush=True)
from pathlib import Path
import DaVinciResolveScript as dvr

HERE = Path(__file__).parent
import job
PROJECT = job.PROJECT
TL_NAME = f"{job.TAG} - Cut"
SRC = job.SRC
SRC_FPS = job.SRC_FPS; FPS = job.FPS
IDT = job.IDT
RCM = {"colorScienceMode": "davinciYRGBColorManagedv2", "rcmPresetMode": "Custom",
       "colorSpaceTimeline": "DaVinci WG/Intermediate", "colorSpaceOutput": "Rec.709 Gamma 2.4",
       "separateColorSpaceAndGamma": "0", "inputDRT": "DaVinci", "outputDRT": "DaVinci",
       "useColorSpaceAwareGradingTools": "1"}
TLS = {"timelineResolutionWidth": str(job.W), "timelineResolutionHeight": str(job.H), "timelineFrameRate": str(job.FPS),
       "timelineInputResMismatchBehavior": "scaleToCrop"}   # 16:9 FX30 into the 9:16 timeline: centre crop, never letterbox

def get_resolve():
    r = dvr.scriptapp("Resolve")
    if not r: sys.exit("Resolve not reachable")
    return r

def open_project(r):
    pm = r.GetProjectManager(); pm.GotoRootFolder()
    cur = pm.GetCurrentProject()
    if cur and cur.GetName() == PROJECT: return pm, cur
    if cur and not cur.GetName().startswith("Untitled Project"): pm.SaveProject()
    if PROJECT in (pm.GetProjectListInCurrentFolder() or []):
        p = pm.LoadProject(PROJECT)
    else:
        p = pm.CreateProject(PROJECT)
        for k, v in {**TLS, **RCM}.items():
            ok = p.SetSetting(k, v)
            print(f"  set {k}={v} ok={ok} rb={p.GetSetting(k)}")
        p.SetSetting("colorSpaceInput", IDT)
    return pm, p

def all_clips(mp):
    out = []
    def walk(f):
        out.extend(f.GetClipList() or [])
        for s in f.GetSubFolderList() or []: walk(s)
    walk(mp.GetRootFolder()); return out

def ensure_media(proj, paths):
    mp = proj.GetMediaPool()
    have = {c.GetClipProperty("File Path"): c for c in all_clips(mp)}
    new = [str(p) for p in paths if str(p) not in have]
    if new:
        for c in mp.ImportMedia(new) or []: have[c.GetClipProperty("File Path")] = c
    return mp, have

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--replace", action="store_true"); ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args()
    edl = json.loads((HERE / "edl.json").read_text())
    r = get_resolve(); pm, proj = open_project(r)
    ph = sorted((HERE / "placeholders").glob("TESTIMONIAL_*_PLACEHOLDER.mov"))
    clips = sorted({it.get("clip") for it in edl["items"] if it["kind"] == "a"}, key=lambda k: (k is not None, str(k)))
    vids = {k: job.source(k)["video"] for k in clips}
    mp, have = ensure_media(proj, [*vids.values(), *ph])
    SRCS = {}
    for k, v in vids.items():
        c = have[str(v)]
        if c.GetClipProperty("Input Color Space") != IDT: c.SetClipProperty("Input Color Space", IDT)
        rb = c.GetClipProperty("Input Color Space")
        print("source", k or "main", "IDT readback:", rb, "| fps", c.GetClipProperty("FPS"), "| res", c.GetClipProperty("Resolution"))
        if rb != IDT: sys.exit(f"ABORT: IDT did not stick ({rb!r}); list the accepted strings in Resolve and fix job.IDT")
        SRCS[k] = c
    for p in ph:
        c = have[str(p)]; c.SetClipProperty("Input Color Space", "Rec.709 Gamma 2.4")
        print(p.name, "IDT", c.GetClipProperty("Input Color Space"))
    r.OpenPage("edit")
    for i in range(1, (proj.GetTimelineCount() or 0) + 1):
        t = proj.GetTimelineByIndex(i)
        if t.GetName() == TL_NAME:
            if not a.replace: sys.exit("timeline exists; --replace")
            mp.DeleteTimelines([t]); break
    tl = mp.CreateEmptyTimeline(TL_NAME); proj.SetCurrentTimeline(tl)
    phq = list(ph); entries = []; st0 = 108000
    for it in [x for x in edl["items"] if x["kind"] != "t"]:
        if it["kind"] == "placeholder":
            c = have[str(phq.pop(0))]
            entries.append({"mediaPoolItem": c, "startFrame": 0, "endFrame": int(round(it["dur"] * FPS)), "trackIndex": 1})
        else:
            entries.append({"mediaPoolItem": SRCS[it.get("clip")], "startFrame": int(round(it["src_in"] * SRC_FPS)),
                            "endFrame": int(round(it["src_out"] * SRC_FPS)), "trackIndex": 1, "recordFrame": tl.GetStartFrame() + int(round(it["rec_in"] * FPS))})
    items = mp.AppendToTimeline(entries) or []
    if len(items) != len(entries): sys.exit(f"ABORT appended {len(items)}/{len(entries)}")
    st = tl.GetStartFrame(); drift = [round((ti.GetStart() - st) / FPS - it["rec_in"], 3) for it, ti in zip([x for x in edl["items"] if x["kind"] != "t"], items)]
    total = (tl.GetEndFrame() - st + 1) / FPS
    print(f"timeline {len(items)} items {total:.2f}s edl {edl['duration']}s max drift {max(map(abs, drift))}")
    if max(map(abs, drift)) > 1.01 / FPS: sys.exit("ABORT drift")
    for it in edl["items"]:
        col = {"placeholder": "Red", "t": "Green"}.get(it["kind"], "Blue")
        tl.AddMarker(int(round(it["rec_in"] * FPS)), col, it["kind"], it["note"][:80], 1)
    pm.SaveProject()
    if a.no_render: return
    r.OpenPage("deliver"); proj.DeleteAllRenderJobs(); proj.SetCurrentTimeline(tl)
    proj.SetCurrentRenderFormatAndCodec("mov", "ProRes422HQ")
    (HERE / "render").mkdir(exist_ok=True)
    proj.SetRenderSettings({"SelectAllFrames": True, "TargetDir": str(HERE / "render"), "CustomName": f"{job.TAG.lower()}_master_clean",
                            "FormatWidth": job.W, "FormatHeight": job.H, "ExportVideo": True, "ExportAudio": True,
                            "AudioCodec": "lpcm", "AudioBitDepth": 24, "AudioSampleRate": 48000})
    jid = proj.AddRenderJob(); proj.StartRendering([jid], False); t0 = time.time()
    while proj.IsRenderingInProgress() and time.time() - t0 < 1800: time.sleep(3)
    s = proj.GetRenderJobStatus(jid); print("render", s, round(time.time() - t0), "s")
    r.OpenPage("edit"); pm.SaveProject()

if __name__ == "__main__": main()
