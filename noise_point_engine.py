# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from engine_schema import DisplayPayload, EngineResult


BEIJING_ROAD_TIER_OVERRIDES: dict[str, str] = {
    # 高速/快速系统
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
    # 环路系统
    "二环路": "expressway",
    "三环路": "expressway",
    "四环路": "expressway",
    "五环路": "expressway",
    "六环路": "expressway",
    # 主干道
    "昌平路": "arterial",
    "北清路": "arterial",
    "回龙观西大街": "arterial",
    "回龙观东大街": "arterial",
    "朝阳北路": "arterial",
    "建国路": "arterial",
    "京密路": "arterial",
    # 次干路 / 社区边路
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

RAIL_KIND_LABEL = {
    "rail_surface": "地上轨道",
    "rail_station": "轨道站点",
    "rail_entrance": "地铁出入口",
}

RAIL_PRIORITY = {
    "rail_surface": 74,
    "rail_station": 68,
    "rail_entrance": 62,
}

BEIJING_SURFACE_RAIL_HINTS = [
    "13号线",
    "八通线",
    "昌平线",
    "亦庄线",
    "S1线",
    "西郊线",
    "燕房线",
    "机场线",
    "大兴机场线",
    "轻轨",
    "城铁",
    "有轨电车",
    "高架",
    "铁路",
]


def _to_int_distance(value: Any) -> int | None:
    try:
        if value in ("", None):
            return None
        return int(round(float(value)))
    except Exception:
        return None


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
    if text.endswith("街"):
        return "secondary"
    if any(x in text for x in ["南路", "北路", "东路", "西路"]):
        return "arterial"
    return "secondary"


def _join_rail_text(item: dict[str, Any]) -> str:
    parts = [
        str(item.get("name", "")).strip(),
        str(item.get("address", "")).strip(),
        str(item.get("type", "")).strip(),
    ]
    return " ".join(x for x in parts if x)


def classify_rail_kind(item: dict[str, Any]) -> str:
    text = _join_rail_text(item)
    if any(k in text for k in ["出入口", "A口", "B口", "C口", "D口"]):
        return "rail_entrance"
    if any(k in text for k in BEIJING_SURFACE_RAIL_HINTS):
        return "rail_surface"
    if any(k in text for k in ["地铁站", "轻轨站", "城铁站", "有轨电车站"]):
        return "rail_station"
    return "rail_station"


class NoisePointEngine:
    """只负责抽取证据，不做 penalty 结算。"""

    def evaluate(self, regeo: dict[str, Any] | None, poi_results: dict[str, list[dict[str, Any]]]) -> list[EngineResult]:
        results: list[EngineResult] = []

        roads = list((regeo or {}).get("roads", []) or [])
        picked_by_kind: dict[str, dict[str, Any]] = {}
        for road in roads:
            distance_m = _to_int_distance(road.get("distance"))
            road_name = str(road.get("name", "")).strip() or "道路"
            road_kind = classify_road_kind(road_name)
            current = picked_by_kind.get(road_kind)
            if current is None or current.get("distance_m") is None or (distance_m is not None and distance_m < current.get("distance_m")):
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
            poi_name = str(item.get("name", "")).strip() or label
            results.append(
                EngineResult(
                    engine="noise_point_engine",
                    enabled=True,
                    score_delta=0,
                    confidence=0.82,
                    category=category,
                    priority=priority,
                    evidence={
                        "poi_kind": key,
                        "poi_name": poi_name,
                        "distance_m": distance_m,
                    },
                    explanation=f"识别到{label}，距离约 {distance_m}m。",
                    display=DisplayPayload(
                        label=label,
                        detail=f"{poi_name}｜{distance_m}m",
                        value_text="",
                    ),
                    tags=["evidence_only", key],
                )
            )

        rail_candidates: list[dict[str, Any]] = []
        rail_candidates.extend(list(poi_results.get("rail_station", []) or []))
        rail_candidates.extend(list(poi_results.get("rail_entrance", []) or []))

        best_rail_by_kind: dict[str, dict[str, Any]] = {}
        for item in rail_candidates:
            rail_kind = classify_rail_kind(item)
            distance_m = _to_int_distance(item.get("distance"))
            current = best_rail_by_kind.get(rail_kind)
            if current is None:
                best_rail_by_kind[rail_kind] = item
                continue
            current_dist = _to_int_distance(current.get("distance"))
            if current_dist is None or (distance_m is not None and distance_m < current_dist):
                best_rail_by_kind[rail_kind] = item

        for rail_kind, item in best_rail_by_kind.items():
            distance_m = _to_int_distance(item.get("distance"))
            rail_name = str(item.get("name", "")).strip() or RAIL_KIND_LABEL[rail_kind]
            results.append(
                EngineResult(
                    engine="noise_point_engine",
                    enabled=True,
                    score_delta=0,
                    confidence=0.88 if rail_kind == "rail_surface" else 0.80,
                    category="rail",
                    priority=RAIL_PRIORITY[rail_kind],
                    evidence={
                        "poi_kind": rail_kind,
                        "poi_name": rail_name,
                        "distance_m": distance_m,
                    },
                    explanation=f"识别到{RAIL_KIND_LABEL[rail_kind]}，距离约 {distance_m}m。",
                    display=DisplayPayload(
                        label=RAIL_KIND_LABEL[rail_kind],
                        detail=f"{rail_name}｜{distance_m}m",
                        value_text="",
                    ),
                    tags=["evidence_only", rail_kind, "rail"],
                )
            )

        return results
