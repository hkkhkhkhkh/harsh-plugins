"""Audio stems (each on its own Resolve track at unity; together job.LUFS_TARGET, default -16 LUFS).
dialogue: dialogue.py output (source-cut, 8 ms join fades, DeepFilterNet + EQ/de-ess/comp).
music: v3 = "Paris" by ELSE (Harsh's own local copy, same file R3 used), from the top, ducked under the voice.
v3 levels: whole mix -16 LUFS (Harsh: v2 at -14 was too loud; R3 sat at ~-17.5), music 4 dB lower than v2.
sfx (sound design): placed by sfx_rules.py from the graphics, inserts and zooms (whoosh per card, pop per row, strike,
riser + impact on the price, whip per punch/snap, air whoosh around inserts, pop on the CTA). Files come from sfx.py:
the approved house sounds, or rotating level-matched library variants when job.SFX_VARIANTS is True.
music drop outs: job.MUSIC_DROPS = [(start, end), ...] record-time spans of lines that should land with no bed."""
import json, re, subprocess, imageio_ffmpeg
import zooms, sfx, sfx_rules, job
FF = imageio_ffmpeg.get_ffmpeg_exe()
E = json.load(open('edl.json')); DUR = E['duration']
G = json.load(open('graphics/graphics_timing.json')); I = json.load(open('graphics/inserts_timing.json'))
# sound design comes from the edit (sfx_rules.py); job.EXTRA_HITS = [(t, key, gain_db), ...] for one-offs
H = sfx_rules.hits(G, I, zooms.plan(), E['items'], extra=getattr(job, 'EXTRA_HITS', ()))
VARIANTS = getattr(job, 'SFX_VARIANTS', False)
PICK = [sfx.pick(k, VARIANTS) for _, k, _ in H]          # (file, level correction dB) per hit
# music drop outs: the bed goes silent just before a line that should land alone, back in after it
DROPS = [(round(s - 0.45, 3), round(e + 0.15, 3)) for s, e in getattr(job, 'MUSIC_DROPS', ())]
def bed_gain():
    if not DROPS: return ''
    f = '*'.join(f"(1-min(1,max(0,min((t-{a:.3f})/0.12,({b:.3f}-t)/0.30))))" for a, b in DROPS)
    return f",volume='{f}':eval=frame"
def run(a):
    r = subprocess.run([FF, '-nostdin', '-v', 'error', '-y', *a], capture_output=True, text=True)
    if r.returncode: raise SystemExit(r.stderr[-2000:])
def lufs(f):
    m = subprocess.run([FF, '-nostdin', '-i', f, '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True)
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", m.stderr)[-1])
MUSIC_TARGET = -24.0   # pre-duck bed level; voice sits at -14, ducking takes the bed ~4-6 dB lower under speech
MUSIC = job.MUSIC
MUS_GAIN = round(MUSIC_TARGET - lufs(MUSIC), 2)
def post_limit(f, lim):
    # peak-limit a finished stem in its own pass: a limiter (look-ahead) inside the shared sidechain graph deadlocks ffmpeg
    tmp = f + ".lim.wav"; run(['-i', f, '-af', f'alimiter=limit={lim}:attack=2:release=50:level=disabled', '-c:a', 'pcm_s24le', tmp]); __import__('os').replace(tmp, f)

def build(off):
    ins = ['-i', 'audio/dialogue_enhanced.wav', '-i', MUSIC]
    fc = [f"[0:a]atrim=0:{DUR},volume={off}dB,alimiter=limit=0.8:attack=2:release=40:level=disabled,aformat=sample_rates=48000:channel_layouts=stereo,asplit=2[dlg][key]",
          f"[1:a]atrim=0:{DUR},asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.8,afade=t=out:st={DUR-2.2}:d=2.2,volume={MUS_GAIN+off}dB{bed_gain()},aformat=sample_rates=48000:channel_layouts=stereo[mus]",
          "[mus][key]sidechaincompress=threshold=0.06:ratio=2.5:attack=15:release=450[musd]"]
    labs = []
    for k, ((t, name, g), (f, corr)) in enumerate(zip(H, PICK)):
        ins += ['-i', f]; ms = int(t * 1000)
        fc.append(f"[{2+k}:a]aresample=48000,aformat=sample_rates=48000:channel_layouts=stereo,volume={g+corr+off+getattr(job, 'SFX_TRIM_DB', 0)}dB,adelay={ms}|{ms}[s{k}]"); labs.append(f"[s{k}]")
    fc.append(''.join(labs) + f"amix=inputs={len(labs)}:normalize=0:duration=longest,apad=whole_dur={DUR},atrim=0:{DUR}[sfx]")
    run([*ins, '-filter_complex', ';'.join(fc), '-map', '[dlg]', '-c:a', 'pcm_s24le', 'audio/stem_dialogue.wav',
         '-map', '[musd]', '-c:a', 'pcm_s24le', 'audio/stem_music.wav', '-map', '[sfx]', '-c:a', 'pcm_s24le', 'audio/stem_sfx.wav'])
    post_limit('audio/stem_music.wav', 0.6); post_limit('audio/stem_sfx.wav', 0.5)
    run(['-i', 'audio/stem_dialogue.wav', '-i', 'audio/stem_music.wav', '-i', 'audio/stem_sfx.wav', '-filter_complex',
         'amix=inputs=3:normalize=0:duration=first', '-c:a', 'pcm_s24le', 'audio/mix_sum_check.wav'])
    m = subprocess.run([FF, '-nostdin', '-i', 'audio/mix_sum_check.wav', '-af', 'loudnorm=I=-14:TP=-1.5:print_format=json', '-f', 'null', '-'], capture_output=True, text=True)
    j = json.loads(re.findall(r"\{[^{}]*\}", m.stderr, flags=re.S)[-1]); return float(j['input_i']), float(j['input_tp'])
if __name__ == '__main__':
    import numpy as np
    from scipy.io import wavfile
    def sep():  # median voice-over-music (dB) where the voice is speaking, 0.4 s windows
        def r(f):
            sr, x = wavfile.read(f); x = x.astype(np.float64); x = x / 2**31 if np.abs(x).max() > 40000 else x / 2**15
            x = x.mean(1) if x.ndim == 2 else x; w = int(sr * 0.4); n = len(x) // w
            return 20 * np.log10(np.sqrt((x[:n*w].reshape(n, w) ** 2).mean(1)) + 1e-9)
        d, m = r('audio/stem_dialogue.wav'), r('audio/stem_music.wav'); k = min(len(d), len(m)); d, m = d[:k], m[:k]
        sp = d > np.percentile(d, 30); return float(np.median(d[sp] - m[sp]))
    print(len(H), 'sfx hits'); off = 0.0
    for it in range(4):   # land both targets: whole-mix loudness AND voice-over-music gap
        I1, TP = build(off); off = round(off + job.LUFS_TARGET - I1, 2); I2, TP = build(off); gap = sep()
        print(f'pass {it}: {I2} LUFS {TP} dBTP, voice over music {gap:.1f} dB (music gain {MUS_GAIN})')
        if abs(gap - job.VOICE_OVER_MUSIC_DB) < 1.0: break
        MUS_GAIN = round(MUS_GAIN + (gap - job.VOICE_OVER_MUSIC_DB), 2)
    json.dump([{'t': round(t, 3), 'sfx': k, 'gain_db': g, 'file': f, 'corr_db': c} for (t, k, g), (f, c) in zip(H, PICK)],
              open('audio/sfx_cues.json', 'w'), indent=0)
