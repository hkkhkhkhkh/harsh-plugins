---
name: editing-talking-head-reels
description: Edit a raw talking-head recording into a finished, polished video inside DaVinci Resolve with After Effects motion graphics and Higgsfield inserts. Covers 9:16 reels and ads (log camera like a Sony FX30, or an iPhone selfie) and 16:9 sales videos / VSLs / YouTube talking-heads with real client proof. Use whenever someone hands over a camera clip (an .MP4/.MOV from a card such as /Volumes/.../M4ROOT/CLIP, or a phone video) and asks to edit, cut, tighten, grade, caption, add motion graphics, zooms, B-roll, sound design or music, make a VSL or sales video from a recording, fix stutters or bad cuts, add testimonials or client results to a video, or put the finished video on a landing page. Also use for "use the editing skill we used", "same style as the last reel", "edit this vsl on davinci with after effects", or any follow-up note on an edit in progress (a stutter at 06:18, a wrong client name, replace a photo, a cut that feels wrong).
---

# Talking-head editing (Resolve-led finish)

One camera take in; one finished video out, built inside **one DaVinci Resolve timeline** the creator can open and change:
V1 graded A-roll (Fusion zoom + ResolveFX per piece), V2 B-roll / stills / real client clips, V3 After Effects graphics
(ProRes 4444 alpha), V4 power-word captions (Fusion Text+), A2 cleaned dialogue, A3 music, A4 sound design.
Everything is scripted (Python + Resolve API + After Effects ExtendScript via osascript), so a note like "cut the stutter
at 6:18" is a change to data and a re-render, not a manual re-edit.

The house style came from rounds of the creator's notes; each default below exists because the alternative was rejected.
Read `references/house-style.md` once per job. Don't re-litigate a default unless the creator asks.

## Before anything

- **Get the script** if one exists. It is the source of truth for caption words, names and which take to keep.
- **Pick the format from what the video is FOR**, not from the camera: sales video / VSL / YouTube → 16:9 `vsl`;
  Instagram reel or ad → 9:16 (`reel` for a log camera, `iphone` for a phone selfie). Long-form course video → `vsl` with
  the long-form settings in `references/formats.md`. A VSL was once cut 9:16 and had to be redone.
- **Check the tools you will lean on**: Resolve running with external scripting on (Preferences → System → General);
  After Effects driven only through the GUI-session osascript tool (`DoScriptFile`; launching AE from a shell hangs);
  Higgsfield credits (`higgsfield account status`, `higgsfield generate cost <model>`). The cheapest video model costs
  about 5 credits per 5 s; z_image stills cost 0.15. With low credits, plan stills with a slow push, and say what a top-up buys.
- **Resolve and After Effects are shared.** Two Resolve renders at once crash it; two AE scripts collide. If another
  session might use them, message it before you start and when you finish. Never kill processes you didn't start.
- **Disk**: a 4K 50p source is ~1.5 GB/min, a 1080p master ~90 MB/min. Skip the ProRes master when space is tight.

## Start a job

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/new_job.py <clip> --format vsl|reel|iphone [--name C0040]
```
It probes the clip (fps, size, Sony log or iPhone HLG), copies it off the card with a byte check, builds the job folder
with the format's scripts and writes `job.py` (all settings, documented) from `~/.config/talking-head-editor/config.json`.
Every script runs from the job folder and imports `job.py`. Edit `job.py` first if anything is off.

## The pipeline (each step has a gate: don't move on until it passes)

**1. Clean + transcribe.** `python3 clean_source.py` (DeepFilterNet 3 over the whole source), then
`python3 transcribe.py` in the background (two ASR passes: whole-clip small for take boundaries, per-phrase medium for
words). Read the transcript tail: spoken edit notes ("use this one", "put a paragraph before this") are instructions.

**2. Cut.** Write `SPANS` in `keep_spans.py`: later take wins, drop false starts, asides and repeated lines.
`python3 keep_spans.py --edges` shows the words and the quietest 10 ms point at every edge; cut on the dip, because a
cut a few hundredths late keeps the onset of the next word and plays as a stutter. Then `python3 edl.py`
(silence removal, word-anchored take edges, sliver cleanup, and a self-check that no take or word was lost).
**Gate: `python3 stutter_scan.py`** transcribes every piece on its own and flags repeats across cuts, false starts,
doubled words and wordless pieces. Fix each one in `keep_spans.py` (span start or inner cut) and re-run until clean.
This scan exists because a render transcript reads fluently even when the audio stutters: ASR smooths repeats away.
Catalogue of stutter shapes and how to cut each: `references/qc.md`.

**3. Faces + layout.** `python3 wordmap.py && python3 faces.py`. The median face position decides the graphics layout:
a face filling the top half of a 9:16 crop wants split scenes; a centred 16:9 face wants the right-hand plate with the
A-roll sliding him left. See `references/formats.md`.

**4. Claims and proof.** Before any graphic exists, check every product fact against the live source and every client
claim against the client's records. Real client clips, photos, lab values and quotes only, each with a source line;
never a quote nobody said or a number nobody measured; confirm who is in a clip before naming them. When the records
contradict the voice, the card shows the records and the creator gets a flag, never a silent edit of their words.
`references/proof-and-claims.md` has the rules and how to pull the data.

**5. Captions.** `python3 captions_lines.py --draft` → read and fix every line in `captions_lines.json` against the script
and the audio (names, units, words removed by the cut), choose the power words, then `python3 captions_lines.py`.

**6. Graphics.** Write `G` in `gen_ae.py` (typed templates; every cue is a spoken word via `at(word, take)`; the full
catalogue is in `references/graphics.md`). Render a few ids first (`python3 gen_ae.py g02 g04`, run the jsx), composite
each over a real A-roll frame, look at it, then render all. Then `python3 power_captions.py` (captions drop out while any
graphic is on screen) and `python3 proof_captions.py` (captions for client clips without burned-in ones).

**7. Inserts.** Higgsfield stills or video for the beats that need a picture (`higgsfield-generate` skill). Look at
every result: drop or regenerate anything with fake readable text (labels, screens). Stills ride V2 under the captions.

**8. Audio.** `python3 dialogue.py` (cut at the picture's frame times, 8 ms join fades, voice chain), music bed in
`job.MUSIC` (extend a short bed with `python3 music/build_bed.py`), then `python3 stems.py` (sound design placed by
`sfx_rules.py` from the graphics, inserts and zooms; iterates to -16 LUFS with voice 25 dB over the bed).

**9. Resolve.** `./rv.sh resolve_build.py --no-render` (project, colour management, cut timeline), then
`./rv.sh resolve_final.py --test 0 40` and LOOK: grade, captions size, the plate slide, ResolveFX. Measure the colour
against the camera-LUT preview before the full render (`references/qc.md`). Then `./rv.sh resolve_final.py` (H.264 only).

**10. QC + delivery.** `python3 qc_render.py render/<OUT>_final.mp4 --joins` (duration, black frames at cuts, loudness,
colour, transcripts around joins). Then a contact sheet you actually look at. For a site: `python3 web_encode.py ...`
and `references/delivery.md`. Send the creator the file and a short list of what changed and what is still open.

## Notes from the creator mid-edit

Treat each note as data: a stutter → find it (`stutter_scan.py`, 10 ms energy around the time), fix the span, re-run
from `edl.py`. A wrong name or photo → fix the data and re-render that graphic only (`gen_ae.py <id>`). Anything that
moves time (a cut, a moved clip) means re-running edl → faces → wordmap → captions → gen_ae (all) → power_captions →
dialogue → stems → resolve_final. Take ids stay stable when clips move, so cues keep working; derive any absolute time
(music drops) from the word map, never a fixed number.

## Reference files

- `references/house-style.md`: the approved defaults and why (cuts, voice, captions, calm finish, zoom, sound, music, loudness).
- `references/formats.md`: what differs for reel / iPhone / 16:9 VSL / long-form, including the 16:9 plate geometry.
- `references/graphics.md`: every After Effects template and block, calm-layout rules, testing graphics.
- `references/proof-and-claims.md`: claims checks, client proof from records, identity, consent, privacy.
- `references/qc.md`: every gate, the stutter catalogue, colour and loudness checks, what to look at.
- `references/traps.md`: Resolve, Fusion, After Effects, audio, Whisper, Higgsfield and iPhone traps (each cost a render).
- `references/delivery.md`: web encode, putting the video on a landing page, verifying it plays from the live URL.
