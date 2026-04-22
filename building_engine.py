# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from engine_schema import DisplayPayload, EngineResult


def zone_result(zone_type: str, locator_confidence: str = "中") -> EngineResult:
    return EngineResult(
        engine="building_engine",
        enabled=True,
        score_delta=0,
        confidence=1.0,
        category="zone",
        priority=70,
        evidence={"zone_type": zone_type, "locator_confidence": locator_confidence},
        explanation=f"楼栋位置证据：{zone_type}。",
        display=DisplayPayload(
            label="楼栋位置证据",
            detail=f"{zone_type}｜定位置信度 {locator_confidence}",
            value_text="",
        ),
        tags=["evidence_only", "zone"],
    )


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
            label="密度证据",
            detail=f"容积率 {far_ratio if far_ratio not in ('', None) else '-'}",
            value_text="",
        ),
        tags=["evidence_only", "density"],
    )


def override_result(label: str, score_delta: int = 0, notes: str = "") -> EngineResult:
    return EngineResult(
        engine="override_engine",
        enabled=True,
        score_delta=0,
        confidence=1.0,
        category="override",
        priority=100,
        evidence={"notes": notes, "label": label},
        explanation=notes or "人工校正规则证据。",
        display=DisplayPayload(
            label=label,
            detail=notes,
            value_text="",
        ),
        tags=["evidence_only", "override"],
    )
