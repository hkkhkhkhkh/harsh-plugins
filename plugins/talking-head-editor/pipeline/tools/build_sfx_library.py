"""Build the tagged SFX library the reel pipeline picks from (run again whenever a pack is added).

Sources: the house sounds shipped with the plugin (pipeline/audio/sd: made with Higgsfield Seed Audio, owned) plus any
sound packs you pass with --pack (check each pack's licence before paid ads; a pack whose terms are not on file is
fine for organic posts only). Usage: python3 build_sfx_library.py --lib ~/sfx-library [--pack DIR ...] Every file is copied to LIB/<role>/, leading silence trimmed so the transient sits on
sample 0, converted to 48 kHz stereo 24-bit. Levels are NOT normalised: the index stores each file's max
loudest-100ms RMS so sfx.py can swap a variant in at the same perceived level as the approved house sound.

Roles: whoosh, whip, pop, strike, riser, impact, subdrop, shutter, typing, glitch, bell, misc.
glitch and bell are 'restricted' (game/meme feel, a doctor loses trust): never auto-picked."""
import json, re, subprocess, sys
from pathlib import Path
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
PIPE = Path(__file__).resolve().parents[1]          # pipeline/ (house sounds live in pipeline/audio/sd)
def _arg(name, many=False):
    vals = [sys.argv[i + 1] for i, a in enumerate(sys.argv[:-1]) if a == name]
    return [Path(v).expanduser() for v in vals] if many else (Path(vals[-1]).expanduser() if vals else None)
LIB = _arg("--lib") or Path.home() / "sfx-library"
PACKS = _arg("--pack", many=True)
HOUSE = {"whoosh_soft": "whoosh", "pop": "pop", "strike": "strike", "riser": "riser", "impact": "impact",
         "whip_zoom": "whip", "fastwhoosh": "whoosh"}
RESTRICTED = {"glitch", "bell"}


def role_for(path: Path):
    s = (path.parent.name + " " + path.stem).lower()
    rules = [("glitch", "glitch"), ("tv noise", "glitch"), ("camera", "shutter"), ("shutter", "shutter"),
             ("subdrop", "subdrop"), ("sub drop", "subdrop"), ("impact", "impact"), ("horn", "impact"),
             ("whip", "whip"), ("whoosh", "whoosh"), ("swoosh", "whoosh"), ("panoramic", "whoosh"),
             ("button", "pop"), ("select", "pop"), ("notification", "pop"), ("bips", "pop"), ("hud", "pop"),
             ("type text", "typing"), ("bell", "bell"), ("wrong", "bell"), ("right", "bell")]
    for key, role in rules:
        if key in s:
            return role
    return "misc"


def probe(f: Path):
    """(loudest 100 ms RMS in dBFS, duration). Short hits (a 0.27 s whip) have no EBU momentary value, so RMS."""
    import numpy as np
    raw = subprocess.run([FF, "-v", "error", "-i", str(f), "-ac", "1", "-ar", "48000", "-f", "f32le", "-"],
                         capture_output=True).stdout
    x = np.frombuffer(raw, np.float32)
    if not len(x):
        return -90.0, 0.0
    w = 4800
    n = max(1, len(x) // w)
    xx = np.pad(x, (0, max(0, n * w - len(x))))[:n * w].reshape(n, w)
    return float(20 * np.log10(np.sqrt((xx ** 2).mean(1)).max() + 1e-9)), len(x) / 48000


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def main():
    LIB.mkdir(parents=True, exist_ok=True)
    src = [(p, HOUSE[p.stem], "house", "owned (Higgsfield seed_audio)")
           for p in sorted((PIPE / "audio/sd").glob("*.wav")) if p.stem in HOUSE]
    for PACK in PACKS:
        for p in sorted(PACK.rglob("*")) if PACK.exists() else []:
            if p.suffix.lower() in (".wav", ".mp3", ".aif", ".aiff"):
                src.append((p, role_for(p), "pack", "pack: check its licence before paid ads"))
    if not PACKS: print("no --pack given: house sounds only", file=sys.stderr)
    idx, seen = [], set()
    for p, role, origin, lic in src:
        name = ("house_" if origin == "house" else "") + slug(p.parent.name if origin == "pack" else "") + "_" + slug(p.stem)
        name = name.replace("__", "_").strip("_")
        while name in seen:
            name += "_b"
        seen.add(name)
        out = LIB / role / f"{name}.wav"
        out.parent.mkdir(exist_ok=True)
        if not out.exists():
            r = subprocess.run([FF, "-v", "error", "-y", "-i", str(p), "-af",
                                "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.005",
                                "-ar", "48000", "-ac", "2", "-c:a", "pcm_s24le", str(out)], capture_output=True, text=True)
            if r.returncode:
                print("skip", p.name, r.stderr[-200:], file=sys.stderr)
                continue
        mmax, dur = probe(out)
        length = "short" if dur < 0.6 else ("normal" if dur < 1.6 else "long")
        idx.append({"file": str(out.relative_to(LIB)), "role": role, "origin": origin, "house_key": p.stem if origin == "house" else None,
                    "dur": round(dur, 3), "length": length, "peak_rms_db": round(mmax, 1),
                    "intensity": 1 if mmax < -26 else (2 if mmax < -18 else 3),
                    "restricted": role in RESTRICTED, "licence": lic, "source": str(p)})
    (LIB / "index.json").write_text(json.dumps(idx, indent=1))
    from collections import Counter
    print(len(idx), "sounds ->", LIB, dict(Counter(e["role"] for e in idx)))


if __name__ == "__main__":
    main()
