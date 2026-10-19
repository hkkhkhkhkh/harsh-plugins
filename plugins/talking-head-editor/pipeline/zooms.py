"""Zoom plan per TAKE (a line of script), applied to every EDL piece of that take so a gradual push runs smoothly across
silence-removal cuts. Pivot = top of the head (median face over the take), so zooms grow the face DOWN, away from the cards
in the top band; no reliable face -> left edge (x 0), where he stands, so a punch-in never pushes him out of frame.
kind 'push' = gradual a -> b over the take, 'punch' = prompt (cut in at a, drift to b), SNAPS = prompt zoom on a word."""
import json, statistics
E = json.load(open("edl.json"))["items"]; F = {f["i"]: f for f in json.load(open("transcripts/faces.json"))}
W = json.load(open("transcripts/rec_words.json"))
PLAN = {}   # take id: (kind, from, to). Takes not listed get the house rhythm below (hook push-in, then punch / push / pull).
SNAPS = {}  # take id: (word as ASR spelled it, zoom added at that word, held to the take's end), e.g. {26: ("18", 0.06)}
_takes = sorted({it["take"] for it in E if it.get("kind") == "a"})
for _k, _t in enumerate(_takes):
    PLAN.setdefault(_t, ("push", 1.00, 1.08) if _k == 0 else [("punch", 1.12, 1.13), ("push", 1.00, 1.05), ("push", 1.08, 1.00)][_k % 3])
def plan():
    out = []
    takes = sorted({it["take"] for it in E if it.get("kind") == "a"})
    for tk in takes:
        pcs = [(i, it) for i, it in enumerate(E) if it.get("kind") == "a" and it["take"] == tk]
        t0, t1 = pcs[0][1]["rec_in"], pcs[-1][1]["rec_out"]; D = t1 - t0
        good = [F[i] for i, _ in pcs if F.get(i, {}).get("cx") and F[i]["w"] >= 400]
        if good: cx = statistics.median(f["cx"] for f in good); cy = statistics.median(f["cy"] - 0.5 * f["w"] for f in good)
        else: cx, cy = 0, 500
        kind, a, b = PLAN[tk]
        snap = None
        if tk in SNAPS:
            word, extra = SNAPS[tk]; snap = (next(w["s"] for w in W if w["take"] == tk and __import__("re").sub(r"[^a-z0-9]", "", w["w"].lower()).startswith(word)), extra)
        def val(t, end=False):  # a piece END just before the snap word must not take the snap yet
            v = a + (b - a) * (t - t0) / D
            return v + (snap[1] if snap and t >= snap[0] + (0.12 if end else -0.15) else 0)
        for i, it in pcs:
            d = it["rec_out"] - it["rec_in"]; keys = [(0.0, val(it["rec_in"])), (d, val(it["rec_out"], end=True))]
            snap_t = None
            if snap and abs(snap[0] - it["rec_in"]) <= 0.15: snap_t = 0.0   # snap word opens the piece: prompt zoom on the cut
            if snap and it["rec_in"] + 0.15 < snap[0] < it["rec_out"]:
                snap_t = snap[0] - it["rec_in"]
                ts = snap[0] - it["rec_in"]; base = a + (b - a) * (snap[0] - t0) / D
                keys = [(0.0, val(it["rec_in"])), (max(0.0, ts - 0.04), base), (ts + 0.12, base + snap[1]), (d, val(it["rec_out"], end=True))]
            out.append({"piece": i, "take": tk, "kind": kind, "first": i == pcs[0][0], "snap_t": snap_t,
                        "pivot": [round(cx / 1080, 4), round(1 - cy / 1920, 4)], "keys": [(round(t, 3), round(v, 4)) for t, v in keys]})
    return out
if __name__ == "__main__":
    for z in plan(): print(z)
