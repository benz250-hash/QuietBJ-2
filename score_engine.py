# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine_schema import EngineResult, ScoreBreakdown, build_score_breakdown


@dataclass(slots=True)
class ScoreEngineConfig:
    base_score: int = 85
    score_low: int = 50
    score_high: int = 95
    category_weights: dict[str, float] | None = None
    global_weight: float = 1.0

    def resolved_category_weights(self) -> dict[str, float]:
        return dict(self.category_weights or {})


class ScoreEngine:
    def __init__(self, config: ScoreEngineConfig | None = None) -> None:
        self.cfg = config or ScoreEngineConfig()

    def aggregate(self, results: list[EngineResult], base_score: int | None = None) -> ScoreBreakdown:
        base = int(base_score if base_score is not None else self.cfg.base_score)
        return build_score_breakdown(
            base_score=base,
            results=results,
            score_low=self.cfg.score_low,
            score_high=self.cfg.score_high,
            category_weights=self.cfg.resolved_category_weights(),
            global_weight=self.cfg.global_weight,
        )

    def total_score(self, results: list[EngineResult], base_score: int | None = None) -> int:
        return self.aggregate(results, base_score=base_score).final_score

    def debug_dict(self, results: list[EngineResult], base_score: int | None = None) -> dict[str, Any]:
        return self.aggregate(results, base_score=base_score).to_dict()
