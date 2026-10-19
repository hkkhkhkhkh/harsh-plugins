"""Map source word timestamps (transcripts/phrases.json, per-phrase medium ASR) onto the record timeline via edl.json."""
import json, job
def rec_words():
    e = json.load(open('edl.json')); WS = {}
    def words(clip):
        if clip not in WS:   # Whisper sometimes stamps a word with zero length; give it 60 ms so the overlap test can place it
            WS[clip] = [{**w, 'e': max(w['e'], w['s'] + 0.06)} for p in json.load(open(job.source(clip)['phrases'])) for w in p['words']]
        return WS[clip]
    out = []
    for i, it in enumerate(e['items']):
        if it['kind'] != 'a': continue
        for w in words(it.get('clip')):
            # assign each word to the piece it overlaps most (Whisper word starts run early, so a midpoint test drops words)
            ov = lambda p: min(p['src_out'], w['e']) - max(p['src_in'], w['s'])
            cands = [(ov(p), k) for k, p in enumerate(e['items']) if p['kind'] == 'a' and p.get('clip') == it.get('clip') and ov(p) > 0]
            if cands and max(cands)[1] == i:
                out.append({"piece": i, "take": it["take"], "w": w['w'].strip(), "s": round(it['rec_in'] + max(0, w['s'] - it['src_in']), 3),
                            "e": round(it['rec_in'] + min(it['src_out'], w['e']) - it['src_in'], 3)})
    return out
if __name__ == '__main__':
    ws = rec_words(); json.dump(ws, open('transcripts/rec_words.json', 'w'), indent=0)
    cur = None
    for w in ws:
        if w['piece'] != cur: print(); cur = w['piece']; print(f"[{cur}]", end=' ')
        print(f"{w['w']}@{w['s']:.2f}", end=' ')
