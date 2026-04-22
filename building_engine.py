# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from engine_schema import DisplayPayload, EngineResult


LOCATOR_CONFIDENCE_WEIGHTS = {
    "高": 1.00,
    "中": 0.90,
    "低": 0.75,
}


def zone_result(zone_type: str, locator_confidence: str = "中") -> EngineResult:
    zone = str(zone_type or "").strip()
    conf = str(locator_confidence or "").strip() or "中"
    return EngineResult(
        engine="building_engine",
        enabled=True,
        score_delta=0,
        confidence=float(LOCATOR_CONFIDENCE_WEIGHTS.get(conf, 0.90)),
        category="zone",
        priority=70,
        evidence={"zone_type": zone, "locator_confidence": conf},
        explanation=f"楼栋位置按 {zone or '-'} 识别，等待主引擎结算。",
        display=DisplayPayload(
            label="楼栋位置调整",
            detail=f"{zone or '-'}｜定位置信度 {conf}",
            value_text="",
        ),
        tags=["zone"],
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
        explanation="建筑年份证据，等待主引擎结算。",
        display=DisplayPayload(
            label="建筑年份修正",
            detail=f"建成年份 {build_year or '-'}",
            value_text="",
        ),
        tags=["build_year"],
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
        explanation="容积率证据，等待主引擎结算。",
        display=DisplayPayload(
            label="密度调整",
            detail=f"容积率 {far_ratio if far_ratio not in ('', None) else '-'}",
            value_text="",
        ),
        tags=["density"],
    )


def override_result(label: str, score_delta: int = 0, notes: str = "") -> EngineResult:
    # 人工校正当前只作为证据和说明，不直接在子引擎内结算。
    return EngineResult(
        engine="override_engine",
        enabled=True,
        score_delta=0,
        confidence=1.0,
        category="override",
        priority=100,
        evidence={"notes": notes, "requested_score_delta": int(score_delta)},
        explanation=notes or "人工校正规则。",
        display=DisplayPayload(
            label=label,
            detail=notes,
            value_text="",
        ),
        tags=["override"],
    )
