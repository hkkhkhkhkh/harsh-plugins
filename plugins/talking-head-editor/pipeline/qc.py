"""Step 6. QC the rendered file: loudness, full decode, black edges (zoom bugs), pauses left in the dialogue, a transcript
of the render (compare with the verified script), a 1 fps contact sheet. Read the sheet and the transcript yourself."""
import json, os, re, subprocess, sys, imageio_ffmpeg, numpy as np, job
from scipy.io import wavfile
FF = imageio_ffmpeg.get_ffmpeg_exe(); F = sys.argv[1] if len(sys.argv) > 1 else f'render/{job.OUT_NAME}_final.mp4'
m = subprocess.run([FF, '-nostdin', '-i', F, '-af', f'loudnorm=I={job.LUFS_TARGET}:TP=-1.5:print_format=summary', '-f', 'null', '-'], capture_output=True, text=True)
print('\n'.join(l for l in m.stderr.splitlines() if 'Input Integrated' in l or 'Input True Peak' in l))
print('decode', 'ok' if subprocess.run([FF, '-nostdin', '-v', 'error', '-i', F, '-f', 'null', '-'], capture_output=True).returncode == 0 else 'FAILED')
p = subprocess.run([FF, '-nostdin', '-v', 'error', '-i', F, '-vf', 'fps=4,scale=270:480,format=gray', '-f', 'rawvideo', '-'], capture_output=True)
a = np.frombuffer(p.stdout, np.uint8).reshape(-1, 480, 270)
print('black-edge frames:', sum(1 for f in a if min(f[:, -4:].mean(), f[-4:, :].mean(), f[:, :4].mean()) < 6))
sr, x = wavfile.read('audio/dialogue_raw.wav'); x = x.astype(np.float32); x = x / 32768 if np.abs(x).max() > 2 else x
w = int(sr * 0.01); n = len(x) // w; r = 20 * np.log10(np.sqrt((x[:n*w].reshape(n, w) ** 2).mean(1)) + 1e-9)
gaps, k, sp = [], 0, r > (np.percentile(r, 95) - 29)   # same relative line as edl.py
while k < n:
    if not sp[k]:
        j = k
        while j < n and not sp[j]: j += 1
        gaps.append((j - k) * 0.01); k = j
    else: k += 1
print('dialogue pauses >= 0.12 s:', sum(g >= 0.12 for g in gaps), '| longest %.2f s' % max(gaps or [0]))
os.makedirs('qc', exist_ok=True)
subprocess.run([FF, '-nostdin', '-v', 'error', '-y', '-i', F, '-vf', 'fps=1,scale=180:320,tile=10x12', '-frames:v', '1', 'qc/contact_sheet.jpg'], check=True)
print('contact sheet: qc/contact_sheet.jpg (read it)')
line = getattr(job, "CAPTION_Y", 1150 if getattr(job, "AD_SAFE", False) else 1280)
print(f"caption line y {line}:", "clear of Meta's ad UI (y 1248)" if line + 60 <= 1248 else
      "inside Meta's ad UI zone (fine organic; set job.AD_SAFE = True before this runs as a paid ad)")
subprocess.run([FF, '-nostdin', '-v', 'error', '-y', '-i', F, '-vn', '-ac', '1', '-ar', '16000', 'audio/final_16k.wav'])
from faster_whisper import WhisperModel
ss, _ = WhisperModel('medium', device='cpu', compute_type='int8').transcribe('audio/final_16k.wav', language='en', condition_on_previous_text=False, beam_size=5, vad_filter=True)
print('RENDER TRANSCRIPT:', ' '.join(s.text.strip() for s in ss))
