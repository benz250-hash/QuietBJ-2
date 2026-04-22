# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from engine_schema import DisplayPayload, EngineResult


def _to_float(value: Any) -> float | None:
    try:
        if value in ("", None):
            return None
        return float(value)
    except Exception:
        return None


def building_year_result(build_year: Any) -> EngineResult:
    return EngineResult(
        engine="building_engine",
        enabled=True,
        score_delta=0,
        confidence=0.82,
        category="building",
        priority=60,
        evidence={"build_year": build_year},
        explanation="建筑年份证据。",
        display=DisplayPayload(
            label="建筑年份",
            detail=f"建成年份 {build_year or '-'}",
            value_text="",
        ),
        tags=["evidence_only", "build_year"],
    )


def density_result(far_ratio: Any) -> EngineResult:
    return EngineResult(
        engine="building_engine",
        enabled=True,
        score_delta=0,
        confidence=0.82,
        category="building",
        priority=55,
        evidence={"far_ratio": far_ratio},
        explanation="容积率证据。",
        display=DisplayPayload(
            label="建筑密度",
            detail=f"容积率 {far_ratio if far_ratio not in ('', None) else '-'}",
            value_text="",
        ),
        tags=["evidence_only", "density"],
    )


def zone_result(zone_type: str, locator_confidence: str = "中") -> EngineResult:
    return EngineResult(
        engine="building_engine",
        enabled=False,
        score_delta=0,
        confidence=0.0,
        category="zone",
        priority=0,
        evidence={"zone_type": zone_type, "locator_confidence": locator_confidence},
        explanation="旧楼栋位置调整逻辑已退出主评分链。",
        display=DisplayPayload(
            label="旧位置逻辑",
            detail=f"{zone_type}｜{locator_confidence}",
            value_text="",
        ),
        tags=["deprecated"],
    )


def override_result(label: str, score_delta: int = 0, notes: str = "") -> EngineResult:
    return EngineResult(
        engine="override_engine",
        enabled=False,
        score_delta=0,
        confidence=0.0,
        category="override",
        priority=0,
        evidence={"notes": notes, "label": label},
        explanation="旧人工校正逻辑已退出主评分链。",
        display=DisplayPayload(label=label or "旧人工校正", detail=notes, value_text=""),
        tags=["deprecated"],
    )
