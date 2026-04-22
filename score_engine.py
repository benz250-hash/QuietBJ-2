# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine_schema import DisplayPayload, EngineResult, ScoreBreakdown, build_score_breakdown


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

ROAD_TIER_BANDS = {
    "S": [(100, 15), (300, 10), (600, 6), (1000, 3)],
    "A": [(100, 12), (300, 8), (600, 5), (1000, 2)],
    "B": [(100, 9), (300, 6), (600, 3), (1000, 1)],
    "C": [(50, 7), (150, 4), (300, 2), (600, 1)],
    "D": [(30, 4), (100, 2), (200, 1)],
    "E": [(20, 2), (50, 1)],
}

POI_BANDS = {
    "rail": [(40, 9), (80, 7), (120, 6), (180, 4), (260, 2), (400, 1)],
    "school": [(40, 5), (80, 4), (120, 3), (180, 2), (260, 1)],
    "hospital": [(50, 4), (100, 3), (160, 2), (250, 1)],
    "commercial": [(20, 7), (40, 6), (70, 5), (110, 3), (170, 2), (260, 1)],
    "restaurant": [(15, 6), (30, 5), (50, 4), (80, 3), (130, 2), (220, 1)],
}

ROAD_SHIELDING_FACTOR = {"none": 1.00, "partial": 0.72, "strong": 0.50}
LOCAL_SHIELDING_FACTOR = {"none": 1.00, "partial": 0.82, "strong": 0.62}


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
        scored_results = [self._score_result(item) for item in results if item.enabled]
        return build_score_breakdown(
            base_score=base,
            results=scored_results,
            score_low=self.cfg.score_low,
            score_high=self.cfg.score_high,
            category_weights=self.cfg.resolved_category_weights(),
            global_weight=self.cfg.global_weight,
        )

    def total_score(self, results: list[EngineResult], base_score: int | None = None) -> int:
        return self.aggregate(results, base_score=base_score).final_score

    def debug_dict(self, results: list[EngineResult], base_score: int | None = None) -> dict[str, Any]:
        return self.aggregate(results, base_score=base_score).to_dict()

    def _score_result(self, item: EngineResult) -> EngineResult:
        if item.engine == "noise_point_engine":
            if item.category == "road":
                return self._score_road(item)
            if item.category in {"rail", "poi"}:
                return self._score_poi(item)
        if item.engine == "building_engine":
            if item.category == "zone":
                return self._score_zone(item)
            if item.category == "building":
                if "build_year" in item.tags:
                    return self._score_build_year(item)
                if "density" in item.tags:
                    return self._score_density(item)
        if item.engine == "shielding_engine":
            return self._score_shielding(item)
        if item.engine == "override_engine":
            return self._with_delta(item, 0)
        return item

    @staticmethod
    def _to_float(value: Any) -> float | None:
        try:
            if value in ("", None):
                return None
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _to_int_distance(value: Any) -> int | None:
        try:
            if value in ("", None):
                return None
            return int(round(float(value)))
        except Exception:
            return None

    @staticmethod
    def _band_score(distance: int | None, bands: list[tuple[int, int]]) -> int:
        if distance is None:
            return 0
        for upper, score in bands:
            if distance <= upper:
                return score
        return 0

    def _with_delta(self, item: EngineResult, score_delta: int, *, explanation: str | None = None, evidence_updates: dict[str, Any] | None = None) -> EngineResult:
        display = DisplayPayload(
            label=item.display.label,
            detail=item.display.detail,
            value_text=f"{int(score_delta):+d}" if int(score_delta) != 0 else "0",
        )
        evidence = dict(item.evidence or {})
        if evidence_updates:
            evidence.update(evidence_updates)
        return EngineResult(
            engine=item.engine,
            enabled=item.enabled,
            score_delta=int(score_delta),
            confidence=item.confidence,
            category=item.category,
            priority=item.priority,
            evidence=evidence,
            explanation=explanation if explanation is not None else item.explanation,
            display=display,
            tags=list(item.tags or []),
            weight_hint=item.weight_hint,
            min_effective_delta=item.min_effective_delta,
            max_effective_delta=item.max_effective_delta,
        )

    def _score_road(self, item: EngineResult) -> EngineResult:
        tier = str(item.evidence.get("road_tier", "D")).strip() or "D"
        distance = self._to_int_distance(item.evidence.get("distance_m"))
        penalty = self._band_score(distance, ROAD_TIER_BANDS.get(tier, ROAD_TIER_BANDS["D"]))
        road_name = str(item.evidence.get("road_name", "道路")).strip() or "道路"
        label = str(item.evidence.get("road_tier_label", item.display.label or "道路")).strip() or "道路"
        detail = f"{road_name}｜{distance if distance is not None else '-'}m"
        scored = self._with_delta(
            item,
            -penalty,
            explanation=f"{label}距离约 {distance}m，主引擎道路分级后扣 {penalty} 分。",
            evidence_updates={"road_tier_label": label, "distance_m": distance},
        )
        scored.display = DisplayPayload(label=label, detail=detail, value_text=f"{-penalty:+d}")
        return scored

    def _score_poi(self, item: EngineResult) -> EngineResult:
        poi_key = str(item.evidence.get("poi_key", "")).strip() or ("rail" if item.category == "rail" else "")
        distance = self._to_int_distance(item.evidence.get("poi_distance_m"))
        penalty = self._band_score(distance, POI_BANDS.get(poi_key, []))
        poi_name = str(item.evidence.get("poi_name", item.display.label or "POI")).strip() or "POI"
        label = item.display.label or poi_key or item.category
        scored = self._with_delta(
            item,
            -penalty,
            explanation=f"{label}距离约 {distance}m，主引擎按 {poi_key or item.category} 规则扣 {penalty} 分。",
            evidence_updates={"poi_distance_m": distance},
        )
        scored.display = DisplayPayload(label=label, detail=f"{poi_name}｜{distance if distance is not None else '-'}m", value_text=f"{-penalty:+d}")
        return scored

    def _score_zone(self, item: EngineResult) -> EngineResult:
        zone_type = str(item.evidence.get("zone_type", "")).strip()
        score = int(ZONE_ADJUSTMENTS.get(zone_type, 0))
        locator_confidence = str(item.evidence.get("locator_confidence", "中")).strip() or "中"
        scored = self._with_delta(item, score, explanation=f"楼栋位置按 {zone_type or '-'} 处理，主引擎修正 {score:+d} 分。")
        scored.display = DisplayPayload(label=item.display.label or "楼栋位置调整", detail=f"{zone_type or '-'}｜定位置信度 {locator_confidence}", value_text=f"{score:+d}")
        return scored

    def _score_build_year(self, item: EngineResult) -> EngineResult:
        year = self._to_float(item.evidence.get("build_year"))
        score = 0
        if year is not None:
            if year >= 2025:
                score = 5
            elif year >= 2015:
                score = 3
            elif year >= 2005:
                score = 1
        scored = self._with_delta(item, score, explanation=f"建筑年份 {item.evidence.get('build_year', '-') }，主引擎修正 {score:+d} 分。")
        scored.display = DisplayPayload(label=item.display.label or "建筑年份修正", detail=f"建成年份 {item.evidence.get('build_year', '-')}", value_text=f"{score:+d}")
        return scored

    def _score_density(self, item: EngineResult) -> EngineResult:
        ratio = self._to_float(item.evidence.get("far_ratio"))
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
        detail_value = item.evidence.get("far_ratio") if item.evidence.get("far_ratio") not in ("", None) else "-"
        scored = self._with_delta(item, score, explanation=f"容积率 {detail_value}，主引擎修正 {score:+d} 分。")
        scored.display = DisplayPayload(label=item.display.label or "密度调整", detail=f"容积率 {detail_value}", value_text=f"{score:+d}")
        return scored

    def _score_shielding(self, item: EngineResult) -> EngineResult:
        level = str(item.evidence.get("shielding_level", "none")).strip() or "none"
        if level == "none":
            return self._with_delta(item, 0)

        road_tier = str(item.evidence.get("road_tier", "D")).strip() or "D"
        road_kind = str(item.evidence.get("road_kind", "secondary")).strip() or "secondary"
        distance = self._to_int_distance(item.evidence.get("distance_m"))
        raw = self._band_score(distance, ROAD_TIER_BANDS.get(road_tier, ROAD_TIER_BANDS["D"]))
        factor_map = LOCAL_SHIELDING_FACTOR if road_tier in {"D", "E"} or road_kind in {"local", "internal"} else ROAD_SHIELDING_FACTOR
        factor = float(factor_map.get(level, 1.0))
        adjusted = max(1, round(raw * factor)) if raw > 0 else 0
        correction = raw - adjusted
        if correction <= 0:
            correction = 0
        blocker_count = int(item.evidence.get("blocker_count", 0) or 0)
        blocker_names = list(item.evidence.get("blocker_names", []) or [])
        scored = self._with_delta(
            item,
            correction,
            explanation=f"前排遮挡 {level}，道路原始影响 {raw}，遮挡后 {adjusted}，回补 {correction} 分。",
            evidence_updates={
                "raw_impact": raw,
                "adjusted_impact": adjusted,
                "shielding_factor": factor,
                "blocker_count": blocker_count,
                "blocker_names": blocker_names,
            },
        )
        scored.display = DisplayPayload(label=item.display.label or "遮挡修正", detail=f"原始影响 {raw} → 遮挡后 {adjusted}｜{level}｜挡住 {blocker_count} 栋", value_text=f"{correction:+d}")
        scored.max_effective_delta = correction
        return scored
