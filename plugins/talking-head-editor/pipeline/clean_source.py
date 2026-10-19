"""Step 1b. Extract the source audio and clean the WHOLE clip with DeepFilterNet 3 (job.DFPY venv).
-> audio/c0023_16k.wav (ASR), audio/c0023_48k.wav (raw), audio/c0023_48k_df.wav (cleaned; edl.py and dialogue.py read this).
File names keep the reference 'c0023_' prefix on purpose so the other scripts need no edits."""
import subprocess, imageio_ffmpeg, os, job
FF = imageio_ffmpeg.get_ffmpeg_exe(); os.makedirs('audio', exist_ok=True)
run = lambda a: subprocess.run([FF, '-nostdin', '-v', 'error', '-y', *a], check=True)
run(['-i', str(job.SRC), '-map', '0:a:0', '-ac', '1', '-ar', '16000', 'audio/c0023_16k.wav'])
run(['-i', str(job.SRC), '-map', '0:a:0', '-c:a', 'pcm_s24le', 'audio/c0023_48k.wav'])
run(['-i', 'audio/c0023_48k.wav', '-ac', '1', '-c:a', 'pcm_s16le', 'audio/c0023_48k_mono.wav'])
code = ("from df.enhance import enhance, init_df, load_audio, save_audio\nm,s,_=init_df()\n"
        "a,_=load_audio('audio/c0023_48k_mono.wav', sr=s.sr())\nsave_audio('audio/c0023_48k_df.wav', enhance(m,s,a,atten_lim_db=30), s.sr())\n")
subprocess.run([job.DFPY, '-c', code], check=True); print('cleaned')
