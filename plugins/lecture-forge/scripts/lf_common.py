"""Shared helpers for the lecture-forge pipeline.

Everything here is deliberately dependency-light: only the standard library plus
ffmpeg on PATH. numpy and faster-whisper are imported by the scripts that
actually need them.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, asdict
from pathlib import Path

# --------------------------------------------------------------------------
# Binaries
# --------------------------------------------------------------------------

def _find(name: str, extra: list[str] | None = None) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for cand in (extra or []):
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


HOME = Path.home()

FFMPEG = _find("ffmpeg", [str(HOME / ".local/bin/ffmpeg"), "/opt/homebrew/bin/ffmpeg",
                         "/usr/local/bin/ffmpeg"])
# ffprobe is optional. lf_probe falls back to parsing `ffmpeg -i` stderr.
FFPROBE = _find("ffprobe", [str(HOME / ".local/bin/ffprobe"), "/opt/homebrew/bin/ffprobe",
                            "/usr/local/bin/ffprobe"])

LF_HOME = Path(os.environ.get("LECTURE_FORGE_HOME", HOME / ".lecture-forge"))
PROFILES_DIR = LF_HOME / "profiles"
VENV_PYTHON = LF_HOME / "venv" / "bin" / "python"


def require_ffmpeg() -> str:
    if not FFMPEG:
        die("ffmpeg not found. Install it (brew install ffmpeg) or put it on PATH.")
    return FFMPEG


# --------------------------------------------------------------------------
# Process / logging
# --------------------------------------------------------------------------

def die(msg: str, code: int = 1) -> None:
    print(f"lecture-forge: error: {msg}", file=sys.stderr)
    sys.exit(code)


def log(msg: str) -> None:
    print(f"  {msg}", file=sys.stderr, flush=True)


def run(cmd: list[str], *, capture: bool = True, check: bool = True,
        stdin_text: str | None = None) -> subprocess.CompletedProcess:
    """Run a command. ffmpeg writes its report to stderr even on success, so we
    always capture stderr and only surface it when something actually fails."""
    proc = subprocess.run(
        cmd,
        input=stdin_text,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE,
        text=True,
    )
    if check and proc.returncode != 0:
        tail = "\n".join((proc.stderr or "").strip().splitlines()[-25:])
        die(f"command failed ({proc.returncode}): {' '.join(cmd[:6])} ...\n{tail}")
    return proc


def ffmpeg_run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    """Run ffmpeg with the noise turned down. `args` excludes the binary itself."""
    return run([require_ffmpeg(), "-hide_banner", "-nostdin", "-loglevel", "error", *args],
               check=check)


# --------------------------------------------------------------------------
# Time formatting
# --------------------------------------------------------------------------

def hhmmss(seconds: float, *, ms: bool = False, srt: bool = False) -> str:
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    if srt:
        return f"{h:02d}:{m:02d}:{int(s):02d},{int(round((s % 1) * 1000)):03d}"
    if ms:
        return f"{h:02d}:{m:02d}:{s:06.3f}"
    return f"{h:02d}:{m:02d}:{int(s):02d}"


def parse_timecode(text: str) -> float:
    """Accept 90, 1:30, 01:02:03, 01:02:03.250 -> seconds."""
    text = text.strip()
    if not text:
        raise ValueError("empty timecode")
    parts = text.replace(",", ".").split(":")
    if len(parts) > 3:
        raise ValueError(f"bad timecode: {text}")
    total = 0.0
    for part in parts:
        total = total * 60 + float(part)
    return total


def slugify(text: str, *, max_len: int = 60) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return (text[:max_len].rstrip("-")) or "clip"


# --------------------------------------------------------------------------
# Interval algebra — the backbone of every edit decision
# --------------------------------------------------------------------------

Interval = tuple[float, float]


def merge_intervals(intervals: list[Interval], *, gap: float = 0.0) -> list[Interval]:
    """Union of intervals. Intervals separated by <= `gap` are joined."""
    clean = [(a, b) for a, b in intervals if b > a]
    if not clean:
        return []
    clean.sort()
    out = [list(clean[0])]
    for a, b in clean[1:]:
        if a - out[-1][1] <= gap:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def subtract_intervals(base: list[Interval], remove: list[Interval]) -> list[Interval]:
    """base minus remove. Both are treated as unions, not ordered pairs."""
    base = merge_intervals(base)
    remove = merge_intervals(remove)
    out: list[Interval] = []
    for a, b in base:
        cursor = a
        for ra, rb in remove:
            if rb <= cursor or ra >= b:
                continue
            if ra > cursor:
                out.append((cursor, min(ra, b)))
            cursor = max(cursor, rb)
            if cursor >= b:
                break
        if cursor < b:
            out.append((cursor, b))
    return [(a, b) for a, b in out if b > a]


def intersect_intervals(a: list[Interval], b: list[Interval]) -> list[Interval]:
    a, b = merge_intervals(a), merge_intervals(b)
    out: list[Interval] = []
    i = j = 0
    while i < len(a) and j < len(b):
        lo = max(a[i][0], b[j][0])
        hi = min(a[i][1], b[j][1])
        if hi > lo:
            out.append((lo, hi))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return out


def total_duration(intervals: list[Interval]) -> float:
    return sum(b - a for a, b in merge_intervals(intervals))


def drop_short(intervals: list[Interval], min_len: float) -> list[Interval]:
    return [(a, b) for a, b in intervals if (b - a) >= min_len]


# --------------------------------------------------------------------------
# Workdir + JSON state
# --------------------------------------------------------------------------

@dataclass
class MediaInfo:
    path: str
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool
    audio_rate: int
    vcodec: str
    acodec: str

    def to_dict(self) -> dict:
        return asdict(self)


def workdir_for(source: Path, out_root: str | None = None) -> Path:
    source = Path(source).expanduser().resolve()
    root = Path(out_root).expanduser().resolve() if out_root else source.parent / "lecture-forge"
    wd = root / slugify(source.stem, max_len=48)
    wd.mkdir(parents=True, exist_ok=True)
    return wd


def read_json(path: Path) -> dict:
    p = Path(path)
    if not p.exists():
        die(f"missing {p.name} — run the earlier stage first ({p})")
    with p.open() as fh:
        return json.load(fh)


def write_json(path: Path, data) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w") as fh:
        json.dump(data, fh, indent=2)
    tmp.replace(p)


def load_profile(name: str | None) -> dict:
    """Camera/room profile. Absent profile is fine — callers use defaults."""
    if not name:
        return {}
    path = PROFILES_DIR / f"{slugify(name)}.json"
    if not path.exists():
        die(f"profile '{name}' not found at {path}. Run /lecture-forge-calibrate first.")
    with path.open() as fh:
        return json.load(fh)
