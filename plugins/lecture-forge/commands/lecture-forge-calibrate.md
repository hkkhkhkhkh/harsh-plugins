---
description: Calibrate a camera setup once so punch-ins never crop the smartboard
argument-hint: <lecture-file> [--name room-name]
allowed-tools: Bash, Read
---

Calibrate the room and camera from: **$ARGUMENTS**

Run `lf_calibrate.py SOURCE --name NAME` (no `--write` yet), then **show the
user the generated `*-calibration.png`** with the Read tool. The green box is
the board, the red box is the speaker.

Ask them to confirm the green box fully contains the smartboard, including its
edges. This box is the constraint that stops punch-ins from cropping board
writing off, so an under-sized box is the failure that matters — err large.

Motion detection often over-reads the speaker box; that is harmless, since it
only nudges where a punch-in centres.

Once confirmed, re-run with `--write`, or write a corrected profile to
`~/.lecture-forge/profiles/NAME.json` by hand if they gave you better numbers.
Then tell them to pass `--profile NAME` on future runs.

If the setup has no board at all, pass `--no-board`.
