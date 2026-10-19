"""Run after power_captions.py. Appends small-style captions for client clips WITHOUT burned-in captions, from the
clip's own word stamps (tclips/src/transcripts.json), <= 4 words a group, cut at pauses and at the joins between pieces."""
import json, re
import job
import os, sys
E = json.load(open("edl.json"))["items"]
if not any(i["kind"] == "t" for i in E): print("no client clips: nothing to caption"); sys.exit()
T = json.load(open("tclips/src/transcripts.json")); M = json.load(open("tclips/meta.json"))["clips"]
def fix(t):
    for a, b in getattr(job, "CAPTION_FIXES", []): t = re.sub(a, b, t)
    return t
C = json.load(open("captions.json")); add = []
for it in E:
    if it["kind"] != "t" or M[it["id"]]["burned"]: continue
    m = M[it["id"]]; ws = []; off = 0.0
    for a, b in m["pieces"]:
        for seg in T[m["src"]]:
            for w in seg["words"]:
                if a - 0.05 <= w["s"] < b - 0.05:
                    ws.append({"w": fix(w["w"].strip()), "s": round(it["rec_in"] + off + max(0, w["s"] - a), 3),
                               "e": round(it["rec_in"] + off + min(b, w["e"]) - a, 3), "piece": off})
        off += b - a
    cur = []
    def flush():
        if cur: add.append({"start": round(cur[0]["s"] - 0.04, 3), "end": round(cur[-1]["e"] + 0.2, 3), "layout": "small", "pre": [{"w": x["w"], "s": x["s"]} for x in cur],
                            "power": [], "post": [], "text": " ".join(x["w"] for x in cur)}); cur.clear()
    for w in ws:
        if cur and (len(cur) >= 4 or w["s"] - cur[-1]["e"] > 0.35 or w["piece"] != cur[-1]["piece"]): flush()
        cur.append(w)
        if w["w"][-1] in ".,?!": flush()
    flush()
for i, g in enumerate(add[:-1]): g["end"] = min(g["end"], add[i + 1]["start"])
TS = [(it["rec_in"], it["rec_out"]) for it in E if it["kind"] == "t"]
for g in add:   # never outside the clip itself
    a, b = next((a, b) for a, b in TS if a - 0.2 <= g["start"] <= b); g["start"] = max(g["start"], a); g["end"] = min(g["end"], b - 0.04)
C = sorted(C + add, key=lambda g: g["start"]); json.dump(C, open("captions.json", "w"), indent=0)
print(len(add), "client-clip groups added;", len(C), "total"); [print(f"{g['start']:7.2f} {g['text']}") for g in add]
