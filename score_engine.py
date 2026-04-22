# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine_schema import DisplayPayload, EngineResult, ScoreBreakdown, build_score_breakdown


ROAD_SHIELDING_FACTOR = {
    "none": 1.00,
    "partial": 0.72,
    "strong": 0.50,
}

LOCAL_SHIELDING_FACTOR = {
    "none": 1.00,
    "partial": 0.82,
    "strong": 0.62,
}


@dataclass(slots=True)
class DetailedScoreBreakdown(ScoreBreakdown):
    traffic_penalty: int = 0
    local_life_penalty: int = 0
    building_adjustment: int = 0
    zone_adjust: int = 0
    external_environment_impact: int = 0


@dataclass(slots=True)
class ScoreEngineConfig:
    base_score: int = 85
    score_low: int = 50
    score_high: int = 95
    category_weights: dict[str, float] | None = None
    global_weight: float = 1.0

    expressway_bands: list[tuple[int, int]] | None = None
    arterial_bands: list[tuple[int, int]] | None = None
    secondary_bands: list[tuple[int, int]] | None = None
    local_bands: list[tuple[int, int]] | None = None
    internal_bands: list[tuple[int, int]] | None = None

    rail_surface_bands: list[tuple[int, int]] | None = None
    rail_station_bands: list[tuple[int, int]] | None = None
    rail_entrance_bands: list[tuple[int, int]] | None = None

    school_bands: list[tuple[int, int]] | None = None
    hospital_bands: list[tuple[int, int]] | None = None
    commercial_bands: list[tuple[int, int]] | None = None
    restaurant_bands: list[tuple[int, int]] | None = None

    def __post_init__(self) -> None:
        if self.expressway_bands is None:
            self.expressway_bands = [(30, 18), (60, 16), (100, 14), (150, 12), (220, 10), (320, 7), (450, 4), (650, 2)]
        if self.arterial_bands is None:
            self.arterial_bands = [(20, 12), (40, 10), (60, 8), (90, 7), (120, 6), (160, 4), (220, 3), (320, 1)]
        if self.secondary_bands is None:
            self.secondary_bands = [(15, 7), (30, 6), (50, 5), (80, 3), (120, 2), (180, 1)]
        if self.local_bands is None:
            self.local_bands = [(8, 3), (15, 2), (25, 2), (40, 1)]
        if self.internal_bands is None:
            self.internal_bands = [(5, 2), (10, 1), (18, 1)]

        if self.rail_surface_bands is None:
            self.rail_surface_bands = [(50, 10), (100, 8), (160, 6), (250, 4), (400, 2)]
        if self.rail_station_bands is None:
            self.rail_station_bands = [(40, 6), (80, 5), (140, 3), (220, 2), (350, 1)]
        if self.rail_entrance_bands is None:
            self.rail_entrance_bands = [(20, 4), (50, 3), (90, 2), (140, 1)]

        # 本地生活噪音阈值按你要求收窄到更近场
        if self.school_bands is None:
            self.school_bands = [(75, 4), (150, 2), (250, 1)]
        if self.hospital_bands is None:
            self.hospital_bands = [(100, 2)]
        if self.commercial_bands is None:
            self.commercial_bands = [(150, 2)]
        if self.restaurant_bands is None:
            self.restaurant_bands = [(25, 4), (75, 2)]

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

    def _road_bands(self, road_kind: str) -> list[tuple[int, int]]:
        if road_kind == "expressway":
            return self.cfg.expressway_bands or []
        if road_kind == "arterial":
            return self.cfg.arterial_bands or []
        if road_kind == "local":
            return self.cfg.local_bands or []
        if road_kind == "internal":
            return self.cfg.internal_bands or []
        return self.cfg.secondary_bands or []

    def _road_label(self, road_kind: str) -> str:
        return {
            "expressway": "高速系统",
            "arterial": "主干路",
            "secondary": "次干路",
            "local": "小路/支路",
            "internal": "小区内部路",
        }.get(road_kind, "次干路")

    def _score_road(self, item: EngineResult) -> EngineResult | None:
        evidence = dict(item.evidence or {})
        road_kind = str(evidence.get("road_kind", "secondary")).strip() or "secondary"
        distance = evidence.get("distance_m")
        penalty = self.band_score(distance, self._road_bands(road_kind))
        if penalty <= 0:
            return None
        label = self._road_label(road_kind)
        return EngineResult(
            engine=item.engine,
            enabled=True,
            score_delta=-penalty,
            confidence=item.confidence,
            category="road",
            priority=item.priority,
            evidence={**evidence, "penalty": penalty, "raw_penalty": penalty, "impact_group": "traffic"},
            explanation=item.explanation,
            display=DisplayPayload(label=label, detail=item.display.detail, value_text=f"-{penalty}"),
            tags=[tag for tag in item.tags if tag != "evidence_only"] + ["traffic"],
        )

    def _score_rail_or_poi(self, item: EngineResult) -> EngineResult | None:
        evidence = dict(item.evidence or {})
        poi_kind = str(evidence.get("poi_kind", "")).strip()
        distance = evidence.get("distance_m")
        penalty = 0
        label = item.display.label or poi_kind
        category = item.category
        impact_group = "local_life"

        if poi_kind == "rail_surface":
            penalty = self.band_score(distance, self.cfg.rail_surface_bands or [])
            label = "地上轨道"
            category = "rail"
            impact_group = "traffic"
        elif poi_kind == "rail_station":
            penalty = self.band_score(distance, self.cfg.rail_station_bands or [])
            label = "轨道站点"
            category = "rail"
            impact_group = "traffic"
        elif poi_kind == "rail_entrance":
            penalty = self.band_score(distance, self.cfg.rail_entrance_bands or [])
            label = "地铁出入口"
            category = "rail"
            impact_group = "traffic"
        elif poi_kind == "school":
            penalty = self.band_score(distance, self.cfg.school_bands or [])
            label = "学校"
        elif poi_kind == "hospital":
            penalty = self.band_score(distance, self.cfg.hospital_bands or [])
            label = "医院"
        elif poi_kind == "commercial":
            penalty = self.band_score(distance, self.cfg.commercial_bands or [])
            label = "本地生活噪音"
        elif poi_kind == "restaurant":
            penalty = self.band_score(distance, self.cfg.restaurant_bands or [])
            label = "餐饮"

        if penalty <= 0:
            return None

        return EngineResult(
            engine=item.engine,
            enabled=True,
            score_delta=-penalty,
            confidence=item.confidence,
            category=category,
            priority=item.priority,
            evidence={**evidence, "penalty": penalty, "raw_penalty": penalty, "impact_group": impact_group},
            explanation=item.explanation,
            display=DisplayPayload(label=label, detail=item.display.detail, value_text=f"-{penalty}"),
            tags=[tag for tag in item.tags if tag != "evidence_only"] + [impact_group],
        )

    def _score_building(self, item: EngineResult) -> EngineResult | None:
        evidence = dict(item.evidence or {})
        tags = set(item.tags or [])
        if "build_year" in tags:
            try:
                year = int(float(evidence.get("build_year")))
            except Exception:
                return None
            score = 0
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
                evidence={**evidence, "impact_group": "building"},
                explanation="建筑年份带来的居住品质修正。",
                display=DisplayPayload(label="建筑年份修正", detail=f"建成年份 {year}", value_text=f"+{score}"),
                tags=["build_year"],
            )
        if "density" in tags:
            try:
                ratio = float(evidence.get("far_ratio"))
            except Exception:
                return None
            score = 0
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
                evidence={**evidence, "impact_group": "building", "penalty": abs(min(score,0)), "raw_penalty": abs(min(score,0))},
                explanation="容积率带来的密度修正。",
                display=DisplayPayload(label="密度调整", detail=f"容积率 {ratio}", value_text=f"{score:+d}"),
                tags=["density"],
            )
        return None

    def _score_shielding(self, item: EngineResult, road_penalties: dict[tuple[str, str, Any], int]) -> EngineResult | None:
        evidence = dict(item.evidence or {})
        road_name = str(evidence.get("road_name", "")).strip()
        road_kind = str(evidence.get("road_kind", "secondary")).strip() or "secondary"
        road_distance = evidence.get("road_distance_m")
        raw = road_penalties.get((road_name, road_kind, road_distance), 0)
        if raw <= 0:
            raw = road_penalties.get((road_name, road_kind, None), 0)
        if raw <= 0:
            return None
        level = str(evidence.get("shielding_level", "none")).strip() or "none"
        factor_map = LOCAL_SHIELDING_FACTOR if road_kind in {"local", "internal"} else ROAD_SHIELDING_FACTOR
        factor = factor_map.get(level, 1.0)
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
                "penalty": adjusted,
                "raw_penalty": raw,
                "impact_group": "traffic",
            },
            explanation=f"前排遮挡 {level}，道路影响由 {raw} 修正为 {adjusted}。",
            display=DisplayPayload(label="遮挡修正", detail=f"原始影响 {raw} → 遮挡后 {adjusted}｜{level}｜挡住 {int(evidence.get('blocker_count', 0) or 0)} 栋", value_text=f"+{correction}"),
            tags=["shielding", "traffic"],
            max_effective_delta=correction,
        )

    def _score_results(self, results: list[EngineResult]) -> list[EngineResult]:
        scored: list[EngineResult] = []
        road_penalties: dict[tuple[str, str, Any], int] = {}
        shielding_inputs: list[EngineResult] = []

        for item in results:
            if not item.enabled:
                continue
            if item.category == "road":
                scored_item = self._score_road(item)
                if scored_item:
                    scored.append(scored_item)
                    e = scored_item.evidence or {}
                    penalty = int(e.get("penalty", 0) or 0)
                    key = (str(e.get("road_name", "")).strip(), str(e.get("road_kind", "secondary")).strip(), e.get("distance_m"))
                    road_penalties[key] = penalty
                    key2 = (str(e.get("road_name", "")).strip(), str(e.get("road_kind", "secondary")).strip(), None)
                    road_penalties[key2] = penalty
                continue
            if item.category in {"rail", "poi"}:
                scored_item = self._score_rail_or_poi(item)
                if scored_item:
                    scored.append(scored_item)
                continue
            if item.category == "building":
                scored_item = self._score_building(item)
                if scored_item:
                    scored.append(scored_item)
                continue
            if item.category == "shielding":
                shielding_inputs.append(item)
                continue
            # zone / override 当前退出主评分链

        for item in shielding_inputs:
            scored_item = self._score_shielding(item, road_penalties)
            if scored_item:
                scored.append(scored_item)
        return scored

    def _attach_summary(self, breakdown: ScoreBreakdown) -> DetailedScoreBreakdown:
        traffic_penalty = 0
        local_life_penalty = 0
        building_adjustment = 0
        zone_adjust = 0
        for item in list(getattr(breakdown, "results", []) or []):
            value = int(getattr(item, "effective_score_delta", 0))
            evidence = getattr(item, "evidence", {}) or {}
            impact_group = str(evidence.get("impact_group", "")).strip()
            category = str(getattr(item, "category", ""))
            if impact_group == "traffic" and value < 0:
                traffic_penalty += abs(value)
            elif impact_group == "local_life" and value < 0:
                local_life_penalty += abs(value)
            elif impact_group == "building":
                building_adjustment += value
            elif category == "zone":
                zone_adjust += value

        return DetailedScoreBreakdown(
            base_score=breakdown.base_score,
            results=breakdown.results,
            raw_total_delta=breakdown.raw_total_delta,
            adopted_total_delta=breakdown.adopted_total_delta,
            final_score=breakdown.final_score,
            summary=breakdown.summary,
            traffic_penalty=traffic_penalty,
            local_life_penalty=local_life_penalty,
            building_adjustment=building_adjustment,
            zone_adjust=zone_adjust,
            external_environment_impact=traffic_penalty,
        )

    def aggregate(self, results: list[EngineResult], base_score: int | None = None) -> DetailedScoreBreakdown:
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
        return self.aggregate(results, base_score=base_score).to_dict()
