"""Step 2. Two ASR passes (never trust one): whole-clip faster-whisper small for take boundaries, then medium on each
energy phrase (speech > -25 dBFS on the 16 kHz source, gaps < 0.5 s merged) for words. -> transcripts/phrases.json
(source-time words; wordmap.py maps them to the cut). Print the phrase list and write KEEP in edl.py from it:
later take wins, drop false starts / asides / compliance lines, keep one complete thought per take."""
import json, os, numpy as np
from scipy.io import wavfile
from faster_whisper import WhisperModel
os.makedirs('transcripts', exist_ok=True)
sr, x = wavfile.read('audio/c0023_16k.wav'); x = x.astype(np.float32) / 32768
w = int(sr * 0.02); n = len(x) // w; r = 20 * np.log10(np.sqrt((x[:n*w].reshape(n, w) ** 2).mean(1)) + 1e-9)
TH = float(np.percentile(r, 15)) + 12.0   # adaptive: room floor + 12 dB (FX30 lav ~ -25 dBFS; iPhone mics sit lower)
print(f'phrase threshold {TH:.1f} dBFS')
sp = r > TH; spans = []; i = 0
while i < n:
    if sp[i]:
        j = i
        while j < n and sp[j:j + 25].any(): j += 1
        if (j - i) * 0.02 > 0.25: spans.append([round(i * 0.02, 2), round(j * 0.02, 2)])
        i = j
    else: i += 1
# pass 1: whole clip, small model -> take boundaries (keeps retakes apart; words may be garbled)
small = WhisperModel('small', device='cpu', compute_type='int8')
segs, _ = small.transcribe('audio/c0023_16k.wav', language='en', word_timestamps=True, condition_on_previous_text=False, beam_size=5)
whole = [{"start": s.start, "end": s.end, "text": s.text} for s in segs]
json.dump(whole, open('transcripts/whole.small.json', 'w'), indent=1)
print('--- pass 1 (take boundaries) ---'); [print(f"{s['start']:7.2f}-{s['end']:7.2f} {s['text']}") for s in whole]
print('--- pass 2 (words, per phrase) ---')
m = WhisperModel('medium', device='cpu', compute_type='int8'); out = []
for a, b in spans:
    seg = x[max(0, int((a - 0.15) * sr)):int((b + 0.15) * sr)]
    ss, _ = m.transcribe(seg, language='en', word_timestamps=True, condition_on_previous_text=False, beam_size=5)
    words = []; txt = ''
    for s in ss:
        txt += s.text; words += [{"w": q.word, "s": round(a - 0.15 + q.start, 3), "e": round(a - 0.15 + q.end, 3)} for q in s.words]
    out.append({"s": a, "e": b, "text": txt.strip(), "words": words}); print(f"{a:7.2f}-{b:7.2f} {txt.strip()}", flush=True)
json.dump(out, open('transcripts/phrases.json', 'w'), indent=1)
