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
    VERTEX_SNAP_THRESHOLD_M,
    PIXEL_TO_METRE,
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

def _build_wall_3d(wall, idx: int, scale_x: float, scale_z: float) -> Wall3D:
    """
    Convert a normalized Wall to a Wall3D descriptor.

    Coordinate mapping:
        norm_x * SCALE_FACTOR  →  Three.js X  (left-right)
        norm_y * SCALE_FACTOR  →  Three.js Z  (depth, front-back)
        Y axis in Three.js  =  vertical (up)

    The wall's BoxGeometry is centered at (cx, WALL_HEIGHT/2, cz).
    Rotation around Y axis aligns the box with the wall direction.
    """
    sx = wall.start_point.x * scale_x
    sz = wall.start_point.y * scale_z
    ex = wall.end_point.x * scale_x
    ez = wall.end_point.y * scale_z

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

    # Thickness - uniform 0.2m for architectural purity
    thickness = 0.2

    # Color
    color = WALL_COLOR_HEX.get(wall.type, "#888888")

    return Wall3D(
        id=wall.id,
        wall_type=wall.type,
        is_load_bearing=wall.is_load_bearing,
        center_x=round(cx, 4),
        center_y=round(cy, 4),
        center_z=round(cz, 4),
        start_x=round(sx, 4),
        start_z=round(sz, 4),
        end_x=round(ex, 4),
        end_z=round(ez, 4),
        length=round(length, 4),
        height=WALL_HEIGHT_M,
        thickness=thickness,
        rotation_y=round(rotation_y, 6),
        color_hex=color,
    )


# ─────────────────────────────────────────────────────────────────────────────
# ROOM → Slab3D
# ─────────────────────────────────────────────────────────────────────────────

def _build_slab(room, idx: int, scale_x: float, scale_z: float) -> Slab3D:
    """
    Build a thin floor slab for a room.
    Uses normalized bounding box → Three.js world coords.
    Exports both center (for BoxGeometry) and centroid (for CSS2D label).
    """
    bb = room.bounding_box
    cx = ((bb.x_min + bb.x_max) / 2) * scale_x
    cz = ((bb.y_min + bb.y_max) / 2) * scale_z
    width = bb.width * scale_x
    depth = bb.height * scale_z

    return Slab3D(
        room_id=room.id,
        room_name=room.name,
        center_x=round(cx, 4),
        center_z=round(cz, 4),
        centroid_x=round(cx, 4),   # for rectangular rooms centroid == center
        centroid_z=round(cz, 4),
        width=round(max(width, 0.1), 4),
        depth=round(max(depth, 0.1), 4),
        color_index=idx % len(ROOM_SLAB_COLORS),
    )


# ─────────────────────────────────────────────────────────────────────────────
# OPENING → Opening3D
# ─────────────────────────────────────────────────────────────────────────────

def _build_opening_3d(opening, wall_map: dict[str, Wall3D], scale_x: float, scale_z: float) -> Opening3D:
    """
    Place door/window markers in 3D space.
    Extrapolates rotation and wall depth from the attached structural wall.
    """
    cx = opening.location.x * scale_x
    cz = opening.location.y * scale_z

    wall = wall_map.get(opening.wall_id)
    w_thickness = wall.thickness + 0.1 if wall else 0.35
    rotation_y = wall.rotation_y if wall else 0.0

    width = opening.estimated_width_m

    if opening.type == "window":
        cy = WALL_HEIGHT_M * 0.65   # window center at 65% height
        height = WALL_HEIGHT_M * 0.40
    else:
        cy = WALL_HEIGHT_M * 0.40   # door center at 40% height
        height = WALL_HEIGHT_M * 0.80

    return Opening3D(
        id=opening.id,
        opening_type=opening.type,
        center_x=round(cx, 4),
        center_y=round(cy, 4),
        center_z=round(cz, 4),
        width=round(width, 4),
        height=round(height, 4),
        thickness=round(w_thickness, 4),
        rotation_y=round(rotation_y, 4),
    )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def _snap_wall_endpoints(walls: list) -> list:
    """
    Vertex snapping pass: if two wall endpoints (in world space) are within
    VERTEX_SNAP_THRESHOLD_M of each other, snap them to their midpoint.
    Prevents Z-fighting gaps at wall intersections.
    """
    endpoints = []  # list of [x, z, wall_idx, which_end (0=start,1=end)]
    for wi, w in enumerate(walls):
        endpoints.append([w.start_x, w.start_z, wi, 0])
        endpoints.append([w.end_x, w.end_z, wi, 1])

    for i in range(len(endpoints)):
        for j in range(i + 1, len(endpoints)):
            ex1, ez1, wi1, end1 = endpoints[i]
            ex2, ez2, wi2, end2 = endpoints[j]
            dist = math.sqrt((ex1 - ex2) ** 2 + (ez1 - ez2) ** 2)
            if dist < VERTEX_SNAP_THRESHOLD_M and wi1 != wi2:
                snap_x = (ex1 + ex2) / 2
                snap_z = (ez1 + ez2) / 2
                endpoints[i][0] = snap_x
                endpoints[i][1] = snap_z
                endpoints[j][0] = snap_x
                endpoints[j][1] = snap_z

    # Write snapped values back
    snapped = list(walls)  # shallow copy list
    for ex, ez, wi, end in endpoints:
        w = snapped[wi]
        if end == 0:
            snapped[wi] = w.model_copy(update={"start_x": round(ex, 4), "start_z": round(ez, 4)})
        else:
            snapped[wi] = snapped[wi].model_copy(update={"end_x": round(ex, 4), "end_z": round(ez, 4)})
    return snapped


def build_3d_model(parsed: ParsedFloorPlan) -> ThreeDModel:
    """
    Main Stage 3 function.
    Takes a ParsedFloorPlan (output of Stage 2) and returns a ThreeDModel.
    Performs precise 1D physical segmentation of walls resolving "Empty Portals".
    """
    # --- DECOUPLE PIXEL SCALE TO FIX SQUASHED VERTICAL BUG ---
    # Map the entire model to exactly ASSUMED_BUILDING_WIDTH_M (20.0m).
    # This guarantees the geometry depth of 2.5m is always architecturally
    # proportionate to the footprint, regardless of the uploaded image resolution!
    scale_x = ASSUMED_BUILDING_WIDTH_M
    scale_z = ASSUMED_BUILDING_WIDTH_M * (parsed.image_height_px / parsed.image_width_px)

    base_walls_3d = [_build_wall_3d(w, i, scale_x, scale_z) for i, w in enumerate(parsed.walls)]
    slabs    = [_build_slab(r, i, scale_x, scale_z)    for i, r in enumerate(parsed.rooms)]
    
    wall_map = {w.id: w for w in base_walls_3d}
    openings_3d = [_build_opening_3d(o, wall_map, scale_x, scale_z) for o in parsed.openings]

    # --- 1D WALL SEGMENTATION FOR TRUE APERTURE GAPS ---
    wall_openings = {w.id: [] for w in parsed.walls}
    for op in parsed.openings:
        if op.wall_id in wall_openings:
            wall_openings[op.wall_id].append(op)

    segmented_walls_3d = []
    
    for wall, w3d in zip(parsed.walls, base_walls_3d):
        ops = wall_openings[wall.id]
        if not ops:
            segmented_walls_3d.append(w3d)
            continue
            
        sx = wall.start_point.x * scale_x
        sz = wall.start_point.y * scale_z
        ex = wall.end_point.x * scale_x
        ez = wall.end_point.y * scale_z
        
        wall_len = math.sqrt((ex - sx)**2 + (ez - sz)**2)
        if wall_len < 0.05:
            segmented_walls_3d.append(w3d)
            continue
            
        dx = (ex - sx) / wall_len
        dz = (ez - sz) / wall_len
        
        # Valid segments remaining after carving out apertures
        segments = [(0.0, wall_len)]
        
        for op in ops:
            ox = op.location.x * scale_x
            oz = op.location.y * scale_z
            
            # Project onto the wall's 1D vector line
            t = (ox - sx) * dx + (oz - sz) * dz
            w_op = op.estimated_width_m
            
            # Calculate geometric void
            op_start = t - (w_op / 2)
            op_end   = t + (w_op / 2)
            
            new_segments = []
            for seg_start, seg_end in segments:
                if op_end <= seg_start or op_start >= seg_end:
                    new_segments.append((seg_start, seg_end))
                else:
                    if op_start > seg_start:
                        new_segments.append((seg_start, op_start))
                    if op_end < seg_end:
                        new_segments.append((op_end, seg_end))
            segments = new_segments
            
        # Rehydrate surviving slivers back into Wall3D chunks
        for idx, (seg_start, seg_end) in enumerate(segments):
            seg_len = seg_end - seg_start
            if seg_len < 0.05: continue
            
            t_center = (seg_start + seg_end) / 2
            seg_cx = sx + (t_center * dx)
            seg_cz = sz + (t_center * dz)
            seg_sx = sx + (seg_start * dx)
            seg_sz = sz + (seg_start * dz)
            seg_ex = sx + (seg_end * dx)
            seg_ez = sz + (seg_end * dz)
            
            segmented_walls_3d.append(
                w3d.model_copy(update={
                    "id": f"{w3d.id}_seg_{idx}",
                    "center_x": round(seg_cx, 4),
                    "center_z": round(seg_cz, 4),
                    "start_x": round(seg_sx, 4),
                    "start_z": round(seg_sz, 4),
                    "end_x": round(seg_ex, 4),
                    "end_z": round(seg_ez, 4),
                    "length": round(seg_len, 4)
                })
            )

    # --- VERTEX SNAPPING PASS (manifold wall corners, no Z-fighting) ---
    segmented_walls_3d = _snap_wall_endpoints(segmented_walls_3d)

    # --- BASEPLATE POLYGON PROPAGATION (Triangulation Fix) ---
    baseplate_3d = []
    for pt in parsed.baseplate_polygon:
        # Map normalized [0, 1] polygon outline directly into the 20.0m scaled building area
        bp_x = pt.x * scale_x
        bp_z = pt.y * scale_z
        baseplate_3d.append([round(bp_x, 4), round(bp_z, 4)])

    return ThreeDModel(
        scale=PIXEL_TO_METRE,
        wall_height=WALL_HEIGHT_M,
        walls_3d=segmented_walls_3d,
        slabs=slabs,
        openings_3d=openings_3d,
        baseplate_polygon=baseplate_3d,
    )