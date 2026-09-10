# Audio chain

The order is not arbitrary. Each stage assumes the previous one has run.

```
highpass=f=70
afftdn=nr=12:nf=-28:tn=1
loudnorm=I=-16:TP=-1.5:LRA=11:measured_*=...:linear=true
alimiter=limit=0.7943:level=false     # hard ceiling at -2 dBFS
aresample=async=1
```

## Why this order

**highpass first.** Room rumble, HVAC, desk bumps and handling noise live below
70 Hz and carry real energy. Removing them first means the denoiser and the
loudness meter are not reacting to sound nobody can hear on a phone speaker.

**Denoise before loudness.** `afftdn` with `tn=1` tracks the noise floor as it
changes through the recording. Measuring loudness before denoising would fold
the noise into the integrated measurement and normalize the clip too quietly.

`nr=12` is a deliberate 12 dB reduction rather than the maximum. Aggressive
spectral denoise gives speech a hollow, underwater ring that is far more
noticeable than the room tone it removed. Raise it only if the room is genuinely
bad, and listen to the result.

`--denoise rnn` swaps in `arnndn`, a recurrent-network speech denoiser. It is
better on steady broadband noise and worse on anything unusual, and it needs an
external `.rnnn` model file named in the profile as `rnnoise_model`.
`--denoise off` skips denoising entirely.

**loudnorm last, in two passes.** Pass one measures; pass two normalizes with
those measurements and `linear=true`, which applies one constant gain instead of
riding the level dynamically. Single-pass loudnorm is dynamic by necessity and
audibly pumps on speech.

## Measure on the cut audio, not the source

This is the part that is easy to get wrong. Integrated loudness is an average
over time, and it counts silence. Cutting several minutes of dead air out of a
lecture *raises* the integrated loudness of what remains, sometimes by more than
a decibel. Measure the source and you normalize the clip to the wrong target.

`lf_render.py` runs its measurement pass over the same `aselect` range list the
final render uses, with `-vn` so it costs seconds rather than minutes.

## Targets

−16 LUFS / −1.5 dBTP is the streaming-speech convention: YouTube normalizes to
about −14, podcasts to −16, and −16 with 1.5 dB of headroom survives both
without clipping after lossy encoding. `LRA=11` leaves normal speech dynamics
alone.

Verify a rendered clip with:

```
ffmpeg -i out.mp4 -af loudnorm=I=-16:TP=-1.5:print_format=json -f null -
```

`input_i` within ±0.7 LU of −16 and `input_tp` below −1.0 is on target.

## Why a limiter after loudnorm

loudnorm aims at a true-peak target but cannot guarantee it in `linear=true`
mode, and the AAC encode then overshoots by a couple of tenths more. In
practice a clip normalized to -1.5 dBTP measured -0.86 dBTP once encoded. The
limiter is the hard ceiling that makes the target real.

`level=false` is not optional. alimiter's auto-level is **on** by default and
gains the signal back up to the ceiling, which would undo the loudness
normalization immediately upstream of it.

## Clicks at joins

Cuts land inside detected silence, so joins are between two low-energy samples
and clicks are rare. If a particular recording does click — a very noisy room
where "silence" still has real amplitude — the cause is the noise floor, not the
cut. Raise the denoise or record better audio; adding crossfades would desync
video from audio, because every fade shortens the audio relative to the picture.
