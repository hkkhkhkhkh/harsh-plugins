"""The edit decision list. Takes come from keep_spans.py (coarse keep ranges split at sentence ends); inside each take the
pauses are removed from the DeepFilterNet-cleaned source audio. ("T", id) items are real client clips cut by proof.py,
placed right after the line they prove (CLIPS_AFTER). Source seconds in, frame-quantised record seconds out -> edl.json.

Take ids are the split_takes() index and never depend on where client clips sit, so gen_ae.py cues, captions_lines.LINES
and zooms.PUNCH stay valid when a clip moves (moving a clip used to renumber every later line).

Self-checks after building: every take produced at least one piece, and every transcribed word inside a take landed in a
piece. A silent loss here is a missing word in the render that nobody hears until the client does."""
import json, math, sys
import job
SRC = job.CLIP
FPS = job.FPS
from keep_spans import split_takes
_T = split_takes()
CLIPS_AFTER = {}   # split_takes() index -> client clip id from proof.py, e.g. {8: "t2_client_a"}
KEEP = []
for i, t in enumerate(_T):
    KEEP.append((*t, i))                                   # (src_in, src_out, note, src_key, inner_cuts, take_id)
    if i in CLIPS_AFTER: KEEP.append(("T", CLIPS_AFTER[i], "client clip: " + CLIPS_AFTER[i]))
def q(t): return round(round(t * FPS) / FPS, 4)
# Tight silence removal (house): every pause >= MERGE is cut; each span keeps PAD_IN before / PAD_OUT after.
# The threshold is RELATIVE to the clip's own speech (p95 - 29 dB), so it works for a lav (-11 -> -40 dBFS) and a phone mic
# (-30 -> -59 dBFS) alike. Long-form course videos want MERGE 0.50 (else hundreds of jump cuts); reels and VSLs use 0.10.
TH_BELOW_P95, MERGE, PAD_IN, PAD_OUT, MIN_SPAN, HOP = 29.0, 0.10, 0.02, 0.04, 0.08, 0.01
EDGE_BELOW_P95 = 42.0   # take edges follow the audio down to this lower line so soft first/last words aren't shaved
def speech_spans(a, b, r):
    import numpy as np
    TH = float(np.percentile(r, 95)) - TH_BELOW_P95
    i0, i1 = int(a / HOP), int(b / HOP); seg = r[i0:i1] > TH; spans = []; k = 0
    while k < len(seg):
        if seg[k]:
            j = k
            while j < len(seg) and seg[j:j + int(MERGE / HOP)].any(): j += 1
            spans.append([a + k * HOP, a + j * HOP]); k = j
        else: k += 1
    out = []
    for s0, s1 in spans:
        if s1 - s0 < MIN_SPAN: continue
        s0, s1 = max(a, s0 - PAD_IN), min(b, s1 + PAD_OUT)
        if out and s0 - out[-1][1] < 0.06: out[-1][1] = s1
        else: out.append([s0, s1])
    return out or [[a, b]]
_RMS, _W = {}, {}
def rms(key=None):
    if key in _RMS: return _RMS[key]
    import numpy as np
    from scipy.io import wavfile
    sr, x = wavfile.read(job.source(key)["audio_df"]); x = x.astype("float32"); x = x / 32768 if abs(x).max() > 2 else x
    w = int(sr * HOP); n = len(x) // w
    _RMS[key] = 20 * np.log10(np.sqrt((x[:n * w].reshape(n, w) ** 2).mean(1)) + 1e-9); return _RMS[key]
def words(key=None):
    if key not in _W: _W[key] = [w for p in json.load(open(job.source(key)["phrases"])) for w in p["words"]]
    return _W[key]
def refine(keep=KEEP):
    out = []
    for ki, (a, b, note, *rest) in enumerate(keep):
        if a in ("TESTIMONIAL", "T"): out.append((a, b, note, None, None)); continue
        src = rest[0] if rest else None; cuts = rest[1] if len(rest) > 1 else []; tid = rest[2] if len(rest) > 2 else ki
        sp = speech_spans(a, b, rms(src))
        # The energy gate shaves soft first/last words ("we start with", "investment back"). Keep the take's first and last
        # ASR words whole: follow the AUDIO (Whisper's word edges run into silence) down to p95 - 42 dB, only as far as
        # the first/last word reaches. Whisper starts run early, never late, so never reach back into a breath.
        ws = [w for w in words(src) if a - 0.05 <= w["s"] and w["e"] <= b + 0.05]
        if ws and sp:
            import numpy as np
            R = rms(src); low = float(np.percentile(R, 95)) - EDGE_BELOW_P95
            k0, k1 = int(round(sp[-1][1] / HOP)), int(min(b, ws[-1]["e"] + 0.12) / HOP)
            hot = [k for k in range(k0, min(k1, len(R))) if R[k] > low]
            if hot: sp[-1][1] = min(b, max(sp[-1][1], (hot[-1] + 1) * HOP + 0.04))
            k0, k1 = int(max(a, ws[0]["s"] - 0.04) / HOP), int(round(sp[0][0] / HOP))
            hot = [k for k in range(k0, k1) if R[k] > low]
            if hot: sp[0][0] = max(a, min(sp[0][0], hot[0] * HOP - 0.02))
        for c0, c1 in cuts:
            nsp = []
            for s0, s1 in sp:
                if s1 <= c0 or s0 >= c1: nsp.append([s0, s1]); continue
                if s0 < c0: nsp.append([s0, c0])
                if s1 > c1: nsp.append([c1, s1])
            sp = nsp
        for k, (s0, s1) in enumerate(sp): out.append((s0, s1, note if k == 0 else note[:40] + " (cont.)", tid, src))
    return out
def tidy(pcs, short=0.30, quiet_db=12.0, max_gap=0.40):
    """Silence removal at sentence splits leaves 2-8 frame slivers. A wordless, quiet sliver (breath, lip noise) is dropped;
    a short piece that carries a word is merged into its nearest same-take neighbour, so no 2-frame shot survives.
    Wordless pieces of 0.3-0.5 s still get through: stutter_scan.py lists them with their level."""
    import numpy as np
    W = words(None); r = rms(None); p95 = float(np.percentile(r, 95)); out = []
    pcs = [list(p) for p in pcs]
    for k, p in enumerate(pcs):
        if p[0] in ("T", "TESTIMONIAL") or p[1] - p[0] >= short: out.append(p); continue
        pk = float(r[int(p[0] / HOP):max(int(p[0] / HOP) + 1, int(p[1] / HOP))].max())
        has_word = any(w["e"] > p[0] + 0.03 and w["s"] < p[1] - 0.03 for w in W)
        if not has_word and pk < p95 - quiet_db: continue
        prev = out[-1] if out and out[-1][0] not in ("T", "TESTIMONIAL") and out[-1][3] == p[3] else None
        nxt = pcs[k + 1] if k + 1 < len(pcs) and pcs[k + 1][0] not in ("T", "TESTIMONIAL") and pcs[k + 1][3] == p[3] else None
        gp = p[0] - prev[1] if prev else 9; gn = nxt[0] - p[1] if nxt else 9
        if min(gp, gn) > max_gap: out.append(p); continue
        if gp <= gn: prev[1] = p[1]
        else: nxt[0] = p[0]
    return [tuple(p) for p in out]
def build(keep=None):
    keep = tidy(refine()) if keep is None else keep
    items = []; rec = 0.0
    for a, b, note, *rest in keep:
        take = rest[0] if rest else None; clip = rest[1] if len(rest) > 1 else None
        if a == "T":   # real client clip (proof.py): tclips/<id>.mov on V2 over a V1 gap, its own audio on the dialogue stem
            m = json.load(open("tclips/meta.json"))["clips"][b]; d = q(m["dur"])
            items.append({"kind": "t", "id": b, "take": None, "file": f"tclips/{b}.mov", "dur": d, "rec_in": round(rec, 4), "rec_out": round(rec + d, 4),
                          "note": note, "burned": m["burned"], "name": m["name"]}); rec += d; continue
        if a == "TESTIMONIAL":
            d = q(b); items.append({"kind": "placeholder", "dur": d, "rec_in": round(rec, 4), "rec_out": round(rec + d, 4), "note": note}); rec += d; continue
        a, b = q(a), q(b)
        if items and items[-1].get('clip') == clip and items[-1].get('src_in', 1e9) < a < items[-1].get('src_out', -1): a = items[-1]['src_out']   # overlap only (pickups may jump back)
        d = round(b - a, 4)
        if d <= 0: continue
        items.append({"kind": "a", "take": take, "clip": clip, "src_in": a, "src_out": b, "rec_in": round(rec, 4), "rec_out": round(rec + d, 4), "note": note}); rec += d
    return {"fps": FPS, "source": SRC, "duration": round(rec, 4), "items": items}
def check(e):
    A = [i for i in e["items"] if i["kind"] == "a"]; ok = True
    missing = [k for k in range(len(_T)) if not any(i["take"] == k for i in A)]
    if missing: ok = False; print("TAKES WITH NO PIECE:", missing)
    lost = []
    for k, (a, b, note, src, cuts) in enumerate(_T):
        for w in words(src):
            mid = (w["s"] + max(w["e"], w["s"] + 0.06)) / 2
            if a <= mid < b and not any(c0 <= mid < c1 for c0, c1 in cuts) and not any(i["src_in"] - 0.02 <= mid <= i["src_out"] + 0.02 for i in A if i["clip"] == src):
                lost.append((k, w["w"].strip(), round(w["s"], 2)))
    if lost: ok = False; print("WORDS IN A TAKE BUT IN NO PIECE (check the audio there):", lost[:20])
    short = [(round(i["src_in"], 2), round(i["src_out"] - i["src_in"], 2)) for i in A if i["src_out"] - i["src_in"] < 0.3]
    if short: print("pieces under 0.3 s (fine if they carry a word):", short[:12])
    return ok
if __name__ == "__main__":
    e = build(); json.dump(e, open("edl.json", "w"), indent=1)
    print(len(e["items"]), "items", e["duration"], "s;", sum(1 for i in e["items"] if i["kind"] == "a"), "pieces")
    if not check(e): print("edl.py: fix the spans above before going on")
