"""Social proof: real client clips cut on their own words and dropped right after the line they prove (edl.CLIPS_AFTER).
Put each source video in tclips/src/<key>.<mp4|mov|...>, then:
  python3 proof.py --transcribe   # word stamps for every source -> tclips/src/transcripts.json (prints them: pick bites)
  python3 proof.py                # cut CLIPS -> tclips/<id>.mov (+ .wav cleaned with DeepFilterNet) + tclips/meta.json
Vertical / 4:5 sources sit centred at full height over a blurred, darkened fill of themselves; landscape fills the frame
(16:9 delivery). 9:16 delivery: landscape sources are cropped round the face.

Who is in the clip is a FACT, not a guess: confirm every identity with the person who knows the clients before naming
anyone (a website caption is not proof; a clip once went out tagged with the wrong client). Use only what the client
actually said, cut on word boundaries; skip profanity and anything the client did not consent to."""
import json, subprocess, sys, imageio_ffmpeg
from pathlib import Path
import job
FF = imageio_ffmpeg.get_ffmpeg_exe()
S = Path("tclips/src")
# id: (source key, [(in, out), ...] source seconds on word boundaries, burned-in captions?, (name, role) or None)
CLIPS = {
    # "t2_client_a": ("t2", [(0.00, 12.95), (35.30, 45.10)], True, ("Client A", "Business owner")),
}
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".mkv", ".webm")
def src_file(key):
    hits = [p for p in S.glob(f"{key}.*") if p.suffix.lower() in VIDEO_EXT]
    if not hits: raise SystemExit(f"no source video tclips/src/{key}.*")
    return hits[0]
def run(a): subprocess.run([FF, "-nostdin", "-v", "error", "-y", *a], check=True)
def probe(p):
    import re; r = subprocess.run([FF, "-hide_banner", "-i", str(p)], capture_output=True, text=True).stderr
    return tuple(map(int, re.search(r"Video:.*?(\d{3,4})x(\d{3,4})", r).groups()))
def vfilter(src):
    w, h = probe(src)
    if job.W > job.H:
        if w > h: return f"scale={job.W}:{job.H}:force_original_aspect_ratio=increase,crop={job.W}:{job.H},fps={job.FPS},format=yuv422p10le"
        fw = round(job.H * w / h / 2) * 2
        return (f"fps={job.FPS},split[fg][bg];[bg]scale={job.W}:-2,crop={job.W}:{job.H},boxblur=40:2,eq=brightness=-0.16:saturation=0.8[bb];"
                f"[fg]scale={fw}:{job.H}:flags=lanczos[ff];[bb][ff]overlay=(W-w)/2:0,format=yuv422p10le")
    if w > h: return f"crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale={job.W}:{job.H}:flags=lanczos,fps={job.FPS},format=yuv422p10le"
    return f"scale={job.W}:{job.H}:force_original_aspect_ratio=increase,crop={job.W}:{job.H},fps={job.FPS},format=yuv422p10le"
def transcribe():
    from faster_whisper import WhisperModel
    m = WhisperModel("small", device="cpu", compute_type="int8"); out = {}
    for p in sorted(x for x in S.iterdir() if x.suffix.lower() in VIDEO_EXT):
        segs, _ = m.transcribe(str(p), language="en", word_timestamps=True, beam_size=5)
        segs = list(segs); out[p.stem] = [{"s": s.start, "e": s.end, "text": s.text, "words": [{"w": w.word, "s": w.start, "e": w.end} for w in s.words]} for s in segs]
        print(f"== {p.stem}"); [print(f"  {s.start:6.2f}-{s.end:6.2f} {s.text}") for s in segs]
    json.dump(out, open(S / "transcripts.json", "w"), indent=1)
if __name__ == "__main__":
    if "--transcribe" in sys.argv: transcribe(); sys.exit()
    T = Path("tclips"); meta = {}; raws = []
    for cid, (src, pieces, burned, name) in CLIPS.items():
        p = src_file(src); V = vfilter(p); parts = []
        flag = "-filter_complex" if "[" in V else "-vf"
        for k, (a, b) in enumerate(pieces):
            o = T / f"{cid}_p{k}.mov"; parts.append(o)
            run(["-ss", f"{a:.3f}", "-t", f"{b-a:.3f}", "-i", str(p), flag, V, "-color_primaries", "bt709", "-color_trc", "bt709",
                 "-colorspace", "bt709", "-c:v", "prores_ks", "-profile:v", "3", "-an", str(o)])
            run(["-ss", f"{a:.3f}", "-t", f"{b-a:.3f}", "-i", str(p), "-map", "0:a:0", "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", str(T / f"{cid}_p{k}.raw.wav")])
        (T / f"{cid}.txt").write_text("".join(f"file '{x.name}'\n" for x in parts))
        run(["-f", "concat", "-safe", "0", "-i", str(T / f"{cid}.txt"), "-c", "copy", str(T / f"{cid}.mov")])
        (T / f"{cid}.a.txt").write_text("".join(f"file '{x.stem}.raw.wav'\n" for x in parts))
        run(["-f", "concat", "-safe", "0", "-i", str(T / f"{cid}.a.txt"), "-c", "copy", str(T / f"{cid}.raw.wav")])
        raws.append(T / f"{cid}.raw.wav"); dur = sum(b - a for a, b in pieces)
        meta[cid] = {"src": src, "pieces": pieces, "dur": round(dur, 3), "burned": burned, "name": list(name) if name else None}
        print("cut", cid, round(dur, 2), flush=True)
    if raws:
        code = ("import sys\nfrom df.enhance import enhance, init_df, load_audio, save_audio\nm,s,_=init_df()\n"
                "for f in sys.argv[1:]:\n  a,_=load_audio(f, sr=s.sr()); save_audio(f.replace('.raw.wav','.wav'), enhance(m,s,a,atten_lim_db=24), s.sr())\n")
        subprocess.run([job.DFPY, "-c", code, *map(str, raws)], check=True)
    json.dump({"clips": meta}, open(T / "meta.json", "w"), indent=1)
    print("ok", len(meta), "clips")
