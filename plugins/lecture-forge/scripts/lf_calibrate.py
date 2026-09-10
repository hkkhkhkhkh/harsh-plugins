#!/usr/bin/env python3
"""One-time room/camera calibration.

Samples frames across the recording and proposes two boxes:

  board_box    bright, and still across time — the smartboard or whiteboard.
               The punch-in crop is required to contain this box, which is the
               only thing stopping a zoom from cropping the board writing off.
  speaker_box  where the motion is — the punch-in centres here when it can.

Both are proposals. Look at calibration.png, correct the numbers if they are
wrong, and save. A profile is per camera setup, not per lecture: record from the
same position and you calibrate once.

    lf_calibrate.py SOURCE [--name room] [--write] [--samples 24]
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np

from lf_common import (
    PROFILES_DIR, die, hhmmss, log, require_ffmpeg, slugify, write_json,
)
from lf_probe import probe

GRID_W, GRID_H = 320, 180


def sample_frames(src: Path, duration: float, n: int) -> np.ndarray:
    """n RGB frames spread across the recording, as (n, GRID_H, GRID_W, 3)."""
    # Skip the first and last 5%: intros and packing-up are not representative.
    times = np.linspace(duration * 0.05, duration * 0.95, n)
    frames = []
    for t in times:
        proc = subprocess.run(
            [require_ffmpeg(), "-v", "error", "-nostdin", "-ss", f"{t:.3f}", "-i", str(src),
             "-frames:v", "1", "-vf", f"scale={GRID_W}:{GRID_H}", "-pix_fmt", "rgb24",
             "-f", "rawvideo", "-"],
            capture_output=True)
        buf = proc.stdout
        if len(buf) == GRID_W * GRID_H * 3:
            frames.append(np.frombuffer(buf, dtype=np.uint8).reshape(GRID_H, GRID_W, 3))
    if len(frames) < 3:
        die("could not sample enough frames — is the source readable?")
    return np.stack(frames).astype(np.float32)


def bbox_of(mask: np.ndarray, *, lo_pct: float = 2.0, hi_pct: float = 98.0):
    """Bounding box of a mask, trimmed at percentiles so a few stray pixels
    cannot stretch it across the whole frame."""
    ys, xs = np.nonzero(mask)
    if xs.size < 20:
        return None
    x0, x1 = np.percentile(xs, [lo_pct, hi_pct])
    y0, y1 = np.percentile(ys, [lo_pct, hi_pct])
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    return (float(x0 / GRID_W), float(y0 / GRID_H),
            float((x1 - x0) / GRID_W), float((y1 - y0) / GRID_H))


def expand(box, pad: float):
    """Grow a box by `pad` of the frame on every side, clamped to the frame.

    Percentile trimming deliberately under-reads the board so that a few stray
    bright pixels cannot stretch the box. Under-reading the board is the
    dangerous direction — the punch-in would then crop real board edges off — so
    the proposal is grown back before anyone relies on it."""
    if not box:
        return None
    x, y, w, h = box
    x0, y0 = max(0.0, x - pad), max(0.0, y - pad)
    x1, y1 = min(1.0, x + w + pad), min(1.0, y + h + pad)
    return (x0, y0, x1 - x0, y1 - y0)


def luma(frames: np.ndarray) -> np.ndarray:
    return frames @ np.array([0.299, 0.587, 0.114], dtype=np.float32)


def coverage_bbox(mask: np.ndarray, coverage: float = 0.15):
    """Box from row and column coverage rather than from pixel percentiles.

    Percentile trimming measures the bulk of the mask, which under-reads a board
    whose edges are thin or partly occluded. Asking instead "which columns are
    board in at least `coverage` of their height" finds the real edges, and a
    handful of stray pixels cannot move them."""
    if not mask.any():
        return None
    cols = np.nonzero(mask.mean(axis=0) > coverage)[0]
    rows = np.nonzero(mask.mean(axis=1) > coverage)[0]
    if cols.size < 2 or rows.size < 2:
        return None
    x0, x1 = int(cols.min()), int(cols.max())
    y0, y1 = int(rows.min()), int(rows.max())
    return (x0 / GRID_W, y0 / GRID_H, (x1 - x0) / GRID_W, (y1 - y0) / GRID_H)


def propose(frames: np.ndarray, board_pad: float = 0.03
            ) -> tuple[tuple | None, tuple | None]:
    """frames is (n, H, W, 3).

    A board is what is *lit and still*. Stillness is what separates it from the
    speaker, who occludes a different part of it in every frame and so reads as
    motion wherever he has been.

    "Lit" means bright **or** strongly coloured. A plain whiteboard is bright; a
    smartboard running dark-blue with yellow ink is not, and a brightness-only
    test reads it as part of the dark room and cuts the box off partway down the
    board. Chroma catches the coloured case.
    """
    lum = luma(frames)
    chroma = frames.max(axis=3) - frames.min(axis=3)

    brightness = lum.mean(axis=0)
    colourfulness = chroma.mean(axis=0)
    motion = lum.std(axis=0)

    lit = (brightness >= np.percentile(brightness, 72)) | (colourfulness >= 22)
    still = motion <= np.percentile(motion, 60)
    board = expand(coverage_bbox(lit & still), board_pad)

    speaker = bbox_of(motion >= np.percentile(motion, 93), lo_pct=5, hi_pct=95)
    return board, speaker


def draw_preview(src: Path, duration: float, board, speaker, dest: Path,
                 width: int, height: int) -> None:
    boxes = []
    for box, colour in ((board, "0x00ff66"), (speaker, "0xff3366")):
        if not box:
            continue
        x, y, w, h = box
        boxes.append(f"drawbox=x={int(x * width)}:y={int(y * height)}:"
                     f"w={int(w * width)}:h={int(h * height)}:color={colour}:t=6")
    vf = ",".join(boxes) if boxes else "null"
    subprocess.run([require_ffmpeg(), "-v", "error", "-nostdin", "-y",
                    "-ss", f"{duration * 0.5:.3f}", "-i", str(src),
                    "-frames:v", "1", "-vf", vf, str(dest)], check=False)


def main() -> None:
    ap = argparse.ArgumentParser(description="lecture-forge: calibrate a camera setup")
    ap.add_argument("source")
    ap.add_argument("--name", default=None, help="profile name (default: source stem)")
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--punch-zoom", type=float, default=1.10)
    ap.add_argument("--board-pad", type=float, default=0.03,
                    help="safety margin added around the detected board (frame fraction)")
    ap.add_argument("--write", action="store_true", help="save the profile")
    ap.add_argument("--no-board", action="store_true",
                    help="this setup has no board; punch-in may crop freely")
    args = ap.parse_args()

    src = Path(args.source).expanduser().resolve()
    if not src.is_file():
        die(f"not a file: {src}")

    info = probe(src)
    log(f"sampling {args.samples} frames across {hhmmss(info.duration)}")
    frames = sample_frames(src, info.duration, args.samples)
    board, speaker = propose(frames, args.board_pad)
    if args.no_board:
        board = None

    name = slugify(args.name or src.stem)
    preview = (PROFILES_DIR if args.write else Path.cwd()) / f"{name}-calibration.png"
    preview.parent.mkdir(parents=True, exist_ok=True)
    draw_preview(src, info.duration, board, speaker, preview, info.width, info.height)

    fmt = lambda b: [round(v, 4) for v in b] if b else None
    profile = {
        "name": name,
        "source_sample": str(src),
        "frame_size": [info.width, info.height],
        "board_box": fmt(board),
        "speaker_box": fmt(speaker),
        "punch_zoom": args.punch_zoom,
    }

    log(f"board_box   {fmt(board)}  (green in the preview)")
    log(f"speaker_box {fmt(speaker)}  (red in the preview)")
    log(f"preview     {preview}")
    if board is None and not args.no_board:
        log("no board detected — punch-in will be unconstrained. Pass --no-board to "
            "confirm that is right, or set board_box by hand.")

    if args.write:
        path = PROFILES_DIR / f"{name}.json"
        write_json(path, profile)
        log(f"wrote {path} — check the preview and correct the boxes if they are off")
    else:
        log("dry run: pass --write to save this profile")
    print(json.dumps(profile, indent=2))


if __name__ == "__main__":
    main()
