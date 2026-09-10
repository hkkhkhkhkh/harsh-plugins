#!/usr/bin/env python3
"""Stage 0 — ingest and probe.

Creates the workdir, reads the media properties, and extracts the 16 kHz mono
WAV that every later analysis stage reads.

ffprobe is not installed on every machine, so the properties are parsed out of
`ffmpeg -i` stderr when ffprobe is missing. ffprobe is used when available
because its JSON is unambiguous.

    lf_probe.py SOURCE [--out-root DIR] [--force]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from lf_common import (
    FFPROBE, MediaInfo, die, ffmpeg_run, hhmmss, log, require_ffmpeg, run,
    workdir_for, write_json,
)

ANALYSIS_RATE = 16000


# --------------------------------------------------------------------------
# ffprobe path (preferred)
# --------------------------------------------------------------------------

def _probe_with_ffprobe(src: Path) -> MediaInfo:
    proc = run([FFPROBE, "-v", "error", "-print_format", "json",
                "-show_format", "-show_streams", str(src)])
    data = json.loads(proc.stdout)
    video = next((s for s in data["streams"] if s.get("codec_type") == "video"), None)
    audio = next((s for s in data["streams"] if s.get("codec_type") == "audio"), None)
    if video is None:
        die(f"no video stream in {src}")

    fps = 0.0
    for key in ("avg_frame_rate", "r_frame_rate"):
        raw = video.get(key) or ""
        if "/" in raw:
            num, den = raw.split("/")
            if float(den) > 0:
                fps = float(num) / float(den)
                if fps > 0:
                    break

    return MediaInfo(
        path=str(src),
        duration=float(data["format"].get("duration") or video.get("duration") or 0.0),
        width=int(video["width"]),
        height=int(video["height"]),
        fps=round(fps, 6),
        has_audio=audio is not None,
        audio_rate=int(audio.get("sample_rate", 0)) if audio else 0,
        vcodec=video.get("codec_name", "?"),
        acodec=(audio or {}).get("codec_name", ""),
    )


# --------------------------------------------------------------------------
# ffmpeg stderr fallback
# --------------------------------------------------------------------------

_DUR_RE = re.compile(r"Duration:\s*(\d+):(\d\d):(\d\d(?:\.\d+)?)")
_VIDEO_RE = re.compile(r"Stream #\d+:\d+.*?: Video:\s*([\w0-9]+).*", re.IGNORECASE)
_AUDIO_RE = re.compile(r"Stream #\d+:\d+.*?: Audio:\s*([\w0-9]+).*?(\d+)\s*Hz", re.IGNORECASE)
# Match WxH but not a bitrate or a display-aspect fragment.
_SIZE_RE = re.compile(r"(?<![\d])(\d{2,5})x(\d{2,5})(?![\d])")
_FPS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*fps")
_TBR_RE = re.compile(r"(\d+(?:\.\d+)?)\s*tbr")


def _probe_with_ffmpeg(src: Path) -> MediaInfo:
    # `ffmpeg -i FILE` with no output exits 1 by design; the report is on stderr.
    proc = run([require_ffmpeg(), "-hide_banner", "-i", str(src)], check=False)
    text = proc.stderr or ""
    if "Invalid data found" in text or "No such file" in text:
        die(f"ffmpeg cannot read {src}")

    duration = 0.0
    m = _DUR_RE.search(text)
    if m:
        duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))

    vline = next((ln for ln in text.splitlines() if _VIDEO_RE.search(ln)), None)
    if vline is None:
        die(f"no video stream found in {src}")
    vcodec = _VIDEO_RE.search(vline).group(1)

    size = _SIZE_RE.search(vline)
    if not size:
        die(f"could not read frame size from ffmpeg output for {src}")
    width, height = int(size.group(1)), int(size.group(2))

    fps = 0.0
    for rex in (_FPS_RE, _TBR_RE):
        m = rex.search(vline)
        if m:
            fps = float(m.group(1))
            break

    aline = next((ln for ln in text.splitlines() if _AUDIO_RE.search(ln)), None)
    acodec, arate = "", 0
    if aline:
        am = _AUDIO_RE.search(aline)
        acodec, arate = am.group(1), int(am.group(2))

    return MediaInfo(
        path=str(src), duration=duration, width=width, height=height,
        fps=round(fps, 6), has_audio=aline is not None, audio_rate=arate,
        vcodec=vcodec, acodec=acodec,
    )


def probe(src: Path) -> MediaInfo:
    info = _probe_with_ffprobe(src) if FFPROBE else _probe_with_ffmpeg(src)
    if info.duration <= 0:
        die(f"could not determine duration of {src}")
    if not info.has_audio:
        die(f"{src} has no audio track — nothing to transcribe")
    if info.fps <= 0:
        log("warning: frame rate unknown, assuming 30 fps for punch-in scheduling")
        info.fps = 30.0
    return info


# --------------------------------------------------------------------------

def extract_analysis_audio(src: Path, dest: Path, *, force: bool = False) -> None:
    if dest.exists() and not force:
        log(f"analysis audio already present: {dest.name}")
        return
    log("extracting 16 kHz mono analysis audio")
    ffmpeg_run(["-y", "-i", str(src), "-vn", "-ac", "1", "-ar", str(ANALYSIS_RATE),
                "-c:a", "pcm_s16le", str(dest)])


def main() -> None:
    ap = argparse.ArgumentParser(description="lecture-forge stage 0: probe and ingest")
    ap.add_argument("source")
    ap.add_argument("--out-root", default=None,
                    help="parent directory for the workdir (default: <source_dir>/lecture-forge)")
    ap.add_argument("--force", action="store_true", help="re-extract analysis audio")
    args = ap.parse_args()

    src = Path(args.source).expanduser().resolve()
    if not src.is_file():
        die(f"not a file: {src}")

    wd = workdir_for(src, args.out_root)
    info = probe(src)
    extract_analysis_audio(src, wd / "analysis.wav", force=args.force)

    payload = info.to_dict()
    payload["workdir"] = str(wd)
    write_json(wd / "media.json", payload)

    log(f"source   {src.name}")
    log(f"duration {hhmmss(info.duration)}  ({info.duration:.2f}s)")
    log(f"video    {info.width}x{info.height} @ {info.fps:g} fps  [{info.vcodec}]")
    log(f"audio    {info.acodec} {info.audio_rate} Hz")
    log(f"workdir  {wd}")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
