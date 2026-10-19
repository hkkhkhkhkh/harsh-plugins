"""Extend a short music bed to the edit's length without an audible loop point: intro, then alternating full sections
looped on bar lines, then the track's own ending timed to land on the last line. 0.4 s equal-power crossfades.
Generated beds (Higgsfield Sonilo, about 3.75 credits a minute) usually come out 60-90 s; a VSL runs 7-10 minutes.

  python3 music/build_bed.py --src bed.wav --bpm 90 [--sections 16-45.33,60-74.67] [--ending 45.33] [--out music/bed.wav]

--sections  loopable full sections (seconds, start-end) that begin and end on bar lines; alternate them to avoid sameness.
            Default: one section, the middle 40% of the track snapped to bars.
--ending    where the track's own breakdown/ending starts (default: 75% of the track, snapped to a bar).
Length defaults to edl.json duration + 1 s. Point job.MUSIC at the output. Music licence: use beds you own (Sonilo output)
or have a sync licence for; a commercial track you only have a local copy of is fine for organic posts, not for paid ads."""
import argparse, json, numpy as np
from scipy.io import wavfile
ap = argparse.ArgumentParser(); ap.add_argument("--src", required=True); ap.add_argument("--bpm", type=float, required=True)
ap.add_argument("--sections", default=""); ap.add_argument("--ending", type=float, default=None)
ap.add_argument("--out", default="music/bed.wav"); ap.add_argument("--dur", type=float, default=None)
a = ap.parse_args()
DUR = a.dur or json.load(open("edl.json"))["duration"] + 1.0
sr, x = wavfile.read(a.src); x = x.astype(np.float32); x /= max(1e-9, np.abs(x).max())
if x.ndim == 1: x = x[:, None]
T = len(x) / sr; bar = 240.0 / a.bpm; snap = lambda t: round(t / bar) * bar
secs = [tuple(map(float, s.split("-"))) for s in a.sections.split(",") if s] or [(snap(0.3 * T), snap(0.7 * T))]
end0 = a.ending if a.ending is not None else snap(0.75 * T)
X = int(0.4 * sr); fi = np.sin(np.linspace(0, np.pi / 2, X))[:, None]; fo = np.cos(np.linspace(0, np.pi / 2, X))[:, None]
seg = lambda s, e: x[int(s * sr):int(e * sr)]
def join(p, q): return np.concatenate([p[:-X], p[-X:] * fo + q[:X] * fi, q[X:]])
intro_end = secs[0][1]
out = seg(0, intro_end + 0.4); end = seg(end0, T); k = 0
while (len(out) + len(end) - X) / sr < DUR:
    s, e = secs[k % len(secs)]; out = join(out, seg(s, e + 0.4)); k += 1
need = int(DUR * sr) - (len(end) - X)             # keep this much, then crossfade into the ending (never a raw cut)
out = join(out[:need], end)
wavfile.write(a.out, sr, (out * 0.9).astype(np.float32))
print(f"{a.out}: {len(out) / sr:.2f} s from {T:.1f} s source, {k} loops, bar {bar:.3f} s")
