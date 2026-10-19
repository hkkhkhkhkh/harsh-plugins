"""Per-job settings. scripts/new_job.py writes this file into each job folder as job.py; every pipeline script imports it.
Edit it first. Values marked HOUSE are the signed-off finish: change them for a reason, and write the reason next to it.
__FORMAT_NOTE__"""
from pathlib import Path
HERE = Path(__file__).resolve().parent

# ── source ─────────────────────────────────────────────────────────────────────────────────────────────────────────
CLIP = "__CLIP__"                 # file name of the camera clip
SRC = Path("__SRC__")             # the byte-checked copy (new_job.py copies it off the card)
FORMAT = "__FORMAT__"             # reel (9:16, log camera) | iphone (9:16, phone HDR) | vsl (16:9 sales video / YouTube)
IDT = "__IDT__"                   # Resolve input colour space. Sony FX30 log: "S-Gamut3/S-Log3" (no "Sony " prefix).
                                  # Apple-converted iPhone (tools/tosdr.swift): "Rec.709 Gamma 2.4". Verify by readback in Resolve.
LUT = "__LUT__"                   # the camera's own log->709 LUT, used only for previews, face detection and the QC colour check
SRC_FPS = __SRC_FPS__             # camera rate (FX30: 50; iPhone: 30 or 30000/1001)
FPS = __FPS__                     # timeline + delivery rate (FX30 jobs: 25; iPhone: 30). Resolve wants "29.97" as a STRING if you need it.
W, H = __W__, __H__               # delivery frame
TAG = "__TAG__"                   # short id used in timeline and file names
PROJECT = "__PROJECT__"           # Resolve project (created if missing; never save an untitled one)
OUT_NAME = "__OUT_NAME__"         # render file stem

# ── audio ──────────────────────────────────────────────────────────────────────────────────────────────────────────
DFPY = "__DFPY__"                 # python of the DeepFilterNet 3 venv (py3.11; see README)
MUSIC = "__MUSIC__"               # the bed. Shorter than the edit? extend it: python3 music/build_bed.py --help
LUFS_TARGET = -16.0               # HOUSE: whole mix. -14 was judged too loud.
VOICE_OVER_MUSIC_DB = 25.0        # HOUSE (calm finish): median voice-over-bed gap under speech; stems.py iterates to land it
SFX_TRIM_DB = -4.0                # HOUSE (calm finish): every placed effect 4 dB under the rule's gain
MUSIC_DROPS = []                  # [(start, end)] record-time spans where the bed drops out (a line that should land alone).
                                  # Derive them from transcripts/rec_words.json, not fixed numbers: a re-cut moves every time.
SFX_HOUSE_DIR = HERE / "audio/sd" # the house sounds (whoosh_soft, pop, strike, riser, impact, whip_zoom, fastwhoosh): see README
SFX_LIBRARY = "__SFX_LIBRARY__"   # optional tagged library (tools/build_sfx_library.py) for SFX_VARIANTS
SFX_VARIANTS = False              # True: rotate level-matched library sounds instead of repeating the house ones
EXTRA_HITS = []                   # one-off sounds: [(t, key, gain_db)]

# ── picture ────────────────────────────────────────────────────────────────────────────────────────────────────────
GRADE = __GRADE__                 # clip CDL on top of the colour-managed conversion
AROLL_FX = __AROLL_FX__           # ResolveFX run inside each A-roll Fusion comp (16:9 finisher): {"Name": {input: value}}
                                  # Measure before trusting: the Vignette default (size 0.5, transparency 0) crushed a dark room to black.
PREVIEW_VF = __PREVIEW_VF__       # ffmpeg filter that turns a source frame into a viewable Rec.709 still
TOP_DARKEN = False                # iPhone finisher only: soften a bright ceiling
CUTOUT = None                     # person cut-out clip for text-behind-head (only for clean-edged subjects; see references)
HEAD_TOP = None                   # iPhone finisher: measured y of the top of the hair, if no matte

# ── captions ───────────────────────────────────────────────────────────────────────────────────────────────────────
CAPTION_Y = __CAPTION_Y__         # caption line, px from the top (9:16: 1280; 16:9: 880 over the chest)
PX_PER_SIZE = __PX_PER_SIZE__     # Fusion Text+ Size 1.0 in px. Scales with frame WIDTH: 700 at 1080 wide, 1244 at 1920 wide.
AD_SAFE = False                   # True for paid-ad 9:16 cuts: captions up to y 1150, clear of Meta's bottom-35% UI
CAPTION_KEYWORDS = []             # test only: words shown alone and 1.5x
CAPTION_KEYWORD_SCALE = 1.5
CAPTION_FIXES = [                 # regex -> replacement applied to ASR words when drafting caption lines (names, terms, units)
    (r"(\d+) ?kgs\b", r"\1 kg"), (r"\bkgs\b", "kg"), (r"(\d+) %", r"\1%"), (r" -", "-"),
]

# ── brand (After Effects kit) ──────────────────────────────────────────────────────────────────────────────────────
BRAND = __BRAND__                 # colours + font PostScript names for ae/kit.jsx; fonts must be installed for AE

# ── Resolve ────────────────────────────────────────────────────────────────────────────────────────────────────────
# Resolve only imports media under a mounted volume (GetMountedVolumeList: ~/Movies and /Volumes/*). Anything else
# (a job folder in ~/Documents, say) returns None from ImportMedia with no error. rp() routes it through the boot volume.
RESOLVE_VOLUME = "__RESOLVE_VOLUME__"
def rp(p):
    p = str(p)
    return p if p.startswith("/Volumes/") or p.startswith(str(Path.home() / "Movies")) else RESOLVE_VOLUME + p

# Extra sources for paragraphs pulled from another clip: KEEP entries may carry a source key; run clean_source/transcribe there first.
EXTRA = {}   # e.g. {"b": {"video": Path(".../C0041.MP4"), "dir": "../c0041"}}
def source(key=None):
    if key is None: return {"video": SRC, "audio_df": "audio/c0023_48k_df.wav", "phrases": "transcripts/phrases.json"}
    e = EXTRA[key]; d = e["dir"]
    return {"video": e["video"], "audio_df": f"{d}/audio/c0023_48k_df.wav", "phrases": f"{d}/transcripts/phrases.json"}
