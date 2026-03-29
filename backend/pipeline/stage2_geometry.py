"""
pipeline/stage2_geometry.py
Stage 2 — Geometry Reconstruction

Takes ParsedFloorPlan from Stage 1 and:
  1. Merges duplicate/near-duplicate wall lines
  2. Snaps coordinates to a grid (eliminates floating-point gaps)
  3. Classifies walls as exterior / interior_load_bearing / partition
  4. Detects adjacent rooms per wall
  5. Refines building_shape (rectangular vs L-shaped etc.)
  6. Detects openings' room connections

All input/output coordinates remain normalized 0-1.
"""

import math
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import (
    SNAP_GRID_PX,
    SPINE_FRACTION,
    ASSUMED_BUILDING_WIDTH_M,
)
from utils.geometry_utils import (
    merge_collinear_lines,
    snap,
    bounding_box_of_lines,
    is_on_perimeter,
    spans_building,
    distance,
    midpoint,
    line_angle_deg,
)
from models.schemas import (
    ParsedFloorPlan, Wall, Room, Opening, Point, BoundingBox
)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _normalized_to_px(
    nx: float, ny: float, img_w: int, img_h: int
) -> tuple[float, float]:
    return nx * img_w, ny * img_h


def _px_to_normalized(
    x: float, y: float, img_w: int, img_h: int
) -> tuple[float, float]:
    return (
        max(0.0, min(1.0, x / img_w)),
        max(0.0, min(1.0, y / img_h)),
    )


def _snap_normalized(
    nx: float, ny: float, img_w: int, img_h: int, grid_px: int
) -> tuple[float, float]:
    """
    Convert to pixels, snap, convert back. Operates in pixel space
    so the grid_px value is meaningful.
    """
    px_x = snap(nx * img_w, grid_px)
    px_y = snap(ny * img_h, grid_px)
    return _px_to_normalized(px_x, px_y, img_w, img_h)


# ─────────────────────────────────────────────────────────────────────────────
# 1. MERGE DUPLICATE WALLS
# ─────────────────────────────────────────────────────────────────────────────

def _merge_walls(
    walls: list[Wall], img_w: int, img_h: int
) -> list[Wall]:
    """
    Convert walls to pixel tuples, run merge_collinear_lines,
    convert back to Wall objects.
    Preserves thickness of the "dominant" (longest) segment per group.
    """
    if not walls:
        return []

    # Build pixel segments, keeping metadata in a parallel list
    px_lines: list[tuple[float, float, float, float]] = []
    for w in walls:
        x1, y1 = _normalized_to_px(w.start_point.x, w.start_point.y, img_w, img_h)
        x2, y2 = _normalized_to_px(w.end_point.x, w.end_point.y, img_w, img_h)
        px_lines.append((x1, y1, x2, y2))

    merged_px = merge_collinear_lines(
        px_lines,
        dist_threshold=12.0,
        angle_tol_deg=6.0,
    )

    # For each merged line, find the original wall with the closest midpoint
    # to inherit thickness classification
    merged_walls: list[Wall] = []
    for idx, (x1, y1, x2, y2) in enumerate(merged_px):
        mx, my = midpoint(x1, y1, x2, y2)

        best_wall = walls[0]
        best_dist = float("inf")
        for w in walls:
            wx1, wy1 = _normalized_to_px(
                w.start_point.x, w.start_point.y, img_w, img_h
            )
            wx2, wy2 = _normalized_to_px(
                w.end_point.x, w.end_point.y, img_w, img_h
            )
            wmx, wmy = midpoint(wx1, wy1, wx2, wy2)
            d = distance(mx, my, wmx, wmy)
            if d < best_dist:
                best_dist = d
                best_wall = w

        nx1, ny1 = _px_to_normalized(x1, y1, img_w, img_h)
        nx2, ny2 = _px_to_normalized(x2, y2, img_w, img_h)

        length_px = distance(x1, y1, x2, y2)
        length_m = round(
            (length_px / img_w) * ASSUMED_BUILDING_WIDTH_M, 2
        )

        merged_walls.append(Wall(
            id=f"wall_{idx+1}",
            type=best_wall.type,
            is_load_bearing=best_wall.is_load_bearing,
            start_point=Point(x=nx1, y=ny1),
            end_point=Point(x=nx2, y=ny2),
            estimated_length_m=length_m,
            thickness=best_wall.thickness,
            separates_rooms=[],
        ))

    return merged_walls


# ─────────────────────────────────────────────────────────────────────────────
# 2. SNAP COORDINATES
# ─────────────────────────────────────────────────────────────────────────────

def _snap_all_coords(
    walls: list[Wall], img_w: int, img_h: int
) -> list[Wall]:
    snapped = []
    for w in walls:
        sx1, sy1 = _snap_normalized(
            w.start_point.x, w.start_point.y, img_w, img_h, SNAP_GRID_PX
        )
        sx2, sy2 = _snap_normalized(
            w.end_point.x, w.end_point.y, img_w, img_h, SNAP_GRID_PX
        )
        snapped.append(w.model_copy(update={
            "start_point": Point(x=sx1, y=sy1),
            "end_point":   Point(x=sx2, y=sy2),
        }))
    return snapped


# ─────────────────────────────────────────────────────────────────────────────
# 3. CLASSIFY WALLS
# ─────────────────────────────────────────────────────────────────────────────

def _classify_walls(
    walls: list[Wall], img_w: int, img_h: int
) -> list[Wall]:
    """
    Apply three rules in priority order:
    1. On perimeter → exterior (always load-bearing)
    2. Spans > SPINE_FRACTION of building → interior_load_bearing
    3. Otherwise → partition
    Also uses thickness: thick = at least interior_load_bearing.
    """
    if not walls:
        return walls

    # Collect pixel endpoints to find bounding box
    px_lines = []
    for w in walls:
        x1, y1 = _normalized_to_px(w.start_point.x, w.start_point.y, img_w, img_h)
        x2, y2 = _normalized_to_px(w.end_point.x, w.end_point.y, img_w, img_h)
        px_lines.append((x1, y1, x2, y2))

    bbox = bounding_box_of_lines(px_lines)
    if bbox is None:
        return walls

    classified = []
    for i, w in enumerate(walls):
        x1, y1 = px_lines[i][0], px_lines[i][1]
        x2, y2 = px_lines[i][2], px_lines[i][3]

        # Rule 1: perimeter?
        if is_on_perimeter(x1, y1, x2, y2, bbox, tol=20.0):
            wall_type = "exterior"
            load_bearing = True

        # Rule 2: structural spine (long interior wall)?
        elif spans_building(x1, y1, x2, y2, bbox, fraction=SPINE_FRACTION):
            wall_type = "interior_load_bearing"
            load_bearing = True

        # Rule 3: thickness override
        elif w.thickness == "thick":
            wall_type = "interior_load_bearing"
            load_bearing = True

        else:
            wall_type = "partition"
            load_bearing = False

        classified.append(w.model_copy(update={
            "type": wall_type,
            "is_load_bearing": load_bearing,
        }))

    return classified


# ─────────────────────────────────────────────────────────────────────────────
# 4. ROOM ADJACENCY
# ─────────────────────────────────────────────────────────────────────────────

def _find_adjacent_rooms(rooms: list[Room]) -> list[Room]:
    """
    Two rooms are adjacent if their bounding boxes share an edge
    (i.e. x_max of one ≈ x_min of other, with overlapping y ranges, etc.).
    """
    tol = 0.03  # 3% tolerance in normalized space

    updated = [r.model_copy() for r in rooms]

    for i, r1 in enumerate(updated):
        for j, r2 in enumerate(updated):
            if i == j:
                continue

            b1, b2 = r1.bounding_box, r2.bounding_box

            # Shared vertical edge (r1 right ≈ r2 left, or vice versa)
            shared_v = (
                abs(b1.x_max - b2.x_min) < tol or
                abs(b2.x_max - b1.x_min) < tol
            )
            v_overlap = (
                min(b1.y_max, b2.y_max) - max(b1.y_min, b2.y_min) > tol
            )

            # Shared horizontal edge
            shared_h = (
                abs(b1.y_max - b2.y_min) < tol or
                abs(b2.y_max - b1.y_min) < tol
            )
            h_overlap = (
                min(b1.x_max, b2.x_max) - max(b1.x_min, b2.x_min) > tol
            )

            if (shared_v and v_overlap) or (shared_h and h_overlap):
                adj = updated[i].adjacent_rooms
                if r2.id not in adj:
                    updated[i] = updated[i].model_copy(update={
                        "adjacent_rooms": adj + [r2.id]
                    })

    return updated


# ─────────────────────────────────────────────────────────────────────────────
# 5. WALL ↔ ROOM SEPARATION
# ─────────────────────────────────────────────────────────────────────────────

def _find_wall_room_separation(
    walls: list[Wall], rooms: list[Room]
) -> list[Wall]:
    """
    For each wall, find which rooms it separates by checking which
    room bounding boxes are on either side.
    """
    updated_walls = []
    for w in walls:
        wx1, wy1 = w.start_point.x, w.start_point.y
        wx2, wy2 = w.end_point.x, w.end_point.y
        wmx, wmy = midpoint(wx1, wy1, wx2, wy2)

        close_rooms = []
        for r in rooms:
            bb = r.bounding_box
            # Expand bbox slightly and check if wall midpoint is near it
            pad = 0.05
            if (bb.x_min - pad <= wmx <= bb.x_max + pad and
                    bb.y_min - pad <= wmy <= bb.y_max + pad):
                close_rooms.append(r.id)

        updated_walls.append(w.model_copy(update={
            "separates_rooms": close_rooms[:2]  # at most 2
        }))

    return updated_walls


# ─────────────────────────────────────────────────────────────────────────────
# 6. OPENING ↔ ROOM CONNECTIONS
# ─────────────────────────────────────────────────────────────────────────────

def _find_opening_room_connections(
    openings: list[Opening], rooms: list[Room]
) -> list[Opening]:
    updated = []
    for op in openings:
        ox, oy = op.location.x, op.location.y
        connected = []
        for r in rooms:
            bb = r.bounding_box
            pad = 0.06
            if (bb.x_min - pad <= ox <= bb.x_max + pad and
                    bb.y_min - pad <= oy <= bb.y_max + pad):
                connected.append(r.id)
        updated.append(op.model_copy(update={
            "connects_rooms": connected[:2]
        }))
    return updated


# ─────────────────────────────────────────────────────────────────────────────
# 7. BUILDING SHAPE DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def _detect_building_shape(rooms: list[Room]) -> str:
    """
    Heuristic: if total room bounding box coverage has a large empty corner,
    it's L-shaped. Otherwise rectangular.
    """
    if not rooms:
        return "rectangular"

    all_x = [r.bounding_box.x_min for r in rooms] + [r.bounding_box.x_max for r in rooms]
    all_y = [r.bounding_box.y_min for r in rooms] + [r.bounding_box.y_max for r in rooms]

    total_w = max(all_x) - min(all_x)
    total_h = max(all_y) - min(all_y)
    total_area = total_w * total_h

    room_area_sum = sum(
        r.bounding_box.width * r.bounding_box.height for r in rooms
    )

    coverage = room_area_sum / total_area if total_area > 0 else 1.0

    if coverage < 0.70:
        return "L-shaped"
    return "rectangular"


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def reconstruct_geometry(parsed: ParsedFloorPlan) -> ParsedFloorPlan:
    """
    Main Stage 2 function.
    Takes ParsedFloorPlan from Stage 1, returns improved ParsedFloorPlan.
    """
    img_w = parsed.image_width_px
    img_h = parsed.image_height_px

    walls = list(parsed.walls)
    rooms = list(parsed.rooms)
    openings = list(parsed.openings)

    # Step 1: merge duplicate walls
    if walls:
        walls = _merge_walls(walls, img_w, img_h)

    # Step 2: snap coordinates to grid
    if walls:
        walls = _snap_all_coords(walls, img_w, img_h)

    # Step 3: classify walls (exterior / load-bearing / partition)
    if walls:
        walls = _classify_walls(walls, img_w, img_h)

    # Step 4: room adjacency
    if rooms:
        rooms = _find_adjacent_rooms(rooms)

    # Step 5: wall-room separation
    if walls and rooms:
        walls = _find_wall_room_separation(walls, rooms)

    # Step 6: opening-room connections
    if openings and rooms:
        openings = _find_opening_room_connections(openings, rooms)

    # Step 7: building shape
    building_shape = _detect_building_shape(rooms)

    return parsed.model_copy(update={
        "walls": walls,
        "rooms": rooms,
        "openings": openings,
        "building_shape": building_shape,
    })