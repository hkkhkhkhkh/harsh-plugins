"""Power-word captions (Harsh's reference: Nick Price edit "Doctors Were Never Taught Nutrition", 27 Sep 2026).

Each caption group is built around ONE power word or phrase: the power word sits big and UPPERCASE on the caption line, the
small lowercase lead-in words sit just above it and the small follow-on words just below it. Every word appears on the frame it
is spoken (the power phrase builds word by word too: LOSE -> LOSE WEIGHT). Groups with no power word show 1-4 small words
on the caption line. Font stays Inter SemiBold throughout.

Input: captions_lines.LINES (verified words) + captions_lines.POWER (list of lowercase power words/phrases for this video).
Output: captions.json with groups {start, end, layout: "power"|"small", pre[], power[], post[]} (each word {w, s}).
Run inside a job folder: python3 ../ae_lib/power_captions.py
"""
import json, re, sys
sys.path.insert(0, '.')
import captions_lines as CL

import os
def norm(t): return re.sub(r"[^a-z0-9%&]", "", t.lower().replace("₹", ""))
# no caption over ANY motion graphic (Harsh, 27 Sep): words spoken while a graphic is on screen get no caption
BLOCKS = [(g['start'] - 0.1, g['end'] + 0.05) for g in json.load(open('graphics/graphics_timing.json'))] if os.path.exists('graphics/graphics_timing.json') else []
HERO = {norm(x) for x in getattr(CL, "HERO", [])}   # a few single power words shown huge BEHIND his head (person cut-out on top)
POWER = [[norm(x) for x in p.split()] for p in getattr(CL, "POWER", [])]
POWER.sort(key=len, reverse=True)          # match 2-word phrases before single words
MAX_PRE, MAX_POST, MAX_SMALL = 4, 4, 4      # word caps (the reference never shows more than ~4 small words per line)
MAX_SMALL_CH = 26                           # char cap for a small line
GAP = 0.35                                  # a pause this long starts a new group
REPEAT_S = 8.0                              # the same power word again within 8 s stays small (reference: "of learning nutrition")

def mark_power(ws):
    toks = [norm(w['w']) for w in ws]; tag = [0] * len(ws); i = 0; pid = 0
    while i < len(ws):
        for p in POWER:
            if toks[i:i + len(p)] == p and all(ws[i + k]['piece'] == ws[i]['piece'] for k in range(len(p))):
                pid += 1
                for k in range(len(p)): tag[i + k] = pid
                i += len(p); break
        else: i += 1
    # repeats: same power text again within REPEAT_S -> small
    last = {}
    for pid in sorted(set(t for t in tag if t)):
        idx = [k for k, t in enumerate(tag) if t == pid]; key = ' '.join(toks[k] for k in idx); t0 = ws[idx[0]]['s']
        if key in last and t0 - last[key] < REPEAT_S:
            for k in idx: tag[k] = 0
        else: last[key] = t0
    return tag

def build():
    ws = [w for w in CL.timed_words() if not any(a <= w['s'] <= b for a, b in BLOCKS)]; tag = mark_power(ws); G = []; cur = None
    def new(): return {"pre": [], "power": [], "post": [], "pid": 0}
    def flush():
        nonlocal cur
        if cur and (cur["pre"] or cur["power"]): G.append(cur)
        cur = None
    def chars(lst): return len(' '.join(x['w'] for x in lst))
    for i, w in enumerate(ws):
        brk = cur is not None and (w['s'] - prev_e > GAP)
        if brk: flush()
        if cur is None: cur = new()
        if tag[i]:
            if cur["pid"] and cur["pid"] != tag[i]: flush(); cur = new()     # one power phrase per group
            if cur["post"]: flush(); cur = new()
            cur["pid"] = tag[i]; cur["power"].append(w)
        elif cur["power"]:
            # words that lead into the NEXT power word belong above it, not below this one ("and IRON / bisglycinate")
            lead = any(tag[j] and tag[j] != cur["pid"] for j in range(i + 1, min(len(ws), i + 4)) if ws[j]['piece'] == w['piece'])
            if lead or len(cur["post"]) >= MAX_POST or chars(cur["post"] + [w]) > MAX_SMALL_CH: flush(); cur = new(); cur["pre"].append(w)
            else: cur["post"].append(w)
        else:
            # small words wait for a power word, but never more than MAX_PRE / the char cap
            nxt_power = any(tag[j] for j in range(i + 1, min(len(ws), i + 3)) if ws[j]['piece'] == w['piece'])
            if len(cur["pre"]) >= (MAX_PRE if nxt_power else MAX_SMALL) or chars(cur["pre"] + [w]) > MAX_SMALL_CH: flush(); cur = new()
            cur["pre"].append(w)
        prev_e = w['e']
        if w['w'][-1] in '.?!': flush()
    flush()
    out = []; used_hero = set()
    for gi, g in enumerate(G):
        words = g["pre"] + g["power"] + g["post"]; start = max(0.0, words[0]['s'] - 0.04)
        nxt = (G[gi + 1]["pre"] + G[gi + 1]["power"] + G[gi + 1]["post"])[0]['s'] - 0.04 if gi + 1 < len(G) else 1e9
        end = min(nxt, max(words[-1]['e'] + 0.35, start + 0.45))
        nb = min([a for a, b in BLOCKS if a > start] or [1e9]); end = min(end, nb)   # never run into a graphic
        ptxt = norm(' '.join(x['w'] for x in g["power"]))
        hero = len(g["power"]) == 1 and ptxt in HERO and ptxt not in used_hero and len(ptxt) <= 10   # longer words: his head hides too much
        if hero: used_hero.add(ptxt); end = min(max(end, start + 1.1), nxt, nb)
        # power words: UPPERCASE, no trailing punctuation; small words keep theirs (as in the reference)
        f = lambda lst: [{"w": re.sub(r"[.,;:!]+$", "", x['w']).upper() if lst is g["power"] else x['w'], "s": x['s']} for x in lst]
        out.append({"start": round(start, 3), "end": round(end, 3), "layout": "hero" if hero else ("power" if g["power"] else "small"),
                    "pre": f(g["pre"]), "power": f(g["power"]), "post": f(g["post"]),
                    "text": ' '.join(x['w'] for x in words)})
    return out

if __name__ == "__main__":
    G = build(); json.dump(G, open('captions.json', 'w'), indent=0)
    for g in G:
        print(f"{g['start']:7.2f}-{g['end']:7.2f} {'H' if g['layout'] == 'hero' else ' '} {' '.join(x['w'] for x in g['pre']):26s} | {' '.join(x['w'] for x in g['power']):22s} | {' '.join(x['w'] for x in g['post'])}")
    print(len(G), 'groups,', sum(1 for g in G if g['layout'] == 'power'), 'with a power word')
