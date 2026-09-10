---
description: Turn a recorded lecture into bite-sized clips — transcribe, analyse, propose clips for your approval
argument-hint: <lecture-file-or-folder> [--profile NAME] [--model medium.en]
allowed-tools: Bash, Read, Write, Glob, Task
---

Run stages 0–3 of lecture-forge on: **$ARGUMENTS**

This stops at a review sheet. Nothing renders until the user approves.

Follow `${CLAUDE_PLUGIN_ROOT}/skills/lecture-forge/SKILL.md` — read it first if
it is not already in context. Short version:

1. `lf_probe.py SOURCE` → note the workdir it prints.
2. `lf_transcribe.py WORKDIR` — the slow stage. Tell the user the estimate
   (roughly a third of the lecture's length on this machine) before starting it.
3. `lf_analyze.py WORKDIR`
4. `lf_curate.py WORKDIR --dump`, then dispatch one **lecture-curator** agent
   per window file, in parallel in a single message. Each agent writes
   `windows/win-NN.json` next to its `.md`.
5. `lf_curate.py WORKDIR --collect`
6. `lf_reviewsheet.py WORKDIR`

Then show the user the review table inline — titles, lengths, scores, and why
each clip stands alone — and tell them to delete the rows they do not want and
run `/lecture-forge-render`. Report anything the analysis refused to cut and any
clip proposals that failed validation; both are in the review sheet.

If a folder was given, process each video in it in turn.
