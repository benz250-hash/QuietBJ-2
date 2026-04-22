# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Literal


EngineCategory = Literal[
    "road",
    "rail",
    "poi",
    "building",
    "shielding",
    "zone",
    "override",
    "other",
]


DEFAULT_CATEGORY_WEIGHTS: dict[str, float] = {
    "road": 1.00,
    "rail": 1.00,
    "poi": 0.90,
    "building": 1.00,
    "shielding": 0.85,
    "zone": 1.00,
    "override": 1.00,
    "other": 1.00,
}


@dataclass(slots=True)
class DisplayPayload:
    label: str
    detail: str = ""
    value_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EngineResult:
    engine: str
    enabled: bool
    score_delta: int
    confidence: float
    category: EngineCategory
    priority: int
    evidence: dict[str, Any] = field(default_factory=dict)
    explanation: str = ""
    display: DisplayPayload = field(default_factory=lambda: DisplayPayload(label=""))
    tags: list[str] = field(default_factory=list)
    weight_hint: float = 1.0
    min_effective_delta: int | None = None
    max_effective_delta: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AdoptedEngineResult:
    engine: str
    category: EngineCategory
    priority: int
    raw_score_delta: int
    effective_score_delta: int
    confidence: float
    category_weight: float
    weight_hint: float
    enabled: bool
    evidence: dict[str, Any] = field(default_factory=dict)
    explanation: str = ""
    display: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ScoreBreakdown:
    base_score: int
    results: list[AdoptedEngineResult]
    raw_total_delta: int
    adopted_total_delta: int
    final_score: int
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_score": self.base_score,
            "results": [item.to_dict() for item in self.results],
            "raw_total_delta": self.raw_total_delta,
            "adopted_total_delta": self.adopted_total_delta,
            "final_score": self.final_score,
            "summary": self.summary,
        }


def clamp_int(value: float | int, low: int, high: int) -> int:
    return max(low, min(high, int(round(value))))


def clamp_confidence(value: float | int) -> float:
    return max(0.0, min(1.0, float(value)))


def sort_engine_results(results: list[EngineResult]) -> list[EngineResult]:
    return sorted(
        [item for item in results if item.enabled],
        key=lambda x: (x.priority, abs(x.score_delta)),
        reverse=True,
    )


def _apply_single_engine_weight(
    item: EngineResult,
    category_weights: dict[str, float],
    global_weight: float,
) -> AdoptedEngineResult:
    category_weight = float(category_weights.get(item.category, 1.0))
    confidence = clamp_confidence(item.confidence)
    weight_hint = max(0.0, float(item.weight_hint))
    weighted = item.score_delta * confidence * category_weight * weight_hint * global_weight
    effective = int(round(weighted))

    if item.min_effective_delta is not None:
        effective = max(effective, int(item.min_effective_delta))
    if item.max_effective_delta is not None:
        effective = min(effective, int(item.max_effective_delta))

    return AdoptedEngineResult(
        engine=item.engine,
        category=item.category,
        priority=item.priority,
        raw_score_delta=int(item.score_delta),
        effective_score_delta=effective,
        confidence=confidence,
        category_weight=category_weight,
        weight_hint=weight_hint,
        enabled=item.enabled,
        evidence=item.evidence,
        explanation=item.explanation,
        display=item.display.to_dict(),
        tags=item.tags,
    )


def adopt_engine_results(
    results: list[EngineResult],
    category_weights: dict[str, float] | None = None,
    global_weight: float = 1.0,
) -> list[AdoptedEngineResult]:
    weights = dict(DEFAULT_CATEGORY_WEIGHTS)
    if category_weights:
        weights.update(category_weights)
    ordered = sort_engine_results(results)
    adopted = [_apply_single_engine_weight(item, weights, float(global_weight)) for item in ordered]
    return sorted(adopted, key=lambda x: (x.priority, abs(x.effective_score_delta)), reverse=True)


def summarize_results(results: list[AdoptedEngineResult]) -> str:
    if not results:
        return "当前没有识别到足够强的环境影响线索。"
    negatives = [x for x in results if x.effective_score_delta < 0]
    positives = [x for x in results if x.effective_score_delta > 0]
    if negatives:
        top_neg = "与".join(item.display.get("label") or item.engine for item in negatives[:2])
        if positives:
            top_pos = "与".join(item.display.get("label") or item.engine for item in positives[:1])
            return f"当前结果显示，主要受{top_neg}影响，但也存在{top_pos}带来的缓冲。"
        return f"当前结果显示，主要受{top_neg}影响。"
    top_pos = "与".join(item.display.get("label") or item.engine for item in positives[:2])
    return f"当前结果显示，主要由{top_pos}提供缓冲。"


def build_score_breakdown(
    base_score: int,
    results: list[EngineResult],
    score_low: int = 50,
    score_high: int = 95,
    category_weights: dict[str, float] | None = None,
    global_weight: float = 1.0,
) -> ScoreBreakdown:
    adopted = adopt_engine_results(results, category_weights=category_weights, global_weight=global_weight)
    raw_total_delta = sum(item.score_delta for item in results if item.enabled)
    adopted_total_delta = sum(item.effective_score_delta for item in adopted)
    final_score = clamp_int(base_score + adopted_total_delta, score_low, score_high)
    summary = summarize_results(adopted)
    return ScoreBreakdown(
        base_score=base_score,
        results=adopted,
        raw_total_delta=raw_total_delta,
        adopted_total_delta=adopted_total_delta,
        final_score=final_score,
        summary=summary,
    )
