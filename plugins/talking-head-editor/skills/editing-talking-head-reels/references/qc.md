# QC: the gates and how to run them

## After edl.py
- `edl.py` self-check: every take produced a piece; every ASR word inside a take landed in a piece. A word in no piece is
  usually a soft word the energy gate shaved; look at the 10 ms envelope there.
- **`python3 stutter_scan.py`**: every piece transcribed on its own (medium, no VAD, no conditioning) so Whisper can't merge
  a repeat across a cut. Flags: `repeat_across_cut`, `false_start`, `double_word`, `double_bigram`, plus wordless pieces with
  their peak. Fix in keep_spans.py and re-run until it's clean. Takes ~2x the clip length on CPU: run it in the background.

### Stutter catalogue (all from one VSL that had "passed" a render-transcript check)
| what you hear | cause | fix |
|---|---|---|
| "Click the button. Click the button below this video" | a false start kept as its own piece | start the span at the second attempt |
| "spots at, at a time" | a doubled word with a tiny pause | inner cut over the first word (find it in the 10 ms envelope) |
| "This, this method" | a restart at a sentence start | start the span after the first word |
| "injury and, and now" | the cut kept the ONSET of the next word (cut 50 ms late, inside a continuous phrase) | end the span at the end of the last kept word, not at the dip after it |
| "I... If that sounds fair" | a quiet blip before the line (a swallowed word, a lip noise) | start the span after it |
| a breath or click between words | a wordless 0.3-0.5 s piece | inner cut over it |
To find one by ear-time: map record time to the EDL piece, then print the 10 ms envelope and run a medium transcript on a
tight window of the SOURCE (not the render) on each side of the join.

## Before the full render
- `./rv.sh resolve_final.py --test 0 40` (and a section with graphics, stills and client clips). Look at it.
- **Colour vs the camera LUT** (log sources): grab the render frame and the source frame through the LUT at the same moment;
  face luma within ~10%, room no more than 0.7 stop darker. A default ResolveFX Vignette once took the room from 41 to 8.
- Caption size: Text+ Size is relative to frame width (700 px per unit at 1080 wide; 1244 at 1920 wide). Check a power word.

## After the render
`python3 qc_render.py render/<OUT>_final.mp4 --joins` checks:
- duration = edl duration (a stretched timeline means an fps fault or an unclamped caption);
- **zero** black frames (`blackdetect=d=0.01:pix_th=0.10`): a clip read at the wrong fps drops a frame at every cut;
- loudness -16 LUFS +-1, true peak under -1 dBTP;
- colour as above;
- a medium transcript around every take join (and `--at t1,t2` for any time the creator named). Read them; they confirm the
  stutter fixes on the finished file.
Then a contact sheet (`ffmpeg -i F -vf "fps=1/12,scale=384:216,tile=6x6"`) that you actually look at: wrong person in a
clip, a heading with nothing under it, a photo covering text, a caption on a graphic.
Whisper skipping a client clip's window doesn't mean the audio is missing: check its level (p90 should match the creator's).
