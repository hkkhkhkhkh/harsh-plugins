# lecture-forge

One raw lecture recording in, several publish-ready bite-sized lectures out.

You decide *what* is worth publishing. Everything else — cutting, tightening
pauses, removing chatter and false starts, cleaning and levelling the audio —
is automated.

Output is 16:9 MP4 at source resolution, plus a re-timed `.srt` and a `.md`
with a title, description and transcript for each clip.

---

## Install

**From the marketplace** (preferred — you get updates with `/plugin update`):

```
/plugin marketplace add hkkhkhkhkh/harsh-plugins
/plugin install lecture-forge@harsh-marketplace
```

**From a zip:** unpack into `~/.claude/plugins/` and restart Claude Code.

Restart matters either way: the slash commands and the `lecture-curator` agent
are registered at startup, so a plugin installed mid-session is not live until
you restart.

## One-time setup

**1. ffmpeg** must be on your PATH. `ffprobe` is optional.

```
brew install ffmpeg          # or any build on PATH
```

**2. A Python environment** for transcription:

```
uv venv --python 3.12 ~/.lecture-forge/venv
uv pip install --python ~/.lecture-forge/venv/bin/python faster-whisper numpy
```

**3. Calibrate your room**, once per camera position — not per lecture:

```
/lecture-forge-calibrate <a-lecture.mp4> --name my-room
```

It samples frames and proposes where the board is, then shows you the picture
with the box drawn on. **Check the box covers the whole board including its
edges.** That box is the only thing stopping a zoom from cropping your writing
off, so err large: an over-sized box just means less zoom.

## Using it

```
/lecture-forge <lecture.mp4> --profile my-room
```

Transcribes, analyses, and proposes clips. **It stops and waits for you.**
Budget roughly a third of the lecture's length for transcription — about 20
minutes for an hour of video on an M-series Mac.

Then open `review.md` in the work folder and approve:

- **Delete the row** of any clip you do not want.
- **Edit a title or timecode** in place — the table wins over what was proposed.
- **Content cuts** are listed separately, longest first. These remove *spoken
  words*, not pauses. Delete any row you disagree with and those words stay.

```
/lecture-forge-render --profile my-room
```

Renders exactly the rows that survived. Add `--fast` to trade quality for
roughly 5× the speed.

## After rendering, read `removed.md`

Every cut, with the words it took out and the rule that made it.

This is worth the two minutes. A clip that *kept* something it shouldn't is
obvious the first time you watch it. A clip that *lost* a punchline looks
completely fine — there is nothing left to notice. `removed.md` is the only
place that failure is visible.

## When it gets something wrong

Tell it, so the fix sticks for every future lecture instead of just this one.
See `docs/FEEDBACK-DESIGN.md` for how feedback becomes a change and who
approves it.

Most behaviour is data, not code: `config/defaults.json` holds the pause
budgets, the off-topic patterns, the clip length bounds. Settings resolve
narrowest-wins:

```
CLI flag > room profile > ~/.lecture-forge/config.json > config/defaults.json > code defaults
```

So a change for one room goes in that room's profile, a change for everyone
goes in `config/defaults.json` and through review, and the code defaults stay
put as a fallback you can always drop back to.

## What it does that is not obvious

- **Pause budgets depend on what the pause is doing.** A pause while you write
  on the board is not dead air — the viewer is reading — so it is kept whole. A
  stumble mid-sentence is cut hardest. Beats after a question survive.
- **Every cut boundary must land in detected silence**, or the cut is refused
  and logged rather than forced. This is why the occasional "um" survives:
  there was no pause around it to cut in, and keeping it beats clipping the
  word next to it.
- **Punch-in disables itself** rather than crop the board. If your board fills
  most of the frame, expect hard cuts — that is the correct behaviour.
- **Transcription is resumable.** An out-of-memory kill costs one chunk, not
  the lecture.

## Docs

| File | What |
|---|---|
| `skills/lecture-forge/SKILL.md` | full pipeline reference |
| `references/pipeline.md` | what each stage does and why |
| `references/selection-rubric.md` | what counts as a clip worth publishing |
| `references/audio-chain.md` | the filter chain and the order it must run in |
| `references/troubleshooting.md` | symptoms, causes, and which knob to turn |
| `docs/FEEDBACK-DESIGN.md` | how feedback turns into approved change |
