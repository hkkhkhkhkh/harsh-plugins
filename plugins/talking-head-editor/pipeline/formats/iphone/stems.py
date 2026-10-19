"""Audio stems (each on its own Resolve track at unity; together job.LUFS_TARGET, default -16 LUFS).
dialogue: dialogue.py output (source-cut, 8 ms join fades, DeepFilterNet + EQ/de-ess/comp).
music: v3 = "Paris" by ELSE (Harsh's own local copy, same file R3 used), from the top, ducked under the voice.
v3 levels: whole mix -16 LUFS (Harsh: v2 at -14 was too loud; R3 sat at ~-17.5), music 4 dB lower than v2.
sfx (sound design): whoosh on card entries, pop per list item, marker strike on crossings-out, whip on every prompt zoom,
riser into the price and a soft sub impact on it, air whooshes on the insert cuts, pop on the CTA button."""
import json, re, subprocess, imageio_ffmpeg, wave
import zooms
FF = imageio_ffmpeg.get_ffmpeg_exe()
E = json.load(open('edl.json')); DUR = E['duration']

def dur(f): w = wave.open(f); return w.getnframes() / w.getframerate()
SD = 'audio/sd/'; RISER = dur(SD + 'riser.wav')
H = [(h['t'], h['sfx'], h['gain_db']) for h in json.load(open('audio/sfx_plan.json'))]
for z, it in zip(zooms.plan(), E['items']):
    if z['kind'] == 'punch' and z['first'] and z['piece'] > 0: H.append((it['rec_in'] - .06, 'whip_zoom', -21))
    if z['snap_t'] is not None: H.append((it['rec_in'] + z['snap_t'] - .04, 'whip_zoom', -19))
FILES = {k: SD + f'{k}.wav' for k in ('whoosh_soft', 'pop', 'strike', 'riser', 'impact', 'whip_zoom')}
FILES['fastwhoosh'] = 'audio/sfx/Fast whoosh.wav'
H = sorted((max(0, t), k, g) for t, k, g in H)
def run(a):
    r = subprocess.run([FF, '-nostdin', '-v', 'error', '-y', *a], capture_output=True, text=True)
    if r.returncode: raise SystemExit(r.stderr[-2000:])
def lufs(f):
    m = subprocess.run([FF, '-nostdin', '-i', f, '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True)
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", m.stderr)[-1])
MUSIC_TARGET = -24.0   # pre-duck bed level; voice sits at -14, ducking takes the bed ~4-6 dB lower under speech
import job
MUSIC = job.MUSIC
MO = float(getattr(job, 'MUSIC_OFFSET', 0))   # start point inside the track
MUS_GAIN = round(MUSIC_TARGET - lufs(MUSIC), 2)
def post_limit(f, lim):
    # peak-limit a finished stem in its own pass: a limiter (look-ahead) inside the shared sidechain graph deadlocks ffmpeg
    tmp = f + ".lim.wav"; run(['-i', f, '-af', f'alimiter=limit={lim}:attack=2:release=50:level=disabled', '-c:a', 'pcm_s24le', tmp]); __import__('os').replace(tmp, f)

def build(off):
    ins = ['-i', 'audio/dialogue_enhanced.wav', '-i', MUSIC]
    fc = [f"[0:a]atrim=0:{DUR},volume={off}dB,alimiter=limit=0.75:attack=2:release=40:level=disabled,aformat=sample_rates=48000:channel_layouts=stereo,asplit=3[dlg][key][key2]",
          f"[1:a]atrim={MO}:{MO+DUR},asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.8,afade=t=out:st={DUR-2.2}:d=2.2,volume={MUS_GAIN+off}dB,aformat=sample_rates=48000:channel_layouts=stereo[mus]",
          "[mus][key]sidechaincompress=threshold=0.06:ratio=2.5:attack=15:release=450[musd]"]
    labs = []
    for k, (t, name, g) in enumerate(H):
        ins += ['-i', FILES[name]]; ms = int(t * 1000)
        fc.append(f"[{2+k}:a]aresample=48000,aformat=sample_rates=48000:channel_layouts=stereo,volume={g+off}dB,adelay={ms}|{ms}[s{k}]"); labs.append(f"[s{k}]")
    fc.append(''.join(labs) + f"amix=inputs={len(labs)}:normalize=0:duration=longest,apad=whole_dur={DUR},atrim=0:{DUR}[sfxraw]")
    fc.append("[sfxraw][key2]sidechaincompress=threshold=0.08:ratio=4:attack=5:release=200[sfx]")  # hits duck under the voice so they never stack on a speech peak
    run([*ins, '-filter_complex', ';'.join(fc), '-map', '[dlg]', '-c:a', 'pcm_s24le', 'audio/stem_dialogue.wav',
         '-map', '[musd]', '-c:a', 'pcm_s24le', 'audio/stem_music.wav', '-map', '[sfx]', '-c:a', 'pcm_s24le', 'audio/stem_sfx.wav'])
    post_limit('audio/stem_music.wav', 0.5); post_limit('audio/stem_sfx.wav', 0.35)
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
        if abs(gap - job.VOICE_OVER_MUSIC_DB) < 1.0 and TP <= -1.0: break
        if TP > -1.0:  # true-peak guard: trade a little loudness rather than clip on Instagram's encoder
            off = round(off - (TP + 1.3), 2); I2, TP = build(off); print(f'  tp guard: {I2} LUFS {TP} dBTP')
        MUS_GAIN = round(MUS_GAIN + (gap - job.VOICE_OVER_MUSIC_DB), 2)
    json.dump([{'t': round(t, 3), 'sfx': k, 'gain_db': g} for t, k, g in H], open('audio/sfx_cues.json', 'w'), indent=0)
