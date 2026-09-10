#!/usr/bin/env python3
"""Stage 1 — word-level transcription with faster-whisper.

Writes transcript.json:

    {"model": ..., "language": ..., "duration": ...,
     "segments": [{"id", "start", "end", "text",
                   "words": [{"start","end","word","probability"}]}]}

Every later stage keys off word timings, so word_timestamps is not optional.

**Chunked and resumable.** The audio is split at silences into chunks of about
--chunk-seconds, and each chunk's result is written to chunks/NN.json the moment
it finishes. Re-running skips whatever is already on disk. This matters on a
memory-tight machine: an OS out-of-memory kill then costs one chunk instead of
the whole lecture, and peak memory stays at model + one chunk rather than model
+ a full 52-minute decode.

Splits land in the middle of a detected silence, so no word is ever cut in half
by a chunk boundary.

    lf_transcribe.py WORKDIR [--model medium.en] [--chunk-seconds 300] [--force]
"""

from __future__ import annotations

import argparse
import gc
import time
from pathlib import Path

from lf_analyze import rms_envelope, silence_from_envelope
from lf_common import die, ffmpeg_run, hhmmss, log, read_json, write_json

DEFAULT_MODEL = "medium.en"
DEFAULT_CHUNK = 300.0
BOUNDARY_SEARCH_FRAC = 0.15   # search this fraction of a chunk either side of a split
BOUNDARY_SEARCH_MAX = 45.0


# --------------------------------------------------------------------------

def split_points(wav: Path, duration: float, chunk_seconds: float) -> list[tuple[float, float]]:
    """Chunk spans, each boundary sitting in the middle of a silence."""
    if duration <= chunk_seconds:
        return [(0.0, duration)]
    search = min(BOUNDARY_SEARCH_MAX, chunk_seconds * BOUNDARY_SEARCH_FRAC)
    min_gap = min(30.0, chunk_seconds * 0.25)

    db, _, _ = rms_envelope(wav)
    # A coarse gate is enough here: we only need somewhere safe to cut, not an
    # accurate silence map. Stage 2 does the careful version.
    import numpy as np
    floor_db = float(np.percentile(db, 10))
    silences = silence_from_envelope(db, min(floor_db + 11.0, -28.0))
    del db
    gc.collect()

    bounds = [0.0]
    target = chunk_seconds
    while target < duration - search:
        window = [(a, b) for a, b in silences
                  if a > bounds[-1] + min_gap and abs((a + b) / 2 - target) <= search]
        if window:
            # the longest silence near the target is the safest place to cut
            a, b = max(window, key=lambda iv: iv[1] - iv[0])
            bounds.append((a + b) / 2)
        else:
            bounds.append(target)
        target = bounds[-1] + chunk_seconds
    bounds.append(duration)
    return [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]


def extract_chunk(wav: Path, start: float, end: float, dest: Path) -> None:
    ffmpeg_run(["-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(wav),
                "-c:a", "pcm_s16le", str(dest)])


def transcribe_chunk(model, path: Path, offset: float, language: str | None,
                     beam_size: int) -> tuple[list[dict], str, float]:
    segments, info = model.transcribe(
        str(path),
        language=language,
        beam_size=beam_size,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 400},
        # Long lecture silences are the classic trigger for whisper looping one
        # sentence for minutes. Dropping text conditioning is what stops it.
        condition_on_previous_text=False,
    )
    out = []
    for seg in segments:
        words = [
            {"start": round(float(w.start) + offset, 3),
             "end": round(float(w.end) + offset, 3),
             "word": w.word,
             "probability": round(float(w.probability), 4)}
            for w in (seg.words or [])
            if w.start is not None and w.end is not None
        ]
        out.append({"start": round(float(seg.start) + offset, 3),
                    "end": round(float(seg.end) + offset, 3),
                    "text": seg.text.strip(),
                    "words": words})
    return out, info.language, float(info.language_probability or 0)


# --------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="lecture-forge stage 1: transcribe")
    ap.add_argument("workdir")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help=f"faster-whisper model (default {DEFAULT_MODEL}); "
                         "small.en is lighter, large-v3-turbo more accurate")
    ap.add_argument("--compute-type", default="int8",
                    help="int8 (default, lightest), int8_float32, or float32")
    ap.add_argument("--language", default=None)
    ap.add_argument("--beam-size", type=int, default=5)
    ap.add_argument("--threads", type=int, default=0, help="0 = let ctranslate2 decide")
    ap.add_argument("--chunk-seconds", type=float, default=DEFAULT_CHUNK,
                    help=f"approximate chunk length (default {DEFAULT_CHUNK:.0f}s)")
    ap.add_argument("--force", action="store_true",
                    help="discard cached chunks and start over")
    args = ap.parse_args()

    wd = Path(args.workdir).expanduser().resolve()
    media = read_json(wd / "media.json")
    wav = wd / "analysis.wav"
    if not wav.exists():
        die(f"missing {wav} — run lf_probe.py first")

    out = wd / "transcript.json"
    if out.exists() and not args.force:
        cached = read_json(out)
        log(f"transcript already present ({cached.get('model')}, "
            f"{len(cached.get('segments', []))} segments) — use --force to redo")
        return

    chunk_dir = wd / "transcript_chunks"
    if args.force and chunk_dir.exists():
        for stale in chunk_dir.glob("*.json"):
            stale.unlink()
    chunk_dir.mkdir(exist_ok=True)

    duration = float(media["duration"])
    spans = split_points(wav, duration, args.chunk_seconds)
    done = sorted(chunk_dir.glob("chunk-*.json"))
    log(f"{len(spans)} chunks of ~{args.chunk_seconds:.0f}s"
        + (f", {len(done)} already transcribed — resuming" if done else ""))

    model = None
    language, lang_prob = "en", 0.0
    started = time.time()
    tmp = wd / "_chunk.wav"

    for i, (lo, hi) in enumerate(spans, start=1):
        target = chunk_dir / f"chunk-{i:03d}.json"
        if target.exists() and not args.force:
            continue
        if model is None:
            # Loaded lazily so a fully-resumed run never pays for it.
            try:
                from faster_whisper import WhisperModel
            except ImportError:
                die("faster-whisper is not installed in this interpreter. Run: "
                    "uv pip install --python ~/.lecture-forge/venv/bin/python faster-whisper")
            log(f"loading model {args.model} ({args.compute_type})")
            model = WhisperModel(args.model, device="cpu",
                                 compute_type=args.compute_type, cpu_threads=args.threads)

        log(f"chunk {i}/{len(spans)}  {hhmmss(lo)}–{hhmmss(hi)}")
        extract_chunk(wav, lo, hi, tmp)
        segs, language, lang_prob = transcribe_chunk(
            model, tmp, lo, args.language, args.beam_size)
        write_json(target, {"start": lo, "end": hi, "segments": segs,
                            "language": language, "model": args.model})
        gc.collect()

    tmp.unlink(missing_ok=True)

    # Merge every chunk in order.
    segments: list[dict] = []
    for path in sorted(chunk_dir.glob("chunk-*.json")):
        data = read_json(path)
        language = data.get("language", language)
        segments += data["segments"]
    if not segments:
        die("no speech transcribed — is there audio on this recording?")

    segments.sort(key=lambda s: s["start"])
    for n, seg in enumerate(segments):
        seg["id"] = n

    elapsed = time.time() - started
    payload = {
        "model": args.model,
        "compute_type": args.compute_type,
        "language": language,
        "language_probability": round(lang_prob, 4),
        "audio_duration": round(duration, 3),
        "spoken_duration": round(sum(s["end"] - s["start"] for s in segments), 3),
        "transcribe_seconds": round(elapsed, 1),
        "chunks": len(spans),
        "segments": segments,
    }
    write_json(out, payload)
    log(f"done in {hhmmss(elapsed)} — {len(segments)} segments, "
        f"{sum(len(s['words']) for s in segments)} words")
    log(f"wrote {out}")


if __name__ == "__main__":
    main()
