"""Sound design placed from the edit itself: every graphic template, insert and zoom brings its own sounds.
Rules = the signed-off reel finish (26 Sep 2026), generalised. Gains are dB applied to the house sound.
  card / panel entry     whoosh_soft 0.10-0.12 s before, -16
  row / chip / item      pop 0.02 s before, -20 (skipped if within 0.15 s of the card's own whoosh)
  strike-through         strike on the cue, -17 (-18 on the price card's old price, 0.35 s in)
  price / stat landing   riser ending on the number, -19, then impact 0.03 s before it, -13 (stat: impact -16, no riser)
  refund chip            pop, -19        CTA button     pop 0.05 s before, -17
  bigword / wordmark     whoosh_soft on the card, -16
  verdict stamp          impact on the stamp, -15    study / paper   shutter on the card, -20, pop on the highlight, -20
  insert (b-roll)        fastwhoosh 0.15 s before it starts, -21, and 0.10 s before it ends, -23
  zoom                   whip_zoom 0.06 s before a punch-in cut, -21; 0.04 s before a snap, -19
Pacing: the same sound twice within 0.12 s keeps only the louder one. Different sounds may layer (whip + pop, as approved).
Restraint: nothing else gets sound. Talking-head jump cuts get none. Glitch / bell / game sounds are never used."""
import wave


def _dur(f):
    w = wave.open(f)
    return w.getnframes() / w.getframerate()


def hits(G, inserts, zplan, items, riser_file="audio/sd/riser.wav", extra=()):
    RISER = _dur(riser_file)
    H = []
    for g in G:
        c, ty = g["cues"], g.get("type")
        if ty == "chips_strike":
            labs = [c[l[1]] for l in g["labels"]]
            H.append((labs[0] - .12, "whoosh_soft", -16))
            H += [(t - .02, "pop", -20) for t in labs[1:]]
            H += [(c["strike"], "strike", -17), (c["one"] - .1, "whoosh_soft", -16)]
        elif ty in ("list", "compare", "steps"):
            rows = g.get("rows") or g.get("steps")
            cue_of = (lambda r: c[r[3]] if len(r) > 3 and r[3] else c.get("card")) if ty == "compare" else (lambda r: c[r[1]])
            card = c.get("card", cue_of(rows[0]))
            H.append((card - .1, "whoosh_soft", -16))
            H += [(cue_of(r) - .02, "pop", -20) for r in rows if cue_of(r) - card > .15]
        elif ty == "price":
            H += [(c["card"] - .1, "whoosh_soft", -16), (c["card"] + .35, "strike", -18),
                  (c["price"] - RISER, "riser", -19), (c["price"] - .03, "impact", -13)]
            if "refund" in c:
                H.append((c["refund"] - .02, "pop", -19))
        elif ty == "side":   # 9:16 right-side stack: whoosh on the card, pop per row, strike, whoosh on the swap card
            H.append((c["card"] - .1, "whoosh_soft", -16))
            H += [(c[r[1]] - .02, "pop", -20) for r in g["rows"] if c[r[1]] - c["card"] > .15]
            if "strike" in c: H.append((c["strike"], "strike", -17))
            if "final" in c: H.append((c["final"] - .1, "whoosh_soft", -16))
        elif ty == "wall":   # video wall: one whoosh as it opens, soft pops as the tiles land
            H.append((c["card"] - .12, "whoosh_soft", -16))
            H += [(c["t%d" % k] - .02, "pop", -24) for k in range(1, len(g["tiles"]))]
        elif ty == "name":
            H.append((c["card"] - .08, "whoosh_soft", -21))
        elif ty == "cta":
            H.append((c["btn"] - .05, "pop", -17))
        elif ty == "stat":
            H += [(c["card"] - .1, "whoosh_soft", -16), (c["land"] - .03, "impact", -16)]
        elif ty in ("bigword", "wordmark"):
            H.append((c["card"] - .1, "whoosh_soft", -16))
        elif ty == "verdict":
            H.append((c["stamp"] - .02, "impact", -15))
        elif ty in ("study", "paper"):
            H.append((c["card"] - .05, "shutter", -20))
            if "hl" in c:
                H.append((c["hl"] - .02, "pop", -20))
        elif ty in ("rsplit", "fblocks"):   # 16:9: plate/scene in, soft pop per landing row/chip/number, whoosh on the swap card
            card = c.get("card", g["start"] + (0 if g.get("hard_in") else 0.1))
            if ty == "fblocks" or not g.get("hard_in"): H.append((card - .1, "whoosh_soft", -17))
            cues = []
            for b in g.get("blocks", []):
                if b.get("cue") in c: cues.append(c[b["cue"]])
                if b.get("cue2") in c: cues.append(c[b["cue2"]])
                for itm in b.get("items", []): cues.append(c[itm["cue"] if isinstance(itm, dict) else itm[1]])
            H += [(t - .02, "pop", -23) for t in cues if t - card > .25]
            if "final" in c: H.append((c["final"] - .1, "whoosh_soft", -17))
        elif ty == "chain":
            H.append((c["card"] - .1, "whoosh_soft", -16))
            H += [(c[n[1]] - .02, "pop", -22) for n in g["nodes"] if c[n[1]] - c["card"] > .25]
            H += [(c[f[1]] - .02, "pop", -24) for f in g.get("fan", [])]
            if g.get("close"): H.append((c[g["close"][1]] - .1, "whoosh_soft", -19))
        elif ty == "compare2":
            H.append((c["card"] - .1, "whoosh_soft", -16))
            H += [(c[k] - .02, "pop", -22) for k in ("c1", "r1", "r2") if k in c]
        elif ty == "cta169":
            H.append((c["btn"] - .05, "pop", -17))
        elif ty == "name169":
            H.append((c["card"] - .08, "whoosh_soft", -22))
    for ins in inserts:
        if ins.get("quiet"): continue
        H += [(ins["start"] - .15, "fastwhoosh", -21), (ins["end"] - .1, "fastwhoosh", -23)]
    for z in zplan:
        it = items[z["piece"]]
        if z["kind"] == "punch" and z["first"] and z["piece"] > 0:
            H.append((it["rec_in"] - .06, "whip_zoom", -21))
        if z["snap_t"] is not None:
            H.append((it["rec_in"] + z["snap_t"] - .04, "whip_zoom", -19))
    H += list(extra)
    H = sorted((max(0, t), k, gdb) for t, k, gdb in H)
    out = []
    for h in H:   # same sound within 0.12 s: keep the louder
        dup = next((o for o in out if o[1] == h[1] and abs(o[0] - h[0]) < .12), None)
        if dup is None:
            out.append(h)
        elif h[2] > dup[2]:
            out[out.index(dup)] = h
    return out
