---
name: lecture-forge
description: Turn a full-length recorded lecture into several publish-ready bite-sized lectures. Transcribes with word-level timestamps, proposes the valuable self-contained segments for human approval, then renders 16:9 MP4s with pauses shortened to 0.2s, fillers and mistakes removed, jump cuts hidden by alternating punch-ins, noise reduced and loudness normalized to -16 LUFS. Use when the user wants to chop a lecture, recording, webinar, or long-form talk into clips, cut silence or filler words out of a video, clean up lecture audio, or repurpose a recorded class into short teaching videos. Trigger on "/lecture-forge", "cut up this lecture", "chop this recording", "remove the silences from this video", "make clips from my class", "edit this talk down".
---

# lecture-forge

One raw lecture in, several finished clips out. The human decides *what* is
worth publishing; everything else is mechanical and automated.

**Commands:** `/lecture-forge <file>` runs the analysis and stops at a review
sheet. `/lecture-forge-render` renders what survived the review.
`/lecture-forge-calibrate <file>` sets up a camera profile once.

## Run everything with the pipeline's own interpreter

```
PY=~/.lecture-forge/venv/bin/python
S=${CLAUDE_PLUGIN_ROOT}/scripts
```

`$PY $S/lf_*.py`. The system python does not have faster-whisper. If the venv is
missing, create it once:

```
uv venv --python 3.12 ~/.lecture-forge/venv
uv pip install --python ~/.lecture-forge/venv/bin/python faster-whisper numpy
```

## The pipeline

| Stage | Command | Writes |
|---|---|---|
| 0 Probe | `lf_probe.py SOURCE [--out-root DIR]` | `media.json`, `analysis.wav`, prints the workdir |
| 1 Transcribe | `lf_transcribe.py WD [--model medium.en]` | `transcript.json` |
| 2 Analyse | `lf_analyze.py WD [--max-gap 0.2]` | `edits.json` |
| 3a Windows | `lf_curate.py WD --dump` | `windows/win-NN.md` |
| 3b Curate | one **lecture-curator** agent per window | `windows/win-NN.json` |
| 3c Collect | `lf_curate.py WD --collect` | `clips.json` |
| 3d Sheet | `lf_reviewsheet.py WD [--previews]` | `review.md` ← **human gate** |
| 4 Render | `lf_render.py WD [--profile N] [--fast]` | `clips/*.mp4` + `.srt` + `.md` |
| 5 Report | (automatic) | `summary.md`, `render-report.json` |

Every stage is resumable: each reads the previous stage's JSON from the workdir,
so a failed render never costs you the transcription.

## Running it

**Stage 1 is the slow one.** On an M3, `medium.en` at `int8` runs roughly 3–5×
faster than realtime, so budget about a third of the lecture's length — 20–30
minutes for a 90-minute recording. Say this to the user before starting rather
than leaving them watching a silent terminal. `--model large-v3-turbo` is more
accurate if they will wait; `small.en` is the fast, rougher option.

**Stage 3b fans out.** Dispatch every window to a `lecture-curator` agent in a
single message so they run in parallel. Tell each agent its window path and that
it must write the sibling `.json`. A 90-minute lecture is about 10 windows.

**Stage 3d is a hard stop.** Show the user the review table inline. Do not
render until they have replied. They approve by deleting rows from `review.md`;
whatever rows remain are what renders. They can also edit a title or a timecode
in the table and it wins over `clips.json`.

**Before a long render**, run `lf_render.py --dry-run` and show the plan.

## What is decided without asking

These come from decisions already made with the user. Do not re-litigate them
per run; do surface them in the summary.

- Pauses longer than **0.2 s are shortened to 0.2 s**, never deleted outright —
  removing pauses entirely makes speech sound breathless.
- Fillers (`um`, `uh`, `you know`, `i mean`, …) and stuttered repeats are
  removed, but only where real silence borders them on both sides.
- Jump cuts are hidden by an **alternating punch-in**, constrained so the
  smartboard is never cropped out of frame.
- Audio: high-pass, `afftdn` denoise, then two-pass **loudnorm to −16 LUFS /
  −1.5 dBTP**, measured on the cut audio.
- Output is **16:9 at source resolution**, H.264 CRF 18, AAC 192k, faststart.

## The rule that keeps clips listenable

**Every cut boundary must land inside detected silence.** A cut that cannot be
placed there is refused and logged rather than forced. This is why a filler
sometimes survives — there was no pause around it to cut in, and keeping an
"um" is a smaller failure than clipping the word next to it. The refusal count
appears in `review.md` and `summary.md`; report it rather than hiding it.

## Camera profiles

A profile (`~/.lecture-forge/profiles/NAME.json`) records where the smartboard
sits in frame. Punch-in solves for the largest zoom whose crop still contains
the whole board; if no zoom ≥ 1.06 can, punch-in disables itself for that
lecture and you get plain hard cuts plus a warning. Without a profile, punch-in
zooms on frame centre — fine for a plain talking head, wrong for a board.

Calibrate once per camera position, not per lecture.

## When something looks wrong

`references/troubleshooting.md` covers A/V drift, clicks at joins, over-cutting,
under-cutting, board cropping, and whisper hallucination loops. Read it before
changing tunables — most symptoms have a specific cause and a specific knob.

Other references: `pipeline.md` (what each stage does and why),
`selection-rubric.md` (what counts as a valuable clip), `audio-chain.md` (the
filter strings and the order they must run in).
