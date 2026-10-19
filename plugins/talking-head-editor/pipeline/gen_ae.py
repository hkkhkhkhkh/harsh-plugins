"""Graphics plan -> ae/graphics.jsx (one After Effects comp per graphic, job.W x job.H, job.FPS, ProRes 4444 alpha).
Fill G with typed templates (ae/kit.jsx); every string is data and every cue is a SPOKEN WORD found with at(word, take).
  python3 gen_ae.py            # all graphics           python3 gen_ae.py g04_x g05_y   # render only these ids
Then run it: osascript -e 'tell application "Adobe After Effects 2026" to DoScriptFile "<job>/ae/graphics.jsx"'
(DoScript returns before the render ends; poll graphics/*.mov. One AE user at a time across sessions.)

Template types (fields at the top of each T.<type> in ae/kit.jsx; references/graphics.md has the full list):
  9:16  chips_strike, list, price, cta, study, verdict, stat, compare, steps, paper, bigword, wordmark, side, split, wall, name
  16:9  rsplit (right-hand Ink plate; Resolve slides him left: zones 'side'), fblocks / chain / compare2 (full-frame scenes,
        "full": True), cta169, name169, still (Higgsfield/z_image still with a slow push, on V2 under the captions)
  rsplit / fblocks blocks: eyebrow, big (text or from/to with a drawn arrow), sub, row (mark check|x|plus|up|down|upgood|dot),
        delta (label, from -> to, unit, mark), chips, photos (side-by-side photos with labels), quote (Paper card + attribution),
        gap, source (citation line at the bottom). g.final swaps the blocks for a title card or a photo + quote at c.final.
Rules that keep it calm: nothing on screen under 2.5 s; back-to-back cards join with hard_in/hard_out (no wipe between);
every number on a card comes from a source you can name (paper, lab report, app record), never from the script alone."""
import json, re, sys, os
import job
W = json.load(open('transcripts/rec_words.json')); E = json.load(open('edl.json'))['items']
END = json.load(open('edl.json'))['duration']
def n(s): return re.sub(r"[^a-z0-9%]", "", s.lower())
def at(word, take, nth=0):
    """Record time of the nth word in a take starting with `word` (ASR spelling: check rec_words.json, e.g. 'meenu')."""
    hits = [w for w in W if w['take'] == take and n(w['w']).startswith(n(word))]
    if len(hits) <= nth: raise SystemExit(f"cue not found: {word!r} in take {take}")
    return hits[nth]['s']
def span(take):
    tp = [it for it in E if it.get('take') == take]; return tp[0]['rec_in'], tp[-1]['rec_out']
TE = {it["id"]: it for it in E if it["kind"] == "t"}          # client clips by id: TE[id]["rec_in"], ["rec_out"]
PH = lambda f: os.path.abspath(f)                              # photos/stills: absolute paths for AE
EB = lambda t, cue=None: {"k": "eyebrow", "text": t, **({"cue": cue} if cue else {})}
def row(text, cue, mark="check"): return {"k": "row", "text": text, "cue": cue, "mark": mark}
def delta(label, a, b, cue, cue2=None, unit="", mark="down"):
    d = {"k": "delta", "label": label, "from": a, "to": b, "cue": cue, "mark": mark, "unit": unit}
    if cue2: d["cue2"] = cue2
    return d
def rs(gid, start, end, blocks, cues, final=None, hard_in=False, hard_out=False, **kw):
    """16:9 right-hand plate. Plate slides in over 0.45 s and out over 0.40 s unless the join is hard."""
    g = {"id": gid, "type": "rsplit", "start": round(start, 3), "end": round(end, 3), "blocks": blocks, "cues": cues, "hard_in": hard_in, "hard_out": hard_out, **kw}
    if final: g["final"] = final
    return g
G = [
    # 16:9 examples (uncomment and adapt; takes are split_takes() indices):
    # rs("g01_markers", at("sugar", 0) - 0.55, span(0)[1], [EB("IF YOUR LAST REPORT SHOWED"), row("High sugar", "a", "up")], {"a": at("sugar", 0)}, hard_out=True),
    # rs("g02_guarantee", span(1)[0], span(1)[1], [EB("MY GUARANTEE"), {"k": "big", "text": "6 months", "cue": "six"}],
    #    {"six": at("6", 1), "final": at("double", 1)}, final={"title": "Double your\rinvestment back", "sub": "for the coaching"}, hard_in=True),
    # {"id": "g11_chain", "type": "chain", "full": True, "start": span(26)[0], "end": span(29)[1], "head": "ONE ROOT CAUSE",
    #  "nodes": [["Visceral fat", "n0"], ["Poor metabolism", "n1"]], "cues": {"card": span(26)[0] + 0.05, "n0": span(26)[0] + 0.25, "n1": at("metabolism", 26)}},
    # {"id": "g21_cta", "type": "cta169", "start": span(54)[0], "end": span(54)[1], "text": "Click the button below", "y": 800,
    #  "steps": [["Answer a few questions", "s1"]], "cues": {"btn": span(54)[0] + 0.08, "s1": at("answer", 54), "out": span(54)[1] - 0.25}},
]
# name tags on client clips that carry no burned-in name (proof.py meta: name = [name, role])
NAME_TYPE = "name169" if job.W > job.H else "name"
for tid, it in TE.items():
    nm = (it.get("name") or [None, ""])
    if nm and nm[0]:
        G.append({"id": f"n_{tid}", "type": NAME_TYPE, "name": nm[0], "role": nm[1] if len(nm) > 1 else "", "start": it["rec_in"] + 0.2,
                  "end": min(it["rec_out"], it["rec_in"] + 5.2), "cues": {"card": it["rec_in"] + 0.35, "out": min(it["rec_out"], it["rec_in"] + 5.2) - 0.3}})
# stills on V2 (under the captions): {"id": "i_desk", "type": "still", "image": PH("inserts/hf/desk.png"), "start": .., "end": .., "zoom": 1.07, "dx": -30, "cues": {}}
STILLS = []
for g in G + STILLS:
    for k, v in list(g["cues"].items()): g["cues"][k] = round(v, 3)
    g["start"], g["end"] = round(g["start"], 3), round(g["end"], 3)
    if g["end"] - g["start"] < 2.5 and g["type"] not in ("name", "name169", "cta", "cta169"): print(f"warning: {g['id']} is on screen {g['end'] - g['start']:.1f} s (< 2.5 s)")
INSERTS = [{"file": f"graphics/{s['id']}.mov", "start": s["start"], "end": s["end"], "src_off": 0.0} for s in STILLS]
INSERTS += [{"file": it["file"], "start": it["rec_in"], "end": it["rec_out"], "src_off": 0.0, "clip": True} for it in E if it["kind"] == "t"]
ZONES = [{"kind": "side", "start": g["start"], "end": g["end"], "hard_in": g.get("hard_in", False), "hard_out": g.get("hard_out", False), "id": g["id"]} for g in G if g["type"] == "rsplit"]
ZONES += [{"kind": "full", "start": g["start"], "end": g["end"], "id": g["id"]} for g in G if g.get("full")]
ZONES += [{"kind": "split", "start": g["start"], "end": g["end"], "hard_in": g.get("hard_in", False), "hard_out": g.get("hard_out", False), "id": g["id"]} for g in G if g["type"] == "split"]
os.makedirs('graphics', exist_ok=True)
json.dump(sorted(INSERTS, key=lambda x: x["start"]), open('graphics/inserts_timing.json', 'w'), indent=1)
json.dump(G, open('graphics/graphics_timing.json', 'w'), indent=1)
json.dump(sorted(ZONES, key=lambda z: z["start"]), open('graphics/zones.json', 'w'), indent=1)
out = os.path.abspath('graphics') + '/'
kit = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ae/kit.jsx')).read()
pre = (f"var OUT = {json.dumps(out)};\nvar G = {json.dumps(G + STILLS)};\nvar ONLY = {json.dumps(sys.argv[1:])};\nvar FPS = {job.FPS};\n"
       f"var CW = {job.W}, CH = {job.H};\nvar AEP = {json.dumps(out + '../ae/graphics.aep')};\nvar BRAND = {json.dumps(getattr(job, 'BRAND', None))};\n")
open('ae/graphics.jsx', 'w').write(pre + kit)
for g in G + STILLS: print(f"{g['id']:16s} {g['type']:9s} {g['start']:7.2f}-{g['end']:7.2f} ({g['end']-g['start']:4.1f}s)")
