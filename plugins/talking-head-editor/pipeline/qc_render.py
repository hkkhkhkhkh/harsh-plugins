"""Render QC: the checks that caught real faults before anyone else saw them. Run on every render you hand over.
  python3 qc_render.py render/<OUT_NAME>_final.mp4 [--joins] [--at 357.2,378.0]
1. duration matches edl.json (a stretched or short timeline means an fps or caption-clamp fault)
2. no black frames anywhere (blackdetect d=0.01): a clip read at the wrong fps drops one frame at EVERY cut
3. loudness lands on job.LUFS_TARGET (+-1 LU) with true peak under -1 dBTP
4. colour (log sources): face and room luma of 3 A-roll frames vs the camera-LUT preview of the same source frame.
   Face within 10%, room no more than 0.7 stop darker. A plugin default once took the room from luma 41 to 8 unseen.
5. --joins: a windowed medium transcript around every take boundary; --at: around chosen record times. Read them.
   A transcript of the whole render reads fluently even when the audio stutters (ASR smooths repeats): stutter_scan.py
   before the render is the real stutter gate; this is the confirmation on the finished file.
Exit code 1 if 1-4 fail."""
import json, re, subprocess, sys, statistics
import numpy as np, imageio_ffmpeg
import job
FF = imageio_ffmpeg.get_ffmpeg_exe()
F = sys.argv[1]; E = json.load(open("edl.json")); A = [i for i in E["items"] if i["kind"] == "a"]; ok = True
def ffs(args): return subprocess.run([FF, "-nostdin", *args], capture_output=True, text=True).stderr
# 1 duration
hh, mm, ss = re.findall(r"Duration: (\d+):(\d+):([\d.]+)", ffs(["-i", F]))[0]; d = 3600 * int(hh) + 60 * int(mm) + float(ss)
print(f"duration {d:.2f} s vs edl {E['duration']:.2f} s"); ok &= abs(d - E["duration"]) < 0.3
# 2 black frames
blk = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", ffs(["-i", F, "-vf", "blackdetect=d=0.01:pix_th=0.10", "-an", "-f", "null", "-"]))
print(f"black runs: {len(blk)}", blk[:8]); ok &= not blk
# 3 loudness
lo = ffs(["-i", F, "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"])
I = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", lo)[-1]); TP = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", lo)[-1])
print(f"loudness {I} LUFS (target {job.LUFS_TARGET}), true peak {TP} dBFS"); ok &= abs(I - job.LUFS_TARGET) <= 1.0 and TP < -1.0
# 4 colour vs the camera LUT
if "{lut}" in job.PREVIEW_VF and job.LUT:
    G = json.load(open("graphics/graphics_timing.json")) if __import__("os").path.exists("graphics/graphics_timing.json") else []
    I2 = json.load(open("graphics/inserts_timing.json")) if __import__("os").path.exists("graphics/inserts_timing.json") else []
    busy = [(g["start"], g["end"]) for g in G] + [(i["start"], i["end"]) for i in I2]
    free = [p for p in A if p["rec_out"] - p["rec_in"] > 1.5 and not any(a < p["rec_out"] and b > p["rec_in"] for a, b in busy)]
    picks = [free[k * (len(free) - 1) // 2] for k in range(3)] if len(free) >= 3 else free
    FA = [f for f in json.load(open("transcripts/faces.json")) if f.get("cx")]
    fx, fy, fw = (statistics.median(f[k] for f in FA) for k in ("cx", "cy", "w")) if FA else (job.W / 2, job.H / 3, job.W / 6)
    def grab(src, t, vf):
        raw = subprocess.run([FF, "-v", "error", "-ss", f"{t:.3f}", "-i", src, "-frames:v", "1", "-vf", f"{vf}scale={job.W}:{job.H}", "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
        return np.frombuffer(raw, np.uint8)[:job.W * job.H].reshape(job.H, job.W).astype(float)
    for p in picks:
        t = (p["rec_in"] + p["rec_out"]) / 2; st = p["src_in"] + t - p["rec_in"]
        r = grab(F, t, ""); s = grab(str(job.SRC), st, job.PREVIEW_VF.format(lut=job.LUT) + ",")
        h = int(fw * 0.4); face = lambda a: a[int(fy - h):int(fy + h), int(fx - h):int(fx + h)].mean()
        room = lambda a: np.concatenate([a[: job.H // 2, : job.W // 8].ravel(), a[: job.H // 2, -job.W // 8:].ravel()]).mean()
        fr, rr = face(r) / max(1, face(s)), np.log2(max(1, room(r)) / max(1, room(s)))
        print(f"colour @ {t:7.2f}s: face {face(r):.0f} vs LUT {face(s):.0f} ({fr:.2f}x), room {room(r):.0f} vs {room(s):.0f} ({rr:+.2f} stop)")
        ok &= 0.9 <= fr <= 1.15 and rr > -0.7
# 5 join transcripts
want = []
if "--joins" in sys.argv:
    tk = sorted({p["take"] for p in A})
    for t in tk[1:]: want.append([p for p in A if p["take"] == t][0]["rec_in"])
if "--at" in sys.argv: want += [float(x) for x in sys.argv[sys.argv.index("--at") + 1].split(",")]
if want:
    from scipy.io import wavfile
    from faster_whisper import WhisperModel
    subprocess.run([FF, "-nostdin", "-v", "error", "-y", "-i", F, "-vn", "-ac", "1", "-ar", "16000", "/tmp/_qc16k.wav"], check=True)
    sr, x = wavfile.read("/tmp/_qc16k.wav"); x = x.astype(np.float32) / 32768
    m = WhisperModel("medium", device="cpu", compute_type="int8")
    for t in want:
        a, b = max(0, t - 1.6), t + 2.2
        s, _ = m.transcribe(x[int(a * sr):int(b * sr)], language="en", beam_size=5, condition_on_previous_text=False, vad_filter=False)
        txt = " ".join(q.text.strip() for q in s); ws = re.findall(r"[a-z0-9']+", txt.lower())
        rep = [ws[k] for k in range(len(ws) - 1) if ws[k] == ws[k + 1]]
        print(f"{t:7.2f}s  {txt}" + (f"   <- repeated: {rep}" if rep else ""))
print("QC", "PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
