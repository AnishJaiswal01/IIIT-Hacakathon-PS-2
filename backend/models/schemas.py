"""
models/schemas.py
All Pydantic models used across the PS2 pipeline.
Every stage imports from here — no type definitions anywhere else.
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 1 — Floor Plan Parsing
# ─────────────────────────────────────────────────────────────────────────────

class Point(BaseModel):
    """Normalized coordinate (0.0 – 1.0 relative to image dims)."""
    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)


class BoundingBox(BaseModel):
    """Normalized bounding box (0.0 – 1.0)."""
    x_min: float = Field(..., ge=0.0, le=1.0)
    y_min: float = Field(..., ge=0.0, le=1.0)
    x_max: float = Field(..., ge=0.0, le=1.0)
    y_max: float = Field(..., ge=0.0, le=1.0)

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min

    @property
    def center(self) -> Point:
        return Point(
            x=(self.x_min + self.x_max) / 2,
            y=(self.y_min + self.y_max) / 2,
        )


class Wall(BaseModel):
    id: str
    type: str = Field(
        ...,
        description="exterior | interior_load_bearing | partition",
    )
    is_load_bearing: bool
    start_point: Point
    end_point: Point
    estimated_length_m: float = Field(..., ge=0.0)
    thickness: str = Field(
        ...,
        description="thick | standard | thin",
    )
    separates_rooms: list[str] = Field(default_factory=list)


class Room(BaseModel):
    id: str
    name: str
    type: str = Field(
        ...,
        description=(
            "bedroom | bathroom | kitchen | living_room | dining_room "
            "| foyer | laundry | corridor | other"
        ),
    )
    estimated_area_sqm: float = Field(..., ge=0.0)
    dimensions: dict[str, float] = Field(
        default_factory=dict,
        description='{"width_m": float, "length_m": float}',
    )
    bounding_box: BoundingBox
    adjacent_rooms: list[str] = Field(default_factory=list)


class Opening(BaseModel):
    id: str
    type: str = Field(
        ...,
        description="door | window | archway | sliding_door",
    )
    location: Point
    wall_id: str
    connects_rooms: list[str] = Field(default_factory=list)
    estimated_width_m: float = Field(default=0.9, ge=0.0)
    is_exterior: bool = False


class ParsedFloorPlan(BaseModel):
    """Output of Stage 1 (parser) and Stage 2 (geometry)."""
    image_width_px: int
    image_height_px: int
    building_shape: str = Field(
        default="rectangular",
        description="rectangular | L-shaped | U-shaped | irregular",
    )
    walls: list[Wall] = Field(default_factory=list)
    rooms: list[Room] = Field(default_factory=list)
    openings: list[Opening] = Field(default_factory=list)
    baseplate_polygon: list[Point] = Field(default_factory=list)
    estimated_total_area_sqm: float = Field(default=0.0)
    # Flag set to True when OpenCV fails and manual coords are used
    used_fallback: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 3 — 3D Model
# ─────────────────────────────────────────────────────────────────────────────

class Wall3D(BaseModel):
    """Single wall ready for Three.js ExtrudeGeometry."""
    id: str
    wall_type: str          # exterior | interior_load_bearing | partition
    is_load_bearing: bool
    # Center position in world-space metres
    center_x: float
    center_y: float         # always WALL_HEIGHT / 2
    center_z: float
    # Raw endpoints in world-space (for ExtrudeGeometry)
    start_x: float
    start_z: float
    end_x: float
    end_z: float
    # Box dimensions in metres
    length: float
    height: float           # always WALL_HEIGHT (3 m)
    thickness: float        # 0.38 thick | 0.26 standard | 0.14 thin
    # Rotation around Y axis in radians
    rotation_y: float
    color_hex: str = Field(
        description="#e74c3c exterior | #f39c12 load-bearing | #3498db partition",
    )


class Slab3D(BaseModel):
    """Floor slab per room."""
    room_id: str
    room_name: str
    center_x: float
    center_z: float
    centroid_x: float       # polygon centroid for accurate label placement
    centroid_z: float
    width: float
    depth: float
    color_index: int        # index into ROOM_COLORS on frontend


class Opening3D(BaseModel):
    """Door or window marker for Three.js."""
    id: str
    opening_type: str       # door | window
    center_x: float
    center_y: float
    center_z: float
    width: float
    height: float
    thickness: float
    rotation_y: float


class ThreeDModel(BaseModel):
    """Complete 3D scene data. Frontend consumes this directly."""
    scale: float = Field(
        default=20.0,
        description="Multiplier: normalized coord → Three.js units",
    )
    wall_height: float = Field(default=3.0)
    walls_3d: list[Wall3D] = Field(default_factory=list)
    slabs: list[Slab3D] = Field(default_factory=list)
    openings_3d: list[Opening3D] = Field(default_factory=list)
    baseplate_polygon: list[list[float]] = Field(default_factory=list)  # list of [x, z] coords


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 4 — Material Analysis
# ─────────────────────────────────────────────────────────────────────────────

class MaterialOption(BaseModel):
    rank: int = Field(..., ge=1, le=3)
    material: str
    cost_level: str
    strength_level: str
    durability_level: str
    tradeoff_score: float = Field(..., ge=0.0, le=10.0)
    justification: str      # filled by Stage 5 (LLM)
    best_for: str


class MaterialRecommendation(BaseModel):
    element_type: str = Field(
        ...,
        description=(
            "exterior_walls | load_bearing_walls | partition_walls "
            "| floor_slab | columns"
        ),
    )
    element_ids: list[str] = Field(default_factory=list)
    options: list[MaterialOption] = Field(default_factory=list)


class StructuralConcern(BaseModel):
    severity: str = Field(..., description="low | medium | high")
    description: str
    affected_elements: list[str] = Field(default_factory=list)
    recommendation: str


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 5 — Explainability
# ─────────────────────────────────────────────────────────────────────────────

class Summary(BaseModel):
    overall_assessment: str
    key_structural_features: list[str] = Field(default_factory=list)
    estimated_construction_complexity: str = Field(
        ...,
        description="simple | moderate | complex",
    )
    primary_material_strategy: str


# ─────────────────────────────────────────────────────────────────────────────
# FINAL — Top-level API response
# ─────────────────────────────────────────────────────────────────────────────

class AnalysisResult(BaseModel):
    """
    The complete JSON returned by POST /analyse.
    Frontend consumes this directly.
    """
    # Metadata
    plan_id: str
    filename: str
    image_width_px: int
    image_height_px: int
    building_shape: str
    estimated_total_area_sqm: float
    used_fallback: bool = False

    # Stage 1 + 2 outputs
    rooms: list[Room] = Field(default_factory=list)
    walls: list[Wall] = Field(default_factory=list)
    openings: list[Opening] = Field(default_factory=list)

    # Stage 3 output
    model_3d: ThreeDModel

    # Stage 4 output
    material_recommendations: list[MaterialRecommendation] = Field(
        default_factory=list
    )
    structural_concerns: list[StructuralConcern] = Field(default_factory=list)

    # Stage 5 output
    summary: Optional[Summary] = None


# ─────────────────────────────────────────────────────────────────────────────
# API helper models (request / error)
# ─────────────────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    stage: Optional[str] = None     # which pipeline stage failed


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "PS2 Floor Plan API"
    version: str = "1.0.0"