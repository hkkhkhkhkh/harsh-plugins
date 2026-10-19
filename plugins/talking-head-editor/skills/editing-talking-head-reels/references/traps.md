# Traps (each one cost a render)

## DaVinci Resolve (Studio 20, scripting API)
- **Only media under a mounted volume imports** (`GetMountedVolumeList`: ~/Movies, /Volumes/*). A job folder anywhere else
  returns None from ImportMedia with no error. `job.rp()` routes paths through `/Volumes/Macintosh HD`.
- `SaveProject()` on "Untitled Project" opens a modal that blocks the API. Never save an untitled project. If the API hangs:
  `pkill -9 Resolve`, relaunch via osascript `launch`, wait until `scriptapp("Resolve")` returns a project manager.
- Never run two renders at once, even from different sessions: Resolve crashes. Kill only PIDs you started.
- `timelineFrameRate` rejects `str(30000/1001)` and silently stays at 24: use the string "29.97". It can't change while any
  timeline exists. Clips are stamped with the project fps at import: set the rate before importing stems.
- A 30.0 clip on a 29.97 timeline is NOT cosmetic: Resolve drops a frame at every cut (one-frame black flashes).
  `clip.SetClipProperty("FPS", "29.97")` (a string) right after import. The finisher asserts V1 joins are gap 0.
- Captions must be clamped to the picture's last frame, or the tail caption stretches the timeline and renders black.
- The API can't set a title's duration: use transparent ProRes 4444 carrier clips placed with
  `AppendToTimeline(recordFrame=..., trackIndex=...)`, then `AddFusionComp` -> Text+ -> Merge.
- A graphic overlapping the one before it on the same track is silently overwritten: the finisher moves it to V5.
- Render the MP4 alone. MP4 + ProRes in one batch hung the ProRes at 0% and the MP4 lost its moov atom.
- A test render straight after a rebuild can come out without captions though the comps are right: re-render before
  concluding anything. "Complete" is not proof a layer rendered: pixel-sample.
- Resolve caches clip length: after re-rendering a file under the same name, `DeleteClips` it from the pool and re-import
  (the finisher does this for the job's graphics, stems, carriers and client clips).
- Resolve's Python process is named `Python`, not `python3`: process monitors grepping python3 think it died.
- A user (or another session) can stop a render from the UI: the status comes back "Cancelled" at some %. Ask before re-running.

## Fusion (inside Resolve)
- Never `comp.Lock()`: the comp renders nothing, silently.
- Animating an input (`tool.Blend = comp.BezierSpline({})`) drops a key at frame 0 holding the current value: always set frame 0
  yourself, or every caption state fades in slowly and they ghost over each other.
- Text+ font = macOS family name + Style ("Avenir Next Condensed", "Heavy"). Fit widths with PIL font metrics, not character counts.
- Text+ Size is relative to frame WIDTH (700 px per unit at 1080 wide, 1244 at 1920 wide). Fusion y runs bottom-up.
- Under colour management, Fusion text lands at ~78% white: CDL slope 1.4 on each caption clip; `useInverseDRT=1` for SDR graphics.
- In a Transform, keep Center at 0.5 for a plain zoom and move Pivot, or you get black edges. A-roll comps count at the
  SOURCE rate (50 fps), frame 0 = clip start, coordinates in source px.
- ResolveFX are scriptable inside Fusion comps (`comp.AddTool("ofx.com.blackmagicdesign.resolvefx.Vignette")`; inputs by id,
  e.g. size/softness/transparency; ContrastPop MidtoneDetail). Their defaults are tuned for a demo frame: the Vignette default
  (size 0.5, transparency 0) crushed a dark room to black. Measure one frame before a full render.

## After Effects (2026, ExtendScript)
- Drive it only through the GUI-session osascript tool (`DoScriptFile`). Launching AE from a shell hangs. System Events
  clicks are blocked.
- `DoScript` returns nothing useful and often "fails" while the render continues: check the output files instead.
- ExtendScript is ES3: an unquoted object key like `true` or `class` = "Illegal use of reserved word" and a modal AE can't be
  scripted past. Quote keys. Wrap template builds in try/catch that saves an ERR_*.aep (the kit does).
- If AE hangs on a modal or the Home screen with an empty project: `kill -9` it, relaunch with osascript `launch`, then
  `open POSIX file "<job>/ae/graphics.aep"` before any `DoScriptFile`. Look only at AE's own windows (window-id captures),
  never full-screen screenshots.
- Fetch shape property handles only after the group is complete; set anchor and position to 0,0 for comp-coordinate shapes.
- Render a small ONLY subset to test a new template before the full batch.
- `\r` breaks a line inside AE text. In a Python string that must be the escape `"\r"`, not a literal backslash-r.

## Audio
- Never put a limiter (or any look-ahead filter) inside the shared sidechain ffmpeg graph in stems.py: it deadlocks at 0% CPU.
  Limit stems in a separate pass and pass `-nostdin`.
- DeepFilterNet needs Python 3.11 (`uv venv --python 3.11`, `deepfilternet==0.5.6 torch==2.2.2 torchaudio==2.2.2 "numpy<2"`).
- Use the imageio-ffmpeg 7.1 binary: system ffmpeg 7.0 couldn't read FX30 files.

## Whisper (faster-whisper)
- Two passes disagree in opposite ways: whole-clip small for take boundaries, per-phrase medium for words.
- It smooths repeats ("click the button. click the button" -> once) and stretches a word across a pause to hide a restart
  ("the" lasting 0.9 s). That's why stutter_scan.py transcribes each piece alone.
- It sometimes stamps a word with zero length; wordmap gives it 60 ms so captions keep it.
- It hallucinates in silence ("Thank you. Good night."): ignore text in a removed gap.
- It may skip a client clip's window in a long transcript; transcribe that window alone before deciding audio is missing.

## Higgsfield
- Check credits and per-model cost before planning (`higgsfield account status`, `higgsfield generate cost <model> ...`).
- Inserts mangle small text: drop or regenerate any shot with fake readable text (tube labels, screens). Ask for "plain blank
  labels, absolutely no text".
- Seed Audio makes house sounds (0.1 credit each); Sonilo makes music beds (~3.75 credits per minute).

## iPhone
- HDR HLG: convert with Apple's pipeline (tools/tosdr.swift), not Resolve's HLG IDT.
- VFR: force CFR when re-encoding (`-fps_mode cfr -r 30000/1001`); ffmpeg's "drop=" on that conversion is correct.

## Working alongside other sessions
- Resolve and After Effects are single-user resources. Message other sessions before a render or AE run, and when you finish.
- Never commit or touch files another session is editing in a shared repo checkout: fast-forward a branch on the remote
  (`git push origin <sha>:refs/heads/main`) instead of switching branches under someone's uncommitted work.
