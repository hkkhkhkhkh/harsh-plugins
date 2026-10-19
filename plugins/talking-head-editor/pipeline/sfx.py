"""Sound picker. House sounds come from job.SFX_HOUSE_DIR (<key>.wav: whoosh_soft, pop, strike, riser, impact, whip_zoom,
fastwhoosh); shutter and subdrop come from the optional tagged library is job.SFX_LIBRARY (built by tools/build_sfx_library.py).
Default = the approved house sound for each role, exactly as signed off. job.SFX_VARIANTS = True rotates through
library variants of the same role and length instead (never the same file twice in a row, restricted roles never),
level-matched to the house sound by loudest-100 ms RMS, so the approved gains in sfx_rules.py still hold."""
import json, os
from pathlib import Path
import job
LIB = Path(job.SFX_LIBRARY).expanduser() if getattr(job, "SFX_LIBRARY", "") else Path("/nonexistent")
HOUSE_DIR = Path(job.SFX_HOUSE_DIR)
HOUSE = {k: str(HOUSE_DIR / f"{k}.wav") for k in ("whoosh_soft", "pop", "strike", "riser", "impact", "whip_zoom", "fastwhoosh")}   # shutter, subdrop: library roles
HERE = Path(__file__).parent
ROLE = {"whoosh_soft": "whoosh", "pop": "pop", "strike": "strike", "riser": "riser", "impact": "impact",
        "whip_zoom": "whip", "fastwhoosh": "whoosh", "shutter": "shutter", "subdrop": "subdrop"}
_IDX = json.loads((LIB / "index.json").read_text()) if (LIB / "index.json").exists() else []
_last = {}


def _house_entry(key):
    return next((e for e in _IDX if e["origin"] == "house" and e["house_key"] == Path(HOUSE[key]).stem), None)


def pick(key, variants=False):
    """-> (file path, gain correction dB). key is a house key (whoosh_soft, pop, ...) or a library role."""
    if key in HOUSE and not variants:
        if not Path(HOUSE[key]).exists(): raise SystemExit(f"missing house sound {HOUSE[key]}: copy your set into {HOUSE_DIR} (see README: house sounds)")
        return HOUSE[key], 0.0
    role = ROLE.get(key, key)
    ref = _house_entry(key) if key in HOUSE else None
    pool = [e for e in _IDX if e["role"] == role and not e["restricted"] and e["origin"] != "house"
            and (ref is None or e["length"] == ref["length"])] or [e for e in _IDX if e["role"] == role and not e["restricted"]]
    if not pool:
        if key in HOUSE:
            if not Path(HOUSE[key]).exists(): raise SystemExit(f"missing house sound {HOUSE[key]}: copy your set into {HOUSE_DIR} (see README: house sounds)")
        return HOUSE[key], 0.0
        raise KeyError(f"no sound for role {role!r}")
    pool.sort(key=lambda e: e["file"])
    i = (_last.get(role, -1) + 1) % len(pool)
    _last[role] = i
    e = pool[i]
    level = ref["peak_rms_db"] if ref else -18.0
    return str(LIB / e["file"]), round(level - e["peak_rms_db"], 1)
