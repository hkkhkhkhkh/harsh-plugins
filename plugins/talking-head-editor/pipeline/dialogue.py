"""Dialogue for v2: cut straight from the source 48 kHz audio at the EDL's frame-quantised times (so it is sample-locked to
the Resolve picture), 8 ms fades at every join (no clicks), then voice enhancement:
DeepFilterNet 3 (noise/room removal, 48 kHz model, run in the py3.11 scratch venv) -> HPF 80 -> -3 dB @ 300 Hz (boxiness)
-> +3 dB @ 3.2 kHz (presence) -> +2 dB shelf @ 10 kHz (air) -> de-ess -> 3:1 compression -> limiter."""
import json, subprocess, sys, numpy as np, imageio_ffmpeg
from scipy.io import wavfile
from pathlib import Path
FF = imageio_ffmpeg.get_ffmpeg_exe()
import job
DFPY = job.DFPY
E = json.load(open("edl.json")); SR = 48000
AUD = {}
def mono(clip):  # whole source already cleaned by DeepFilterNet 3 (clean_source.py)
    if clip not in AUD:
        sr, x = wavfile.read(job.source(clip)["audio_df"]); x = x.astype(np.float32)
        x = x / (2 ** 31 if x.dtype == np.int32 or np.abs(x).max() > 40000 else (2 ** 15 if np.abs(x).max() > 2 else 1))
        AUD[clip] = (x.mean(1) if x.ndim == 2 else x).astype(np.float32)
    return AUD[clip]
fade = int(0.008 * SR); out = []
def rms_db(v):
    w = int(0.05 * SR); n = len(v) // w; r = 20 * np.log10(np.sqrt((v[:n * w].reshape(n, w) ** 2).mean(1)) + 1e-9); return float(np.percentile(r, 90))
REF = None
for it in E["items"]:
    if it["kind"] == "t":   # testimonial: its own audio, matched to Harsh's speech level (p90 of 50 ms RMS), exact record length
        if REF is None: REF = rms_db(mono(None))
        sr_, v = wavfile.read(f"tclips/{it['id']}.wav"); v = v.astype(np.float32); v = v / (32768 if np.abs(v).max() > 2 else 1)
        v = (v.mean(1) if v.ndim == 2 else v); n = round((it["rec_out"] - it["rec_in"]) * SR); v = np.pad(v, (0, max(0, n - len(v))))[:n]
        seg = v * 10 ** ((REF - rms_db(v)) / 20); seg[:fade] *= np.linspace(0, 1, fade); seg[-fade:] *= np.linspace(1, 0, fade); out.append(seg.astype(np.float32)); continue
    a, b = round(it["src_in"] * SR), round(it["src_out"] * SR); seg = mono(it.get("clip"))[a:b].copy()
    seg[:fade] *= np.linspace(0, 1, fade); seg[-fade:] *= np.linspace(1, 0, fade); out.append(seg)
raw = np.concatenate(out); wavfile.write("audio/dialogue_raw.wav", SR, raw)
print("raw", len(raw) / SR, "s vs edl", E["duration"])
if "--df" in sys.argv:  # v3: not needed, source is pre-cleaned
    code = ("from df.enhance import enhance, init_df, load_audio, save_audio\n"
            "m, s, _ = init_df()\n"
            "a, _ = load_audio('audio/dialogue_raw.wav', sr=s.sr())\n"
            "e = enhance(m, s, a, atten_lim_db=18)\n"
            "save_audio('audio/dialogue_df.wav', e, s.sr())\n")
    r = subprocess.run([DFPY, "-c", code], capture_output=True, text=True)
    if r.returncode: sys.exit(r.stderr[-1500:])
chain = ("highpass=f=80,equalizer=f=300:t=q:w=1.0:g=-3,equalizer=f=3200:t=q:w=1.2:g=3,highshelf=f=10000:g=2,"
         "deesser=i=0.4:m=0.5:f=0.5,acompressor=threshold=-20dB:ratio=3:attack=6:release=110:makeup=4,"
         "alimiter=limit=0.89:attack=3:release=50,aformat=sample_rates=48000:channel_layouts=stereo")
subprocess.run([FF, "-nostdin", "-v", "error", "-y", "-i", "audio/dialogue_raw.wav", "-af", chain, "-c:a", "pcm_s24le", "audio/dialogue_enhanced.wav"], check=True)
print("ok")
