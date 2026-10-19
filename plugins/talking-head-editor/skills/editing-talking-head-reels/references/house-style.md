# House style: the signed-off finish

Each line is a default the creator approved after rounds of notes. The "why" is what was rejected. Change a default
only when the creator asks, and write the reason next to the setting in `job.py`.

## Cuts
- **Later take wins.** Recordings carry restarts; keep the last complete version of each line.
- **Remove every pause of 0.10 s or longer** inside reels and VSLs (0.28 s pauses read as "too much gap"). Long-form course
  videos use 0.50 s, or the cut turns into hundreds of jump cuts.
- Speech detection is relative to the clip's own level (p95 - 29 dB on the cleaned audio), so a lav and a phone mic both work.
- Take edges follow the audio down to p95 - 42 dB as far as the first/last word reaches, so soft first and last words survive.
- No shot under ~0.3 s unless it carries a word; breaths and lip noise between pieces are cut.
- Doubled lines ("you do not understand... you do not understand") are cut where the energy dips; check the words either side.

## Voice
DeepFilterNet 3 over the whole source, then HPF 80 Hz, -3 dB at 300 Hz, +3 dB at 3.2 kHz, air shelf, de-ess, 3:1 compression,
limiter. Dialogue is cut at the picture's frame times with 8 ms fades at every join (no clicks). Client clips are cleaned the
same way and matched to the creator's speech level.

## Captions
- **Power-word style**: each group is built round one power word, big and UPPERCASE on the caption line (Avenir Next Condensed
  Heavy); small lead-in words on the line above, follow-on words below (Avenir Next Demi Bold); every line re-centres as each
  word lands. Power words: nouns and claims, about one every 1.5 s; the same word again within 8 s stays small.
- Caption line: y 1280 of 1920 (9:16; y 1150 with `AD_SAFE` for paid ads, clear of Meta's bottom-35% UI); y 880 of 1080 (16:9,
  over the chest).
- **Captions never sit on a motion graphic**: words spoken while a graphic is up get no caption. Never move captions to dodge.
- The words come from verified lines, never straight from ASR.

## Calm finish ("visually calm and depictive, not a mess")
- No stickers: no chips, seals, badges, ribbons, "LIVE" tags, kicker labels. Keep only graphics that show something:
  comparisons, strikes, lists, a mechanism, numbers with a source, the guarantee, the CTA, real photos.
- Nothing on screen under 2.5 s. Back-to-back graphics join with hard cuts (no wipe, no plate re-animation, no whoosh).
- Mix side/split panels with full-screen scenes.
- Zoom: one pivot for the whole video (median face, top of the head). Re-pivoting per clip made the frame jump at cuts.
  9:16 iPhone: one slow breathe (1.00 to 1.045 over 18 s). Log-camera reels and 16:9: gentle per-line push in / pull out
  (1.00 to 1.06) with an occasional punch-in (1.10-1.16) on a face-only line that turns the argument.
- Grade: log camera through Resolve colour management; iPhone through the phone's own HDR-to-SDR conversion with no grade on
  top ("keep it normal"). Background slightly darker than the face is good; a crushed, black room is not.
- Text behind the head: only for clean-edged subjects (short hair, plain backdrop). Curly hair on phone footage keys badly.

## Sound design
Whoosh per card, pop per landing item (quiet), scratch on strikes, whip on punch-ins, riser + sub impact only on a price
reveal, air whoosh around inserts. Effects sit 4 dB under the rule gains (calm finish). Energy comes from pace and music,
not effects: measured reference creators use effects barely above chance. No glitch, bell or game sounds, ever.

## Music and loudness
- Whole mix -16 LUFS (-14 was too loud). Voice sits 25 dB over the bed under speech (`stems.py` iterates to land it).
- The bed can drop out for a line that must land alone (`MUSIC_DROPS`, derived from the word map).
- Licence: paid traffic needs a bed you own (e.g. Higgsfield Sonilo output) or a sync licence. A commercial track you only
  have a local copy of is for organic posts. Extend a short owned bed with `music/build_bed.py` (bar-line loops).

## Deliverables
One H.264 render (plus a ProRes master only if asked and there is disk), at the format's resolution. The Resolve project and
the After Effects project stay so the creator can change anything. No placeholders unless asked; no PDFs for internal work.
