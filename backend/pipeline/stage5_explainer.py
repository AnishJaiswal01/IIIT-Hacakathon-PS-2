"""
pipeline/stage5_explainer.py
Stage 5 — LLM Explainability

Calls Claude Sonnet (preferred) or GPT-4o to:
  1. Write plain-English justifications for each material recommendation
  2. Write an overall structural assessment
  3. Identify key structural features
  4. Estimate construction complexity

This is the ONLY file that calls an external LLM API.
Input is structured text — no image is sent here.
"""

import json
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import (
    ANTHROPIC_API_KEY,
    OPENAI_API_KEY,
    LLM_PROVIDER,
    LLM_MODEL_CLAUDE,
    LLM_MODEL_OPENAI,
    LLM_MAX_TOKENS,
)
from models.schemas import (
    ParsedFloorPlan,
    MaterialRecommendation,
    StructuralConcern,
    Summary,
)


# ─────────────────────────────────────────────────────────────────────────────
# PROMPT BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def _build_prompt(
    parsed: ParsedFloorPlan,
    recommendations: list[MaterialRecommendation],
    concerns: list[StructuralConcern],
) -> str:
    """
    Build a structured text prompt for the LLM.
    Returns all context needed for the LLM to write good justifications.
    """
    # ── Building summary ──────────────────────────────────────────────────────
    room_lines = "\n".join(
        f"  - {r.name} ({r.type}): ~{r.estimated_area_sqm} sqm, "
        f"{r.dimensions.get('width_m', '?')}m x {r.dimensions.get('length_m', '?')}m"
        for r in parsed.rooms[:10]   # cap at 10 to keep prompt short
    )

    lb_count = sum(1 for w in parsed.walls if w.is_load_bearing)
    pt_count = len(parsed.walls) - lb_count

    wall_summary = (
        f"Total walls detected: {len(parsed.walls)} "
        f"({lb_count} load-bearing, {pt_count} partitions). "
        f"Building shape: {parsed.building_shape}. "
        f"Estimated total area: {parsed.estimated_total_area_sqm} sqm."
    )

    # Longest wall span (structural concern indicator)
    max_span = max((w.estimated_length_m for w in parsed.walls), default=0.0)

    # ── Material recs (brief) ─────────────────────────────────────────────────
    rec_lines = []
    for rec in recommendations:
        top = rec.options[0] if rec.options else None
        if top:
            rec_lines.append(
                f"  - {rec.element_type}: top pick is {top.material} "
                f"(score {top.tradeoff_score}, cost={top.cost_level}, "
                f"strength={top.strength_level})"
            )

    # ── Concerns ──────────────────────────────────────────────────────────────
    concern_lines = [
        f"  - [{c.severity.upper()}] {c.description}" for c in concerns
    ]

    prompt = f"""You are a senior structural engineer reviewing a residential floor plan analysis.

BUILDING OVERVIEW:
{wall_summary}

ROOMS:
{room_lines if room_lines else "  (No rooms detected)"}

LONGEST WALL SPAN: {max_span:.1f} m

MATERIAL RECOMMENDATIONS (top pick per element type):
{chr(10).join(rec_lines) if rec_lines else "  (None)"}

STRUCTURAL CONCERNS:
{chr(10).join(concern_lines) if concern_lines else "  None detected."}

TASK:
Return a JSON object with EXACTLY this structure (no markdown, no extra keys):
{{
  "justifications": {{
    "exterior_walls": "2-3 sentences explaining why the recommended material suits exterior walls for this specific building",
    "load_bearing_walls": "2-3 sentences for load-bearing walls",
    "partition_walls": "2-3 sentences for partition walls",
    "floor_slab": "2-3 sentences for the floor slab",
    "columns": "2-3 sentences for columns"
  }},
  "overall_assessment": "3-4 sentences: overall structural quality, dominant load system, key risks",
  "key_structural_features": [
    "Feature 1 (specific, not generic)",
    "Feature 2",
    "Feature 3"
  ],
  "estimated_construction_complexity": "simple OR moderate OR complex",
  "primary_material_strategy": "One sentence describing the overall material strategy"
}}

RULES:
- Every justification must cite specific evidence: span length, load type, room function, or tradeoff score.
- Do NOT write generic phrases like "this material is good". Be specific.
- Do NOT wrap the JSON in markdown code fences.
- Return only the JSON object.
"""
    return prompt


# ─────────────────────────────────────────────────────────────────────────────
# LLM CALLERS
# ─────────────────────────────────────────────────────────────────────────────

def _call_claude(prompt: str) -> str:
    """Call Anthropic Claude API. Returns raw text response."""
    try:
        import anthropic
    except ImportError:
        raise ImportError("anthropic package not installed. Run: pip install anthropic")

    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is not set in .env")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=LLM_MODEL_CLAUDE,
        max_tokens=LLM_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def _call_openai(prompt: str) -> str:
    """Call OpenAI API. Returns raw text response."""
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("openai package not installed. Run: pip install openai")

    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set in .env")

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=LLM_MODEL_OPENAI,
        max_tokens=LLM_MAX_TOKENS,
        messages=[
            {
                "role": "system",
                "content": "You are a senior structural engineer. Respond only with valid JSON.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content.strip()


def _call_llm(prompt: str) -> str:
    """Route to the configured LLM provider."""
    provider = LLM_PROVIDER.lower()

    if provider == "claude" and ANTHROPIC_API_KEY:
        return _call_claude(prompt)

    if provider == "openai" and OPENAI_API_KEY:
        return _call_openai(prompt)

    # Fallback: try whichever key is available
    if ANTHROPIC_API_KEY:
        return _call_claude(prompt)
    if OPENAI_API_KEY:
        return _call_openai(prompt)

    raise ValueError(
        "No LLM API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env"
    )


def _parse_llm_response(raw: str) -> dict:
    """
    Parse JSON from LLM response.
    Strips markdown fences if the model added them despite instructions.
    """
    text = raw.strip()
    # Strip ```json ... ``` fences
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```) and last line (```)
        inner = "\n".join(
            line for line in lines
            if not line.strip().startswith("```")
        )
        text = inner.strip()
    return json.loads(text)


# ─────────────────────────────────────────────────────────────────────────────
# FALLBACK (no LLM key)
# ─────────────────────────────────────────────────────────────────────────────

def _fallback_explanation(
    recommendations: list[MaterialRecommendation],
    parsed: ParsedFloorPlan,
) -> dict:
    """
    Generate basic explanations without LLM when no API key is configured.
    Used in development or when keys are missing.
    """
    lb = sum(1 for w in parsed.walls if w.is_load_bearing)
    complexity = (
        "complex" if lb > 10 else
        "moderate" if lb > 5 else
        "simple"
    )

    justifications = {}
    for rec in recommendations:
        top = rec.options[0] if rec.options else None
        if top:
            justifications[rec.element_type] = (
                f"{top.material} is recommended for {rec.element_type.replace('_', ' ')} "
                f"with a tradeoff score of {top.tradeoff_score}/10. "
                f"Cost level: {top.cost_level}, strength: {top.strength_level}. "
                f"Best used for: {top.best_for}."
            )

    return {
        "justifications": justifications,
        "overall_assessment": (
            f"This {parsed.building_shape} building has {len(parsed.rooms)} rooms "
            f"with {len(parsed.walls)} walls ({lb} load-bearing). "
            f"Estimated area: {parsed.estimated_total_area_sqm} sqm. "
            f"The structural system is {complexity} in nature."
        ),
        "key_structural_features": [
            f"{lb} load-bearing walls identified",
            f"{parsed.building_shape.title()} building footprint",
            f"Estimated floor area: {parsed.estimated_total_area_sqm} sqm",
        ],
        "estimated_construction_complexity": complexity,
        "primary_material_strategy": (
            "Mixed masonry and RCC strategy balancing cost and structural integrity."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def generate_explanations(
    parsed: ParsedFloorPlan,
    recommendations: list[MaterialRecommendation],
    concerns: list[StructuralConcern],
) -> tuple[list[MaterialRecommendation], Summary]:
    """
    Main Stage 5 function.

    Returns:
        updated_recommendations — same list but with justification strings filled
        summary                 — overall assessment and key features
    """
    # Try LLM; fall back to rule-based if no key or API error
    try:
        has_key = bool(ANTHROPIC_API_KEY or OPENAI_API_KEY)
        if has_key:
            prompt = _build_prompt(parsed, recommendations, concerns)
            raw = _call_llm(prompt)
            data = _parse_llm_response(raw)
        else:
            data = _fallback_explanation(recommendations, parsed)
    except Exception as exc:
        # Never crash the whole pipeline on LLM failure
        print(f"[Stage5] LLM call failed ({exc}), using fallback explanation.")
        data = _fallback_explanation(recommendations, parsed)

    justifications: dict[str, str] = data.get("justifications", {})

    # ── Inject justifications into recommendations ─────────────────────────
    updated_recs: list[MaterialRecommendation] = []
    for rec in recommendations:
        just_text = justifications.get(rec.element_type, "")
        # Distribute the same justification text across all options
        # (per-option details come from their scores / best_for fields)
        updated_options = []
        for opt in rec.options:
            updated_options.append(opt.model_copy(update={
                "justification": just_text if opt.rank == 1 else opt.justification
            }))
        updated_recs.append(rec.model_copy(update={"options": updated_options}))

    # ── Build Summary ─────────────────────────────────────────────────────────
    summary = Summary(
        overall_assessment=data.get(
            "overall_assessment",
            "Structural analysis complete.",
        ),
        key_structural_features=data.get("key_structural_features", []),
        estimated_construction_complexity=data.get(
            "estimated_construction_complexity", "moderate"
        ),
        primary_material_strategy=data.get(
            "primary_material_strategy",
            "Mixed masonry and RCC system.",
        ),
    )

    return updated_recs, summary