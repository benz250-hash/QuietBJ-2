# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine_schema import DisplayPayload, EngineResult


@dataclass(frozen=True)
class NoiseBands:
    expressway: list[tuple[int, int]]
    arterial: list[tuple[int, int]]
    secondary: list[tuple[int, int]]
    local: list[tuple[int, int]]
    internal: list[tuple[int, int]]
    rail: list[tuple[int, int]]
    school: list[tuple[int, int]]
    hospital: list[tuple[int, int]]
    commercial: list[tuple[int, int]]
    restaurant: list[tuple[int, int]]

    @staticmethod
    def default() -> "NoiseBands":
        return NoiseBands(
            expressway=[(30, 18), (60, 16), (100, 14), (150, 12), (220, 10), (320, 7), (450, 4), (650, 2)],
            arterial=[(20, 12), (40, 10), (60, 8), (90, 7), (120, 6), (160, 4), (220, 3), (320, 1)],
            secondary=[(15, 7), (30, 6), (50, 5), (80, 3), (120, 2), (180, 1)],
            local=[(8, 3), (15, 2), (25, 2), (40, 1), (60, 0)],
            internal=[(5, 2), (10, 1), (18, 1), (30, 0)],
            rail=[(40, 9), (80, 7), (120, 6), (180, 4), (260, 2), (400, 1)],
            school=[(40, 5), (80, 4), (120, 3), (180, 2), (260, 1)],
            hospital=[(50, 4), (100, 3), (160, 2), (250, 1)],
            commercial=[(20, 7), (40, 6), (70, 5), (110, 3), (170, 2), (260, 1)],
            restaurant=[(15, 6), (30, 5), (50, 4), (80, 3), (130, 2), (220, 1)],
        )


def _to_int_distance(value: Any) -> int | None:
    try:
        if value in ("", None):
            return None
        return int(round(float(value)))
    except Exception:
        return None


BEIJING_ROAD_TIER_OVERRIDES: dict[str, str] = {
    # S
    "京藏高速": "expressway",
    "京新高速": "expressway",
    "京港澳高速": "expressway",
    "京哈高速": "expressway",
    "京沪高速": "expressway",
    "京昆高速": "expressway",
    "大广高速": "expressway",
    "机场高速": "expressway",
    "机场第二高速": "expressway",
    "首都环线高速": "expressway",
    "G1辅路": "expressway",
    "G2辅路": "expressway",
    "G4辅路": "expressway",
    "G5辅路": "expressway",
    "G6辅路": "expressway",
    "G7辅路": "expressway",
    # A/C/D mapping to existing engine kinds
    "三环路": "expressway",
    "四环路": "expressway",
    "五环路": "expressway",
    "六环路": "expressway",
    "昌平路": "arterial",
    "北清路": "arterial",
    "回龙观西大街": "arterial",
    "回龙观东大街": "arterial",
    "朝阳北路": "arterial",
    "建国路": "arterial",
    "南店北路": "secondary",
    "同成街": "secondary",
    "同成南街": "secondary",
    "育知西路": "secondary",
    "金榜园西侧路": "secondary",
    "万润家园东路": "secondary",
}


ROAD_KIND_LABEL = {
    "expressway": "高速系统",
    "arterial": "主干路",
    "secondary": "次干路",
    "local": "小路/支路",
    "internal": "小区内部路",
}


ROAD_PRIORITY = {
    "expressway": 95,
    "arterial": 90,
    "secondary": 85,
    "local": 80,
    "internal": 75,
}


def classify_road_kind(name: str) -> str:
    text = str(name or "").strip()
    if not text:
        return "secondary"
    if text in BEIJING_ROAD_TIER_OVERRIDES:
        return BEIJING_ROAD_TIER_OVERRIDES[text]
    if any(x in text for x in ["京藏", "京新", "京港澳", "京哈", "京沪", "京昆", "机场"]):
        if "辅路" in text or "高速" in text:
            return "expressway"
    if any(x in text for x in ["二环", "三环", "四环", "五环", "六环"]):
        return "expressway"
    if "高速" in text or "快速路" in text or "快速" in text or "高架" in text:
        return "expressway"
    if text.startswith("G") and any(ch.isdigit() for ch in text):
        return "expressway"
    if any(x in text for x in ["小区内部路", "内部路"]):
        return "internal"
    if any(x in text for x in ["胡同", "巷", "里", "支路", "小路"]):
        return "local"
    if any(x in text for x in ["大街", "大道"]):
        return "arterial"
    if any(x in text for x in ["南路", "北路", "东路", "西路"]):
        return "arterial"
    if text.endswith("街"):
        return "secondary"
    return "secondary"


class NoisePointEngine:
    """只负责抽取证据，不做 penalty 结算。"""

    def __init__(self, bands: NoiseBands | None = None) -> None:
        self.bands = bands or NoiseBands.default()

    def evaluate(self, regeo: dict[str, Any] | None, poi_results: dict[str, list[dict[str, Any]]]) -> list[EngineResult]:
        results: list[EngineResult] = []

        roads = list((regeo or {}).get("roads", []) or [])
        picked_by_kind: dict[str, dict[str, Any]] = {}
        for road in roads:
            distance_m = _to_int_distance(road.get("distance"))
            road_name = str(road.get("name", "")).strip() or "道路"
            road_kind = classify_road_kind(road_name)
            current = picked_by_kind.get(road_kind)
            if current is None:
                picked_by_kind[road_kind] = {"name": road_name, "distance_m": distance_m}
                continue
            current_dist = current.get("distance_m")
            if current_dist is None or (distance_m is not None and distance_m < current_dist):
                picked_by_kind[road_kind] = {"name": road_name, "distance_m": distance_m}

        for kind, item in picked_by_kind.items():
            results.append(
                EngineResult(
                    engine="noise_point_engine",
                    enabled=True,
                    score_delta=0,
                    confidence=0.92 if kind in {"expressway", "arterial", "secondary"} else 0.82,
                    category="road",
                    priority=ROAD_PRIORITY[kind],
                    evidence={
                        "road_kind": kind,
                        "road_name": item["name"],
                        "distance_m": item["distance_m"],
                    },
                    explanation=f"识别到{ROAD_KIND_LABEL[kind]}，距离约 {item['distance_m']}m。",
                    display=DisplayPayload(
                        label=ROAD_KIND_LABEL[kind],
                        detail=f"{item['name']}｜{item['distance_m']}m",
                        value_text="",
                    ),
                    tags=["evidence_only", "road"],
                )
            )

        poi_specs = [
            ("rail", "轨道", "rail", 70),
            ("school", "学校", "poi", 55),
            ("hospital", "医院", "poi", 50),
            ("commercial", "商业/底商", "poi", 60),
            ("restaurant", "餐饮", "poi", 58),
        ]
        for key, label, category, priority in poi_specs:
            items = list(poi_results.get(key, []) or [])
            if not items:
                continue
            item = items[0]
            distance_m = _to_int_distance(item.get("distance"))
            results.append(
                EngineResult(
                    engine="noise_point_engine",
                    enabled=True,
                    score_delta=0,
                    confidence=0.85 if key in {"rail", "commercial", "restaurant"} else 0.78,
                    category=category,  # type: ignore[arg-type]
                    priority=priority,
                    evidence={
                        "poi_kind": key,
                        "poi_name": str(item.get("name", "")).strip() or label,
                        "distance_m": distance_m,
                    },
                    explanation=f"识别到{label}，距离约 {distance_m}m。",
                    display=DisplayPayload(
                        label=label,
                        detail=f"{str(item.get('name', '')).strip() or label}｜{distance_m}m",
                        value_text="",
                    ),
                    tags=["evidence_only", key],
                )
            )

        return results
