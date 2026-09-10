---
description: Render the lecture clips you approved in review.md
argument-hint: [workdir] [--clips 1,3] [--fast] [--profile NAME]
allowed-tools: Bash, Read, Glob
---

Render the approved clips: **$ARGUMENTS**

If no workdir is given, use the one from the most recent `/lecture-forge` run in
this session; if that is unknown, glob for `lecture-forge/*/review.md` under the
working directory and ask which one.

Run:

```
lf_render.py WORKDIR [--profile NAME] [--fast]
```

It reads `review.md` and renders exactly the rows still present there. Pass
`--fast` for VideoToolbox encoding when the user wants speed over quality.

Before rendering more than about 20 minutes of output, run with `--dry-run`
first and show the user the plan — clip count, lengths, cut counts.

When it finishes, report the summary table from `summary.md`: what came in, what
went out, and where the files are. Mention any mistake cuts that were refused
for want of silence to cut in.
