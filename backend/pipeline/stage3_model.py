"""
pipeline/stage3_model.py
Stage 3 — 2D → 3D Model Generation

Converts the cleaned ParsedFloorPlan geometry into a ThreeDModel that
the React / Three.js frontend can consume directly.

Every wall becomes a BoxGeometry descriptor with:
  - center_x, center_y (WALL_HEIGHT/2), center_z in world-space metres
  - length, height (always WALL_HEIGHT_M), thickness
  - rotation_y (radians) so the box aligns with the wall direction
  - color_hex per wall type

Every room becomes a Slab3D floor descriptor.
Every opening becomes an Opening3D marker.

Scale: normalized 0-1 → Three.js units via SCALE_FACTOR (default 20).
A building 15 m wide maps to 20 Three.js units.
"""

import math
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import (
    WALL_HEIGHT_M,
    SCALE_FACTOR,
    ASSUMED_BUILDING_WIDTH_M,
    WALL_THICKNESS_M,
    WALL_COLOR_HEX,
)
from utils.geometry_utils import midpoint, distance, line_angle_rad
from models.schemas import (
    ParsedFloorPlan,
    ThreeDModel, Wall3D, Slab3D, Opening3D,
)


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

# 10 distinct colors for room floor slabs (cycled by room index)
ROOM_SLAB_COLORS = [
    "#1abc9c", "#9b59b6", "#3498db", "#e67e22",
    "#2ecc71", "#e91e63", "#00bcd4", "#ff5722",
    "#cddc39", "#607d8b",
]


# ─────────────────────────────────────────────────────────────────────────────
# WALL → Wall3D
# ─────────────────────────────────────────────────────────────────────────────

def _build_wall_3d(wall, idx: int) -> Wall3D:
    """
    Convert a normalized Wall to a Wall3D descriptor.

    Coordinate mapping:
        norm_x * SCALE_FACTOR  →  Three.js X  (left-right)
        norm_y * SCALE_FACTOR  →  Three.js Z  (depth, front-back)
        Y axis in Three.js  =  vertical (up)

    The wall's BoxGeometry is centered at (cx, WALL_HEIGHT/2, cz).
    Rotation around Y axis aligns the box with the wall direction.
    """
    sx = wall.start_point.x * SCALE_FACTOR
    sz = wall.start_point.y * SCALE_FACTOR
    ex = wall.end_point.x * SCALE_FACTOR
    ez = wall.end_point.y * SCALE_FACTOR

    # Center position
    cx = (sx + ex) / 2
    cz = (sz + ez) / 2
    cy = WALL_HEIGHT_M / 2  # always half-height (placed on Y=0 ground plane)

    # Length in Three.js units
    length = math.sqrt((ex - sx) ** 2 + (ez - sz) ** 2)
    if length < 0.01:
        length = 0.01  # guard against zero-length walls

    # Rotation: atan2(dz, dx) → rotation around Y axis
    rotation_y = math.atan2(ez - sz, ex - sx)

    # Thickness
    thickness = WALL_THICKNESS_M.get(wall.thickness, WALL_THICKNESS_M["standard"])

    # Color
    color = WALL_COLOR_HEX.get(wall.type, "#888888")

    return Wall3D(
        id=wall.id,
        wall_type=wall.type,
        is_load_bearing=wall.is_load_bearing,
        center_x=round(cx, 4),
        center_y=round(cy, 4),
        center_z=round(cz, 4),
        length=round(length, 4),
        height=WALL_HEIGHT_M,
        thickness=thickness,
        rotation_y=round(rotation_y, 6),
        color_hex=color,
    )


# ─────────────────────────────────────────────────────────────────────────────
# ROOM → Slab3D
# ─────────────────────────────────────────────────────────────────────────────

def _build_slab(room, idx: int) -> Slab3D:
    """
    Build a thin floor slab for a room.
    Uses normalized bounding box → Three.js world coords.
    """
    bb = room.bounding_box
    cx = ((bb.x_min + bb.x_max) / 2) * SCALE_FACTOR
    cz = ((bb.y_min + bb.y_max) / 2) * SCALE_FACTOR
    width = bb.width * SCALE_FACTOR
    depth = bb.height * SCALE_FACTOR

    return Slab3D(
        room_id=room.id,
        room_name=room.name,
        center_x=round(cx, 4),
        center_z=round(cz, 4),
        width=round(max(width, 0.1), 4),
        depth=round(max(depth, 0.1), 4),
        color_index=idx % len(ROOM_SLAB_COLORS),
    )


# ─────────────────────────────────────────────────────────────────────────────
# OPENING → Opening3D
# ─────────────────────────────────────────────────────────────────────────────

def _build_opening_3d(opening) -> Opening3D:
    """
    Place door/window markers in 3D space.
    Doors sit at lower half of wall, windows at upper half.
    """
    cx = opening.location.x * SCALE_FACTOR
    cz = opening.location.y * SCALE_FACTOR

    if opening.type == "window":
        cy = WALL_HEIGHT_M * 0.65   # window center at 65% height
    else:
        cy = WALL_HEIGHT_M * 0.40   # door center at 40% height

    return Opening3D(
        id=opening.id,
        opening_type=opening.type,
        center_x=round(cx, 4),
        center_y=round(cy, 4),
        center_z=round(cz, 4),
    )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def build_3d_model(parsed: ParsedFloorPlan) -> ThreeDModel:
    """
    Main Stage 3 function.
    Takes a ParsedFloorPlan (output of Stage 2) and returns a ThreeDModel.
    """
    walls_3d = [_build_wall_3d(w, i) for i, w in enumerate(parsed.walls)]
    slabs    = [_build_slab(r, i)    for i, r in enumerate(parsed.rooms)]
    openings_3d = [_build_opening_3d(o) for o in parsed.openings]

    return ThreeDModel(
        scale=SCALE_FACTOR,
        wall_height=WALL_HEIGHT_M,
        walls_3d=walls_3d,
        slabs=slabs,
        openings_3d=openings_3d,
    )