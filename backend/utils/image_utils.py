"""
utils/image_utils.py
Low-level image helpers used by Stage 1.
No business logic here — just pure image I/O and transform utilities.
"""

import io
import math
import numpy as np
import cv2
from PIL import Image

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import MAX_IMAGE_DIM


def load_image_from_bytes(data: bytes) -> np.ndarray:
    """
    Convert raw uploaded bytes → OpenCV BGR ndarray.
    Accepts JPEG, PNG, WEBP — anything Pillow can open.
    """
    pil_img = Image.open(io.BytesIO(data)).convert("RGB")
    cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    return cv_img


def resize_to_max(img: np.ndarray, max_dim: int = MAX_IMAGE_DIM) -> np.ndarray:
    """
    Resize so the longer edge equals max_dim, preserving aspect ratio.
    If image is already smaller, return unchanged.
    """
    h, w = img.shape[:2]
    longer = max(h, w)
    if longer <= max_dim:
        return img
    scale = max_dim / longer
    new_w = int(w * scale)
    new_h = int(h * scale)
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)


def to_grayscale(img: np.ndarray) -> np.ndarray:
    """BGR → grayscale."""
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def normalize_point(x: float, y: float, img_w: int, img_h: int) -> tuple[float, float]:
    """
    Convert pixel (x, y) to normalized (0-1, 0-1).
    Clamps to [0, 1] to guard against off-edge detections.
    """
    nx = max(0.0, min(1.0, x / img_w))
    ny = max(0.0, min(1.0, y / img_h))
    return nx, ny


def denormalize_point(nx: float, ny: float, img_w: int, img_h: int) -> tuple[int, int]:
    """Normalized (0-1) → pixel coordinate."""
    return int(nx * img_w), int(ny * img_h)


def pixel_length_to_metres(
    pixel_length: float,
    img_w: int,
    assumed_building_width_m: float = 15.0,
) -> float:
    """
    Estimate real-world length (m) from pixel length.
    Uses the assumption that the building spans assumed_building_width_m across
    the full image width. Adjust if a scale bar is detected.
    """
    if img_w == 0:
        return 0.0
    return round((pixel_length / img_w) * assumed_building_width_m, 2)


def draw_debug_overlay(
    img: np.ndarray,
    walls_px: list[tuple[int, int, int, int]],
    room_contours: list[np.ndarray],
    opening_centers: list[tuple[int, int]],
) -> np.ndarray:
    """
    Draw detected elements on a copy of the image for debugging.
    Returns the annotated image — does NOT modify the original.
    """
    debug = img.copy()

    # Walls — blue lines
    for x1, y1, x2, y2 in walls_px:
        cv2.line(debug, (x1, y1), (x2, y2), (255, 100, 0), 2)

    # Room contours — green outlines
    for cnt in room_contours:
        cv2.drawContours(debug, [cnt], -1, (0, 200, 0), 2)

    # Opening centers — yellow dots
    for cx, cy in opening_centers:
        cv2.circle(debug, (cx, cy), 6, (0, 220, 220), -1)

    return debug


def encode_debug_image(img: np.ndarray) -> bytes:
    """Encode debug ndarray → PNG bytes (for returning in response if needed)."""
    success, buffer = cv2.imencode(".png", img)
    if not success:
        raise RuntimeError("Failed to encode debug image")
    return buffer.tobytes()


def compute_line_angle_deg(x1: float, y1: float, x2: float, y2: float) -> float:
    """Return the angle of a line in degrees [0, 180)."""
    angle = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180
    return angle


def is_horizontal(x1: float, y1: float, x2: float, y2: float, tol: float = 10.0) -> bool:
    angle = compute_line_angle_deg(x1, y1, x2, y2)
    return angle < tol or angle > (180 - tol)


def is_vertical(x1: float, y1: float, x2: float, y2: float, tol: float = 10.0) -> bool:
    angle = compute_line_angle_deg(x1, y1, x2, y2)
    return 90 - tol < angle < 90 + tol