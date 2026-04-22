# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from engine_schema import DisplayPayload, EngineResult


@dataclass(frozen=True)
class PoiLabels:
    road: dict[str, str]
    poi: dict[str, str]

    @staticmethod
    def default() -> "PoiLabels":
        return PoiLabels(
            road={
                "S": "高速系统",
                "A": "环路系统",
                "B": "城市快速路",
                "C": "重流量主干道",
                "D": "次干路/社区外缘道路",
                "E": "内部小路",
            },
            poi={
                "rail": "轨道",
                "school": "学校",
                "hospital": "医院",
                "commercial": "商业",
                "restaurant": "餐饮",
            },
        )


BEIJING_ROAD_TIER_OVERRIDES = {
    # S：高速系统
    "京藏高速": "S", "京新高速": "S", "京港澳高速": "S", "京哈高速": "S", "京沪高速": "S", "京昆高速": "S",
    "大广高速": "S", "机场高速": "S", "机场第二高速": "S", "首都环线高速": "S",
    "G1": "S", "G2": "S", "G4": "S", "G5": "S", "G6": "S", "G7": "S", "G45": "S", "G95": "S",
    "G1辅路": "S", "G2辅路": "S", "G4辅路": "S", "G5辅路": "S", "G6辅路": "S", "G7辅路": "S",
    "京藏高速辅路": "S", "京港澳高速辅路": "S", "京哈高速辅路": "S", "机场高速辅路": "S",
    # A：环路系统
    "二环路": "A", "三环路": "A", "四环路": "A", "五环路": "A", "六环路": "A",
    "东二环": "A", "西二环": "A", "南二环": "A", "北二环": "A",
    "东三环": "A", "西三环": "A", "南三环": "A", "北三环": "A",
    "东四环": "A", "西四环": "A", "南四环": "A", "北四环": "A",
    "东五环": "A", "西五环": "A", "南五环": "A", "北五环": "A",
    "东六环": "A", "西六环": "A", "南六环": "A", "北六环": "A",
    "东三环中路": "A", "东三环北路": "A", "东三环南路": "A", "西三环中路": "A", "西三环北路": "A", "西三环南路": "A",
    "北三环东路": "A", "北三环中路": "A", "北三环西路": "A", "南三环东路": "A", "南三环中路": "A", "南三环西路": "A",
    "东四环中路": "A", "东四环北路": "A", "东四环南路": "A", "西四环中路": "A", "西四环北路": "A", "西四环南路": "A",
    "北四环东路": "A", "北四环中路": "A", "北四环西路": "A", "南四环东路": "A", "南四环西路": "A",
    # B：快速路
    "京通快速路": "B", "德胜快速路": "B", "广渠路快速路": "B", "阜石路": "B", "莲石东路": "B", "莲石西路": "B",
    "菜户营南路": "B", "通燕高速": "B", "建国快速路": "B",
    # C：重流量主干道
    "建国路": "C", "长安街": "C", "复兴路": "C", "朝阳北路": "C", "朝阳路": "C", "北苑路": "C", "北清路": "C",
    "昌平路": "C", "回龙观西大街": "C", "回龙观东大街": "C", "京密路": "C", "安立路": "C", "阜成路": "C", "广安路": "C",
    "西直门外大街": "C", "西直门北大街": "C", "东直门外大街": "C", "中关村大街": "C", "学院路": "C", "知春路": "C",
    "远大路": "C", "万泉河路": "C", "成府路": "C", "北辰西路": "C", "北辰东路": "C", "立汤路": "C", "京顺路": "C",
    "通马路": "C", "九棵树西路": "C",
    # D：社区外缘/次干路
    "南店北路": "D", "同成街": "D", "同成南街": "D", "育知西路": "D", "金榜园西侧路": "D", "万润家园东路": "D",
    "龙域中路": "D", "龙腾街": "D", "龙禧二街": "D", "龙禧三街": "D", "回南路": "D", "文华东路": "D", "文华西路": "D",
}


ROAD_PRIORITY = {"S": 95, "A": 93, "B": 91, "C": 88, "D": 84, "E": 78}
ROAD_KIND_BY_TIER = {"S": "expressway", "A": "expressway", "B": "expressway", "C": "arterial", "D": "secondary", "E": "internal"}


def _to_int_distance(value: Any) -> int | None:
    try:
        if value in ("", None):
            return None
        return int(round(float(value)))
    except Exception:
        return None


def infer_beijing_road_tier(name: str) -> str:
    road = str(name or "").strip()
    if not road:
        return "E"
    if road in BEIJING_ROAD_TIER_OVERRIDES:
        return BEIJING_ROAD_TIER_OVERRIDES[road]

    if re.search(r"G\d+", road):
        return "S"
    if "高速" in road:
        return "S"

    ring_keywords = ["二环", "三环", "四环", "五环", "六环"]
    if any(k in road for k in ring_keywords):
        return "A"
    if "快速路" in road or "快速" in road:
        return "B"

    if "辅路" in road:
        if any(k in road for k in ["京藏", "京港澳", "京哈", "京沪", "京昆", "机场"]):
            return "S"
        if any(k in road for k in ring_keywords):
            return "A"
        return "C"

    if any(k in road for k in ["大街", "大道"]):
        return "C"
    if road.endswith("路"):
        return "D"
    if road.endswith("街"):
        return "D"
    if any(k in road for k in ["胡同", "巷", "里", "支路", "小路"]):
        return "E"
    return "E"


class NoisePointEngine:
    def __init__(self, labels: PoiLabels | None = None) -> None:
        self.labels = labels or PoiLabels.default()

    def _pick_roads(self, roads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        picked_by_tier: dict[str, dict[str, Any]] = {}
        for road in list(roads or []):
            distance_m = _to_int_distance(road.get("distance"))
            road_name = str(road.get("name", "")).strip() or "道路"
            tier = infer_beijing_road_tier(road_name)
            current = picked_by_tier.get(tier)
            if current is None:
                picked_by_tier[tier] = {"name": road_name, "distance_m": distance_m, "tier": tier}
                continue
            current_dist = current.get("distance_m")
            if current_dist is None or (distance_m is not None and distance_m < current_dist):
                picked_by_tier[tier] = {"name": road_name, "distance_m": distance_m, "tier": tier}
        return sorted(picked_by_tier.values(), key=lambda x: (ROAD_PRIORITY.get(x["tier"], 0), -(999999 if x["distance_m"] is None else (999999 - x["distance_m"]))), reverse=True)

    def evaluate(self, regeo: dict[str, Any] | None, poi_results: dict[str, list[dict[str, Any]]]) -> list[EngineResult]:
        results: list[EngineResult] = []

        for item in self._pick_roads(list((regeo or {}).get("roads", []) or [])):
            tier = item["tier"]
            label = self.labels.road.get(tier, "道路")
            road_kind = ROAD_KIND_BY_TIER.get(tier, "secondary")
            if tier == "E" and "内部" not in item["name"]:
                road_kind = "local"
            results.append(
                EngineResult(
                    engine="noise_point_engine",
                    enabled=True,
                    score_delta=0,
                    confidence=0.92 if tier in {"S", "A", "B", "C", "D"} else 0.82,
                    category="road",
                    priority=ROAD_PRIORITY.get(tier, 80),
                    evidence={
                        "road_tier": tier,
                        "road_tier_label": label,
                        "road_kind": road_kind,
                        "road_name": item["name"],
                        "distance_m": item["distance_m"],
                    },
                    explanation=f"识别到{label}：{item['name']}，距离约 {item['distance_m']}m。",
                    display=DisplayPayload(
                        label=label,
                        detail=f"{item['name']}｜{item['distance_m']}m",
                        value_text="",
                    ),
                    tags=["road", tier],
                )
            )

        poi_specs = [
            ("rail", "轨道", "rail", 70, "rail"),
            ("school", "学校", "poi", 55, "school"),
            ("hospital", "医院", "poi", 50, "hospital"),
            ("commercial", "商业", "poi", 60, "commercial"),
            ("restaurant", "餐饮", "poi", 58, "restaurant"),
        ]
        for key, label, category, priority, tag in poi_specs:
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
                    confidence=0.90 if key == "rail" else 0.85,
                    category=category,
                    priority=priority,
                    evidence={
                        "poi_key": key,
                        "poi_name": poi_name,
                        "poi_distance_m": distance_m,
                    },
                    explanation=f"识别到{label}：{poi_name}，距离约 {distance_m}m。",
                    display=DisplayPayload(
                        label=label,
                        detail=f"{poi_name}｜{distance_m}m",
                        value_text="",
                    ),
                    tags=[tag],
                )
            )

        return results
