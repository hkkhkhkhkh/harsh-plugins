"""Cinematic grade + darker background, baked into a new source file per clip (same frame count, 30 fps, 1440x2560 ProRes HQ).
Background = everything outside the Vision person matte: pulled down ~1 stop and desaturated; subject gets a gentle filmic
curve with warm skin and slightly cool shadows; soft vignette on top. Also writes a person cut-out (ProRes 4444 + alpha) used to
put words BEHIND him. Usage: python3 bake.py IN.mov OUT.mov MATTE.mkv [--test SECONDS]  (matte from personmatte.swift)"""
import subprocess, sys, imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
SRC, OUT, MATTE = sys.argv[1], sys.argv[2], sys.argv[3]
CUT = OUT.rsplit(".", 1)[0] + "_cutout.mov"; n = __import__("os").path.splitext(__import__("os").path.basename(SRC))[0]
W, H = 1440, 2560
test = sys.argv[sys.argv.index('--test') + 1] if '--test' in sys.argv else None
# subject: filmic S-curve, slightly lower blacks, warm highlights / cool shadows, a touch less saturation
SUBJ = ("curves=master='0/0.015 0.25/0.22 0.5/0.5 0.75/0.79 1/0.97',"
        "colorbalance=rs=-0.02:bs=0.03:rh=0.025:gh=0.005:bh=-0.03,eq=saturation=0.94")
# background: same look, then ~1 stop darker and more desaturated
BG = SUBJ + ",eq=saturation=0.78,colorchannelmixer=rr=0.6:gg=0.6:bb=0.62"
# v6 (28 Sep, "rotoscope around the hair looks really bad"): the matte only drives a WIDE soft falloff (sigma 45 px at 1440 wide),
# so the background darkens like light falling off behind him and there is no cut-out edge anywhere to see. No cut-out file.
fc = (f"[0:v]setpts=N/30/TB,scale={W}:{H}:flags=lanczos,format=gbrp10le,split=2[a][b];"
      f"[a]{SUBJ}[fg];[b]{BG}[bg];"
      f"[1:v]setpts=N/30/TB,format=gray,tmix=frames=7,scale={W}:{H}:flags=bicubic,gblur=sigma=45,format=gbrp10le[m];"
      f"[bg][fg][m]maskedmerge,vignette=angle=PI/4.6:mode=forward,format=yuv422p10le[v]")
seek = ["-ss", "0", "-t", test] if test else []
cmd = [FF, "-nostdin", "-loglevel", "error", "-y", *seek, "-i", SRC, *seek, "-i", MATTE, "-filter_complex", fc,
       "-map", "[v]", "-map", "0:a?", "-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le", "-r", "30",
       "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-c:a", "copy", OUT if not test else f"test_{n}.mov"]
import os; os.makedirs(os.path.dirname(OUT), exist_ok=True)
subprocess.run(cmd, check=True); print("baked", n)
