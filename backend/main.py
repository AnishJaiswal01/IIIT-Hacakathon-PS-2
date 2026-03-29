"""
main.py
FastAPI entry point — PS2 Autonomous Structural Intelligence System

Routes:
  POST /analyse        Upload floor plan image → full AnalysisResult JSON
  GET  /health         Health check
  GET  /materials      Return the starter material database
"""

import uuid
import traceback
import json
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import MATERIALS_JSON
from utils.image_utils import load_image_from_bytes, resize_to_max
from pipeline.stage1_parser import parse_floor_plan
from pipeline.stage2_geometry import reconstruct_geometry
from pipeline.stage3_model import build_3d_model
from pipeline.stage4_materials import analyse_materials
from pipeline.stage5_explainer import generate_explanations
from models.schemas import (
    AnalysisResult,
    ErrorResponse,
    HealthResponse,
    ParsedFloorPlan,
    Wall, Room, Opening, Point, BoundingBox,
)

# ─────────────────────────────────────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="PS2 — Autonomous Structural Intelligence System",
    description="Floor Plan Parser · 3D Generator · Material Optimiser",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
MAX_FILE_SIZE_MB = 20


# ─────────────────────────────────────────────────────────────────────────────
# FALLBACK PLAN
# ─────────────────────────────────────────────────────────────────────────────

def _minimal_fallback(img_w: int, img_h: int) -> ParsedFloorPlan:
    """
    When OpenCV detects zero walls/rooms, use a hardcoded rectangular plan
    so Stages 3-5 still run. Disclosed via used_fallback=True.
    """
    walls = [
        Wall(id="wall_1", type="exterior", is_load_bearing=True,
             start_point=Point(x=0.05, y=0.05), end_point=Point(x=0.95, y=0.05),
             estimated_length_m=14.0, thickness="thick"),
        Wall(id="wall_2", type="exterior", is_load_bearing=True,
             start_point=Point(x=0.95, y=0.05), end_point=Point(x=0.95, y=0.95),
             estimated_length_m=9.0, thickness="thick"),
        Wall(id="wall_3", type="exterior", is_load_bearing=True,
             start_point=Point(x=0.05, y=0.95), end_point=Point(x=0.95, y=0.95),
             estimated_length_m=14.0, thickness="thick"),
        Wall(id="wall_4", type="exterior", is_load_bearing=True,
             start_point=Point(x=0.05, y=0.05), end_point=Point(x=0.05, y=0.95),
             estimated_length_m=9.0, thickness="thick"),
        Wall(id="wall_5", type="interior_load_bearing", is_load_bearing=True,
             start_point=Point(x=0.5, y=0.05), end_point=Point(x=0.5, y=0.95),
             estimated_length_m=9.0, thickness="standard"),
        Wall(id="wall_6", type="partition", is_load_bearing=False,
             start_point=Point(x=0.05, y=0.5), end_point=Point(x=0.5, y=0.5),
             estimated_length_m=7.0, thickness="thin"),
    ]
    rooms = [
        Room(id="room_1", name="Living Room", type="living_room",
             estimated_area_sqm=25.0,
             dimensions={"width_m": 7.0, "length_m": 4.5},
             bounding_box=BoundingBox(x_min=0.05, y_min=0.05, x_max=0.5, y_max=0.5)),
        Room(id="room_2", name="Bedroom 1", type="bedroom",
             estimated_area_sqm=15.0,
             dimensions={"width_m": 7.0, "length_m": 4.5},
             bounding_box=BoundingBox(x_min=0.05, y_min=0.5, x_max=0.5, y_max=0.95)),
        Room(id="room_3", name="Kitchen", type="kitchen",
             estimated_area_sqm=12.0,
             dimensions={"width_m": 7.0, "length_m": 4.5},
             bounding_box=BoundingBox(x_min=0.5, y_min=0.05, x_max=0.95, y_max=0.5)),
        Room(id="room_4", name="Bathroom", type="bathroom",
             estimated_area_sqm=6.0,
             dimensions={"width_m": 7.0, "length_m": 4.5},
             bounding_box=BoundingBox(x_min=0.5, y_min=0.5, x_max=0.95, y_max=0.95)),
    ]
    return ParsedFloorPlan(
        image_width_px=img_w,
        image_height_px=img_h,
        building_shape="rectangular",
        walls=walls,
        rooms=rooms,
        openings=[],
        estimated_total_area_sqm=130.0,
        used_fallback=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse()


@app.get("/materials")
def get_materials():
    path = Path(MATERIALS_JSON)
    if not path.exists():
        raise HTTPException(status_code=500, detail="materials.json not found")
    with open(path, "r") as f:
        return json.load(f)


@app.post("/analyse")
async def analyse(
    file: UploadFile = File(...),
    plan_id: str = Query(default="", description="Optional plan ID"),
):
    """
    Full 5-stage pipeline:
    Stage 1 OpenCV parse → Stage 2 geometry → Stage 3 3D model
    → Stage 4 materials → Stage 5 LLM explain → AnalysisResult JSON
    """
    # Validate
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported type '{file.content_type}'. Use PNG/JPG/WEBP.",
        )

    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File too large (max {MAX_FILE_SIZE_MB}MB).")

    if not plan_id:
        plan_id = str(uuid.uuid4())[:8]

    # Stage 1
    try:
        img = load_image_from_bytes(raw_bytes)
        img = resize_to_max(img)
        img_h, img_w = img.shape[:2]
        parsed = parse_floor_plan(img)
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"success": False, "error": f"Stage 1 failed: {exc}", "stage": "stage1_parser"})

    # Fallback if empty
    if not parsed.walls and not parsed.rooms:
        print("[main] OpenCV found nothing — using fallback.")
        parsed = _minimal_fallback(img_w, img_h)

    # Stage 2
    try:
        parsed = reconstruct_geometry(parsed)
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"success": False, "error": f"Stage 2 failed: {exc}", "stage": "stage2_geometry"})

    # Stage 3
    try:
        model_3d = build_3d_model(parsed)
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"success": False, "error": f"Stage 3 failed: {exc}", "stage": "stage3_model"})

    # Stage 4
    try:
        recommendations, concerns = analyse_materials(parsed)
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"success": False, "error": f"Stage 4 failed: {exc}", "stage": "stage4_materials"})

    # Stage 5 (non-fatal)
    summary = None
    try:
        recommendations, summary = generate_explanations(parsed, recommendations, concerns)
    except Exception as exc:
        traceback.print_exc()
        print(f"[main] Stage 5 non-fatal failure: {exc}")

    # Assemble result
    result = AnalysisResult(
        plan_id=plan_id,
        filename=file.filename or "floor_plan",
        image_width_px=parsed.image_width_px,
        image_height_px=parsed.image_height_px,
        building_shape=parsed.building_shape,
        estimated_total_area_sqm=parsed.estimated_total_area_sqm,
        used_fallback=parsed.used_fallback,
        rooms=parsed.rooms,
        walls=parsed.walls,
        openings=parsed.openings,
        model_3d=model_3d,
        material_recommendations=recommendations,
        structural_concerns=concerns,
        summary=summary,
    )

    return result.model_dump()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)