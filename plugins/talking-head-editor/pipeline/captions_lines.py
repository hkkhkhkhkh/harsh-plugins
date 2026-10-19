"""Caption text: one verified line per TAKE (take id = split_takes() index; client clips carry no line). ASR supplies timing only;
the words are an editorial decision. They live in captions_lines.json next to this file:
  {"lines": {"0": "First line as spoken...", ...}, "power": ["guarantee", "10 kg", ...], "hero": []}
  python3 captions_lines.py --draft   # writes captions_lines.json from transcripts/rec_words.json + job.CAPTION_FIXES
Then READ every line against the script and the audio, fix names, terms and numbers by hand, and choose the power words
(lowercase; 1 word, or 2 that only mean something together: "lose weight", "exact plan"; nouns and claims, not verbs;
about one every 1.5 s). Words that were cut out of the audio must not stay in the line; a line that still ends with the
first word of a removed restart ("...from the inside because") gets that word deleted.
  python3 captions_lines.py           # -> captions.json (one-line style); power_captions.py then builds the default style"""
import json, re, difflib, os, sys
_CL = json.load(open("captions_lines.json")) if os.path.exists("captions_lines.json") else {"lines": {}, "power": []}
LINES = {int(k): v for k, v in _CL["lines"].items()}
POWER = _CL.get("power", [])
HERO = _CL.get("hero", [])   # iPhone finisher only: up to a few single power words shown huge above the head
def draft():
    import job
    W = json.load(open("transcripts/rec_words.json")); L = {}
    for t in sorted({w["take"] for w in W}):
        s = " ".join(w["w"] for w in W if w["take"] == t)
        for a, b in getattr(job, "CAPTION_FIXES", []): s = re.sub(a, b, s)
        L[str(t)] = s
    json.dump({"lines": L, "power": POWER}, open("captions_lines.json", "w"), indent=1, ensure_ascii=False)
    for t, s in L.items(): print(t, s)
    print(f"-> captions_lines.json ({len(L)} lines). Now read and fix every line, and fill 'power'.")
def norm(t): return re.sub(r"[^a-z0-9%&]", "", t.lower().replace("₹", ""))
def timed_words():
    W = json.load(open('transcripts/rec_words.json')); E = json.load(open('edl.json'))['items']
    out = []
    for pi, line in LINES.items():
        toks = line.split(); asr = [w for w in W if w['take'] == pi]
        a = [norm(w['w']) for w in asr]; b = [norm(t) for t in toks]
        # ASR splits "18,000" as "18" ",000" and "100%" as "100" "%": merge fragments first
        m = []
        for w in asr:
            if m and (w['w'].startswith((',', '%', '-')) ): m[-1] = {**m[-1], 'w': m[-1]['w'] + w['w'], 'e': w['e']}
            else: m.append(dict(w))
        asr = m; a = [norm(w['w']) for w in asr]
        times = [None] * len(toks)
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if tag in ('equal', 'replace') and (i2 - i1) == (j2 - j1):
                for k in range(j2 - j1): times[j1 + k] = (asr[i1 + k]['s'], asr[i1 + k]['e'])
        # interpolate gaps inside the piece
        tp = [it for it in E if it.get('take') == pi]; s0, s1 = tp[0]['rec_in'], tp[-1]['rec_out']
        for k in range(len(toks)):
            if times[k] is None:
                prev = next((times[j][1] for j in range(k - 1, -1, -1) if times[j]), s0 + 0.2)
                nxt = next((times[j][0] for j in range(k + 1, len(toks)) if times[j]), s1 - 0.1)
                gapn = next((j for j in range(k + 1, len(toks)) if times[j]), len(toks)) - k
                span = (nxt - prev) / (gapn + 1); times[k] = (prev + span * 0.5, prev + span)
        for t, (s, e) in zip(toks, times):
            pc = next((k for k, it in enumerate(E) if it.get('take') == pi and it['rec_in'] - 0.05 <= s < it['rec_out']), E.index(tp[-1]))
            out.append({'piece': pc, 'w': t, 's': round(s, 3), 'e': round(e, 3)})
    return out
def groups(maxch=14):
    """Caption chunks: one line, <= maxch characters (+2 for short words ending in punctuation), never across a pause.
    job.CAPTION_KEYWORDS = ['protein', '18,000', ...] shows each of those words ALONE and bigger (Tharun's trademark,
    off by default: the signed-off finish is one size). Fast chunks (0.2 s) are fine: C0023 had 13 and was approved."""
    import job
    KW = {norm(k) for k in getattr(job, 'CAPTION_KEYWORDS', ())}
    ws = timed_words(); G = []; cur = []; BIG = set()
    def flush():
        if cur: G.append(list(cur)); cur.clear()
    for i, w in enumerate(ws):
        if KW and norm(w['w']) in KW:
            flush(); cur.append(w); flush(); BIG.add(len(G) - 1); continue
        cand = ' '.join(x['w'] for x in cur + [w])
        lim = maxch + (2 if w['w'][-1] in '.,?!' and len(w['w']) <= 4 else 0)
        if cur and (len(cand) > lim or w['piece'] != cur[-1]['piece'] or w['s'] - cur[-1]['e'] > 0.35): flush()
        cur.append(w)
        if w['w'][-1] in '.,?!': flush()
    flush()
    E = json.load(open('edl.json'))['items']; out = []
    for gi, g in enumerate(G):
        start = g[0]['s'] - 0.04
        nxt = G[gi + 1][0]['s'] - 0.04 if gi + 1 < len(G) else 1e9
        pend = E[g[-1]['piece']]['rec_out']
        end = min(nxt, max(g[-1]['e'] + 0.35, start + 0.5), pend if nxt - pend > 0.3 else nxt)
        out.append({'text': ' '.join(x['w'] for x in g), 'start': round(start, 3), 'end': round(end, 3),
                    'words': [{'w': x['w'], 's': x['s']} for x in g], **({'big': True} if gi in BIG else {})})
    # Resolve places each chunk on whole frames and gives it at least 3 (resolve_final: f1 = max(f0 + 3, end)).
    # Repair ONLY chunks that would then run into the next one (collapsed ASR stamps give zero or negative
    # length); every other chunk stays exactly as timed, so clean edits (C0023) are untouched.
    FPS = job.FPS
    def clash(i):
        if i + 1 >= len(out): return out[i]['end'] < out[i]['start']
        f0 = round(out[i]['start'] * FPS); return max(f0 + 3, round(out[i]['end'] * FPS)) > round(out[i + 1]['start'] * FPS)
    for i in range(1, len(out)):   # first try borrowing time from the chunk before
        if clash(i) or out[i]['end'] < out[i]['start']:
            ns = round(out[i]['end'] - 4 / FPS, 3)
            if ns - out[i - 1]['start'] >= 4 / FPS and ns < out[i]['start']: out[i]['start'] = ns; out[i - 1]['end'] = ns
    # still too short (a stray word left beside a keyword pop): fold it into a neighbour that isn't a keyword pop
    i = 0
    while i < len(out):
        if (clash(i) or out[i]['end'] - out[i]['start'] < 3 / FPS) and not out[i].get('big'):
            if i > 0 and not out[i - 1].get('big'):
                out[i - 1]['text'] += ' ' + out[i]['text']; out[i - 1]['words'] += out[i]['words']; out[i - 1]['end'] = out[i]['end']; del out[i]; continue
            if i + 1 < len(out) and not out[i + 1].get('big'):
                out[i + 1]['text'] = out[i]['text'] + ' ' + out[i + 1]['text']; out[i + 1]['words'] = out[i]['words'] + out[i + 1]['words']
                out[i + 1]['start'] = out[i]['start']; del out[i]; continue
        i += 1
    # a keyword pop needs time to be read: stretch it to 0.30 s, into the next chunk first, then the previous one
    for i, g in enumerate(out):
        need = 0.30 - (g['end'] - g['start'])
        if not g.get('big') or need <= 0: continue
        if i + 1 < len(out) and (out[i + 1]['end'] - out[i + 1]['start']) - need >= 0.16:
            g['end'] = round(g['end'] + need, 3); out[i + 1]['start'] = g['end']
        elif i > 0 and (out[i - 1]['end'] - out[i - 1]['start']) - need >= 0.16:
            g['start'] = round(g['start'] - need, 3); out[i - 1]['end'] = g['start']
    return out
if __name__ == '__main__':
    if '--draft' in sys.argv: draft(); sys.exit()
    G = groups(); json.dump(G, open('captions.json', 'w'), indent=0)
    for g in G: print(f"{g['start']:7.2f}-{g['end']:7.2f} {g['text']}")
    print(len(G), 'groups')

