from __future__ import annotations

from typing import Any

from engine_schema import DisplayPayload, EngineResult


ZONE_ADJUSTMENTS = {
    "street_front": -8,
    "edge_building": -3,
    "central": 0,
    "quiet_inner": 6,
    "compound_approx": 0,
    "secondary_street": -4,
    "central_inner": 0,
    "gate_side": -5,
    "commercial_edge": -6,
}

LOCATOR_CONFIDENCE_WEIGHTS = {
    "高": 1.00,
    "中": 0.90,
    "低": 0.75,
}


def _to_float(value: Any) -> float | None:
    try:
        if value in ("", None):
            return None
        return float(value)
    except Exception:
        return None


def zone_result(zone_type: str, locator_confidence: str = "中") -> EngineResult:
    score = int(ZONE_ADJUSTMENTS.get(str(zone_type or "").strip(), 0))
    confidence = float(LOCATOR_CONFIDENCE_WEIGHTS.get(str(locator_confidence or "").strip(), 0.9))
    return EngineResult(
        engine="building_engine",
        enabled=True,
        score_delta=score,
        confidence=confidence,
        category="zone",
        priority=70,
        evidence={"zone_type": zone_type, "locator_confidence": locator_confidence},
        explanation=f"楼栋位置按 {zone_type} 处理。",
        display=DisplayPayload(
            label="楼栋位置调整",
            detail=f"{zone_type}｜定位置信度 {locator_confidence}",
            value_text=f"{score:+d}",
        ),
        tags=["zone"],
    )


def building_year_result(build_year: Any) -> EngineResult:
    year = _to_float(build_year)
    score = 0
    if year is not None:
        if year >= 2025:
            score = 5
        elif year >= 2015:
            score = 3
        elif year >= 2005:
            score = 1

    return EngineResult(
        engine="building_engine",
        enabled=True,
        score_delta=int(score),
        confidence=0.82,
        category="building",
        priority=60,
        evidence={"build_year": build_year},
        explanation="建筑年份带来的居住品质修正。",
        display=DisplayPayload(
            label="建筑年份修正",
            detail=f"建成年份 {build_year or '-'}",
            value_text=f"{int(score):+d}",
        ),
        tags=["build_year"],
    )


def density_result(far_ratio: Any) -> EngineResult:
    ratio = _to_float(far_ratio)
    score = 0
    if ratio is not None:
        if ratio < 1.5:
            score = 2
        elif ratio < 2.2:
            score = 0
        elif ratio < 3.0:
            score = -3
        else:
            score = -6

    return EngineResult(
        engine="building_engine",
        enabled=True,
        score_delta=int(score),
        confidence=0.82,
        category="building",
        priority=55,
        evidence={"far_ratio": far_ratio},
        explanation="容积率带来的密度修正。",
        display=DisplayPayload(
            label="密度调整",
            detail=f"容积率 {far_ratio if far_ratio not in ('', None) else '-'}",
            value_text=f"{int(score):+d}",
        ),
        tags=["density"],
    )


def override_result(label: str, score_delta: int = 0, notes: str = "") -> EngineResult:
    return EngineResult(
        engine="override_engine",
        enabled=True,
        score_delta=int(score_delta),
        confidence=1.0,
        category="override",
        priority=100,
        evidence={"notes": notes},
        explanation=notes or "人工校正规则。",
        display=DisplayPayload(
            label=label,
            detail=notes,
            value_text=f"{int(score_delta):+d}",
        ),
        tags=["override"],
    )
