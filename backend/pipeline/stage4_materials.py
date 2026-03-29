"""
pipeline/stage4_materials.py
Stage 4 — Material Analysis & Cost–Strength Tradeoff

For each structural element type, selects the best 3 materials from
materials.json using a weighted tradeoff formula and detects structural
concerns (large unsupported spans, missing columns, etc.).

Formula (PS2 spec):
  score = (strength × 0.40) + (durability × 0.35) + (cost_efficiency × 0.25)
  where weight scale: very_high=10, high=8, medium-high=6.5, medium=5,
                      low-medium=3.5, low=2
  cost_efficiency is inverted: low cost → higher score.
"""

import json
from pathlib import Path

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import (
    MATERIALS_JSON,
    SCORE_WEIGHT_STRENGTH,
    SCORE_WEIGHT_DURABILITY,
    SCORE_WEIGHT_COST_EFF,
    STRENGTH_SCORE,
    DURABILITY_SCORE,
    COST_EFFICIENCY_SCORE,
    CONCERN_SPAN_M,
    ASSUMED_BUILDING_WIDTH_M,
)
from models.schemas import (
    ParsedFloorPlan,
    MaterialOption,
    MaterialRecommendation,
    StructuralConcern,
)


# ─────────────────────────────────────────────────────────────────────────────
# LOAD MATERIAL DATABASE
# ─────────────────────────────────────────────────────────────────────────────

def _load_materials() -> dict:
    path = Path(MATERIALS_JSON)
    if not path.exists():
        raise FileNotFoundError(f"materials.json not found at {path}")
    with open(path, "r") as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────────────────────
# TRADEOFF SCORING
# ─────────────────────────────────────────────────────────────────────────────

def _compute_score(material_data: dict) -> float:
    """
    Compute tradeoff score 0-10 using weighted formula from PS2 spec.
    """
    s = STRENGTH_SCORE.get(material_data.get("strength", "medium"), 5.0)
    d = DURABILITY_SCORE.get(material_data.get("durability", "medium"), 5.0)
    c = COST_EFFICIENCY_SCORE.get(material_data.get("cost", "medium"), 6.0)
    raw = (s * SCORE_WEIGHT_STRENGTH +
           d * SCORE_WEIGHT_DURABILITY +
           c * SCORE_WEIGHT_COST_EFF)
    return round(raw, 2)


# ─────────────────────────────────────────────────────────────────────────────
# ELEMENT-TYPE → SUITABLE MATERIALS
# ─────────────────────────────────────────────────────────────────────────────

def _get_ranked_options(
    element_type: str,
    materials: dict,
    top_n: int = 3,
) -> list[MaterialOption]:
    """
    Filter materials by suitability for element_type,
    score all candidates, return top_n sorted descending.
    """
    candidates: list[tuple[str, dict, float]] = []

    for name, data in materials.items():
        suitable_for = data.get("suitable_for", [])
        if element_type in suitable_for:
            score = _compute_score(data)
            candidates.append((name, data, score))

    # Sort by score descending
    candidates.sort(key=lambda t: t[2], reverse=True)

    options: list[MaterialOption] = []
    for rank, (name, data, score) in enumerate(candidates[:top_n], start=1):
        options.append(MaterialOption(
            rank=rank,
            material=name,
            cost_level=data.get("cost", "medium"),
            strength_level=data.get("strength", "medium"),
            durability_level=data.get("durability", "medium"),
            tradeoff_score=score,
            justification="",   # Stage 5 fills this in
            best_for=data.get("best_use", ""),
        ))

    return options


# ─────────────────────────────────────────────────────────────────────────────
# WALL → ELEMENT TYPE MAPPING
# ─────────────────────────────────────────────────────────────────────────────

def _wall_type_to_element_type(wall_type: str) -> str:
    mapping = {
        "exterior":              "exterior_walls",
        "interior_load_bearing": "load_bearing_walls",
        "partition":             "partition_walls",
    }
    return mapping.get(wall_type, "partition_walls")


# ─────────────────────────────────────────────────────────────────────────────
# STRUCTURAL CONCERN DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def _detect_concerns(parsed: ParsedFloorPlan) -> list[StructuralConcern]:
    """
    Rule-based concern detection:
    1. Any wall span > CONCERN_SPAN_M without intermediate support → HIGH
    2. Rooms with large open area (> 30 sqm) → MEDIUM (column needed)
    3. L-shaped building → LOW note about load path continuity
    """
    concerns: list[StructuralConcern] = []

    # Rule 1: long wall spans
    long_walls = [
        w for w in parsed.walls
        if w.estimated_length_m > CONCERN_SPAN_M
    ]
    for w in long_walls:
        severity = "high" if w.estimated_length_m > 6.0 else "medium"
        concerns.append(StructuralConcern(
            severity=severity,
            description=(
                f"Wall {w.id} has an unsupported span of "
                f"{w.estimated_length_m:.1f} m, which exceeds the "
                f"recommended {CONCERN_SPAN_M:.0f} m limit without "
                f"intermediate column support."
            ),
            affected_elements=[w.id],
            recommendation=(
                "Add an RCC column or steel post at the midpoint of this "
                "span to prevent deflection and ensure structural integrity."
            ),
        ))

    # Rule 2: large open rooms
    large_rooms = [
        r for r in parsed.rooms
        if r.estimated_area_sqm > 30.0
    ]
    for r in large_rooms:
        concerns.append(StructuralConcern(
            severity="medium",
            description=(
                f"{r.name} has an estimated area of {r.estimated_area_sqm:.0f} sqm. "
                "Large open rooms require careful slab and beam design."
            ),
            affected_elements=[r.id],
            recommendation=(
                "Consider RCC beams spanning the shorter dimension, with "
                "columns at corners to support slab loads."
            ),
        ))

    # Rule 3: L-shaped building
    if parsed.building_shape == "L-shaped":
        concerns.append(StructuralConcern(
            severity="low",
            description=(
                "L-shaped building outline detected. Re-entrant corners "
                "concentrate seismic and wind loads."
            ),
            affected_elements=[],
            recommendation=(
                "Provide seismic separation joint or additional shear walls "
                "at the re-entrant corner. Consult a structural engineer."
            ),
        ))

    return concerns


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def analyse_materials(
    parsed: ParsedFloorPlan,
) -> tuple[list[MaterialRecommendation], list[StructuralConcern]]:
    """
    Main Stage 4 function.

    Returns:
        recommendations — one MaterialRecommendation per element type
        concerns        — list of StructuralConcern
    """
    materials = _load_materials()

    # Group wall IDs by element type
    element_type_ids: dict[str, list[str]] = {
        "exterior_walls":    [],
        "load_bearing_walls": [],
        "partition_walls":   [],
        "floor_slab":        [],
        "columns":           [],
    }

    for w in parsed.walls:
        et = _wall_type_to_element_type(w.type)
        element_type_ids[et].append(w.id)

    # floor_slab and columns don't have explicit elements in the parsed plan,
    # but we still recommend materials for them
    element_type_ids["floor_slab"] = ["slab_1"]
    element_type_ids["columns"]    = ["col_1", "col_2"]

    recommendations: list[MaterialRecommendation] = []
    for element_type, ids in element_type_ids.items():
        options = _get_ranked_options(element_type, materials, top_n=3)
        if not options:
            # Fallback: pick any 3 materials if none matched
            options = _get_ranked_options("partition_walls", materials, top_n=3)
        recommendations.append(MaterialRecommendation(
            element_type=element_type,
            element_ids=ids,
            options=options,
        ))

    # Structural concerns
    concerns = _detect_concerns(parsed)

    return recommendations, concerns