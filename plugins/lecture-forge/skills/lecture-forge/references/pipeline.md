# Pipeline internals

## Stage 0 — probe (`lf_probe.py`)

Resolution, fps, duration, audio layout, plus a 16 kHz mono `analysis.wav` that
every later stage reads instead of decoding the video again.

ffprobe is used when present and otherwise the properties are parsed out of
`ffmpeg -i` stderr, because a standalone ffmpeg binary without ffprobe alongside
it is a common install.

The workdir is `<source_dir>/lecture-forge/<slug>/` unless `--out-root` says
otherwise. All state lives there as JSON, which is what makes every stage
resumable.

## Stage 1 — transcribe (`lf_transcribe.py`)

faster-whisper, word timestamps mandatory — every downstream decision is keyed
to them. `condition_on_previous_text=False` is deliberate: long lecture silences
are the classic trigger for whisper looping one sentence for minutes, and
dropping the text conditioning is what stops it.

## Stage 2 — analyse (`lf_analyze.py`)

Where the mechanical edit is decided.

**Silence map.** An RMS envelope at 10 ms resolution, with the noise floor taken
as the 10th percentile of the whole recording and the speech gate 11 dB above
it. Adaptive, so a quiet room and a noisy one both work without a fixed dB
threshold.

**Word protection, trimmed to real energy.** A word protects the audio under it
from being cut — but only across the part of its span where energy actually
exists. Whisper regularly stretches a short word across the pause after it
("When" reported as 28.02–29.08 for a word spoken in a fifth of that), and
protecting the reported span verbatim makes real dead air permanently uncuttable.
This was a real bug, caught by measuring pauses in a rendered clip.

**Fillers and stutters become silence.** A filler is not cut on its own. It is
reclassified as non-speech, folded into the silence map, and then the one
capping pass handles it. Otherwise removing "um" leaves the pauses that
surrounded it behind, which sounds worse than the "um" did.

**One capping pass.** Every pause — including pauses widened by a removed filler
— is shortened to `--max-gap` by deleting its middle. Padding at each end is
limited to the real silence available on that side, so a short pause yields a
shorter cut rather than a boundary that slices into speech.

**Off-topic asides.** Whole sentences of production chatter — the camera, the
microphone, the battery, "can everyone hear me" — are removed outright rather
than shortened, because no length of them is worth keeping. Detection is
deterministic (narrow regexes over each sentence, listed in `DEFAULT_ASIDES`)
rather than left to the curator's judgement, since this chatter is the most
predictable thing in any recording and the most damaging to a finished clip.
The patterns need equipment context around them: a bare "charge" or "wire"
would fire on real teaching. Add per-room patterns with `--aside-pattern` or an
`aside_patterns` list in the profile.

**Refusal.** A filler or stutter with no real silence on both sides is kept, and
logged. A boundary that cannot be snapped into silence within 300 ms is refused.
Refusals are reported, never silently forced.

## Stage 3 — selection

`lf_curate.py --dump` writes ~10-minute transcript windows with a minute of
overlap so an idea spanning a boundary is seen whole by at least one agent.

Curator output is not trusted verbatim. `--collect` snaps every proposed
boundary onto a real word boundary within 2.5 s, drops proposals that land
nowhere near speech, enforces length bounds, and dedupes proposals overlapping
by 60% or more — the overlap between windows means the same idea gets proposed
twice by design.

## Stage 4 — render (`lf_render.py`)

**Cutting.** One filter graph, `select` and `aselect` driven by the same range
list, `setpts`/`asetpts` to rebuild timestamps, constant frame rate out. Cutting
the two streams in separate passes is the classic cause of clips that drift out
of sync by the end.

The graph goes to a file and is passed with `-filter_complex_script`, because a
long lecture produces a range list far past any command-line length limit. The
graph files are kept in `filtergraphs/` for debugging.

**Punch-in.** Computed on the output timeline after cutting, then applied as one
overlay whose `enable` expression sums all the punched ranges. State alternates
on every cut that removed at least 0.35 s, with a 4-second minimum dwell so it
cannot flicker.

**Board safety.** The crop rectangle must contain the profile's `board_box` plus
a 1% margin. The largest zoom satisfying that is used, clamped to 1.06–1.14; if
nothing ≥ 1.06 fits, punch-in disables itself and logs why. A jump cut is a
smaller problem than a clip with the board writing cropped off.

**Encoding.** libx264 CRF 18 preset slow by default; `--fast` switches to
VideoToolbox for roughly 5× the speed at lower quality per bit.

Each clip also gets an SRT re-timed onto the cut timeline and a markdown sidecar
with the title, description, key points and full transcript.
