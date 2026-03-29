"""
config.py
All environment variables and pipeline constants in one place.
Import this anywhere: from config import settings
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
MATERIALS_JSON = DATA_DIR / "materials.json"

# ── API keys ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

# "claude" or "openai" — falls back to openai if anthropic key missing
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "claude")

# ── Image preprocessing ───────────────────────────────────────────────────────
MAX_IMAGE_DIM: int = 2000          # resize longer edge to this before CV
GAUSSIAN_BLUR_K: int = 3           # GaussianBlur kernel size (must be odd)
CANNY_LOW: int = 50
CANNY_HIGH: int = 150

# ── HoughLinesP ───────────────────────────────────────────────────────────────
HOUGH_RHO: float = 1.0
HOUGH_THETA_DEG: float = 1.0       # degrees — converted to radians in code
HOUGH_THRESHOLD: int = 40
HOUGH_MIN_LINE_LENGTH: int = 15    # pixels — shorter lines discarded
HOUGH_MAX_LINE_GAP: int = 20

# ── Room / contour detection ──────────────────────────────────────────────────
# Minimum room area as fraction of total image area
ROOM_MIN_AREA_FRACTION: float = 0.004
# Maximum room area fraction (avoid picking up the whole floor plan outline)
ROOM_MAX_AREA_FRACTION: float = 0.70

# ── Geometry cleanup (Stage 2) ────────────────────────────────────────────────
SNAP_GRID_PX: int = 5              # snap coords to N-pixel grid
LINE_MERGE_DIST_PX: int = 8        # merge parallel lines closer than this
ANGLE_TOLERANCE_DEG: float = 5.0   # lines within this angle = "parallel"

# ── Wall classification ───────────────────────────────────────────────────────
THICK_WALL_PX: int = 8             # pixel width >= this → thick (load-bearing)
THIN_WALL_PX: int = 4              # pixel width <= this → thin (partition)
# Fraction of building width/height a wall must span to be "structural spine"
SPINE_FRACTION: float = 0.55

# ── 3D model ──────────────────────────────────────────────────────────────────
WALL_HEIGHT_M: float = 3.0         # standard floor height metres
SCALE_FACTOR: float = 20.0         # normalised 0-1 → Three.js units
ASSUMED_BUILDING_WIDTH_M: float = 15.0   # used when no scale bar detected
PIXEL_TO_METRE: float = 0.05       # deterministic fallback: 1px = 0.05m
VERTEX_SNAP_THRESHOLD_M: float = 0.05  # snap wall endpoints closer than this

WALL_THICKNESS_M = {
    "thick":    0.38,
    "standard": 0.26,
    "thin":     0.14,
}

WALL_COLOR_HEX = {
    "exterior":               "#e74c3c",
    "interior_load_bearing":  "#f39c12",
    "partition":              "#3498db",
}

# ── Material scoring weights ──────────────────────────────────────────────────
SCORE_WEIGHT_STRENGTH: float    = 0.40
SCORE_WEIGHT_DURABILITY: float  = 0.35
SCORE_WEIGHT_COST_EFF: float    = 0.25

STRENGTH_SCORE = {
    "very_high":   10.0,
    "high":         8.0,
    "medium-high":  6.5,
    "medium":       5.0,
    "low-medium":   3.5,
    "low":          2.0,
}

DURABILITY_SCORE = {
    "very_high":   10.0,
    "high":         8.0,
    "medium-high":  6.5,
    "medium":       5.0,
    "low-medium":   3.5,
    "low":          2.0,
}

# Lower cost → higher efficiency score
COST_EFFICIENCY_SCORE = {
    "low":          10.0,
    "low-medium":    8.0,
    "medium":        6.0,
    "medium-high":   4.0,
    "high":          2.0,
}

# Unsupported span longer than this (metres) → flag structural concern
CONCERN_SPAN_M: float = 4.0

# ── LLM ──────────────────────────────────────────────────────────────────────
LLM_MODEL_CLAUDE: str = "claude-sonnet-4-20250514"
LLM_MODEL_OPENAI: str = "gpt-4o"
LLM_MAX_TOKENS: int = 2000