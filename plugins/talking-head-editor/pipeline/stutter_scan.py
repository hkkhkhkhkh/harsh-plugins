"""Stutter scan: transcribe every A-roll piece on its own (medium, word stamps, no VAD) so Whisper can't merge a repeat across
a cut, then flag (1) the next piece starting with the word(s) the previous one ended on, (2) a piece that is a false start of the
next (its words are a prefix of the next piece), (3) a doubled word or bigram inside one piece. -> transcripts/stutter_scan.json"""
import json, re, numpy as np, scipy.signal as ss
from scipy.io import wavfile
from faster_whisper import WhisperModel
E = json.load(open('edl.json'))['items']; A = [(i, p) for i, p in enumerate(E) if p['kind'] == 'a']
sr, x = wavfile.read('audio/c0023_48k_df.wav'); x = x.astype('float32'); x = x / 32768 if abs(x).max() > 2 else x
m = WhisperModel('medium', device='cpu', compute_type='int8')
n = lambda w: re.sub(r"[^a-z0-9%]", "", w.lower())
out = []
for i, p in A:
    seg = ss.resample_poly(x[int((p['src_in'] - 0.03) * sr):int((p['src_out'] + 0.03) * sr)], 1, 3).astype('float32')
    s, _ = m.transcribe(seg, language='en', word_timestamps=True, beam_size=5, condition_on_previous_text=False, vad_filter=False)
    ws = [{"w": w.word.strip(), "s": round(p['src_in'] - 0.03 + w.start, 3), "e": round(p['src_in'] - 0.03 + w.end, 3)} for q in s for w in q.words]
    out.append({"piece": i, "take": p['take'], "src_in": p['src_in'], "src_out": p['src_out'], "rec_in": p['rec_in'], "words": ws}); print(i, ' '.join(w['w'] for w in ws), flush=True)
flags = []
for a, b in zip(out, out[1:]):
    wa, wb = [n(w['w']) for w in a['words'] if n(w['w'])], [n(w['w']) for w in b['words'] if n(w['w'])]
    if not wa or not wb: continue
    for k in (3, 2, 1):
        if len(wa) >= k and len(wb) >= k and wa[-k:] == wb[:k]:
            flags.append({"kind": "repeat_across_cut", "words": wa[-k:], "prev": a['piece'], "next": b['piece'], "rec": b['rec_in']}); break
    else:
        if len(wa) >= 2 and wb[:len(wa)] == wa: flags.append({"kind": "false_start", "words": wa, "prev": a['piece'], "next": b['piece'], "rec": a['rec_in']})
for a in out:
    wa = [n(w['w']) for w in a['words'] if n(w['w'])]
    for k in range(len(wa) - 1):
        if wa[k] == wa[k + 1] and wa[k] not in ('had', 'that', 'very', 'time'): flags.append({"kind": "double_word", "words": [wa[k]], "piece": a['piece'], "rec": a['rec_in']})
    for k in range(len(wa) - 3):
        if wa[k:k + 2] == wa[k + 2:k + 4]: flags.append({"kind": "double_bigram", "words": wa[k:k + 2], "piece": a['piece'], "rec": a['rec_in']})
json.dump({"pieces": out, "flags": flags}, open('transcripts/stutter_scan.json', 'w'), indent=1)
print("FLAGS", len(flags)); [print(f) for f in flags]
