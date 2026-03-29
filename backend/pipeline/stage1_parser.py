"""
pipeline/stage1_parser.py
Stage 1 — Floor Plan Parsing

Detects walls, rooms, and openings from a floor plan image using OpenCV.
Returns a ParsedFloorPlan with normalized (0-1) coordinates.

Pipeline inside this file:
  A. Preprocess (grayscale, blur, threshold)
  B. Wall detection (Canny + HoughLinesP)
  C. Room detection (contour finding)
  D. Opening detection (door arcs + window double-lines)
  E. Room label OCR (pytesseract)
  F. Normalize all coordinates to 0-1
"""

import math
import re
import numpy as np
import cv2

# pytesseract is optional — if not installed, OCR is skipped gracefully
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import (
    GAUSSIAN_BLUR_K,
    CANNY_LOW, CANNY_HIGH,
    HOUGH_RHO, HOUGH_THETA_DEG,
    HOUGH_THRESHOLD, HOUGH_MIN_LINE_LENGTH, HOUGH_MAX_LINE_GAP,
    ROOM_MIN_AREA_FRACTION, ROOM_MAX_AREA_FRACTION,
    ASSUMED_BUILDING_WIDTH_M, PIXEL_TO_METRE,
)
from utils.image_utils import (
    normalize_point,
    pixel_length_to_metres,
    compute_line_angle_deg,
    is_horizontal,
    is_vertical,
)
from utils.geometry_utils import distance, midpoint
from models.schemas import (
    ParsedFloorPlan, Wall, Room, Opening, Point, BoundingBox
)


# ─────────────────────────────────────────────────────────────────────────────
# ROOM TYPE MAPPING
# ─────────────────────────────────────────────────────────────────────────────

_ROOM_TYPE_KEYWORDS: dict[str, list[str]] = {
    "bedroom":     ["bedroom", "bed", "master", "guest"],
    "bathroom":    ["bathroom", "bath", "toilet", "wc", "lavatory", "ensuite"],
    "kitchen":     ["kitchen", "kit"],
    "living_room": ["living", "lounge", "great", "family", "sitting"],
    "dining_room": ["dining", "dinner"],
    "foyer":       ["foyer", "entry", "entrance", "hall", "lobby"],
    "laundry":     ["laundry", "utility", "mud"],
    "corridor":    ["corridor", "passage", "hallway"],
}


def _classify_room_type(label: str) -> str:
    """Map OCR text to a room type string."""
    lower = label.lower()
    for room_type, keywords in _ROOM_TYPE_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return room_type
    return "other"


# ─────────────────────────────────────────────────────────────────────────────
# A. PREPROCESSING
# ─────────────────────────────────────────────────────────────────────────────

def _preprocess(img: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Returns (gray, blurred, binary_thresh).
    binary_thresh is inverted so room interiors are white (255).
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cleaned_gray = gray.copy()

    # --- TEXT ERASURE PASS (Inpainting) ---
    if TESSERACT_AVAILABLE:
        try:
            data = pytesseract.image_to_data(
                gray, output_type=pytesseract.Output.DICT, config="--psm 11"
            )
            for i in range(len(data['text'])):
                conf = int(data['conf'][i])
                text = data['text'][i].strip()
                
                # If valid text detected, paint it solid white so Canny/Hough ignores it
                if conf > 25 and len(text) >= 1:
                    x = data['left'][i]
                    y = data['top'][i]
                    w = data['width'][i]
                    h = data['height'][i]
                    
                    pad = 6
                    cv2.rectangle(
                        cleaned_gray, 
                        (max(0, x - pad), max(0, y - pad)), 
                        (x + w + pad, y + h + pad), 
                        255, -1
                    )
        except Exception:
            pass

    blurred = cv2.GaussianBlur(cleaned_gray, (GAUSSIAN_BLUR_K, GAUSSIAN_BLUR_K), 0)
    # Adaptive threshold handles uneven lighting better than global
    binary = cv2.adaptiveThreshold(
        blurred, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=15, C=4,
    )
    return gray, blurred, binary


# ─────────────────────────────────────────────────────────────────────────────
# B. WALL DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def _detect_walls_px(
    blurred: np.ndarray,
) -> list[tuple[int, int, int, int]]:
    """
    Run Canny + HoughLinesP to get raw wall line segments in pixel coords.
    Applies a post-detection straightening pass — snapping near-horizontal lines
    to exactly 0° (y1==y2) and near-vertical lines to exactly 90° (x1==x2).
    Returns list of (x1, y1, x2, y2).
    """
    edges = cv2.Canny(blurred, CANNY_LOW, CANNY_HIGH, apertureSize=3)
    # Dilate to close small gaps in wall lines
    kernel = np.ones((2, 2), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=1)

    lines = cv2.HoughLinesP(
        edges,
        rho=HOUGH_RHO,
        theta=math.radians(HOUGH_THETA_DEG),
        threshold=HOUGH_THRESHOLD,
        minLineLength=HOUGH_MIN_LINE_LENGTH,
        maxLineGap=HOUGH_MAX_LINE_GAP,
    )

    if lines is None:
        return []

    result: list[tuple[int, int, int, int]] = []
    for line in lines:
        x1, y1, x2, y2 = line[0]

        if is_horizontal(x1, y1, x2, y2, tol=15.0):
            # Snap to perfect horizontal: average the y coords
            avg_y = int((y1 + y2) / 2)
            result.append((int(x1), avg_y, int(x2), avg_y))
        elif is_vertical(x1, y1, x2, y2, tol=15.0):
            # Snap to perfect vertical: average the x coords
            avg_x = int((x1 + x2) / 2)
            result.append((avg_x, int(y1), avg_x, int(y2)))
        # Diagonal lines (noise) are silently dropped

    return result


def _estimate_wall_thickness_px(
    gray: np.ndarray,
    x1: int, y1: int, x2: int, y2: int,
) -> int:
    """
    Sample perpendicular cross-section at the midpoint of the wall
    to estimate thickness in pixels.
    """
    mx, my = int((x1 + x2) / 2), int((y1 + y2) / 2)
    h, w = gray.shape

    # Perpendicular direction
    dx, dy = x2 - x1, y2 - y1
    length = math.sqrt(dx * dx + dy * dy) or 1
    px, py = -dy / length, dx / length  # perpendicular unit vector

    thickness = 0
    for step in range(1, 20):
        nx, ny = int(mx + px * step), int(my + py * step)
        if 0 <= nx < w and 0 <= ny < h and gray[ny, nx] < 128:
            thickness += 1
        else:
            break

    return max(1, thickness * 2)  # both sides


def _classify_wall_thickness(thickness_px: int) -> str:
    from config import THICK_WALL_PX, THIN_WALL_PX
    if thickness_px >= THICK_WALL_PX:
        return "thick"
    if thickness_px <= THIN_WALL_PX:
        return "thin"
    return "standard"


# ─────────────────────────────────────────────────────────────────────────────
# C. ROOM DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def _detect_rooms_px(
    binary: np.ndarray,
    img_area_px: int,
) -> list[tuple[np.ndarray, tuple[int, int, int, int], float]]:
    """
    Find room contours.
    Returns list of (contour, (x,y,w,h), area_px).
    """
    min_area = img_area_px * ROOM_MIN_AREA_FRACTION
    max_area = img_area_px * ROOM_MAX_AREA_FRACTION

    # Morphological close to fill small gaps in walls
    kernel = np.ones((5, 5), np.uint8)
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    contours, hierarchy = cv2.findContours(
        closed, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
    )

    if hierarchy is None:
        return []

    rooms = []
    for i, cnt in enumerate(contours):
        area = cv2.contourArea(cnt)
        if not (min_area <= area <= max_area):
            continue
        # Only keep child contours (inside another contour) — actual rooms
        # hierarchy[0][i][3] == parent index; -1 means no parent (outer outline)
        if hierarchy[0][i][3] == -1:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        rooms.append((cnt, (x, y, w, h), area))

    # Sort by area descending
    rooms.sort(key=lambda r: r[2], reverse=True)
    return rooms


# ─────────────────────────────────────────────────────────────────────────────
# D. OPENING DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def _detect_openings_px(
    gray: np.ndarray,
    binary: np.ndarray,
) -> list[tuple[int, int, str, float]]:
    """
    Detect doors (arc symbols) and windows (double parallel lines) using gap analysis.
    Returns list of (cx, cy, type_str, pixel_width).
    """
    openings: list[tuple[int, int, str, float]] = []
    h, w = gray.shape

    # --- Doors: Hough circles for arc detection ---
    # Floor plan door symbols are quarter-circle arcs, which appear as partial
    # circles in the binary image.
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=30,
        param1=60,
        param2=25,
        minRadius=15,
        maxRadius=80,
    )
    if circles is not None:
        for x, y, r in circles[0]:
            cx, cy = int(x), int(y)
            if 0 <= cx < w and 0 <= cy < h:
                openings.append((cx, cy, "door", float(r)))

    # --- Windows: look for small structural gaps or cut-outs inside walls ---
    # Convert to RETR_LIST to catch internal bounding shapes like those in thick walls
    contours, _ = cv2.findContours(
        binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
    )
    for cnt in contours:
        bx, by, bw, bh = cv2.boundingRect(cnt)
        area = cv2.contourArea(cnt)
        # Broaden area constraint to catch glass panes inside thick gaps
        if area < 10 or area > 3000:
            continue
        aspect = bw / (bh + 1e-3)
        # Use a more relaxed multi-class aperture ratio threshold
        if aspect > 2.0 or aspect < 0.5:
            cx, cy = bx + bw // 2, by + bh // 2
            op_w = float(max(bw, bh))
            openings.append((cx, cy, "window", op_w))

    return openings


# ─────────────────────────────────────────────────────────────────────────────
# E. OCR — ROOM LABELS
# ─────────────────────────────────────────────────────────────────────────────

def _ocr_room_labels(
    gray: np.ndarray,
    rooms_bbox: list[tuple[int, int, int, int]],
) -> list[str]:
    """
    Run pytesseract on the full image and match text regions to rooms.
    Returns a list of labels aligned with rooms_bbox.
    Falls back to generic names if OCR unavailable.
    """
    if not TESSERACT_AVAILABLE:
        return [f"Room {i+1}" for i in range(len(rooms_bbox))]

    try:
        data = pytesseract.image_to_data(
            gray,
            output_type=pytesseract.Output.DICT,
            config="--psm 11 --oem 3",
        )
    except Exception:
        return [f"Room {i+1}" for i in range(len(rooms_bbox))]

    # Collect text boxes with confidence > 40
    text_boxes: list[tuple[int, int, int, int, str]] = []
    n = len(data["text"])
    for i in range(n):
        conf = int(data["conf"][i])
        text = data["text"][i].strip()
        if conf > 40 and text and re.search(r"[a-zA-Z]", text):
            tx = data["left"][i]
            ty = data["top"][i]
            tw = data["width"][i]
            th = data["height"][i]
            text_boxes.append((tx, ty, tw, th, text))

    labels: list[str] = []
    for bx, by, bw, bh in rooms_bbox:
        room_cx = bx + bw // 2
        room_cy = by + bh // 2
        best_text = ""
        best_dist = float("inf")
        for tx, ty, tw, th, text in text_boxes:
            tcx = tx + tw // 2
            tcy = ty + th // 2
            # Text must be inside the room bounding box
            if bx <= tcx <= bx + bw and by <= tcy <= by + bh:
                d = distance(room_cx, room_cy, tcx, tcy)
                if d < best_dist:
                    best_dist = d
                    best_text = text
        labels.append(best_text if best_text else f"Room {len(labels)+1}")

    return labels


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def parse_floor_plan(img: np.ndarray) -> ParsedFloorPlan:
    """
    Main Stage 1 function.
    Takes an OpenCV BGR image ndarray.
    Returns ParsedFloorPlan with normalized coords.
    """
    img_h, img_w = img.shape[:2]
    img_area = img_h * img_w

    # A. Preprocess
    gray, blurred, binary = _preprocess(img)

    # B. Wall detection
    raw_walls_px = _detect_walls_px(blurred)

    # C. Room detection
    room_data = _detect_rooms_px(binary, img_area)
    rooms_bbox_px = [r[1] for r in room_data]

    # D. Opening detection
    openings_px = _detect_openings_px(gray, binary)

    # E. OCR labels
    labels = _ocr_room_labels(gray, rooms_bbox_px)

    # ── Build Wall objects ────────────────────────────────────────────────────
    walls: list[Wall] = []
    all_wall_lines_px = []

    for i, (x1, y1, x2, y2) in enumerate(raw_walls_px):
        thick_px = _estimate_wall_thickness_px(gray, x1, y1, x2, y2)
        thickness_str = _classify_wall_thickness(thick_px)

        nx1, ny1 = normalize_point(x1, y1, img_w, img_h)
        nx2, ny2 = normalize_point(x2, y2, img_w, img_h)

        length_px = distance(x1, y1, x2, y2)
        length_m = pixel_length_to_metres(length_px, img_w, ASSUMED_BUILDING_WIDTH_M)

        all_wall_lines_px.append((x1, y1, x2, y2))

        walls.append(Wall(
            id=f"wall_{i+1}",
            type="partition",        # will be reclassified in Stage 2
            is_load_bearing=False,   # will be reclassified in Stage 2
            start_point=Point(x=nx1, y=ny1),
            end_point=Point(x=nx2, y=ny2),
            estimated_length_m=length_m,
            thickness=thickness_str,
            separates_rooms=[],
        ))

    # ── Build Room objects ────────────────────────────────────────────────────
    rooms: list[Room] = []
    total_area_px2 = 0

    for i, (cnt, (bx, by, bw, bh), area_px) in enumerate(room_data):
        label = labels[i] if i < len(labels) else f"Room {i+1}"
        total_area_px2 += area_px

        # Normalize bbox
        nx_min, ny_min = normalize_point(bx, by, img_w, img_h)
        nx_max, ny_max = normalize_point(bx + bw, by + bh, img_w, img_h)

        # Estimate real dimensions
        width_m = pixel_length_to_metres(bw, img_w, ASSUMED_BUILDING_WIDTH_M)
        height_m = pixel_length_to_metres(bh, img_w, ASSUMED_BUILDING_WIDTH_M)
        area_sqm = round(width_m * height_m, 2)

        rooms.append(Room(
            id=f"room_{i+1}",
            name=label.title(),
            type=_classify_room_type(label),
            estimated_area_sqm=area_sqm,
            dimensions={"width_m": round(width_m, 2), "length_m": round(height_m, 2)},
            bounding_box=BoundingBox(
                x_min=nx_min, y_min=ny_min,
                x_max=nx_max, y_max=ny_max,
            ),
            adjacent_rooms=[],
        ))

    # ── Build Opening objects ────────────────────────────────────────────────
    openings: list[Opening] = []
    for i, (cx, cy, op_type, px_width) in enumerate(openings_px):
        nx, ny = normalize_point(cx, cy, img_w, img_h)

        # Find nearest wall
        nearest_wall_id = "wall_1"
        best_dist = float("inf")
        for w_idx, (x1, y1, x2, y2) in enumerate(raw_walls_px):
            # Distance from opening center to wall midpoint
            wmx, wmy = midpoint(x1, y1, x2, y2)
            d = distance(cx, cy, wmx, wmy)
            if d < best_dist:
                best_dist = d
                nearest_wall_id = f"wall_{w_idx+1}"

        # Heuristic: opening near image edge → exterior
        margin = 0.08
        is_ext = (nx < margin or nx > 1 - margin or
                  ny < margin or ny > 1 - margin)

        opening_width_m = pixel_length_to_metres(px_width, img_w, ASSUMED_BUILDING_WIDTH_M)
        # Ensure a minimum practical width (e.g. 0.6m) and maximum realistic window span (4m)
        opening_width_m = max(0.6, min(opening_width_m, 4.0))

        openings.append(Opening(
            id=f"opening_{i+1}",
            type=op_type,
            location=Point(x=nx, y=ny),
            wall_id=nearest_wall_id,
            connects_rooms=[],
            estimated_width_m=round(opening_width_m, 2),
            is_exterior=is_ext,
        ))

    # ── Estimate total building area ─────────────────────────────────────────
    # Rough estimate: scale the image area using building width assumption
    total_area_sqm = pixel_length_to_metres(
        math.sqrt(total_area_px2), img_w, ASSUMED_BUILDING_WIDTH_M
    ) ** 2

    return ParsedFloorPlan(
        image_width_px=img_w,
        image_height_px=img_h,
        building_shape="rectangular",  # Stage 2 will refine
        walls=walls,
        rooms=rooms,
        openings=openings,
        estimated_total_area_sqm=round(total_area_sqm, 1),
        used_fallback=False,
    )