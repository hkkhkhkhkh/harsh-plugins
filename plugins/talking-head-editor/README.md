# talking-head-editor

One talking-head recording in, one finished video out: a 9:16 reel or ad, or a 16:9 sales video (VSL) with real client proof.
Everything ends up in **one DaVinci Resolve timeline** you can open and change: graded A-roll with zooms, After Effects motion
graphics cued to the words, power-word captions, B-roll and stills, a cleaned voice, music and sound design mixed to -16 LUFS.

Claude drives it all (Python, the Resolve scripting API, After Effects via osascript). You give the clip and the script, review
cuts and claims, and give notes like "stutter at 6:18" or "that clip is a different client"; each note becomes a data change
and a re-render.

What it does that a plain edit doesn't:
- **A stutter scan** before every render: each cut piece is transcribed on its own, so repeated words and false starts a
  full-video transcript would hide get caught.
- **Proof from records**: client cards use real check-in photos, dated measurements and lab values with units, and the client's
  own words with a source line. No invented numbers or quotes, and identities are confirmed before naming anyone.
- **Render QC**: black frames at cuts, loudness, colour against the camera LUT, transcripts around every join.
- **Web delivery**: a fast-start 720p encode and poster for a landing page.

## Install

```
/plugin marketplace add hkkhkhkhkh/harsh-plugins
/plugin install talking-head-editor@harsh-marketplace
```
Restart Claude Code afterwards (the command and skill register at startup).

## Requirements (macOS)
- **DaVinci Resolve Studio 20** with Preferences > System > General > External scripting using: Local. The free version has no
  scripting API.
- **Adobe After Effects 2026**, and an MCP tool in Claude that can run osascript in your desktop session (e.g. "Control your
  Mac"): After Effects can't be driven from a terminal.
- **Python 3** with `numpy scipy opencv-python pillow faster-whisper imageio-ffmpeg`:
  `pip3 install numpy scipy opencv-python pillow faster-whisper imageio-ffmpeg`
- **DeepFilterNet 3** in its own Python 3.11 venv:
  ```
  uv venv --python 3.11 ~/.local/share/deepfilter-venv
  uv pip install --python ~/.local/share/deepfilter-venv/bin/python deepfilternet==0.5.6 torch==2.2.2 torchaudio==2.2.2 "numpy<2"
  ```
- **Fonts**: Avenir Next and Avenir Next Condensed ship with macOS (captions). The graphics default to Archivo
  (`ArchivoEF-*` PostScript names); install Archivo or set your own fonts in the config's `brand`.
- **Camera LUT** for log footage (Sony: the s709 LUT from Sony's site). Used for previews, face detection and the colour check.
- Optional: the `higgsfield` CLI with credits for B-roll stills, music beds and new sounds.

## One-time setup: your config
Create `~/.config/talking-head-editor/config.json`. It holds everything specific to YOUR machine, so the plugin stays shareable:
```json
{
  "jobs_dir": "~/Movies/edits",
  "footage_dir": "~/Movies/footage",
  "lut": "~/Movies/LUT/SL3SG3tos709.cube",
  "music": "~/Movies/music/my-owned-bed.wav",
  "dfpy": "~/.local/share/deepfilter-venv/bin/python",
  "sfx_house_dir": "",
  "sfx_library": "",
  "resolve_volume": "/Volumes/Macintosh HD",
  "brand": {"ink": "#10243D", "paper": "#F7F9FB", "red": "#BE2A1B", "green": "#10604F",
            "font_bold": "ArchivoEF-Bold", "font_semibold": "ArchivoEF-SemiBold", "font_medium": "ArchivoEF-Medium"}
}
```
Keep `jobs_dir` and `footage_dir` under `~/Movies` or an external `/Volumes/...` drive: Resolve's API only imports from
mounted volumes.

## Use

```
/talking-head-editor:new-edit /Volumes/Card/PRIVATE/M4ROOT/CLIP/20261017_C0040.MP4 --format vsl
```
or just ask: "edit this VSL in DaVinci with After Effects", with the clip path and your script. The skill walks the
pipeline: clean + transcribe, cut + stutter scan, faces + layout, claims + proof, captions, graphics, inserts, audio,
Resolve test render, full render, QC, delivery. Formats: `reel` (9:16 log camera), `iphone` (9:16 phone HDR), `vsl`
(16:9 sales video / YouTube; long-form settings in the skill's references).

## What's in the box
- `skills/editing-talking-head-reels/`: the workflow (SKILL.md) and references (house style, formats, graphics catalogue,
  proof and claims, QC, traps, delivery).
- `pipeline/`: the scripts copied into every job folder; `pipeline/formats/` holds the iPhone and 16:9 overlays.
- `pipeline/ae/kit.jsx`: the After Effects template kit (9:16 and 16:9 templates; brand colours and fonts from your config).
- `pipeline/audio/sd/`: the house sound effects, made by the author with Higgsfield Seed Audio, free to use with this plugin.
- `scripts/new_job.py`: starts a job (probe, byte-checked copy, job folder, job.py).

## Licences and privacy
- Bring your own music with a licence that covers how the video will be used; paid ads need a sync licence or a bed you own.
  Sound packs you add with `tools/build_sfx_library.py --pack` keep their own terms.
- Client footage, photos, lab data and quotes stay in your job folders. Nothing from a job belongs in this repo.
