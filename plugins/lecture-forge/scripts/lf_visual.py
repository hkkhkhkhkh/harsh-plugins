#!/usr/bin/env python3
"""Stage 1.5 — what is happening on screen, second by second.

Writes visual.json: a low-rate timeline of how much the picture is changing,
measured inside the board region and split into two signals.

    motion   how much the frame changed since the last sample. Catches the
             speaker walking, gesturing, pointing, wiping the board.
    ink      how much written content is on the board, as a fraction of the
             board area, and how fast it is changing. Catches writing, which is
             slow and sparse and barely registers as motion.

Why this exists: a pause while the speaker is writing on the board is not dead
air. The viewer is reading. Cutting those pauses to the same length as a
hesitation makes board content appear out of nowhere and destroys the
explanation. Stage 2 uses this timeline to keep visually busy pauses long and
cut frozen ones hard.

One decode pass at a low frame rate and resolution, so a 52-minute lecture costs
a couple of minutes and a few MB rather than a full-resolution decode per pause.

    lf_visual.py WORKDIR [--profile NAME] [--fps 2] [--force]
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import numpy as np

from lf_common import die, load_profile, log, read_json, require_ffmpeg, write_json

GRID_W, GRID_H = 320, 180
DEFAULT_FPS = 2.0


def decode_gray(src: Path, fps: float) -> np.ndarray:
    """The whole video as (n, H, W) greyscale at `fps`. One pass, low res."""
    proc = subprocess.Popen(
        [require_ffmpeg(), "-v", "error", "-nostdin", "-i", str(src),
         "-vf", f"fps={fps},scale={GRID_W}:{GRID_H}", "-pix_fmt", "gray",
         "-f", "rawvideo", "-"],
        stdout=subprocess.PIPE)
    frame_bytes = GRID_W * GRID_H
    frames = []
    while True:
        buf = proc.stdout.read(frame_bytes)
        if len(buf) < frame_bytes:
            break
        frames.append(np.frombuffer(buf, dtype=np.uint8).reshape(GRID_H, GRID_W))
    proc.stdout.close()
    proc.wait()
    if not frames:
        die("no frames decoded — is the video readable?")
    return np.stack(frames)


def main() -> None:
    ap = argparse.ArgumentParser(description="lecture-forge: on-screen activity timeline")
    ap.add_argument("workdir")
    ap.add_argument("--profile", default=None)
    ap.add_argument("--fps", type=float, default=DEFAULT_FPS)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    wd = Path(args.workdir).expanduser().resolve()
    media = read_json(wd / "media.json")
    out = wd / "visual.json"
    if out.exists() and not args.force:
        log("visual.json already present — use --force to redo")
        return

    src = Path(media["path"])
    if not src.exists():
        die(f"source has moved: {src}")
    profile = load_profile(args.profile)
    board = profile.get("board_box") or [0.0, 0.0, 1.0, 1.0]
    x0 = int(board[0] * GRID_W)
    y0 = int(board[1] * GRID_H)
    x1 = min(GRID_W, int((board[0] + board[2]) * GRID_W))
    y1 = min(GRID_H, int((board[1] + board[3]) * GRID_H))

    log(f"decoding at {args.fps:g} fps, board region {x1 - x0}x{y1 - y0} of {GRID_W}x{GRID_H}")
    frames = decode_gray(src, args.fps)
    board_px = frames[:, y0:y1, x0:x1].astype(np.float32)
    log(f"{len(frames)} samples over {len(frames) / args.fps / 60:.1f} min")

    # Motion: how much the board region changed since the previous sample.
    diff = np.abs(np.diff(board_px, axis=0)).mean(axis=(1, 2))
    motion = np.concatenate([[0.0], diff])

    # Ink: how much of the board is written on.
    cut = float(np.percentile(board_px, 96))
    ink = (board_px > cut).mean(axis=(1, 2))
    ink_delta = np.concatenate([[0.0], np.abs(np.diff(ink))])

    payload = {
        "fps": args.fps,
        "samples": len(frames),
        "board_box": board,
        "ink_threshold": round(cut, 2),
        "motion": [round(float(v), 4) for v in motion],
        "ink": [round(float(v), 5) for v in ink],
        "ink_delta": [round(float(v), 6) for v in ink_delta],
        "motion_percentiles": {str(p): round(float(np.percentile(motion, p)), 4)
                               for p in (25, 50, 75, 90, 95)},
        "ink_delta_percentiles": {str(p): round(float(np.percentile(ink_delta, p)), 6)
                                  for p in (50, 75, 90, 95)},
    }
    write_json(out, payload)
    log(f"motion  p50 {payload['motion_percentiles']['50']}  "
        f"p90 {payload['motion_percentiles']['90']}")
    log(f"ink     mean {np.mean(ink):.3f} of board, "
        f"delta p90 {payload['ink_delta_percentiles']['90']}")
    log(f"wrote {out}")


if __name__ == "__main__":
    main()
