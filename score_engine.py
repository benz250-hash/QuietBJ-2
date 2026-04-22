# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine_schema import DisplayPayload, EngineResult, ScoreBreakdown, build_score_breakdown


@dataclass(slots=True)
class ScoreEngineConfig:
    base_score: int = 85
    score_low: int = 50
    score_high: int = 95
    category_weights: dict[str, float] | None = None
    global_weight: float = 1.0

    expressway_bands: list[tuple[int, int]] = None  # type: ignore[assignment]
    arterial_bands: list[tuple[int, int]] = None  # type: ignore[assignment]
    secondary_bands: list[tuple[int, int]] = None  # type: ignore[assignment]
    local_bands: list[tuple[int, int]] = None  # type: ignore[assignment]
    internal_bands: list[tuple[int, int]] = None  # type: ignore[assignment]
    rail_bands: list[tuple[int, int]] = None  # type: ignore[assignment]
    school_bands: list[tuple[int, int]] = None  # type: ignore[assignment]
    hospital_bands: list[tuple[int, int]] = None  # type: ignore[assignment]
    commercial_bands: list[tuple[int, int]] = None  # type: ignore[assignment]
    restaurant_bands: list[tuple[int, int]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.expressway_bands is None:
            self.expressway_bands = [(30, 18), (60, 16), (100, 14), (150, 12), (220, 10), (320, 7), (450, 4), (650, 2)]
        if self.arterial_bands is None:
            self.arterial_bands = [(20, 12), (40, 10), (60, 8), (90, 7), (120, 6), (160, 4), (220, 3), (320, 1)]
        if self.secondary_bands is None:
            self.secondary_bands = [(15, 7), (30, 6), (50, 5), (80, 3), (120, 2), (180, 1)]
        if self.local_bands is None:
            self.local_bands = [(8, 3), (15, 2), (25, 2), (40, 1), (60, 0)]
        if self.internal_bands is None:
            self.internal_bands = [(5, 2), (10, 1), (18, 1), (30, 0)]
        if self.rail_bands is None:
            self.rail_bands = [(40, 9), (80, 7), (120, 6), (180, 4), (260, 2), (400, 1)]
        if self.school_bands is None:
            self.school_bands = [(40, 5), (80, 4), (120, 3), (180, 2), (260, 1)]
        if self.hospital_bands is None:
            self.hospital_bands = [(50, 4), (100, 3), (160, 2), (250, 1)]
        if self.commercial_bands is None:
            self.commercial_bands = [(20, 7), (40, 6), (70, 5), (110, 3), (170, 2), (260, 1)]
        if self.restaurant_bands is None:
            self.restaurant_bands = [(15, 6), (30, 5), (50, 4), (80, 3), (130, 2), (220, 1)]

    def resolved_category_weights(self) -> dict[str, float]:
        return dict(self.category_weights or {})


class ScoreEngine:
    def __init__(self, config: ScoreEngineConfig | None = None) -> None:
        self.cfg = config or ScoreEngineConfig()

    def band_score(self, distance_m: int | None, bands: list[tuple[int, int]]) -> int:
        if distance_m is None:
            return 0
        for upper, score in bands:
            if distance_m <= upper:
                return score
        return 0

    def _score_road(self, item: EngineResult) -> EngineResult | None:
        evidence = dict(item.evidence or {})
        kind = str(evidence.get("road_kind", "secondary")).strip()
        distance = evidence.get("distance_m")
        if kind == "expressway":
            penalty = self.band_score(distance, self.cfg.expressway_bands)
            label = "高速系统"
        elif kind == "arterial":
            penalty = self.band_score(distance, self.cfg.arterial_bands)
            label = "主干路"
        elif kind == "secondary":
            penalty = self.band_score(distance, self.cfg.secondary_bands)
            label = "次干路"
        elif kind == "local":
            penalty = self.band_score(distance, self.cfg.local_bands)
            label = "小路/支路"
        else:
            penalty = self.band_score(distance, self.cfg.internal_bands)
            label = "小区内部路"
        if penalty <= 0:
            return None
        return EngineResult(
            engine=item.engine,
            enabled=True,
            score_delta=-penalty,
            confidence=item.confidence,
            category="road",
            priority=item.priority,
            evidence={**evidence, "penalty": penalty, "impact_group": "traffic"},
            explanation=item.explanation,
            display=DisplayPayload(
                label=label,
                detail=item.display.detail,
                value_text=f"-{penalty}",
            ),
            tags=[tag for tag in item.tags if tag != "evidence_only"] + ["traffic"],
        )

    def _score_poi_or_rail(self, item: EngineResult) -> EngineResult | None:
        evidence = dict(item.evidence or {})
        distance = evidence.get("distance_m")
        category = item.category
        poi_kind = str(evidence.get("poi_kind", "")).strip()
        penalty = 0
        label = item.display.label or poi_kind
        impact_group = "local_life"
        if category == "rail" or poi_kind == "rail":
            penalty = self.band_score(distance, self.cfg.rail_bands)
            label = "轨道"
            category = "rail"
            impact_group = "traffic"
        elif poi_kind == "school":
            penalty = self.band_score(distance, self.cfg.school_bands)
            label = "学校"
        elif poi_kind == "hospital":
            penalty = self.band_score(distance, self.cfg.hospital_bands)
            label = "医院"
        elif poi_kind == "commercial":
            penalty = self.band_score(distance, self.cfg.commercial_bands)
            label = "本地生活噪音"
        elif poi_kind == "restaurant":
            penalty = self.band_score(distance, self.cfg.restaurant_bands)
            label = "餐饮"
        if penalty <= 0:
            return None
        return EngineResult(
            engine=item.engine,
            enabled=True,
            score_delta=-penalty,
            confidence=item.confidence,
            category=category,  # type: ignore[arg-type]
            priority=item.priority,
            evidence={**evidence, "penalty": penalty, "impact_group": impact_group},
            explanation=item.explanation,
            display=DisplayPayload(
                label=label,
                detail=item.display.detail,
                value_text=f"-{penalty}",
            ),
            tags=[tag for tag in item.tags if tag != "evidence_only"] + [impact_group],
        )

    def _score_building(self, item: EngineResult) -> EngineResult | None:
        evidence = dict(item.evidence or {})
        tags = list(item.tags or [])
        if "build_year" in tags:
            try:
                year = float(evidence.get("build_year"))
            except Exception:
                year = None
            score = 0
            if year is not None:
                if year >= 2025:
                    score = 5
                elif year >= 2015:
                    score = 3
                elif year >= 2005:
                    score = 1
            if score == 0:
                return None
            return EngineResult(
                engine=item.engine,
                enabled=True,
                score_delta=score,
                confidence=item.confidence,
                category="building",
                priority=item.priority,
                evidence={**evidence, "adjustment": score},
                explanation="建筑年份带来的居住品质修正。",
                display=DisplayPayload(label="建筑条件调整", detail=item.display.detail, value_text=f"+{score}"),
                tags=["build_year"],
            )
        if "density" in tags:
            try:
                ratio = float(evidence.get("far_ratio"))
            except Exception:
                ratio = None
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
            if score == 0:
                return None
            return EngineResult(
                engine=item.engine,
                enabled=True,
                score_delta=score,
                confidence=item.confidence,
                category="building",
                priority=item.priority,
                evidence={**evidence, "adjustment": score},
                explanation="容积率带来的密度修正。",
                display=DisplayPayload(label="建筑条件调整", detail=item.display.detail, value_text=f"{score:+d}"),
                tags=["density"],
            )
        return None

    def _score_shielding(self, item: EngineResult, road_penalty_by_name: dict[str, int]) -> EngineResult | None:
        evidence = dict(item.evidence or {})
        road_name = str(evidence.get("road_name", "")).strip()
        raw = int(road_penalty_by_name.get(road_name, 0))
        if raw <= 0:
            return None
        level = str(evidence.get("shielding_level", "none")).strip()
        road_kind = str(evidence.get("road_kind", "secondary")).strip()
        if road_kind in {"local", "internal"}:
            factor_map = {"partial": 0.85, "strong": 0.70}
        else:
            factor_map = {"partial": 0.75, "strong": 0.55}
        factor = float(factor_map.get(level, 1.0))
        adjusted = max(1, round(raw * factor)) if raw > 0 else 0
        correction = raw - adjusted
        if correction <= 0:
            return None
        return EngineResult(
            engine=item.engine,
            enabled=True,
            score_delta=correction,
            confidence=item.confidence,
            category="shielding",
            priority=item.priority,
            evidence={
                **evidence,
                "raw_impact": raw,
                "adjusted_impact": adjusted,
                "correction": correction,
            },
            explanation="前排遮挡对道路影响做折减。",
            display=DisplayPayload(
                label="遮挡修正",
                detail=f"原始影响 {raw} → 遮挡后 {adjusted}｜{level}｜挡住 {evidence.get('blocker_count', 0)} 栋",
                value_text=f"+{correction}",
            ),
            tags=["shielding"],
            max_effective_delta=correction,
        )

    def _score_results(self, evidence_results: list[EngineResult]) -> list[EngineResult]:
        scored: list[EngineResult] = []
        shielding_evidence: list[EngineResult] = []
        road_penalty_by_name: dict[str, int] = {}

        for item in evidence_results:
            if not item.enabled:
                continue
            if item.category == "road":
                scored_item = self._score_road(item)
                if scored_item:
                    scored.append(scored_item)
                    road_name = str(scored_item.evidence.get("road_name", "")).strip()
                    if road_name:
                        road_penalty_by_name[road_name] = abs(int(scored_item.score_delta))
            elif item.category in {"rail", "poi"}:
                scored_item = self._score_poi_or_rail(item)
                if scored_item:
                    scored.append(scored_item)
            elif item.category == "building":
                scored_item = self._score_building(item)
                if scored_item:
                    scored.append(scored_item)
            elif item.category == "shielding":
                shielding_evidence.append(item)

        for item in shielding_evidence:
            scored_item = self._score_shielding(item, road_penalty_by_name)
            if scored_item:
                scored.append(scored_item)

        return scored

    def _attach_summary(self, breakdown: ScoreBreakdown) -> ScoreBreakdown:
        traffic_penalty = 0
        local_life_penalty = 0
        building_adjustment = 0
        for item in breakdown.results:
            value = int(item.effective_score_delta)
            if value < 0 and (item.category in {"road", "rail"} or "traffic" in item.tags):
                traffic_penalty += abs(value)
            elif value < 0 and (item.category == "poi" or "local_life" in item.tags):
                local_life_penalty += abs(value)
            elif item.category == "building":
                building_adjustment += value

        breakdown.summary = {
            "base_score": breakdown.base_score,
            "final_score": breakdown.final_score,
            "traffic_penalty": traffic_penalty,
            "local_life_penalty": local_life_penalty,
            "external_environment_impact": traffic_penalty + local_life_penalty,
            "building_adjustment": building_adjustment,
        }
        return breakdown

    def aggregate(self, results: list[EngineResult], base_score: int | None = None) -> ScoreBreakdown:
        base = int(base_score if base_score is not None else self.cfg.base_score)
        scored = self._score_results(results)
        breakdown = build_score_breakdown(
            base_score=base,
            results=scored,
            score_low=self.cfg.score_low,
            score_high=self.cfg.score_high,
            category_weights=self.cfg.resolved_category_weights(),
            global_weight=self.cfg.global_weight,
        )
        return self._attach_summary(breakdown)

    def total_score(self, results: list[EngineResult], base_score: int | None = None) -> int:
        return self.aggregate(results, base_score=base_score).final_score

    def debug_dict(self, results: list[EngineResult], base_score: int | None = None) -> dict[str, Any]:
        breakdown = self.aggregate(results, base_score=base_score)
        payload = breakdown.to_dict()
        payload["summary"] = breakdown.summary
        return payload
