# Troubleshooting

Each symptom has a specific cause. Diagnose before turning knobs.

## Audio and video drift apart by the end of a clip

Check the tail, not the head — drift accumulates:

```
ffmpeg -v quiet -stats -i clip.mp4 -map 0:v -f null - 2>&1 | tail -1
ffmpeg -v quiet -stats -i clip.mp4 -map 0:a -f null - 2>&1 | tail -1
```

Under 100 ms apart is fine. Beyond that, the cause is almost always that video
and audio were cut with different range lists. Read the graph in
`filtergraphs/<clip>.txt`: the `select` and `aselect` expressions must be
character-for-character identical. Also confirm `-fps_mode cfr` survived; a
variable-rate output drifts against constant-rate audio.

## A long pause survived the cut

Measure it in the rendered file:

```
ffmpeg -i clip.mp4 -af silencedetect=noise=-32dB:d=0.15 -f null -
```

Then find that moment in `edits.json`. Two usual causes:

**A word timestamp is covering it.** Check `transcript.json` for a word whose
span covers the pause. Word protection is trimmed to real energy specifically to
handle this, but a word whose quiet tail is still above the gate can hold a pause
open. Look at `speech_gate_db` in `edits.json` — if the gate sits unusually low,
the room is noisy.

**The pause is not being detected as silence.** A noisy room raises the measured
floor and the gate with it. `noise_floor_db` in `edits.json` tells you; above
about −45 dBFS, denoise before analysing rather than fighting the gate.

## Too much was cut / speech sounds clipped

Nothing should ever be cut mid-word — that rule is enforced. If a word sounds
truncated, suspect the cut boundary landed in silence that was really a quiet
consonant. Raise `WORD_PAD` in `lf_analyze.py` (default 40 ms) and re-analyse.

Speech that sounds breathless rather than clipped is `--max-gap` set too low.
0.2 s is tight but natural; below about 0.15 s it stops sounding human.

## Not enough was cut

Check `refused` in `edits.json`. A high refusal count means the speaker rarely
pauses cleanly around fillers, and the safety rule is doing its job. Loosening
it trades listenability for tightness; usually the better answer is to accept
the fillers.

## The smartboard gets cropped in punched shots

The profile's `board_box` is too small. Re-run `/lecture-forge-calibrate` and
check the green box covers the board including its edges, or widen `board_box`
by hand. Err large — an over-sized board box only reduces the zoom.

To confirm which frames are punched, read the `overlay ... enable=` expression in
`filtergraphs/<clip>.txt` and export a frame from inside one of those ranges.

## Punch-in did not happen at all

Either no zoom ≥ 1.06 keeps the board in frame (the log says so — the board
occupies too much of the frame), or the clip has no cut that removed ≥ 0.35 s,
or `--no-punch` was passed.

## Whisper repeats the same sentence for minutes

Hallucination looping on a long silence. `condition_on_previous_text=False` is
already set, which handles most of it. If it still happens, the recording likely
has a long stretch of near-silence with faint noise; transcribe with
`--model large-v3-turbo`, which is markedly more resistant.

## A clip proposal was dropped

`review.md` lists every dropped proposal with the reason. "Lands nowhere near a
spoken word" means the curator invented a timecode — normal, and correctly
caught. "Only Ns long" means it fell under `--min-clip` (default 40 s).

## Rendering is slow

`--fast` uses VideoToolbox. Also check you are not re-transcribing: stage 1
caches, and `lf_transcribe.py` without `--force` reuses `transcript.json`.
