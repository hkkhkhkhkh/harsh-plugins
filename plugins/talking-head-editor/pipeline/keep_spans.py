"""The spoken edit, as coarse keep ranges in SOURCE seconds. Write SPANS from the transcript (transcribe.py prints both passes):
later take wins; drop false starts, asides ("why is the script saying...") and repeated lines; one complete thought per span.
Each span: (src_in, src_out, note, inner_cuts) where inner_cuts = [(c0, c1), ...] are source ranges removed inside the span
(a doubled phrase, a slip, a breath). split_takes() then breaks spans at sentence ends so every line is its own take:
zooms, captions and graphics cue off take ids.

Edges matter. Start a span ~0.15 s before its first word and end it after the last word's decay; where the next word follows
with no gap, cut at the energy dip between them (python3 keep_spans.py --edges prints the words and the 10 ms dip at every
edge). A cut a few hundredths late keeps the onset of the next word, which plays as a stutter ("injury and, and now").

  python3 keep_spans.py           # print the takes
  python3 keep_spans.py --edges   # words + quietest point around every span edge"""
import json, re, sys
SPANS = [
    # (0.10, 32.62, "hook: the promise, who it's for", []),
    # (36.45, 39.85, "proof line (a false start before it dropped)", []),
    # (312.20, 353.75, "the offer", [(321.55, 322.80)]),   # inner cut: a slip ("or use your least or")
]
def words():
    out = []
    for p in json.load(open("transcripts/phrases.json")): out += p["words"]
    return out
def split_takes(min_len=2.2):
    W = words(); takes = []
    for a, b, note, cuts in SPANS:
        ws = [w for w in W if a - 0.05 <= w["s"] < b and not any(c0 <= w["s"] < c1 for c0, c1 in cuts)]
        bounds = [a]
        for k in range(len(ws) - 1):
            w, nx = ws[k], ws[k + 1]
            if re.search(r"[.?!]$", w["w"].strip()) and nx["s"] - w["e"] >= 0.12 and w["e"] - bounds[-1] >= min_len and b - nx["s"] >= min_len:
                bounds.append(round((w["e"] + nx["s"]) / 2, 3))
        bounds.append(b)
        for k in range(len(bounds) - 1):
            s0, s1 = bounds[k], bounds[k + 1]
            txt = " ".join(w["w"].strip() for w in ws if s0 <= w["s"] < s1)
            tc = [(max(c0, s0), min(c1, s1)) for c0, c1 in cuts if c0 < s1 and c1 > s0]
            takes.append((s0, s1, (note if k == 0 else note.split(":")[0] + " (cont.)") + " | " + txt[:70], None, tc))
    return takes
def edges():
    import numpy as np, job
    from scipy.io import wavfile
    sr, x = wavfile.read(job.source()["audio_df"]); x = x.astype("float32"); x = x / 32768 if abs(x).max() > 2 else x
    def dip(a, b):
        a = max(0.0, a); e = []
        for t in np.arange(a, b, 0.01):
            seg = x[int(t * sr):int((t + 0.01) * sr)]
            if len(seg): e.append((float(t), float(20 * np.log10(np.sqrt((seg ** 2).mean()) + 1e-9))))
        t, v = min(e, key=lambda q: q[1]) if e else (a, 0.0)
        return f"{t:.2f}s at {v:.0f} dB"
    W = words()
    for a, b, note, cuts in SPANS:
        pre = [w for w in W if a - 1.5 <= w["s"] < a + 0.6]; post = [w for w in W if b - 0.6 <= w["s"] < b + 1.0]
        print(f"{a:8.2f} IN : " + " ".join(f"{w['w'].strip()}[{w['s']:.2f}-{w['e']:.2f}]" for w in pre) + f"   dip {dip(a - 0.3, a + 0.2)}")
        print(f"{b:8.2f} OUT: " + " ".join(f"{w['w'].strip()}[{w['s']:.2f}-{w['e']:.2f}]" for w in post) + f"   dip {dip(b - 0.2, b + 0.3)}")
if __name__ == "__main__":
    if "--edges" in sys.argv: edges()
    else:
        for i, t in enumerate(split_takes()): print(f"{i:3d} {t[0]:7.2f}-{t[1]:7.2f} {t[1]-t[0]:5.1f}s {t[2][:120]} {t[4] or ''}")
