#!/usr/bin/env python3
"""Stage 3 output — the review sheet you approve before anything renders.

Writes review.md: one row per proposed clip. Delete the rows you do not want,
edit a title or a timecode in place, then run the render command. The rows that
survive are exactly what gets rendered.

    lf_reviewsheet.py WORKDIR [--previews]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from lf_common import (
    hhmmss, intersect_intervals, log, read_json, require_ffmpeg, run, slugify,
    total_duration,
)

PREVIEW_SECONDS = 15.0


def opening_line(transcript: dict, clip: dict, limit: int = 90) -> str:
    lo, hi = float(clip["start"]), float(clip["end"])
    words: list[str] = []
    for seg in transcript["segments"]:
        if seg["end"] < lo or seg["start"] > hi:
            continue
        for w in seg["words"]:
            if w["start"] >= lo:
                words.append(w["word"].strip())
            if len(" ".join(words)) > limit:
                break
        if len(" ".join(words)) > limit:
            break
    text = " ".join(words).strip()
    return (text[:limit].rsplit(" ", 1)[0] + "…") if len(text) > limit else text


def tightened_length(clip: dict, cuts: list[dict]) -> float:
    span = [(float(clip["start"]), float(clip["end"]))]
    inside = intersect_intervals([(c["start"], c["end"]) for c in cuts], span)
    return (span[0][1] - span[0][0]) - total_duration(inside)


def make_preview(src: Path, clip: dict, dest: Path) -> None:
    start = float(clip.get("hook_start", clip["start"]))
    dur = min(PREVIEW_SECONDS, float(clip["end"]) - start)
    run([require_ffmpeg(), "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
         "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src),
         "-vf", "scale=640:-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
         "-c:a", "aac", "-b:a", "96k", str(dest)])


def main() -> None:
    ap = argparse.ArgumentParser(description="lecture-forge: build the review sheet")
    ap.add_argument("workdir")
    ap.add_argument("--previews", action="store_true",
                    help=f"also render a {PREVIEW_SECONDS:.0f}s hook preview per clip")
    args = ap.parse_args()

    wd = Path(args.workdir).expanduser().resolve()
    media = read_json(wd / "media.json")
    edits = read_json(wd / "edits.json")
    transcript = read_json(wd / "transcript.json")
    doc = read_json(wd / "clips.json")
    clips = doc.get("clips", [])

    previews_dir = wd / "previews"
    if args.previews and clips:
        previews_dir.mkdir(exist_ok=True)
        for c in clips:
            make_preview(Path(media["path"]), c,
                         previews_dir / f"{c['id']:02d}-{slugify(c['title'])}.mp4")
        log(f"wrote {len(clips)} previews to {previews_dir}")

    rows = []
    for c in clips:
        tight = tightened_length(c, edits["cuts"])
        preview = ""
        if args.previews:
            preview = f" [preview](previews/{c['id']:02d}-{slugify(c['title'])}.mp4)"
        rows.append(
            f"| {c['id']} | {c['title']} | {hhmmss(tight, ms=True)} | {c.get('score', '')} | "
            f"{hhmmss(float(c['start']), ms=True)}–{hhmmss(float(c['end']), ms=True)} | "
            f"{c.get('why_valuable', '').strip()} | {opening_line(transcript, c)}{preview} |"
        )

    dropped = doc.get("dropped", [])
    dropped_block = ""
    if dropped:
        dropped_block = ("\n## Proposals that did not survive validation\n\n"
                         + "\n".join(f"- {d}" for d in dropped) + "\n")

    total_tight = sum(tightened_length(c, edits["cuts"]) for c in clips)
    (wd / "review.md").write_text(f"""# Review — {Path(media['path']).name}

Source {hhmmss(float(media['duration']))} · {len(clips)} clips proposed ·
{hhmmss(total_tight)} of finished video.

**How to use this sheet.** Delete the row of any clip you do not want. Edit a
title or a timecode in place if you want it different — what is in the table
wins. Then run `/lecture-forge-render`. Only the rows still here get rendered.

Lengths shown are the finished length after pauses, fillers and mistakes come
out, not the raw span.

| # | Title | Length | Score | Source timecode | Why it stands alone | Opens with |
|---|---|---|---|---|---|---|
{chr(10).join(rows)}
{dropped_block}
## Already decided, applied to every clip

- Pauses over {edits['max_gap']}s shortened to {edits['max_gap']}s — {edits['stats']['seconds_by_kind'].get('silence', 0)}s across the lecture
- {edits['stats']['filler_words_removed']} fillers and {edits['stats']['stutters_removed']} stutters removed
- {edits['stats']['refused']} cuts refused because there was no silence to cut in — those words stay
""")
    log(f"wrote {wd / 'review.md'} — {len(clips)} clips")
    print(str(wd / "review.md"))


if __name__ == "__main__":
    main()
