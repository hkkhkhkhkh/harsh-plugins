# Feedback and approval — design

How lecture-forge gets better every time it gets something wrong, without
anyone editing Python and without each fix silently breaking an earlier one.

Two people, two roles:

- **Aniket** runs the pipeline, approves clips in the review sheet, and files
  feedback when the edit is wrong. He can *propose* tuning changes.
- **Harsh** approves or rejects changes. Only approval makes a change live.

## The problem this solves

The plugin currently encodes a lot of judgement as constants: how long a
mid-phrase pause may be, what counts as production chatter, how big a board
pause must be before it is protected. Every one of those numbers came from one
52-minute lecture. On lecture seven they will be wrong in some new way.

Three failure modes, in order of how much damage they do:

1. **It cut something good** — a hook, a punchline, a board explanation. Worst,
   because it is invisible: you cannot miss what is not there.
2. **It kept something bad** — chatter, a tangent, a false start.
3. **It picked the wrong clips** — missed a lesson, or shipped a dud.

The system has to make (1) visible, make all three reportable in seconds, and
turn repeated reports into a change that sticks.

---

## Part 1 — Make what was removed visible

**`removed.md`, written on every render.** Every cut, with the words it
removed and why:

```
| Out at | Source        | Len   | Why              | Words removed
| 01:12  | 00:14:03.220  | 3.4s  | off-topic aside  | "Okay my camera is on 8% battery, let me put this on charge"
| 02:48  | 00:16:41.100  | 0.9s  | mid-phrase       | (silence)
| 04:02  | 00:18:22.480  | 6.1s  | mistake cut      | "Sorry that's not right, let me say that again"
```

This is the highest-value part of the whole design and the cheapest to build —
`edits.json` already records `reason` and `policy` per cut, and the transcript
gives the words. Without it, "it chopped something important" is unfalsifiable
and nobody can review an edit except by watching the whole clip.

Silence-only rows collapse by default; `--verbose` shows all of them.

## Part 2 — Capture feedback with its cause attached

Feedback is worthless if it says "2:31 is bad" and nobody can tell what
decision produced 2:31. So every entry records the **provenance**: which rule
fired there, with what budget, on what evidence.

Two entry points:

**In the review sheet.** A `Notes` column. Anything written there is captured
at render time — the natural place to say "this clip should start earlier".

**After watching:** `/lecture-forge-feedback <clip> <timecode> "<what's wrong>"`

It resolves the output timecode back through the `TimeMap` to source time, then
looks up what happened there and stores:

```json
{ "when": "2026-09-18", "who": "aniket", "lecture": "...", "clip": 3,
  "out_time": 151.2, "source_time": 1043.6,
  "complaint": "cut off the punchline",
  "decision": { "rule": "mid-phrase", "cap": 0.15, "removed": 1.9,
                "visual": {"motion": 2.1, "ink_delta": 0.0004} },
  "context": "...transcript either side..." }
```

That `decision` block is what makes the entry actionable months later.

## Part 3 — Split feedback into two buckets

The two buckets have completely different risk profiles and must not share a
path.

**Tunables — data, reversible, no code review.**
Pause budgets, aside patterns, filler list, min/max clip length, board box,
punch zoom, denoise strength. A change here is a number in a JSON file.

**Rules — logic and prompts, needs judgement.**
The curator rubric, the aside absorption logic, the gate algorithm, anything in
Python. A change here is a diff.

`/lecture-forge-tune` reads accumulated feedback, groups it by cause, and
proposes changes into whichever bucket fits:

```
5 entries: "cut too tight mid-sentence"
   -> tunable: gap_hesitation 0.15 -> 0.22
   evidence: clips 3,4 (14 Sep), clip 2 (18 Sep)

3 entries: "kept talk about the projector"
   -> tunable: add aside pattern \bprojector\b

2 entries: "started after the question again"
   -> rule: curator rubric already says this; it is being ignored.
      Needs a prompt change, not a number. Escalated.
```

Note the third: the honest answer is sometimes "the rule exists and is not
being followed", which is a different fix from "the rule is wrong".

**Threshold: no change from a single report.** One bad clip is noise — a
speaker having an off day, one odd pause. Two independent reports of the same
cause, or one report Harsh explicitly marks `--now`, is the bar. This is the
main defence against the plugin thrashing.

## Part 4 — The enabling refactor: a config layer

Today every tunable is a Python constant or a CLI flag, so tuning means editing
code. That has to change first or none of the above works.

Precedence, narrowest wins:

```
CLI flag  >  room profile  >  ~/.lecture-forge/config.json  >  code defaults
```

`config.json` is the tuned layer; code defaults stay as the shipped fallback so
a bad config can always be removed rather than untangled. Profiles keep the
per-room things (board box, room-specific aside patterns) they already hold.

## Part 5 — Approval

A proposal is written to `pending.json` with its evidence and never applied
directly. Harsh runs `/lecture-forge-approve`, sees a diff and the feedback
behind it, and accepts or rejects each item:

```
gap_hesitation   0.15 -> 0.22     5 reports    [a]pprove [r]eject [s]kip
aside += "\bprojector\b"          3 reports    [a]pprove [r]eject [s]kip
```

Approved changes are applied to `config.json` and appended to `CHANGELOG.md`
with date, who proposed, evidence count, and the previous value — so any change
can be read and reverted later.

The role split is enforced by convention, not permissions: Aniket proposes,
Harsh approves. Both are recorded.

## Part 6 — Regression safety (the part that stops rot)

This is what keeps a feedback loop from making the tool worse over time. Every
tuning change fixes the lecture that prompted it; nothing so far stops it
breaking the lecture before.

**A golden set.** Each entry is a real source file, a timecode, and an assertion
that must keep holding:

```json
{ "source": "nutrition-mass-balance-2026-09-09.mp4", "assert": [
    {"kind": "removed",  "text": "turn off auto auto focus"},
    {"kind": "kept",     "at": 345.6, "why": "board writing, viewer is reading"},
    {"kind": "clip_opens_on", "clip": 2, "text": "my question for you guys"} ]}
```

`/lecture-forge-approve` runs these **before** applying anything, using
`lf_analyze` only — no rendering, so it is seconds not minutes. A proposal that
breaks a golden assertion is reported and blocked:

```
gap_hesitation 0.15 -> 0.40
  BLOCKED: golden 'nutrition-mass-balance' — the 8% battery aside now survives
```

Cases get added as bugs are found: today's lecture already supplies four good
ones. Keeping the source files means keeping a few large recordings around;
30-second excerpts around each assertion are enough and cheap to store.

---

## Build order

1. `removed.md` on every render — most value, least work, and it makes
   everything downstream reviewable.
2. Config layer + precedence. Nothing else works without it.
3. `/lecture-forge-feedback` with provenance lookup.
4. `/lecture-forge-tune` proposing into `pending.json`.
5. `/lecture-forge-approve` with diff, changelog, and roles.
6. Golden set + the pre-approval check. Seed it from today's four bugs.

Steps 1–2 are useful on their own even if the rest is never built: one makes
mistakes visible, the other makes them fixable without a developer.

## Files

```
~/.lecture-forge/
  config.json           active tunables
  pending.json          proposals awaiting approval
  feedback/*.jsonl      raw entries, append-only
  golden/*.json         regression cases
  CHANGELOG.md          what changed, when, why, previous value
```

## Routing: Aniket works on his own machine

Decided. That means anything that must reach Harsh cannot live only in
`~/.lecture-forge/` — it would be invisible to him. So the shared state lives
in the git repo and syncs by pull/push:

```
repo (shared, reviewed)              ~/.lecture-forge/ (local, per machine)
  config/defaults.json    tuned        config.json     local override
  config/golden/*.json    regression    profiles/*.json  this room's camera
  feedback/*.jsonl        reports       feedback/        staged before commit
  CHANGELOG.md            history
```

Feedback is written locally first, then committed and pushed — an append-only
JSONL per person per lecture, so two people filing at once never conflict.

Approval is a pull request. `/lecture-forge-tune` writes the proposed
`config/defaults.json` change plus its evidence onto a branch and opens a PR;
Harsh reviews the diff and merges. The golden set runs in the PR, so a
proposal that breaks a past lecture fails before anyone looks at it. That
replaces the local `pending.json` and `/lecture-forge-approve` flow described
above — same gate, standard tooling, and a permanent record for free.

Aniket needs push access to the repo and no more than that; merge rights stay
with Harsh, which is exactly the propose/approve split.

## Config precedence

Five layers, narrowest wins:

```
CLI flag
  > room profile        ~/.lecture-forge/profiles/<room>.json   camera facts
  > local config        ~/.lecture-forge/config.json            experiments
  > shared config       <plugin>/config/defaults.json           team-approved
  > code defaults                                               shipped fallback
```

Code defaults stay in the source as the last resort, so a bad config can always
be deleted rather than untangled.
