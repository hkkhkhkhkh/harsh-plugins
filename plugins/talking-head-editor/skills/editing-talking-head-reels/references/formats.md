# Formats

`new_job.py --format` copies the core pipeline plus the format's overlay (`pipeline/formats/<name>/`) and writes job.py.

## reel: 9:16 from a log camera (Sony FX30, S-Log3, 4K 50p)
- Timeline 1080x1920 at 25 fps from the 50p source; Resolve centre-crops the 16:9 frame (scaleToCrop).
- Colour: RCM, input `S-Gamut3/S-Log3` (no "Sony " prefix; read the gamut from the clip's `M01.XML` or grep the MP4 for
  `CaptureColorPrimaries`). Previews and face detection go through the camera's own s709 LUT (`job.LUT`).
- A 16:9 face in a 9:16 crop fills the top half (face box ~680 px, chin ~900-1030). Side cards sit on the hair there, so
  list graphics become split scenes: face in a 560 px window in the upper third, panel below, captions dropped while it's up.
  Cards elsewhere go on the side away from the face, top band y 170-500, CTA button between chin and captions.
- Finisher: `resolve_final.py` (core). Zoom plan: `zooms.py` (per-take push/punch rhythm, optional snaps on numbers).

## iphone: 9:16 phone selfie (HDR HLG)
- Convert first with Apple's own HDR-to-SDR (`swiftc -O tools/tosdr.swift -o tools/tosdr && tools/tosdr IN OUT`): ProRes 422 HQ,
  Rec.709, timing and audio sample-identical. That is exactly what Photos/QuickTime show. Resolve's HLG IDT + DRT came out
  washed and pink. Then IDT `Rec.709 Gamma 2.4`, neutral grade.
- iPhone video is VFR. If you crop or re-encode, force CFR at the source rate (`-fps_mode cfr -r 30000/1001`).
- The phone mic sits ~18 dB below a lav: every audio gate is relative, so nothing to change.
- Split layout: a 560 px square window at y 70-630 with the clip scaled so his FACE sits in the box centre; panel text y 640-1280.
- Finisher: `formats/iphone/resolve_final.py` (calm one-pivot breathe zoom, power + hero captions, graphics blocking).
  Scenes: `formats/iphone/ae_lib/scenes.py` + `lib.jsx` (split box, full panels, mineral, Rx pad, ladder, two-column,
  mechanism, phone mockup, price, CTA) with the worked example kept in place.
- Two related clips must not share content: a 27 s shared block made two ads "seem like the same video".

## vsl: 16:9 sales video / VSL / YouTube (the default for anything that sells from a landing page)
- Timeline 1920x1080, 25 fps from a 50p source. Captions y 880; Text+ size scales with frame WIDTH (`PX_PER_SIZE` 1244).
- **Layout for a centred speaker: the right-hand plate.** An Ink plate covers x 1100-1920 and slides in over 0.45 s (out over
  0.40 s); the A-roll slides him left at the same time, face to x 620 at 1.36x (lossless from a 4K source; at least 1.33x is
  needed so the frame still covers the canvas). Cards stack on the plate (eyebrow, big numbers, rows, deltas, photos, quotes).
  Back-to-back plates join hard: the plate and his position hold, only the content swaps.
- **Full-frame scenes** (opaque Ink) for lists that need room: "not for you if", a mechanism chain, the program timeline,
  month 0 vs month 6. They slide in like a cut.
- **First seconds = his face** (the hook); the first plate comes in after ~4-5 s.
- **Proof section**: each client line gets a card with that client's real data (photos side by side with dates, before -> after
  values with units, the source line) and, where it exists, the client's own video right after, cut on their words, with a
  name tag. See proof-and-claims.md.
- **CTA**: a Paper pill button with a nudging arrow over the chest (y ~800) and the steps on an Ink strip under it; a second
  CTA at the end. Captions drop out while it is up.
- **A-roll finish**: RCM S-Log3 -> DaVinci DRT + CDL (slope 1.03, offset +0.008, power 0.98, sat 1.06) and, inside each piece's
  Fusion comp after the zoom, ResolveFX Contrast Pop (0.10) and a soft Vignette (size 0.85, softness 0.9, transparency 0.65).
- **Music**: a restrained owned bed, extended to length with `music/build_bed.py`; the bed drops out for the pattern-interrupt
  line that opens the "real problem" section.
- **B-roll**: Higgsfield stills (z_image) with a slow push, 3.5-7 s each, for beats that need a picture (a tired desk worker for
  "the 3 pm crash", an anatomy render for "fat around your liver", lab tubes for "your blood report").
- Finisher: `formats/vsl16x9/resolve_final.py`; zooms: `formats/vsl16x9/zooms.py` (one pivot, PUNCH dict per take).
- Delivery: a 720p web encode for the landing page (`web_encode.py`, delivery.md).

## long-form course / talk (16:9, minutes long)
Use `vsl` and change in job.py / edl.py: pauses cut at 0.50 s (`MERGE`), phrase captions instead of per-word power captions
(thousands of Text+ over 9 minutes is slow and busy), music built but muted unless asked, graphics only if asked.
iPhone landscape sources: 29.97 fps needs the STRING "29.97" for the timeline and `SetClipProperty("FPS", "29.97")` on every
clip right after import, or Resolve drops a frame at every cut (a one-frame black flash at 141 cuts once shipped).

## Variants (N hooks x M CTAs)
When the creator records several hooks and CTAs for one body: keep ONE edl with a group label per span (h1, h2, b, c1...),
choose the variant from the job sub-folder name (v_h1c1), skip spans outside the variant but keep global take ids, render
graphics once in the root (ids carry their join state) and one Resolve timeline per variant, H.264 only. Before writing
spans, read the whole transcript tail for spoken edit notes; a later instruction wins over an earlier one, like takes.
