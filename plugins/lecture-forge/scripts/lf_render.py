#!/usr/bin/env python3
"""Stage 4 — render the approved clips.

For each clip: subtract every cut from the clip span, render the surviving
ranges as one continuous video, hide the resulting jump cuts with an alternating
punch-in, clean and normalize the audio, and write the MP4 plus a re-timed SRT
and a title/description sidecar.

    lf_render.py WORKDIR [--clips 1,3,5] [--profile NAME] [--fast] [--dry-run]

Notes on the two things that most often go wrong:

  * A/V sync. Every range boundary is snapped to the video frame grid, video is
    cut with `select`, and audio is cut separately at exact sample offsets and
    fed back in as a second input. Cutting audio inside the graph is what makes
    clips drift: `aselect` works in ~21 ms audio frames against `select`'s
    41.7 ms video frames, and the rounding error accumulates one way across
    every join.
  * Loudness. loudnorm is measured on the CUT audio, not the source. Removing
    dead air raises integrated loudness, so measurements taken before the cut
    normalize to the wrong target.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from lf_analyze import Snapper
from lf_common import (
    Interval, Settings, die, hhmmss, intersect_intervals, load_profile, log, merge_intervals,
    read_json, require_ffmpeg, run, slugify, subtract_intervals, total_duration,
    write_json,
)

# ---- punch-in ------------------------------------------------------------
PUNCH_TARGET = 1.10       # preferred zoom factor
PUNCH_MIN = 1.06          # below this the zoom is not worth the crop risk
PUNCH_MIN_CUT = 0.35      # only a cut that removed this much triggers a switch
PUNCH_MIN_DWELL = 4.0     # seconds a state must hold before switching again
BOARD_MARGIN = 0.01       # keep this much frame around the board, never flush to the edge

MIN_CUT = 0.05            # cuts shorter than this are not worth making
LOUDNESS_I = -16.0
LOUDNESS_TP = -1.5
LOUDNESS_LRA = 11.0
LIMITER_CEILING = 0.7943  # -2.0 dBFS, leaving room for codec true-peak overshoot


# --------------------------------------------------------------------------
# Keep-range maths
# --------------------------------------------------------------------------

def quantize_to_frames(keeps: list[Interval], fps: float) -> list[Interval]:
    """Move every range boundary onto an exact frame boundary.

    `select` keeps whole frames while `aselect` cuts audio at the sample, so a
    range whose bounds fall mid-frame keeps slightly different amounts of video
    and audio. One cut is imperceptible; the error is one-signed and cumulative,
    so sixty-nine of them put the streams 160 ms apart by the end of a clip.
    Snapping the bounds to the frame grid first makes both streams keep the same
    span at every join, and the drift stops accumulating."""
    if not fps or fps <= 0:
        return keeps
    out: list[Interval] = []
    for a, b in keeps:
        qa = round(a * fps) / fps
        qb = round(b * fps) / fps
        if qb - qa > 0.5 / fps:
            out.append((qa, qb))
    return out


def clip_keep_ranges(clip: dict, removals: list[Interval], min_cut: float,
                     fps: float = 0.0) -> list[Interval]:
    span = [(float(clip["start"]), float(clip["end"]))]
    inside = intersect_intervals(removals, span)
    inside = [(a, b) for a, b in inside if (b - a) >= min_cut]
    keeps = subtract_intervals(span, inside)
    keeps = [(a, b) for a, b in keeps if (b - a) > 0.02]
    return quantize_to_frames(keeps, fps)


class TimeMap:
    """Source time -> output time, across the retained ranges."""

    def __init__(self, keeps: list[Interval]):
        self.keeps = keeps
        self.offsets: list[float] = []
        acc = 0.0
        for a, b in keeps:
            self.offsets.append(acc)
            acc += (b - a)
        self.duration = acc

    def to_output(self, t: float) -> float | None:
        for (a, b), off in zip(self.keeps, self.offsets):
            if a <= t <= b:
                return off + (t - a)
            if t < a:
                return off  # inside a removed stretch: collapse to the join
        return self.duration

    def cut_points(self) -> list[tuple[float, float]]:
        """(output_time, seconds_removed) for each join."""
        out = []
        for i in range(len(self.keeps) - 1):
            removed = self.keeps[i + 1][0] - self.keeps[i][1]
            out.append((self.offsets[i + 1], removed))
        return out


def punch_schedule(tmap: TimeMap) -> list[Interval]:
    """Alternate between flat and punched-in on each real cut. Returns the
    output-time ranges that should be punched."""
    ranges: list[Interval] = []
    punched = False
    span_start = 0.0
    last_switch = 0.0
    for out_t, removed in tmap.cut_points():
        if removed < PUNCH_MIN_CUT or (out_t - last_switch) < PUNCH_MIN_DWELL:
            continue
        if punched:
            ranges.append((span_start, out_t))
        else:
            span_start = out_t
        punched = not punched
        last_switch = out_t
    if punched:
        ranges.append((span_start, tmap.duration))
    return ranges


# --------------------------------------------------------------------------
# Punch-in geometry — the smartboard must never be cropped off
# --------------------------------------------------------------------------

def punch_crop(width: int, height: int, profile: dict) -> tuple[int, int, int, int, float] | None:
    """Return (crop_w, crop_h, x, y, zoom) or None when a safe zoom is impossible.

    board_box and speaker_box are normalized [x, y, w, h] in the profile."""
    board = profile.get("board_box")
    speaker = profile.get("speaker_box")
    target = float(profile.get("punch_zoom", PUNCH_TARGET))

    zoom = target
    if board:
        margin_x, margin_y = BOARD_MARGIN * width, BOARD_MARGIN * height
        bx = board[0] * width - margin_x
        by = board[1] * height - margin_y
        bw = board[2] * width + 2 * margin_x
        bh = board[3] * height + 2 * margin_y
        if bw <= 0 or bh <= 0:
            die("profile board_box has zero width or height")
        # The crop must be at least as large as the board plus its margin.
        zoom = min(target, width / bw, height / bh)
        if zoom < PUNCH_MIN:
            return None

    crop_w = int((width / zoom) // 2 * 2)
    crop_h = int((height / zoom) // 2 * 2)
    if crop_w >= width and crop_h >= height:
        return None

    # Preferred centre: the speaker if the profile names one, else frame centre.
    if speaker:
        cx = (speaker[0] + speaker[2] / 2) * width
        cy = (speaker[1] + speaker[3] / 2) * height
    else:
        cx, cy = width / 2, height / 2
    x = cx - crop_w / 2
    y = cy - crop_h / 2

    if board:
        # Keep the whole board inside the crop.
        x = min(max(x, (bx + bw) - crop_w), bx)
        y = min(max(y, (by + bh) - crop_h), by)
    x = int(min(max(x, 0), width - crop_w) // 2 * 2)
    y = int(min(max(y, 0), height - crop_h) // 2 * 2)
    return crop_w, crop_h, x, y, zoom


# --------------------------------------------------------------------------
# Filter graph construction
# --------------------------------------------------------------------------

def between_expr(ranges: list[Interval], offset: float, fps: float = 0.0) -> str:
    """select expression over the source ranges, rebased to the clip start.

    Both bounds are shifted back half a frame so the comparison happens at frame
    centres. `between` is inclusive at both ends, so a range whose end lands
    exactly on a frame — which is now always, since the ranges are snapped to
    the frame grid — would keep that frame as well as the next range's first
    frame. One extra frame per cut: thirteen cuts made a clip five frames longer
    than its own timeline, and the video ran 200 ms past the audio.

    With the half-frame shift a range from frame p to frame q keeps exactly
    q - p frames, which is what its duration says it should.
    """
    half = 0.5 / fps if fps and fps > 0 else 0.0
    parts = [f"between(t,{max(0.0, a - offset - half):.5f},"
             f"{max(0.0, b - offset - half):.5f})"
             for a, b in ranges]
    return "+".join(parts) if parts else "1"


def audio_chain(profile: dict, denoise: str, measured: dict | None) -> str:
    stages = ["highpass=f=70"]
    if denoise == "afftdn":
        stages.append("afftdn=nr=12:nf=-28:tn=1")
    elif denoise == "rnn":
        model = profile.get("rnnoise_model")
        if not model or not Path(model).exists():
            die("--denoise rnn needs profile key 'rnnoise_model' pointing at a .rnnn file")
        stages.append(f"arnndn=m={model}")
    if measured:
        stages.append(
            f"loudnorm=I={LOUDNESS_I}:TP={LOUDNESS_TP}:LRA={LOUDNESS_LRA}"
            f":measured_I={measured['input_i']}:measured_TP={measured['input_tp']}"
            f":measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}"
            f":offset={measured['target_offset']}:linear=true:print_format=summary"
        )
    else:
        stages.append(f"loudnorm=I={LOUDNESS_I}:TP={LOUDNESS_TP}:LRA={LOUDNESS_LRA}"
                      f":print_format=json")
    # Hard ceiling after loudnorm. loudnorm aims for a true-peak target but
    # cannot guarantee it in linear mode, and lossy encoding then overshoots by
    # a couple of tenths more: a clip measured -0.86 dBTP against a -1.5 target.
    # `level=false` matters — the limiter's auto-level is on by default and
    # would gain the signal back up, undoing the normalization it follows.
    stages.append(f"alimiter=limit={LIMITER_CEILING:.4f}:level=false:attack=5:release=50")
    stages.append("aresample=async=1")
    return ",".join(stages)


AUDIO_RATE = 48000
AUDIO_CHANNELS = 2


def cut_audio_to_wav(src: Path, clip_start: float, span: float,
                     keeps: list[Interval], dest: Path) -> float:
    """Cut the clip's audio at exact sample offsets and write it to a WAV.

    The audio is not cut in the filter graph, for two reasons.

    `aselect` — the obvious counterpart to `select` — keeps or drops whole audio
    frames, about 21 ms at 48 kHz, while `select` works in video frames of
    41.7 ms. The two granularities round independently at every join and the
    error accumulates in one direction: across sixty-nine cuts the streams
    finished more than a second apart.

    `atrim` is sample-accurate and fixes that, but needs one branch per range
    behind an `asplit`, and `concat` consumes those branches in order, so every
    later branch buffers the whole stream while the first one drains. Sixty-nine
    branches of a seven-minute clip is gigabytes on a machine that has none.

    Slicing a numpy array is exact, needs one decode, and holds one copy of the
    audio. With the ranges already snapped to the video frame grid, each kept
    span is a whole number of frames, so audio and video stay locked.
    """
    import numpy as np

    import subprocess
    proc = subprocess.run(
        [require_ffmpeg(), "-hide_banner", "-nostdin", "-loglevel", "error",
         "-ss", f"{clip_start:.6f}", "-t", f"{span:.6f}", "-i", str(src),
         "-vn", "-ac", str(AUDIO_CHANNELS), "-ar", str(AUDIO_RATE),
         "-f", "s16le", "-"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)   # binary: no text mode
    if proc.returncode != 0:
        die("audio decode failed:\n" + proc.stderr.decode("utf-8", "replace")[-800:])
    audio = np.frombuffer(proc.stdout, dtype=np.int16).reshape(-1, AUDIO_CHANNELS)

    pieces = []
    for a, b in keeps:
        i0 = max(0, int(round((a - clip_start) * AUDIO_RATE)))
        i1 = min(len(audio), int(round((b - clip_start) * AUDIO_RATE)))
        if i1 > i0:
            pieces.append(audio[i0:i1])
    if not pieces:
        die("no audio survived the cut")
    cut = np.concatenate(pieces)

    import wave as wavemod
    with wavemod.open(str(dest), "wb") as wf:
        wf.setnchannels(AUDIO_CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(AUDIO_RATE)
        wf.writeframes(cut.tobytes())
    return len(cut) / float(AUDIO_RATE)


def build_graph(keeps: list[Interval], clip_start: float, *, fps: float,
                crop: tuple[int, int, int, int, float] | None,
                punches: list[Interval], audio: str, width: int, height: int) -> str:
    sel = between_expr(keeps, clip_start, fps)
    lines = [f"[0:v]select='{sel}',setpts=N/FRAME_RATE/TB[vcut];"]
    if crop and punches:
        cw, ch, cx, cy, _ = crop
        enable = "+".join(f"between(t,{a:.4f},{b:.4f})" for a, b in punches)
        lines += [
            "[vcut]split=2[base][zsrc];",
            f"[zsrc]crop={cw}:{ch}:{cx}:{cy},scale={width}:{height}:flags=lanczos,"
            "setsar=1[zoom];",
            f"[base][zoom]overlay=0:0:enable='{enable}'[vout];",
        ]
    else:
        lines.append("[vcut]null[vout];")
    lines.append(f"[1:a]{audio}[aout]")   # input 1 is the already-cut wav
    return "".join(lines)


# --------------------------------------------------------------------------
# loudnorm measurement pass
# --------------------------------------------------------------------------

_JSON_BLOCK = re.compile(r"\{[^{}]*\"input_i\"[^{}]*\}", re.S)


def measure_loudness(cut_wav: Path, profile: dict, denoise: str) -> dict | None:
    """Measured on the already-cut audio: removing dead air changes integrated
    loudness, so the source measurement would normalize to the wrong target."""
    graph = f"[0:a]{audio_chain(profile, denoise, None)}[aout]"
    proc = run([require_ffmpeg(), "-hide_banner", "-nostdin", "-loglevel", "info",
                "-i", str(cut_wav),
                "-filter_complex", graph, "-map", "[aout]", "-f", "null", "-"],
               check=False)
    match = None
    for match in _JSON_BLOCK.finditer(proc.stderr or ""):
        pass  # the last block is the summary we want
    if not match:
        log("  loudness measurement failed; falling back to single-pass loudnorm")
        return None
    data = json.loads(match.group(0))
    return {k: data[k] for k in
            ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")}


# --------------------------------------------------------------------------
# Subtitles + sidecar
# --------------------------------------------------------------------------

def clip_words(transcript: dict, clip: dict) -> list[dict]:
    lo, hi = float(clip["start"]), float(clip["end"])
    out = []
    for seg in transcript["segments"]:
        for w in seg["words"]:
            if w["start"] >= lo and w["end"] <= hi and w["end"] > w["start"]:
                out.append(w)
    return out


def write_srt(path: Path, words: list[dict], tmap: TimeMap, removals: list[Interval],
              *, max_words: int = 9, max_secs: float = 4.0) -> int:
    kept = [w for w in words
            if not any(a <= w["start"] < b for a, b in removals)]
    lines: list[list[dict]] = []
    for w in kept:
        if (lines and len(lines[-1]) < max_words
                and (w["end"] - lines[-1][0]["start"]) <= max_secs):
            lines[-1].append(w)
        else:
            lines.append([w])

    with path.open("w") as fh:
        n = 0
        for group in lines:
            start = tmap.to_output(group[0]["start"])
            end = tmap.to_output(group[-1]["end"])
            if start is None or end is None or end <= start:
                continue
            n += 1
            text = "".join(w["word"] for w in group).strip()
            fh.write(f"{n}\n{hhmmss(start, srt=True)} --> {hhmmss(end, srt=True)}\n{text}\n\n")
    return n


def write_sidecar(path: Path, clip: dict, tmap: TimeMap, source: str,
                  words: list[dict]) -> None:
    text = " ".join(w["word"].strip() for w in words)
    body = [
        f"# {clip['title']}",
        "",
        f"**Duration:** {hhmmss(tmap.duration, ms=True)}  ",
        f"**Source:** `{source}` {hhmmss(float(clip['start']))}–{hhmmss(float(clip['end']))}  ",
        f"**Tightened from:** {hhmmss(float(clip['end']) - float(clip['start']), ms=True)}",
        "",
        "## Description",
        "",
        clip.get("description", "").strip() or "_(none)_",
        "",
    ]
    if clip.get("why_valuable"):
        body += ["## Why this stands alone", "", clip["why_valuable"].strip(), ""]
    if clip.get("key_points"):
        body += ["## Key points", ""] + [f"- {p}" for p in clip["key_points"]] + [""]
    body += ["## Transcript", "", text, ""]
    path.write_text("\n".join(body))


# --------------------------------------------------------------------------
# Review sheet parsing
# --------------------------------------------------------------------------

_ROW = re.compile(r"^\|\s*(\d+)\s*\|")
_MROW = re.compile(r"^\|\s*(M\d+)\s*\|")


def approved_mistake_ids(review: Path) -> set[str] | None:
    """Which content cuts survived the review sheet.

    None means the sheet has no content-cut section at all (an older sheet), in
    which case every proposed cut applies as before. An empty set means the
    section was there and every row was deleted — the reviewer rejected them
    all, which must be honoured rather than read as "no opinion".
    """
    text = review.read_text()
    if "Content cuts proposed" not in text:
        return None
    return {m.group(1) for line in text.splitlines()
            for m in [_MROW.match(line.strip())] if m}


def clips_from_review(review: Path, clips: list[dict]) -> list[dict]:
    """Rows still present in review.md are the approved clips. Titles and
    timecodes edited in the sheet win over clips.json."""
    from lf_common import parse_timecode

    by_id = {int(c["id"]): c for c in clips}
    approved: list[dict] = []
    for line in review.read_text().splitlines():
        m = _ROW.match(line.strip())
        if not m:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        cid = int(cells[0])
        if cid not in by_id:
            log(f"review.md row {cid} has no matching clip — skipped")
            continue
        clip = dict(by_id[cid])
        if len(cells) > 1 and cells[1]:
            clip["title"] = cells[1]
        if len(cells) > 4 and cells[4]:
            try:
                lo, hi = cells[4].split("–") if "–" in cells[4] else cells[4].split("-")
                clip["start"] = parse_timecode(lo)
                clip["end"] = parse_timecode(hi)
            except ValueError:
                log(f"row {cid}: could not read timecode '{cells[4]}', using clips.json")
        approved.append(clip)
    return approved


# --------------------------------------------------------------------------

def render_clip(idx: int, clip: dict, *, src: Path, wd: Path, media: dict,
                removals: list[Interval], transcript: dict, profile: dict,
                args) -> dict:
    fps = float(media.get("fps") or 0.0)
    keeps = clip_keep_ranges(clip, removals, args.min_cut, fps)
    if not keeps:
        die(f"clip {clip['id']} has nothing left after cutting — check its timecodes")
    tmap = TimeMap(keeps)
    span = float(clip["end"]) - float(clip["start"])

    crop = None if args.no_punch else punch_crop(media["width"], media["height"], profile)
    punches = punch_schedule(tmap) if crop else []
    if not args.no_punch and crop is None:
        log("  punch-in disabled: no zoom keeps the whole board in frame — hard cuts instead")

    slug = f"{idx:02d}-{slugify(clip['title'])}"
    out_mp4 = wd / "clips" / f"{slug}.mp4"
    out_mp4.parent.mkdir(parents=True, exist_ok=True)

    log(f"clip {clip['id']}: {clip['title']}")
    log(f"  {hhmmss(span, ms=True)} source -> {hhmmss(tmap.duration, ms=True)} out, "
        f"{len(keeps) - 1} cuts, {len(punches)} punched spans")

    # (output time of the join, source start, source end) for every applied cut
    applied = [(round(tmap.offsets[i + 1], 3), round(keeps[i][1], 3),
                round(keeps[i + 1][0], 3))
               for i in range(len(keeps) - 1)]

    if args.dry_run:
        return {"id": clip["id"], "title": clip["title"], "file": str(out_mp4),
                "source_seconds": round(span, 2), "output_seconds": round(tmap.duration, 2),
                "cuts": len(keeps) - 1, "punched_spans": len(punches),
                "removals": applied, "rendered": False}

    if fps > 0:
        clip = dict(clip, start=round(float(clip["start"]) * fps) / fps)
    clip_start = float(clip["start"])

    # Audio is cut first, at exact sample offsets, and handed to the render as a
    # second input. See cut_audio_to_wav for why this is not done in the graph.
    cut_wav = wd / "_cutaudio" / f"{slug}.wav"
    cut_wav.parent.mkdir(parents=True, exist_ok=True)
    audio_seconds = cut_audio_to_wav(src, clip_start, span, keeps, cut_wav)
    if abs(audio_seconds - tmap.duration) > 0.05:
        log(f"  warning: cut audio is {audio_seconds:.3f}s but the timeline expects "
            f"{tmap.duration:.3f}s")

    measured = None if args.no_loudnorm else measure_loudness(
        cut_wav, profile, args.denoise)
    graph = build_graph(keeps, clip_start, fps=media["fps"], crop=crop,
                        punches=punches, audio=audio_chain(profile, args.denoise, measured),
                        width=media["width"], height=media["height"])
    graph_file = wd / "filtergraphs" / f"{slug}.txt"
    graph_file.parent.mkdir(parents=True, exist_ok=True)
    graph_file.write_text(graph)

    if args.fast:
        vcodec = ["-c:v", "h264_videotoolbox", "-b:v", "12M"]
    else:
        vcodec = ["-c:v", "libx264", "-preset", args.preset, "-crf", str(args.crf)]

    run([require_ffmpeg(), "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
         "-ss", f"{clip_start:.6f}", "-t", f"{span:.6f}", "-i", str(src),
         "-i", str(cut_wav),
         "-filter_complex_script", str(graph_file),
         "-map", "[vout]", "-map", "[aout]",
         *vcodec, "-pix_fmt", "yuv420p", "-fps_mode", "cfr", "-r", f"{media['fps']:.6f}",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out_mp4)])
    if not args.keep_temp:
        cut_wav.unlink(missing_ok=True)

    words = clip_words(transcript, clip)
    n_subs = write_srt(out_mp4.with_suffix(".srt"), words, tmap, removals)
    write_sidecar(out_mp4.with_suffix(".md"), clip, tmap, Path(media["path"]).name, words)

    return {"id": clip["id"], "title": clip["title"], "file": str(out_mp4),
            "source_seconds": round(span, 2), "output_seconds": round(tmap.duration, 2),
            "cuts": len(keeps) - 1, "punched_spans": len(punches),
            "removals": applied, "subtitles": n_subs,
            "zoom": round(crop[4], 3) if crop else None, "rendered": True}


def write_removed_report(wd: Path, media: dict, transcript: dict, edits: dict,
                         results: list[dict], *, verbose: bool = False) -> int:
    """Every cut that was applied, with the words it took out.

    The dangerous failure mode is invisible: chatter left in gets noticed on the
    first watch, but a punchline cut out leaves nothing behind to notice. This
    turns "it chopped something important" from an unfalsifiable complaint into
    a line someone can point at, and it is what makes reviewing an edit possible
    without watching every clip end to end.

    Pure-silence rows are summarised rather than listed unless --verbose: on a
    52-minute lecture they are most of a thousand rows and they carry no words,
    so listing them buries the ones that removed speech.
    """
    words = [w for s in transcript["segments"] for w in s["words"]
             if w["end"] > w["start"]]

    # Reason lookup: which analysis decision covers this stretch of source.
    sources = [(c["start"], c["end"], c.get("policy", c.get("reason", "cut")),
                c.get("reason", "")) for c in edits.get("cuts", [])]

    lines: list[str] = []
    silent_count = 0
    silent_seconds = 0.0

    for r in results:
        if not r.get("rendered") or not r.get("removals"):
            continue
        lines.append(f"\n### Clip {r['id']} — {r['title']}\n")
        lines.append("| Out at | Source | Length | Why | Words removed |")
        lines.append("|---|---|---|---|---|")
        rows = 0
        for out_t, a, b in r["removals"]:
            taken = [w["word"].strip() for w in words
                     if w["start"] < b and w["end"] > a]
            text = " ".join(taken).strip()
            why = next((p for s0, s1, p, _ in sources if s0 < b and s1 > a), "silence")
            if not text:
                silent_count += 1
                silent_seconds += (b - a)
                if not verbose:
                    continue
                text = "_(silence)_"
            else:
                text = f'"{text}"'
            lines.append(f"| {hhmmss(out_t, ms=True)} | {hhmmss(a, ms=True)} | "
                         f"{b - a:.2f}s | {why} | {text} |")
            rows += 1
        if rows == 0:
            lines.append("| — | — | — | — | _only pauses removed_ |")

    header = f"""# What was removed — {Path(media['path']).name}

Every cut applied to a rendered clip, with the words it took out. Read this
before publishing: a clip that kept something it should not have is obvious on
the first watch, but a clip that lost a punchline looks fine.

Wrong? File it so it changes the tool rather than just this lecture:

    /lecture-forge-feedback <clip> <out-timecode> "what went wrong"

{silent_count} pause-only cuts ({silent_seconds:.0f}s) are not listed
"""
    if verbose:
        header = header.replace(" are not listed", " are listed below")
    (wd / "removed.md").write_text(header + "\n".join(lines) + "\n")
    return silent_count


def write_summary(wd: Path, media: dict, edits: dict, results: list[dict]) -> None:
    src_dur = float(media["duration"])
    out_total = sum(r["output_seconds"] for r in results)
    sel_total = sum(r["source_seconds"] for r in results)
    kinds = edits["stats"]["seconds_by_kind"]

    rows = "\n".join(
        f"| {r['id']} | {r['title']} | {hhmmss(r['output_seconds'], ms=True)} | "
        f"{r['cuts']} | {r['punched_spans']} | `{Path(r['file']).name}` |"
        for r in results
    )
    (wd / "summary.md").write_text(f"""# lecture-forge — {Path(media['path']).name}

| | |
|---|---|
| Source length | {hhmmss(src_dur)} |
| Selected for clips | {hhmmss(sel_total)} |
| Delivered | {hhmmss(out_total)} across {len(results)} clips |
| Left on the floor | {hhmmss(src_dur - sel_total)} not selected |

## Time removed inside the selected spans

| Reason | Seconds |
|---|---|
| Pauses shortened to {edits['max_gap']}s | {kinds.get('silence', 0)} |
| Fillers | {kinds.get('filler', 0)} |
| Stutters | {kinds.get('stutter', 0)} |
| Cuts refused (kept, no safe silence) | {edits['stats']['refused']} |

## Clips

| # | Title | Length | Cuts | Punched spans | File |
|---|---|---|---|---|---|
{rows}
""")


def main() -> None:
    ap = argparse.ArgumentParser(description="lecture-forge stage 4: render")
    ap.add_argument("workdir")
    ap.add_argument("--clips", default=None, help="comma-separated clip ids to render")
    ap.add_argument("--from-review", action="store_true",
                    help="render exactly the rows left in review.md (default when it exists)")
    ap.add_argument("--profile", default=None, help="camera/room profile name")
    ap.add_argument("--min-cut", type=float, default=MIN_CUT)
    ap.add_argument("--denoise", choices=["afftdn", "rnn", "off"], default="afftdn")
    ap.add_argument("--no-loudnorm", action="store_true")
    ap.add_argument("--no-punch", action="store_true")
    ap.add_argument("--fast", action="store_true", help="VideoToolbox encode")
    ap.add_argument("--preset", default="slow")
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--verbose-removed", action="store_true",
                    help="list pause-only cuts in removed.md as well as speech cuts")
    ap.add_argument("--keep-temp", action="store_true",
                    help="keep the intermediate cut-audio WAVs for inspection")
    ap.add_argument("--dry-run", action="store_true", help="report the plan, render nothing")
    args = ap.parse_args()

    wd = Path(args.workdir).expanduser().resolve()
    media = read_json(wd / "media.json")
    edits = read_json(wd / "edits.json")
    transcript = read_json(wd / "transcript.json")
    clips_doc = read_json(wd / "clips.json")
    src = Path(media["path"])
    if not src.exists():
        die(f"source file has moved: {src}")

    profile = load_profile(args.profile)
    settings = Settings(profile)
    args.min_cut = settings.get("render.min_cut", MIN_CUT,
                                args.min_cut if args.min_cut != MIN_CUT else None)
    args.denoise = settings.get("render.denoise", "afftdn",
                                args.denoise if args.denoise != "afftdn" else None)
    args.crf = settings.get("render.crf", 18, args.crf if args.crf != 18 else None)
    args.preset = settings.get("render.preset", "slow",
                               args.preset if args.preset != "slow" else None)
    log(f"settings — {settings.report()}")
    clips = clips_doc.get("clips", [])
    if not clips:
        die("clips.json contains no clips")

    review = wd / "review.md"
    if args.clips:
        wanted = {int(x) for x in args.clips.split(",")}
        clips = [c for c in clips if int(c["id"]) in wanted]
    elif review.exists():
        clips = clips_from_review(review, clips)
        log(f"{len(clips)} clips approved in review.md")
    if not clips:
        die("no clips selected — every row was removed from review.md?")

    # Mechanical cuts, plus the mistake cuts the curator proposed (snapped to
    # silence, refused when no silence is near).
    removals = [(c["start"], c["end"]) for c in edits["cuts"]]
    refused_llm: list[dict] = []
    snapper = Snapper([tuple(x) for x in edits["silence_map"]])

    # Content cuts remove speech, so they only apply if they survived review.
    approved = approved_mistake_ids(review) if review.exists() else None
    proposed = clips_doc.get("mistake_cuts", [])
    if approved is not None:
        rejected = [m for m in proposed if m.get("id") not in approved]
        proposed = [m for m in proposed if m.get("id") in approved]
        if rejected:
            log(f"{len(rejected)} content cuts rejected in review.md — those words stay")
    for mc in proposed:
        snapped = snapper.snap_removal(float(mc["start"]), float(mc["end"]),
                                       mc.get("reason", "mistake"), refused_llm)
        if snapped:
            removals.append((snapped["start"], snapped["end"]))
    if refused_llm:
        log(f"{len(refused_llm)} proposed mistake cuts refused (no silence to cut in)")
    removals = merge_intervals(removals)

    results = [render_clip(i, c, src=src, wd=wd, media=media, removals=removals,
                           transcript=transcript, profile=profile, args=args)
               for i, c in enumerate(clips, start=1)]

    write_json(wd / "render-report.json",
               {"clips": results, "refused_mistake_cuts": refused_llm,
                "removed_total": round(total_duration(removals), 2)})
    if not args.dry_run:
        write_summary(wd, media, edits, results)
        n_silent = write_removed_report(wd, media, transcript, edits, results,
                                        verbose=args.verbose_removed)
        log(f"wrote {len(results)} clips to {wd / 'clips'}")
        log(f"review what was cut: {wd / 'removed.md'} "
            f"({n_silent} pause-only cuts not listed)"
            if not args.verbose_removed else f"review what was cut: {wd / 'removed.md'}")
    print(json.dumps({"clips": len(results),
                      "output_seconds": round(sum(r["output_seconds"] for r in results), 2)},
                     indent=2))


if __name__ == "__main__":
    main()
