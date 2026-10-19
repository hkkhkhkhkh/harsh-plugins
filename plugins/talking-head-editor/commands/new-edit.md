---
description: Start a talking-head edit (9:16 reel, iPhone selfie, or 16:9 VSL) in DaVinci Resolve + After Effects
argument-hint: <camera-clip> --format reel|iphone|vsl [--name slug]
allowed-tools: Bash, Read, Write, Edit, Glob
---

Start an edit job for: **$ARGUMENTS**

Follow `${CLAUDE_PLUGIN_ROOT}/skills/editing-talking-head-reels/SKILL.md` (read it first if it is not in context).

1. If the format wasn't given, choose it from what the video is FOR: a sales video, VSL or YouTube video is 16:9 (`vsl`);
   a reel or ad for Instagram is 9:16 (`reel` for a log camera, `iphone` for a phone selfie). Say which you picked.
2. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/new_job.py <clip> --format <fmt>`. It reads the user's
   `~/.config/talking-head-editor/config.json`; if that file is missing, show the README's example and ask for the paths.
3. In the job folder it prints: `python3 clean_source.py && python3 transcribe.py` (transcription takes about a third
   of the clip's length on CPU: say so, and run it in the background).
4. Ask for the script if the user has one: it is the source of truth for caption words and the take choice.
5. Continue with the skill's pipeline. Do not start a Resolve render or an After Effects run while another session
   is using them: ask it first.
