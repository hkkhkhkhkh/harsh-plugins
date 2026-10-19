"""16:9 zoom plan per TAKE, applied to every EDL piece of that take so a push runs smoothly across silence-removal cuts.
ONE pivot for the whole video (median face, top of the head): re-pivoting per clip made the frame jump at every cut (his 27 Sep
'zoom glitches' note). Gradual pushes alternate in and out; punch-ins only on face-only lines that turn the argument.
Inside a side zone (graphics/zones.json) resolve_final overrides the scale and slides him left for the plate."""
import json, statistics
E = json.load(open("edl.json"))["items"]; F = [f for f in json.load(open("transcripts/faces.json")) if f.get("cx")]
CX = statistics.median(f["cx"] for f in F); TOP = statistics.median(f["cy"] - 0.5 * f["w"] for f in F)
PIVOT = [round(CX / 1920, 4), round(1 - TOP / 1080, 4)]          # Fusion pivot, source-normalised (16:9: timeline = full frame)
FACE = {"cx": CX, "cy": statistics.median(f["cy"] for f in F)}  # timeline px
PUNCH = {}   # take id: scale, for face-only lines that turn the argument (about 1 a minute), e.g. {3: 1.12, 21: 1.16}
def plan():
    out = []; takes = sorted({it["take"] for it in E if it["kind"] == "a"}); k = 0
    for tk in takes:
        pcs = [(i, it) for i, it in enumerate(E) if it["kind"] == "a" and it["take"] == tk]
        t0, t1 = pcs[0][1]["rec_in"], pcs[-1][1]["rec_out"]; D = max(1e-3, t1 - t0)
        if tk in PUNCH: kind, a, b = "punch", PUNCH[tk], PUNCH[tk] + 0.015
        else: kind, a, b = ("push", 1.00, 1.06) if k % 2 == 0 else ("push", 1.06, 1.00); k += 0 if tk in PUNCH else 1
        for i, it in pcs:
            v0 = a + (b - a) * (it["rec_in"] - t0) / D; v1 = a + (b - a) * (it["rec_out"] - t0) / D
            out.append({"piece": i, "take": tk, "kind": kind, "first": i == pcs[0][0], "snap_t": None, "pivot": PIVOT,
                        "keys": [(0.0, round(v0, 4)), (round(it["rec_out"] - it["rec_in"], 3), round(v1, 4))]})
    return out
if __name__ == "__main__":
    print("pivot", PIVOT, "face", FACE)
    for z in plan()[:6]: print(z)
