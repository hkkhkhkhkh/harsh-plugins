"""Web delivery: a landing-page / site encode of the master render plus a poster frame.
  python3 web_encode.py render/<OUT_NAME>_final.mp4 --poster-at 16.7 [--height 720] [--maxrate 1100k] [--out web/vsl.mp4]
720p H.264 (CRF 23, capped bitrate), AAC 128k, +faststart so playback starts before the download ends and seeking works
(range requests). A 7-minute VSL lands near 40 MB, small enough to commit to a site repo's public/ folder; check it plays
from the deployed URL (HTTP 206 on a range request, content-type video/mp4) before calling it live.
Poster: pick a frame that sells (a card with the offer or guarantee on screen beats a mid-word face)."""
import argparse, os, subprocess, imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("--poster-at", type=float, required=True)
ap.add_argument("--height", type=int, default=720); ap.add_argument("--maxrate", default="1100k"); ap.add_argument("--out", default="web/vsl.mp4")
a = ap.parse_args(); os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
subprocess.run([FF, "-nostdin", "-v", "error", "-y", "-i", a.src, "-vf", f"scale=-2:{a.height}:flags=lanczos", "-c:v", "libx264", "-preset", "slow",
                "-crf", "23", "-maxrate", a.maxrate, "-bufsize", str(int(a.maxrate.rstrip("k")) * 2) + "k", "-profile:v", "high", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k", "-ac", "2", "-movflags", "+faststart", a.out], check=True)
poster = os.path.splitext(a.out)[0] + "-poster.jpg"
subprocess.run([FF, "-nostdin", "-v", "error", "-y", "-ss", str(a.poster_at), "-i", a.src, "-frames:v", "1", "-vf", f"scale=-2:{a.height}", "-q:v", "4", poster], check=True)
print(f"{a.out}: {os.path.getsize(a.out) / 1e6:.1f} MB   poster: {poster} ({os.path.getsize(poster) / 1e3:.0f} KB)")
