#!/usr/bin/env python3
"""Stage 3 helper — transcript windows in, validated clips.json out.

Two modes:

  lf_curate.py WORKDIR --dump            write windows/win-NN.md for the curator
  lf_curate.py WORKDIR --collect         merge windows/win-NN.json into clips.json

The judgement in between belongs to the lecture-curator agent. This script only
prepares its input and polices its output: an LLM returns timecodes that are
close but rarely exact, so every proposed boundary is snapped onto a real word
boundary, clamped inside the recording, and rejected if it survives none of that.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lf_common import Settings, die, hhmmss, log, read_json, write_json

WINDOW_SECONDS = 600.0     # ~10 minutes of transcript per curator agent
WINDOW_OVERLAP = 60.0      # so an idea spanning a boundary is seen whole
SNAP_TO_WORD = 2.5         # a proposed boundary may move this far to reach a word
MIN_CLIP = 40.0
MAX_CLIP = 1200.0
OVERLAP_MERGE = 0.6        # two proposals overlapping this much are the same clip


# --------------------------------------------------------------------------

def dump_windows(wd: Path, transcript: dict, duration: float) -> list[Path]:
    out_dir = wd / "windows"
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("win-*.md"):
        stale.unlink()

    segments = transcript["segments"]
    written: list[Path] = []
    start = 0.0
    n = 0
    while start < duration:
        end = min(start + WINDOW_SECONDS, duration)
        rows = [s for s in segments if s["end"] > start and s["start"] < end]
        n += 1
        path = out_dir / f"win-{n:02d}.md"
        body = [
            f"# Transcript window {n}",
            f"Covers {hhmmss(start, ms=True)} to {hhmmss(end, ms=True)} "
            f"of a {hhmmss(duration)} lecture.",
            "",
            "Timecodes are absolute, in the source recording. Use them verbatim.",
            "",
        ]
        body += [f"[{hhmmss(s['start'], ms=True)}] {s['text']}" for s in rows]
        path.write_text("\n".join(body) + "\n")
        written.append(path)
        if end >= duration:
            break
        start = end - WINDOW_OVERLAP
    return written


# --------------------------------------------------------------------------

def word_boundaries(transcript: dict) -> tuple[list[float], list[float]]:
    starts, ends = [], []
    for seg in transcript["segments"]:
        for w in seg["words"]:
            if w["end"] > w["start"]:
                starts.append(float(w["start"]))
                ends.append(float(w["end"]))
    return sorted(starts), sorted(ends)


def nearest(values: list[float], t: float, window: float) -> float | None:
    if not values:
        return None
    best = min(values, key=lambda v: abs(v - t))
    return best if abs(best - t) <= window else None


def validate_clip(clip: dict, starts: list[float], ends: list[float], duration: float,
                  problems: list[str], *, min_clip: float = MIN_CLIP,
                  max_clip: float = MAX_CLIP) -> dict | None:
    try:
        lo, hi = float(clip["start"]), float(clip["end"])
    except (KeyError, TypeError, ValueError):
        problems.append(f"clip {clip.get('id', '?')}: start/end missing or unreadable")
        return None
    if not clip.get("title"):
        problems.append(f"clip at {hhmmss(lo)}: no title")
        return None

    snapped_lo = nearest(starts, lo, SNAP_TO_WORD)
    snapped_hi = nearest(ends, hi, SNAP_TO_WORD)
    if snapped_lo is None or snapped_hi is None:
        problems.append(f"'{clip['title']}': {hhmmss(lo)}–{hhmmss(hi)} lands nowhere "
                        "near a spoken word — dropped")
        return None

    lo = max(0.0, min(snapped_lo, duration))
    hi = max(0.0, min(snapped_hi, duration))
    if hi - lo < min_clip:
        problems.append(f"'{clip['title']}': only {hi - lo:.0f}s long — dropped")
        return None
    if hi - lo > max_clip:
        problems.append(f"'{clip['title']}': {hhmmss(hi - lo)} is too long to be one clip "
                        "— dropped, split it by hand if it matters")
        return None

    out = dict(clip)
    out["start"], out["end"] = round(lo, 3), round(hi, 3)
    out["score"] = float(clip.get("score", 5))
    return out


def dedupe(clips: list[dict]) -> list[dict]:
    """Window overlap means the same idea can be proposed twice. Keep the
    higher-scoring proposal of any heavily overlapping pair."""
    kept: list[dict] = []
    for clip in sorted(clips, key=lambda c: (-c["score"], c["start"])):
        span = clip["end"] - clip["start"]
        clash = False
        for other in kept:
            lo = max(clip["start"], other["start"])
            hi = min(clip["end"], other["end"])
            overlap = max(0.0, hi - lo)
            if overlap / min(span, other["end"] - other["start"]) >= OVERLAP_MERGE:
                clash = True
                break
        if not clash:
            kept.append(clip)
    kept.sort(key=lambda c: c["start"])
    for i, clip in enumerate(kept, start=1):
        clip["id"] = i
    return kept


def collect(wd: Path, transcript: dict, duration: float, *,
            min_clip: float = MIN_CLIP, max_clip: float = MAX_CLIP) -> dict:
    files = sorted((wd / "windows").glob("win-*.json"))
    if not files:
        die(f"no curator output found in {wd / 'windows'} (expected win-NN.json)")

    raw_clips: list[dict] = []
    mistakes: list[dict] = []
    for path in files:
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            die(f"{path.name} is not valid JSON: {exc}")
        raw_clips += data.get("clips", [])
        mistakes += data.get("mistake_cuts", [])

    starts, ends = word_boundaries(transcript)
    problems: list[str] = []
    valid = [c for c in (validate_clip(c, starts, ends, duration, problems,
                                       min_clip=min_clip, max_clip=max_clip)
                         for c in raw_clips) if c]
    clips = dedupe(valid)

    clean_mistakes = []
    seen: set[tuple[float, float]] = set()
    for m in mistakes:
        try:
            lo, hi = float(m["start"]), float(m["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (0 <= lo < hi <= duration) or (hi - lo) > 120:
            continue
        key = (round(lo, 1), round(hi, 1))
        if key in seen:          # windows overlap, so the same cut arrives twice
            continue
        seen.add(key)
        clean_mistakes.append({"start": round(lo, 3), "end": round(hi, 3),
                               "reason": m.get("reason", "mistake")})
    clean_mistakes.sort(key=lambda m: m["start"])
    for i, m in enumerate(clean_mistakes, start=1):
        m["id"] = f"M{i}"

    for p in problems:
        log(f"dropped: {p}")
    log(f"{len(raw_clips)} proposed -> {len(clips)} clips after validation and dedupe")
    log(f"{len(clean_mistakes)} mistake cuts proposed "
        "(each is snapped to silence at render time, or refused)")

    return {"clips": clips, "mistake_cuts": clean_mistakes,
            "dropped": problems, "windows": [p.name for p in files]}


# --------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="lecture-forge stage 3 helper")
    ap.add_argument("workdir")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dump", action="store_true", help="write transcript windows")
    mode.add_argument("--collect", action="store_true", help="merge curator output")
    ap.add_argument("--min-clip", type=float, default=MIN_CLIP,
                    help=f"shortest clip worth keeping, seconds (default {MIN_CLIP:.0f})")
    ap.add_argument("--max-clip", type=float, default=MAX_CLIP,
                    help=f"longest single clip, seconds (default {MAX_CLIP:.0f})")
    args = ap.parse_args()

    wd = Path(args.workdir).expanduser().resolve()
    media = read_json(wd / "media.json")
    transcript = read_json(wd / "transcript.json")
    duration = float(media["duration"])

    if args.dump:
        paths = dump_windows(wd, transcript, duration)
        log(f"wrote {len(paths)} transcript window(s) to {wd / 'windows'}")
        print(json.dumps([str(p) for p in paths], indent=2))
    else:
        st = Settings()
        payload = collect(
            wd, transcript, duration,
            min_clip=st.get("clip.min_seconds", MIN_CLIP,
                            args.min_clip if args.min_clip != MIN_CLIP else None),
            max_clip=st.get("clip.max_seconds", MAX_CLIP,
                            args.max_clip if args.max_clip != MAX_CLIP else None))
        write_json(wd / "clips.json", payload)
        log(f"wrote {wd / 'clips.json'}")
        print(json.dumps({"clips": len(payload["clips"]),
                          "mistake_cuts": len(payload["mistake_cuts"]),
                          "dropped": len(payload["dropped"])}, indent=2))


if __name__ == "__main__":
    main()
