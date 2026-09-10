#!/usr/bin/env python3
"""Stage 2 — mechanical edit analysis.

Produces edits.json: every cut that can be decided without judgement.

Model
-----
A filler ("um") or a stutter ("the the") is not cut on its own. It is
reclassified as NON-SPEECH and folded into the silence map, and then a single
capping pass shortens every resulting pause to --max-gap. That way "…that,
<pause> uh <pause> muscle…" collapses to "…that, <0.2s> muscle…" in one cut
instead of leaving the dead air behind on either side of the removed word.

Safety rules, in force everywhere:

  * A cut boundary must land inside REAL detected silence — never inside a
    filler and never inside a word. Padding at each end of a cut is limited to
    the real silence actually available on that side, so a short pause yields a
    shorter cut rather than a boundary that slices into audible speech.
  * A filler or stutter is only removable when real silence borders it on both
    sides. Otherwise it is refused and logged, and the word survives.
  * A word protects the audio under it from being cut — but only where the word
    actually has energy. Whisper often stretches a word across the pause that
    follows it, and protecting that verbatim would make real dead air uncuttable.

    lf_analyze.py WORKDIR [--max-gap 0.2] [--no-fillers] [--no-stutters]
"""

from __future__ import annotations

import argparse
import bisect
import json
import re
import wave
from pathlib import Path

import numpy as np

from lf_common import (
    Interval, Settings, die, drop_short, hhmmss, intersect_intervals, load_profile,
    log, merge_intervals, read_json, subtract_intervals, total_duration, write_json,
)

# ---- tunables -------------------------------------------------------------
FRAME_MS = 10.0          # RMS envelope hop
MIN_SILENCE = 0.06       # shorter dips are not treated as silence
WORD_PAD = 0.04          # words are protected by 40 ms on each side
SNAP_WINDOW = 0.30       # a cut boundary may move this far to reach silence
SILENCE_ERODE = 0.02     # cut boundaries stay this far inside a silence region
MIN_REMOVAL = 0.03       # removals shorter than this are not worth a cut
MIN_SIDE_SILENCE = 0.05  # real silence needed on each side of a removable word
FLOOR_OFFSET_DB = 11.0   # speech gate sits this far above the measured noise floor
EDGE_TOL = 0.02          # treated as "touching" the start/end of the recording

DEFAULT_FILLERS = [
    "um", "uh", "umm", "uhh", "uhm", "erm", "er", "ah", "eh", "hmm", "mm", "mmm",
    "you know", "i mean",
]

# Production and equipment chatter. A lecture recording always contains some:
# the speaker talking to the room about the camera, the microphone, the battery.
# It is never lecture content, and leaving it in makes a clip feel like
# somebody's screen recording rather than a lesson.
#
# Matched against a whole sentence, with the whole sentence removed. The
# patterns are deliberately narrow — a bare "charge" or "wire" would fire on
# real teaching ("charged particles", "wired to the brain"), so each one needs
# equipment context around it.
DEFAULT_ASIDES = [
    r"\bauto ?focus\b",
    r"\bwebcam\b",
    r"\bcamera\b",
    r"\bmicrophone\b",
    r"\bmic (is|was|on|off|check)\b",
    r"\bbattery\b",
    r"\bon charge\b|\bcharging\b|\bcharger\b",
    r"\busb\b",
    r"\btripod\b",
    r"\b(screen|scree?n) ?shar\w*\b|\bshare my screen\b|\bmy screen\b",
    r"\bcan (you|everyone|anyone|somebody) hear (me|my voice)\b",
    r"\bcan (you|everyone|anyone) see (my|the) (screen|board|slide)\w*\b",
    r"\bis (this|that|it) (visible|audible)\b",
    r"\b(am|are) (i|we) (audible|recording)\b",
    r"\brecording (this|started|is on|has started)\b",
    r"\bzoom (link|call|window)\b|\bgoogle meet\b",
]

_PUNCT = re.compile(r"[^\w']+", re.UNICODE)


def norm_token(word: str) -> str:
    return _PUNCT.sub("", word.strip().lower())


# --------------------------------------------------------------------------
# Silence detection
# --------------------------------------------------------------------------

def rms_envelope(wav_path: Path) -> tuple[np.ndarray, float, int]:
    """dBFS RMS envelope at FRAME_MS resolution. Reads in chunks so a 90-minute
    lecture never lands in memory all at once."""
    with wave.open(str(wav_path), "rb") as wf:
        if wf.getsampwidth() != 2 or wf.getnchannels() != 1:
            die(f"{wav_path.name} must be 16-bit mono (stage 0 writes it that way)")
        rate = wf.getframerate()
        total = wf.getnframes()
        hop = max(1, int(rate * FRAME_MS / 1000.0))
        chunk_frames = hop * 6000  # ~60 s at 16 kHz

        blocks: list[np.ndarray] = []
        carry = np.zeros(0, dtype=np.float32)
        while True:
            raw = wf.readframes(chunk_frames)
            if not raw:
                break
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            samples = np.concatenate([carry, samples]) if carry.size else samples
            usable = (samples.size // hop) * hop
            carry = samples[usable:].copy()
            if usable:
                frames = samples[:usable].reshape(-1, hop)
                blocks.append(np.sqrt(np.mean(frames * frames, axis=1)))
        if carry.size:
            blocks.append(np.array([float(np.sqrt(np.mean(carry * carry)))], dtype=np.float32))

    env = np.concatenate(blocks) if blocks else np.zeros(0, dtype=np.float32)
    db = 20.0 * np.log10(np.maximum(env, 1e-7))
    return db, total / float(rate), rate


def silence_from_envelope(db: np.ndarray, threshold_db: float) -> list[Interval]:
    hop_s = FRAME_MS / 1000.0
    quiet = db < threshold_db
    intervals: list[Interval] = []
    start: int | None = None
    for i, q in enumerate(quiet):
        if q and start is None:
            start = i
        elif not q and start is not None:
            intervals.append((start * hop_s, i * hop_s))
            start = None
    if start is not None:
        intervals.append((start * hop_s, len(quiet) * hop_s))
    return drop_short(intervals, MIN_SILENCE)


def protected_intervals(db: np.ndarray, threshold_db: float, transcript: dict,
                        pad: float = WORD_PAD) -> list[Interval]:
    """The stretches that must never be treated as silence, because a word lives
    there.

    A word is trimmed to the part of its span where energy is actually present
    before being protected. Whisper regularly stretches a short word across the
    pause that follows it — 'When' reported as 28.02-29.08 when the speaker said
    it in a fifth of that and then paused — and protecting the reported span
    verbatim would hand that dead air immunity from every cut. A word with no
    energy anywhere in its span is protected whole: there the gate is the thing
    more likely to be wrong.
    """
    hop = FRAME_MS / 1000.0
    n = db.size
    out: list[Interval] = []
    for seg in transcript["segments"]:
        for w in seg["words"]:
            i0 = max(0, int(w["start"] / hop))
            i1 = min(n, int(-(-w["end"] // hop)))  # ceil
            if i1 <= i0:
                continue
            loud = np.nonzero(db[i0:i1] >= threshold_db)[0]
            if loud.size:
                a = (i0 + int(loud[0])) * hop
                b = (i0 + int(loud[-1]) + 1) * hop
            else:
                a, b = float(w["start"]), float(w["end"])
            out.append((max(0.0, a - pad), b + pad))
    return merge_intervals(out)


def choose_gate(db: np.ndarray, floor_db: float) -> tuple[float, str]:
    """Where to put the speech/silence threshold, in dBFS.

    Loudness in a lecture is bimodal — a silence cluster and a speech cluster
    with a valley between them — so the threshold belongs in that valley. Otsu's
    method finds it by picking the split that minimises variance within the two
    clusters.

    A fixed offset above the noise floor cannot do this. On a recording whose
    silence is near-digital (Meet and Zoom both gate hard), floor + 11 dB lands
    at about -75 dBFS, still inside the silence cluster, and several minutes of
    real pause never register as pause at all.

    Falls back to the fixed offset when the histogram is not clearly bimodal.
    """
    lo, hi = float(np.percentile(db, 1)), float(np.percentile(db, 99))
    fallback = min(floor_db + FLOOR_OFFSET_DB, -28.0)
    if hi - lo < 12.0:
        return fallback, "fixed offset (levels too uniform to split)"

    counts, edges = np.histogram(np.clip(db, lo, hi), bins=96)
    centres = (edges[:-1] + edges[1:]) / 2
    total = counts.sum()
    if total == 0:
        return fallback, "fixed offset"

    w0 = np.cumsum(counts)
    w1 = total - w0
    csum = np.cumsum(counts * centres)
    valid = (w0 > 0) & (w1 > 0)
    if not valid.any():
        return fallback, "fixed offset"
    mean0 = np.where(valid, csum / np.maximum(w0, 1), 0.0)
    mean1 = np.where(valid, (csum[-1] - csum) / np.maximum(w1, 1), 0.0)
    between = w0 * w1 * (mean0 - mean1) ** 2
    between[~valid] = -1.0
    gate = float(centres[int(np.argmax(between))])

    # Never let the split fall on top of the noise floor or up among real speech.
    gate = min(max(gate, floor_db + 6.0), -25.0)
    return gate, "otsu valley"


def build_silence_map(wav: Path, transcript: dict, duration: float
                      ) -> tuple[list[Interval], float, float]:
    db, wav_duration, _ = rms_envelope(wav)
    if db.size == 0:
        die("analysis.wav is empty")

    floor_db = float(np.percentile(db, 10))
    threshold_db, how = choose_gate(db, floor_db)
    log(f"noise floor {floor_db:.1f} dBFS, speech gate {threshold_db:.1f} dBFS ({how})")

    raw = silence_from_envelope(db, threshold_db)
    silence = subtract_intervals(raw, protected_intervals(db, threshold_db, transcript))
    silence = drop_short(merge_intervals(silence), MIN_SILENCE)
    return intersect_intervals(silence, [(0.0, min(duration, wav_duration))]), floor_db, threshold_db


# --------------------------------------------------------------------------
# Silence index — "how much real silence borders this instant?"
# --------------------------------------------------------------------------

class SilenceIndex:
    def __init__(self, silence: list[Interval]):
        self.iv = merge_intervals(silence)
        self.starts = [a for a, _ in self.iv]

    def containing(self, t: float, *, tol: float = 1e-9) -> Interval | None:
        i = bisect.bisect_right(self.starts, t + tol) - 1
        if i < 0:
            return None
        a, b = self.iv[i]
        return (a, b) if (a - tol) <= t <= (b + tol) else None

    def run_after(self, t: float) -> float:
        """Length of contiguous silence starting at t (0 if t is not silent)."""
        iv = self.containing(t)
        return max(0.0, iv[1] - t) if iv else 0.0

    def run_before(self, t: float) -> float:
        """Length of contiguous silence ending at t (0 if t is not silent)."""
        iv = self.containing(t - 1e-6)
        return max(0.0, t - iv[0]) if iv else 0.0


class Snapper:
    """Answers: may a cut boundary live here? Used for LLM-proposed cuts, whose
    timecodes are approximate and must be pulled onto a safe silence."""

    def __init__(self, silence: list[Interval]):
        self.silence = merge_intervals(silence)
        self.safe = [(a + SILENCE_ERODE, b - SILENCE_ERODE)
                     for a, b in self.silence if (b - a) > 2 * SILENCE_ERODE]
        self._starts = [a for a, _ in self.safe]

    def _containing(self, t: float) -> Interval | None:
        i = bisect.bisect_right(self._starts, t) - 1
        if i < 0:
            return None
        a, b = self.safe[i]
        return (a, b) if a <= t <= b else None

    def snap(self, t: float) -> float | None:
        if self._containing(t) is not None:
            return t
        best: float | None = None
        best_dist = SNAP_WINDOW + 1.0
        for a, b in self.safe:
            cand = min(max(t, a), b)
            dist = abs(cand - t)
            if dist < best_dist:
                best, best_dist = cand, dist
            if a - t > best_dist:
                break
        return best if best_dist <= SNAP_WINDOW else None

    def snap_removal(self, start: float, end: float, reason: str,
                     refused: list[dict]) -> dict | None:
        a, b = self.snap(start), self.snap(end)
        if a is None or b is None:
            refused.append({"start": round(start, 3), "end": round(end, 3),
                            "reason": reason,
                            "refused": "no silence within snap window"})
            return None
        if b - a < MIN_REMOVAL:
            return None
        return {"start": round(a, 3), "end": round(b, 3), "reason": reason}


# --------------------------------------------------------------------------
# Removable words: fillers and stutters
# --------------------------------------------------------------------------

def flat_words(transcript: dict) -> list[dict]:
    words: list[dict] = []
    for seg in transcript["segments"]:
        for w in seg["words"]:
            words.append({"start": float(w["start"]), "end": float(w["end"]),
                          "raw": w["word"], "tok": norm_token(w["word"])})
    words.sort(key=lambda w: w["start"])
    return words


def _bounded_by_silence(start: float, end: float, prev_end: float, next_start: float,
                        index: SilenceIndex) -> tuple[float, float] | None:
    """Widen a removable word out to the pauses that surround it, and return the
    whole [pause + word + pause] span. None means one side has no usable pause,
    in which case the word must be kept.

    The search is anchored on the neighbouring real words rather than on the
    filler's own timestamps: whisper regularly reports a filler as zero-length
    and slightly misplaced, so its own bounds cannot be trusted to touch the
    silence on either side.
    """
    tol = 0.03
    lead = None
    for a, b in index.iv:
        if a >= prev_end - tol and b <= start + tol:
            lead = (a, b)          # keep the last one before the word
        elif a > start:
            break
    trail = None
    for a, b in index.iv:
        if a >= end - tol and b <= next_start + tol:
            trail = (a, b)         # first one after the word
            break

    if lead is None or trail is None:
        return None
    if (lead[1] - lead[0]) < MIN_SIDE_SILENCE or (trail[1] - trail[0]) < MIN_SIDE_SILENCE:
        return None
    return (lead[0], trail[1])


def sentences_from(words: list[dict]) -> list[list[dict]]:
    """Group words into sentences on terminal punctuation."""
    out: list[list[dict]] = []
    cur: list[dict] = []
    for w in words:
        cur.append(w)
        if w["raw"].strip().endswith((".", "!", "?")):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


ASIDE_ABSORB_MAX = 3       # trailing fragments an aside may swallow
ASIDE_ABSORB_WORDS = 8     # each must be at most this long
ASIDE_ABSORB_GAP = 2.0     # and follow within this many seconds
ASIDE_ABSORB_SECONDS = 8.0 # total absorbed, as a backstop


def find_asides(words: list[dict], patterns: list, snapper: "Snapper",
                refused: list[dict]) -> list[dict]:
    """Whole sentences of production chatter, removed entirely.

    Unlike a pause, an aside is not shortened — there is no length of "forget
    the autofocus, it's lecture time" worth keeping. The whole sentence goes,
    and only if both its ends snap onto real silence, so the sentences either
    side of it survive intact.

    An aside rarely stops at one sentence. "…turn off autofocus." is followed by
    "Forget that man." and "It's lecture time now.", neither of which mentions
    equipment and neither of which can be matched on its own. So a match
    absorbs the short fragments that trail it, stopping at the first sentence
    long enough to be real teaching again.

    Absorption is forward-only and bounded. Backwards would be dangerous: the
    sentence *before* an aside is usually the teaching the speaker broke off
    from, and it is often short ("that is what everyone recommends").
    """
    out: list[dict] = []
    sentences = sentences_from(words)
    i = 0
    while i < len(sentences):
        sent = sentences[i]
        text = " ".join(w["tok"] for w in sent)
        if next((p for p in patterns if p.search(text)), None) is None:
            i += 1
            continue

        # Collect the fragments this aside could absorb, longest reach first.
        trailing: list[list[dict]] = []
        cursor = sent
        j = i + 1
        while j < len(sentences) and len(trailing) < ASIDE_ABSORB_MAX:
            nxt = sentences[j]
            if (len(nxt) > ASIDE_ABSORB_WORDS
                    or nxt[0]["start"] - cursor[-1]["end"] > ASIDE_ABSORB_GAP
                    or nxt[-1]["end"] - sent[-1]["end"] > ASIDE_ABSORB_SECONDS):
                break
            trailing.append(nxt)
            cursor = nxt
            j += 1

        # Try the widest span, then give absorbed fragments back one at a time.
        # A wider span can reach past the last usable silence, and losing the
        # whole cut over that would leave the chatter in — better to remove the
        # equipment sentence alone than nothing at all.
        cut = None
        used = 0
        for k in range(len(trailing), -1, -1):
            span = list(sent)
            for frag in trailing[:k]:
                span += frag
            snippet = " ".join(w["raw"].strip() for w in span)[:80]
            attempt = snapper.snap_removal(span[0]["start"], span[-1]["end"],
                                           f"aside:{snippet}", [])
            if attempt:
                cut, used = attempt, k
                break

        if cut:
            cut["absorbed"] = [" ".join(w["raw"].strip() for w in f)
                               for f in trailing[:used]]
            out.append(cut)
            i = i + 1 + used
        else:
            snippet = " ".join(w["raw"].strip() for w in sent)[:80]
            refused.append({"start": round(sent[0]["start"], 3),
                            "end": round(sent[-1]["end"], 3),
                            "reason": f"aside:{snippet}",
                            "refused": "no silence to cut in — chatter kept"})
            i += 1
    return out


def find_removable_words(words: list[dict], fillers: set[str], index: SilenceIndex,
                         *, do_fillers: bool, do_stutters: bool,
                         refused: list[dict]) -> list[dict]:
    phrases = {f for f in fillers if " " in f}
    singles = {f for f in fillers if " " not in f}
    max_phrase = max((len(f.split()) for f in phrases), default=1)

    spans: list[dict] = []
    consumed = set()

    if do_fillers:
        i = 0
        while i < len(words):
            hit = None
            for n in range(max_phrase, 1, -1):
                if i + n <= len(words):
                    joined = " ".join(w["tok"] for w in words[i:i + n])
                    if joined in phrases:
                        hit = (i, i + n)
                        break
            if hit is None and words[i]["tok"] in singles:
                hit = (i, i + 1)
            if hit is None:
                i += 1
                continue
            lo, hi = hit
            label = " ".join(w["tok"] for w in words[lo:hi])
            prev_end = words[lo - 1]["end"] if lo > 0 else 0.0
            next_start = words[hi]["start"] if hi < len(words) else float("inf")
            widened = _bounded_by_silence(words[lo]["start"], words[hi - 1]["end"],
                                          prev_end, next_start, index)
            if widened is None:
                refused.append({"start": round(words[lo]["start"], 3),
                                "end": round(words[hi - 1]["end"], 3),
                                "reason": f"filler:{label}",
                                "refused": "no silence on both sides — word kept"})
            else:
                spans.append({"start": widened[0], "end": widened[1],
                              "kind": "filler", "label": label})
                consumed.update(range(lo, hi))
            i = hi

    if do_stutters:
        for i in range(len(words) - 1):
            if i in consumed or (i + 1) in consumed:
                continue
            a, b = words[i], words[i + 1]
            if not a["tok"] or a["tok"] != b["tok"]:
                continue
            if (a["end"] - a["start"]) > 0.5 or (b["start"] - a["end"]) > 0.4:
                continue
            prev_end = words[i - 1]["end"] if i > 0 else 0.0
            widened = _bounded_by_silence(a["start"], a["end"], prev_end, b["start"], index)
            if widened is None:
                refused.append({"start": round(a["start"], 3), "end": round(a["end"], 3),
                                "reason": f"stutter:{a['tok']}",
                                "refused": "no silence on both sides — word kept"})
            else:
                spans.append({"start": widened[0], "end": widened[1],
                              "kind": "stutter", "label": a["tok"]})
                consumed.add(i)

    spans.sort(key=lambda s: s["start"])
    return spans


# --------------------------------------------------------------------------
# The single capping pass
# --------------------------------------------------------------------------

class PausePolicy:
    """How long each individual pause is allowed to be.

    A single cap for every pause is the wrong instrument. A hesitation in the
    middle of a sentence and the beat after a rhetorical question are both
    "silence", and cutting them to the same length flattens the delivery: the
    hesitations stay noticeable and the beats that carry meaning disappear.

    So the budget is set per pause, from three kinds of evidence:

      text    what the speaker had just finished saying. A pause after "?" is a
              beat the viewer is meant to think in; a pause mid-clause is a
              stumble and gets cut hardest of all.
      audio   how loudly the line before the pause was delivered. Emphatic
              delivery earns the pause that follows it.
      visual  whether anything is happening on screen. A pause while the
              speaker is writing on the board is not dead air at all — the
              viewer is reading — and cutting it to a fifth of a second makes
              board content appear from nowhere.
    """

    def __init__(self, *, gaps: dict, words: list[dict], db: np.ndarray,
                 visual: dict | None, speech_db_p75: float):
        self.gaps = gaps
        self.db = db
        self.speech_db_p75 = speech_db_p75
        self.word_ends = [w["end"] for w in words]
        self.words = words
        self.visual = visual
        if visual:
            self.v_fps = float(visual["fps"])
            self.motion = np.asarray(visual["motion"], dtype=np.float32)
            self.ink_delta = np.asarray(visual["ink_delta"], dtype=np.float32)
            self.motion_busy = float(visual["motion_percentiles"]["75"])
            self.ink_busy = max(float(visual["ink_delta_percentiles"]["90"]), 1e-6)

    # -- evidence -----------------------------------------------------------

    def _preceding_word(self, t: float) -> dict | None:
        i = bisect.bisect_right(self.word_ends, t + 1e-6) - 1
        return self.words[i] if i >= 0 else None

    def _pre_loudness(self, t: float, window: float = 1.2) -> float:
        hop = FRAME_MS / 1000.0
        i0, i1 = max(0, int((t - window) / hop)), max(1, int(t / hop))
        seg = self.db[i0:i1]
        return float(np.percentile(seg, 75)) if seg.size else -99.0

    def _visual_activity(self, a: float, b: float) -> tuple[float, float]:
        if not self.visual:
            return 0.0, 0.0
        i0 = max(0, int(a * self.v_fps))
        i1 = min(len(self.motion), max(i0 + 1, int(b * self.v_fps) + 1))
        return (float(self.motion[i0:i1].max()) if i1 > i0 else 0.0,
                float(self.ink_delta[i0:i1].max()) if i1 > i0 else 0.0)

    # -- the decision -------------------------------------------------------

    def cap_for(self, a: float, b: float) -> tuple[float, str]:
        g = self.gaps
        motion, ink = self._visual_activity(a, b)

        # Writing on the board outranks everything: that pause is the lesson.
        if self.visual and ink >= self.ink_busy:
            return g["writing"], "writing"
        if self.visual and motion >= self.motion_busy:
            cap, why = g["motion"], "on-screen motion"
        else:
            cap, why = g["hesitation"], "mid-phrase"
            word = self._preceding_word(a)
            tail = (word["raw"].strip()[-1:] if word else "")
            if tail in ".!":
                cap, why = g["sentence"], "sentence end"
            elif tail == "?":
                cap, why = g["question"], "after a question"
            elif tail in ",;:—-":
                cap, why = g["clause"], "clause break"

        # An emphatic line earns the beat that follows it.
        if self._pre_loudness(a) >= self.speech_db_p75 and cap < g["emphasis"]:
            cap, why = g["emphasis"], why + " + emphatic delivery"
        return cap, why


def build_cuts(silence: list[Interval], removable: list[dict], *, policy: PausePolicy,
               duration: float) -> list[dict]:
    """Shorten every pause — including pauses widened by a removed filler — to
    the budget the policy allows it. Padding on each side is capped by the real
    silence available there, so a cut boundary can never land inside audible
    speech."""
    index = SilenceIndex(silence)
    regions = merge_intervals(
        [(a, b) for a, b in silence] + [(s["start"], s["end"]) for s in removable]
    )
    cuts: list[dict] = []

    for a, b in regions:
        cap, why = policy.cap_for(a, b)
        if (b - a) <= cap:
            continue
        half = cap / 2.0
        at_head = a <= EDGE_TOL
        at_tail = b >= duration - EDGE_TOL
        # Only pad into silence that actually exists at this end of the region.
        pad_l = 0.0 if at_head else min(half, max(0.0, index.run_after(a) - SILENCE_ERODE))
        pad_r = 0.0 if at_tail else min(half, max(0.0, index.run_before(b) - SILENCE_ERODE))

        ra, rb = a + pad_l, b - pad_r
        if rb - ra < MIN_REMOVAL:
            continue

        words_here = [s for s in removable if s["start"] < b and s["end"] > a]
        if words_here:
            kinds = sorted({s["kind"] for s in words_here})
            labels = ",".join(s["label"] for s in words_here)
            reason = f"{'+'.join(kinds)}:{labels}"
        else:
            reason = "silence"
        cuts.append({"start": round(ra, 3), "end": round(rb, 3), "reason": reason,
                     "policy": why, "cap": round(cap, 2),
                     "kept_gap": round((ra - a) + (b - rb), 3)})

    return cuts


# --------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="lecture-forge stage 2: edit analysis")
    ap.add_argument("workdir")
    ap.add_argument("--max-gap", type=float, default=0.2,
                    help="baseline pause budget; the adaptive policy scales the "
                         "other budgets around it (default 0.2 s)")
    ap.add_argument("--gap-hesitation", type=float, default=None,
                    help="mid-phrase stumble (default 0.15)")
    ap.add_argument("--gap-clause", type=float, default=None,
                    help="after a comma or colon (default 0.30)")
    ap.add_argument("--gap-sentence", type=float, default=None,
                    help="after a full stop (default 0.55)")
    ap.add_argument("--gap-question", type=float, default=None,
                    help="after a question - a beat to think in (default 0.85)")
    ap.add_argument("--gap-emphasis", type=float, default=None,
                    help="floor after an emphatic line (default 0.70)")
    ap.add_argument("--gap-motion", type=float, default=None,
                    help="while something moves on screen (default 1.20)")
    ap.add_argument("--gap-writing", type=float, default=None,
                    help="while writing on the board - the viewer is reading "
                         "(default 6.00)")
    ap.add_argument("--profile", default=None,
                    help="camera/room profile, for extra aside_patterns")
    ap.add_argument("--policy", choices=["adaptive", "fixed"], default="adaptive",
                    help="adaptive uses text, loudness and on-screen activity; "
                         "fixed applies --max-gap to every pause")
    ap.add_argument("--no-fillers", action="store_true")
    ap.add_argument("--no-stutters", action="store_true")
    ap.add_argument("--fillers", default=None,
                    help="comma-separated replacement filler list")
    ap.add_argument("--no-asides", action="store_true",
                    help="keep production/equipment chatter (camera, mic, battery)")
    ap.add_argument("--aside-pattern", action="append", default=[],
                    help="extra regex for an off-topic sentence; repeatable")
    args = ap.parse_args()

    wd = Path(args.workdir).expanduser().resolve()
    media = read_json(wd / "media.json")
    transcript = read_json(wd / "transcript.json")
    wav = wd / "analysis.wav"
    if not wav.exists():
        die(f"missing {wav}")

    settings = Settings(load_profile(args.profile))
    duration = float(media["duration"])
    silence, floor_db, gate_db = build_silence_map(wav, transcript, duration)
    speech = subtract_intervals([(0.0, duration)], silence)
    index = SilenceIndex(silence)

    fillers = set(settings.merged_list("fillers", DEFAULT_FILLERS))
    if args.fillers:
        fillers = {f.strip().lower() for f in args.fillers.split(",") if f.strip()}

    refused: list[dict] = []
    words = flat_words(transcript)
    removable = find_removable_words(
        words, fillers, index,
        do_fillers=not args.no_fillers, do_stutters=not args.no_stutters,
        refused=refused,
    )
    db, _, _ = rms_envelope(wav)
    speech_db_p75 = float(np.percentile(db[db >= gate_db], 75)) if (db >= gate_db).any() else 0.0

    visual = None
    vpath = wd / "visual.json"
    if args.policy == "adaptive" and vpath.exists():
        visual = read_json(vpath)
        log(f"using on-screen activity from visual.json ({visual['samples']} samples)")
    elif args.policy == "adaptive":
        log("no visual.json — run lf_visual.py for board-aware pauses; "
            "falling back to text and loudness only")

    if args.policy == "fixed":
        gaps = {k: args.max_gap for k in
                ("hesitation", "clause", "sentence", "question", "emphasis",
                 "motion", "writing")}
        visual = None
    else:
        gaps = {
            "hesitation": settings.get("gaps.hesitation", 0.15, args.gap_hesitation),
            "clause": settings.get("gaps.clause", 0.30, args.gap_clause),
            "sentence": settings.get("gaps.sentence", 0.55, args.gap_sentence),
            "question": settings.get("gaps.question", 0.85, args.gap_question),
            "emphasis": settings.get("gaps.emphasis", 0.70, args.gap_emphasis),
            "motion": settings.get("gaps.motion", 1.20, args.gap_motion),
            "writing": settings.get("gaps.writing", 6.00, args.gap_writing),
        }

    policy = PausePolicy(gaps=gaps, words=words, db=db, visual=visual,
                         speech_db_p75=speech_db_p75)
    cuts = build_cuts(silence, removable, policy=policy, duration=duration)

    aside_cuts: list[dict] = []
    if not args.no_asides:
        snapper = Snapper(silence)
        patterns = [re.compile(p, re.I) for p in
                    settings.merged_list("aside_patterns", DEFAULT_ASIDES)
                    + list(args.aside_pattern)]
        aside_cuts = find_asides(words, patterns, snapper, refused)
        for c in aside_cuts:
            log(f"aside cut {hhmmss(c['start'], ms=True)}-{hhmmss(c['end'], ms=True)}  "
                f"{c['reason'][6:]}")
        cuts = cuts + [dict(c, policy="off-topic aside", cap=0.0, kept_gap=0.0)
                       for c in aside_cuts]
        cuts.sort(key=lambda c: c["start"])

    by_kind: dict[str, float] = {"silence": 0.0, "filler": 0.0, "stutter": 0.0}
    for c in cuts:
        key = "silence" if c["reason"] == "silence" else c["reason"].split(":")[0]
        for part in key.split("+"):
            by_kind[part] = by_kind.get(part, 0.0) + (c["end"] - c["start"]) / len(key.split("+"))

    policy_mix: dict[str, float] = {}
    for c in cuts:
        policy_mix[c.get("policy", "?")] = policy_mix.get(c.get("policy", "?"), 0.0) + (
            c["end"] - c["start"])

    payload = {
        "max_gap": args.max_gap,
        "policy": args.policy,
        "settings_from": settings.report(),
        "gaps": gaps,
        "policy_seconds_removed": {k: round(v, 1) for k, v in
                                   sorted(policy_mix.items(), key=lambda kv: -kv[1])},
        "noise_floor_db": round(floor_db, 2),
        "speech_gate_db": round(gate_db, 2),
        "source_duration": round(duration, 3),
        "speech_duration": round(total_duration(speech), 3),
        "silence_duration": round(total_duration(silence), 3),
        "silence_map": [[round(a, 3), round(b, 3)] for a, b in silence],
        "speech_map": [[round(a, 3), round(b, 3)] for a, b in speech],
        "aside_cuts": aside_cuts,
        "removable_words": [
            {"start": round(s["start"], 3), "end": round(s["end"], 3),
             "kind": s["kind"], "label": s["label"]} for s in removable
        ],
        "cuts": cuts,
        "refused": refused,
        "removable_total": round(total_duration([(c["start"], c["end"]) for c in cuts]), 3),
        "stats": {
            "cuts": len(cuts),
            "filler_words_removed": sum(1 for s in removable if s["kind"] == "filler"),
            "stutters_removed": sum(1 for s in removable if s["kind"] == "stutter"),
            "refused": len(refused),
            "asides_removed": len(aside_cuts),
            "seconds_asides": round(total_duration(
                [(c["start"], c["end"]) for c in aside_cuts]), 2),
            "seconds_by_kind": {k: round(v, 2) for k, v in by_kind.items()},
        },
    }
    write_json(wd / "edits.json", payload)

    s = payload["stats"]
    log(f"speech {hhmmss(payload['speech_duration'])} of {hhmmss(duration)}")
    log(f"{s['cuts']} cuts, {s['filler_words_removed']} fillers, "
        f"{s['stutters_removed']} stutters, {s['refused']} refused")
    log(f"settings — {settings.report()}")
    log(f"removable {payload['removable_total']}s -> "
        f"{hhmmss(duration - payload['removable_total'])} if the whole lecture is kept")
    print(json.dumps(s, indent=2))


if __name__ == "__main__":
    main()
