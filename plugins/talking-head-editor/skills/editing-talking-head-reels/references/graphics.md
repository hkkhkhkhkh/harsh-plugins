# Graphics (After Effects kit)

`gen_ae.py` writes `ae/graphics.jsx` = settings + `G` (data) + `ae/kit.jsx` (templates). Run it in After Effects through the
GUI-session osascript tool: `tell application "Adobe After Effects 2026" to DoScriptFile "<job>/ae/graphics.jsx"`. DoScript
returns before rendering ends: poll `graphics/*.mov` until the count and sizes stop changing. A template that throws saves
`ae/ERR_<id>_line<n>_<message>.aep` instead of hanging on a modal.

Every graphic: `{"id", "type", "start", "end", "cues": {name: record seconds}, ...fields}`. Cues are SPOKEN words:
`at("guarantee", 1)` (the ASR spelling: check `transcripts/rec_words.json`, e.g. a name may be spelled "meenu").
`cues.out` defaults to end - 0.25 s. Colours and fonts come from `job.BRAND`.

## 9:16 templates
| type | what it is | key fields |
|---|---|---|
| chips_strike | three chips land, get struck, swap to one card | labels [[text, cue, width]], eyebrow, title, cues strike/one |
| list | eyebrow + rows landing on their words | head, rows [[text, cue]], top |
| price | old price struck, real price lands, refund chip | old, price, unit, chip, cues card/price/refund, x |
| cta | button between chin and captions, arrow nudges | text, cues btn, y |
| study | journal + year, finding, n + design, highlight | journal, year, finding, n, design, tone support/refute/neutral |
| verdict | MYTH / TRUE / IT DEPENDS stamp | word, sub, tone, cues stamp |
| stat | number counts up to a value, label + source | value, decimals, prefix, suffix, label, source, cues card/land |
| compare | labelled bars growing on cues | head, rows [[label, value, shown, cue, tone]] |
| steps | mechanism chain (3 across, 4-5 stacked) | steps [[text, cue]] |
| paper | real paper screenshot + highlighter | image, hl [x, y, w, h], tone |
| bigword | kinetic type lines | lines [[text, size, tone, cue]], y |
| side | right-side stack for a face that sits left | head, rows [[text, cue, mode plus/x/strike]], final {title, sub} |
| split | Ink plate with a face window (Resolve moves his face into it) | head, rows, final, hard_in/hard_out, full |
| wall | muted video wall of real clips with name chips | tiles, cols, tile, gap |
| name | name tag for a clip without one burned in | name, role, x, y |
Any type + `"full": true` = opaque full-frame scene that slides in like a cut (bg ink|paper).

## 16:9 templates
| type | what it is | key fields |
|---|---|---|
| rsplit | right-hand Ink plate (x 1100-1920); Resolve slides him left (zones.json "side") | blocks, final, hard_in, hard_out, top |
| fblocks | the same blocks as a full-frame centred column (use `"full": true`) | blocks, cw, centre, final |
| chain | full-frame mechanism: nodes left to right, fan chips under, a closing line | head, nodes [[text, cue]], fan [[text, cue]], close [text, cue], lastRed, nw, ny |
| compare2 | full-frame two columns (e.g. MONTH 0 / MONTH 6) | cols [{head, cue, rows [[text, cue]]}], mid [text, cue] |
| cta169 | Paper pill button + nudging arrow, steps on an Ink strip | text, y, steps [[text, cue]], cues btn |
| name169 | name tag bottom-left for a client clip | name, role |
| still | Higgsfield/z_image still filling the frame with a slow push (rides V2, under the captions) | image, zoom, dx, dy |

### Blocks (rsplit, fblocks)
| k | renders | fields |
|---|---|---|
| eyebrow | red rule + spaced caps label; stays when a `final` swaps in | text, cue (optional: appears on its word, not at the start) |
| big | large number/text, or `from` -> `to` with a drawn red arrow | text or from/to, cue, cue2 (to lands on its own word), size, tone |
| sub | secondary line | text, cue |
| row | divider + mark chip + text | text, cue, mark check/x/plus/up/down/upgood/dot |
| delta | label left, `from -> to unit` right, green chip for improved | label, from, to, unit, cue, cue2, mark down/upgood |
| chips | wrapping outlined chips, each on its word | items [[text, cue]] |
| photos | real photos side by side, labels under (dates) | h, items [{img, label, cue}] |
| quote | Paper card, red opening mark, the client's words, attribution with date and channel | text, attr, cue |
| gap | 24 px space | |
| source | citation line at the foot of the plate (use `\r` for two lines) | text |
`final` (rsplit): `{title, sub}` swaps the blocks for a Paper title card at `cues.final` (use `\r` to break a long title
onto two lines), or `{photo, photo_h, label, quote, attr}` for a photo with a quote under it (the eyebrow hides; put the
name in the label). Arrows, ticks and crosses are drawn shapes, never glyphs, so no font can drop them.

## Rules that keep it calm
- A graphic exists only where a point needs showing. Nothing under 2.5 s (gen_ae warns). Join back-to-back cards hard.
- The first plate in a 16:9 hook comes after ~4-5 s of face.
- Captions drop out while any graphic is up; don't fight for the same space.
- Every number on a card names its source (a study: author, journal, year; a client: the record and date range).
- Values reveal on the words that say them (the "before" on "were all over the place", the "after" on "we fixed").

## Testing a new layout
Render a few ids first (`python3 gen_ae.py g02 g04`), then composite each over a real A-roll frame
(`ffmpeg -i frame.png -ss T -i graphics/g02.mov -filter_complex overlay`) and look at it: text overflowing the plate, a
title breaking onto a lone word, a heading appearing before its rows, a photo covering a heading were all caught this way.
After a structural change in Resolve, pixel-sample a short test render: "Complete" is not proof a layer is in the picture.

## Sound for graphics
`sfx_rules.py` places sound from G automatically (whoosh on a plate or scene entering unless it's a hard join, a quiet pop per
landing row/number/chip, a whoosh on a final swap, a pop on a CTA button, a soft whoosh under name tags). Add one-offs with
`job.EXTRA_HITS`.
