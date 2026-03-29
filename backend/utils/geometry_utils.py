"""
utils/geometry_utils.py
Pure geometry helpers — no CV, no I/O, no Pydantic.
All functions operate on plain Python numbers / lists.
"""

import math
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Basic math
# ─────────────────────────────────────────────────────────────────────────────

def distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def midpoint(x1: float, y1: float, x2: float, y2: float) -> tuple[float, float]:
    return (x1 + x2) / 2, (y1 + y2) / 2


def line_angle_deg(x1: float, y1: float, x2: float, y2: float) -> float:
    """Angle of line in degrees [0, 180)."""
    return math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180


def line_angle_rad(x1: float, y1: float, x2: float, y2: float) -> float:
    """Angle for Three.js rotation_y — range [-π, π]."""
    return math.atan2(y2 - y1, x2 - x1)


# ─────────────────────────────────────────────────────────────────────────────
# Grid snapping
# ─────────────────────────────────────────────────────────────────────────────

def snap(value: float, grid: int) -> float:
    """Snap a single coordinate to the nearest grid multiple."""
    if grid <= 0:
        return value
    return round(round(value / grid) * grid, 6)


def snap_line(
    x1: float, y1: float, x2: float, y2: float, grid: int
) -> tuple[float, float, float, float]:
    """Snap all four endpoints of a line to a grid."""
    return snap(x1, grid), snap(y1, grid), snap(x2, grid), snap(y2, grid)


# ─────────────────────────────────────────────────────────────────────────────
# Line segment operations
# ─────────────────────────────────────────────────────────────────────────────

def segments_are_parallel(
    ax1: float, ay1: float, ax2: float, ay2: float,
    bx1: float, by1: float, bx2: float, by2: float,
    angle_tol_deg: float = 5.0,
) -> bool:
    """True if two segments are parallel within angle_tol_deg."""
    da = line_angle_deg(ax1, ay1, ax2, ay2)
    db = line_angle_deg(bx1, by1, bx2, by2)
    diff = abs(da - db) % 180
    return diff < angle_tol_deg or diff > (180 - angle_tol_deg)


def perpendicular_distance(
    px: float, py: float,
    lx1: float, ly1: float, lx2: float, ly2: float,
) -> float:
    """
    Perpendicular distance from point (px, py) to infinite line
    through (lx1, ly1) and (lx2, ly2).
    """
    dx = lx2 - lx1
    dy = ly2 - ly1
    denom = math.sqrt(dx * dx + dy * dy)
    if denom < 1e-9:
        return distance(px, py, lx1, ly1)
    return abs(dy * px - dx * py + lx2 * ly1 - ly2 * lx1) / denom


def segments_overlap_1d(
    a_min: float, a_max: float, b_min: float, b_max: float
) -> bool:
    """True if two 1-D intervals overlap."""
    return a_min <= b_max and b_min <= a_max


def merge_two_segments(
    ax1: float, ay1: float, ax2: float, ay2: float,
    bx1: float, by1: float, bx2: float, by2: float,
) -> tuple[float, float, float, float]:
    """
    Return the bounding segment that covers both input segments.
    Assumes they are collinear.
    """
    xs = [ax1, ax2, bx1, bx2]
    ys = [ay1, ay2, by1, by2]
    # Direction of segment A
    dx = ax2 - ax1
    dy = ay2 - ay1
    length = math.sqrt(dx * dx + dy * dy)
    if length < 1e-9:
        return bx1, by1, bx2, by2
    ux, uy = dx / length, dy / length
    # Project all points onto the line direction
    projs = [ux * x + uy * y for x, y in zip(xs, ys)]
    t_min, t_max = min(projs), max(projs)
    # Reconstruct endpoints from projection
    ref_x, ref_y = ax1, ay1
    x1 = ref_x + ux * (t_min - (ux * ref_x + uy * ref_y))
    y1 = ref_y + uy * (t_min - (ux * ref_x + uy * ref_y))
    x2 = ref_x + ux * (t_max - (ux * ref_x + uy * ref_y))
    y2 = ref_y + uy * (t_max - (ux * ref_x + uy * ref_y))
    return x1, y1, x2, y2


def merge_collinear_lines(
    lines: list[tuple[float, float, float, float]],
    dist_threshold: float = 8.0,
    angle_tol_deg: float = 5.0,
) -> list[tuple[float, float, float, float]]:
    """
    Given a list of (x1,y1,x2,y2) segments, merge segments that are:
    - parallel within angle_tol_deg
    - within dist_threshold pixels of each other perpendicularly
    - overlapping or nearly touching along their length

    Returns a reduced list of merged segments.
    """
    if not lines:
        return []

    merged = list(lines)
    changed = True

    while changed:
        changed = False
        result: list[tuple[float, float, float, float]] = []
        used = [False] * len(merged)

        for i in range(len(merged)):
            if used[i]:
                continue
            ax1, ay1, ax2, ay2 = merged[i]
            for j in range(i + 1, len(merged)):
                if used[j]:
                    continue
                bx1, by1, bx2, by2 = merged[j]

                if not segments_are_parallel(
                    ax1, ay1, ax2, ay2,
                    bx1, by1, bx2, by2,
                    angle_tol_deg,
                ):
                    continue

                if perpendicular_distance(bx1, by1, ax1, ay1, ax2, ay2) > dist_threshold:
                    continue

                # Check 1-D overlap along the longer axis
                if abs(ax2 - ax1) >= abs(ay2 - ay1):
                    a_min, a_max = min(ax1, ax2), max(ax1, ax2)
                    b_min, b_max = min(bx1, bx2), max(bx1, bx2)
                else:
                    a_min, a_max = min(ay1, ay2), max(ay1, ay2)
                    b_min, b_max = min(by1, by2), max(by1, by2)

                gap = max(0.0, max(a_min, b_min) - min(a_max, b_max))
                if gap > dist_threshold * 3:
                    continue

                # Merge
                ax1, ay1, ax2, ay2 = merge_two_segments(
                    ax1, ay1, ax2, ay2, bx1, by1, bx2, by2
                )
                used[j] = True
                changed = True

            result.append((ax1, ay1, ax2, ay2))
            used[i] = True

        merged = result

    return merged


# ─────────────────────────────────────────────────────────────────────────────
# Point-in-polygon
# ─────────────────────────────────────────────────────────────────────────────

def point_in_polygon(
    px: float, py: float, polygon: list[tuple[float, float]]
) -> bool:
    """
    Ray-casting test. polygon is a list of (x, y) vertex pairs.
    Returns True if (px, py) is inside the polygon.
    """
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and (
            px < (xj - xi) * (py - yi) / ((yj - yi) + 1e-12) + xi
        ):
            inside = not inside
        j = i
    return inside


# ─────────────────────────────────────────────────────────────────────────────
# Perimeter / convex-hull helpers
# ─────────────────────────────────────────────────────────────────────────────

def bounding_box_of_lines(
    lines: list[tuple[float, float, float, float]],
) -> Optional[tuple[float, float, float, float]]:
    """
    Return (min_x, min_y, max_x, max_y) of all line endpoints.
    Returns None if lines is empty.
    """
    if not lines:
        return None
    xs = [v for line in lines for v in (line[0], line[2])]
    ys = [v for line in lines for v in (line[1], line[3])]
    return min(xs), min(ys), max(xs), max(ys)


def is_on_perimeter(
    x1: float, y1: float, x2: float, y2: float,
    bbox: tuple[float, float, float, float],
    tol: float = 15.0,
) -> bool:
    """
    True if a line segment lies close to the outer bounding box edge.
    Used to classify exterior walls.
    """
    min_x, min_y, max_x, max_y = bbox

    def near(v: float, ref: float) -> bool:
        return abs(v - ref) <= tol

    # Both endpoints near the same edge?
    near_left  = near(x1, min_x) and near(x2, min_x)
    near_right = near(x1, max_x) and near(x2, max_x)
    near_top   = near(y1, min_y) and near(y2, min_y)
    near_bot   = near(y1, max_y) and near(y2, max_y)

    return near_left or near_right or near_top or near_bot


def spans_building(
    x1: float, y1: float, x2: float, y2: float,
    bbox: tuple[float, float, float, float],
    fraction: float = 0.55,
) -> bool:
    """
    True if the line covers at least `fraction` of the building width
    or height — used to detect structural spine walls.
    """
    min_x, min_y, max_x, max_y = bbox
    bw = max_x - min_x
    bh = max_y - min_y
    seg_w = abs(x2 - x1)
    seg_h = abs(y2 - y1)
    return (bw > 0 and seg_w / bw >= fraction) or (
        bh > 0 and seg_h / bh >= fraction
    )