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


def _band_score(distance: int | None, bands: list[tuple[int, int]]) -> int:
    if distance is None:
        return 0
    for upper, score in bands:
        if distance <= upper:
            return score
    return 0


def classify_road_kind(name: str) -> str:
    text = str(name or "").strip()
    if any(x in text for x in ["高速", "快速", "高架", "环路", "三环", "四环", "五环", "六环"]):
        return "expressway"
    if any(x in text for x in ["小区内部路", "内部路"]):
        return "internal"
    if any(x in text for x in ["胡同", "巷", "里", "支路", "小路"]):
        return "local"
    if any(x in text for x in ["主干", "大街", "大道", "南路", "北路", "东路", "西路"]):
        return "arterial"
    return "secondary"


class NoisePointEngine:
    def __init__(self, bands: NoiseBands | None = None) -> None:
        self.bands = bands or NoiseBands.default()

    def _road_score(self, road_kind: str, distance_m: int | None) -> int:
        mapping = {
            "expressway": self.bands.expressway,
            "arterial": self.bands.arterial,
            "secondary": self.bands.secondary,
            "local": self.bands.local,
            "internal": self.bands.internal,
        }
        return _band_score(distance_m, mapping.get(road_kind, self.bands.secondary))

    def _poi_score(self, key: str, distance_m: int | None) -> int:
        mapping = {
            "rail": self.bands.rail,
            "school": self.bands.school,
            "hospital": self.bands.hospital,
            "commercial": self.bands.commercial,
            "restaurant": self.bands.restaurant,
        }
        return _band_score(distance_m, mapping[key])

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

        road_label = {
            "expressway": "高速/快速路",
            "arterial": "主干路",
            "secondary": "次干路",
            "local": "小路/支路",
            "internal": "小区内部路",
        }
        road_priority = {
            "expressway": 95,
            "arterial": 90,
            "secondary": 85,
            "local": 80,
            "internal": 75,
        }

        for kind, item in picked_by_kind.items():
            score = self._road_score(kind, item["distance_m"])
            if score <= 0:
                continue
            results.append(
                EngineResult(
                    engine="noise_point_engine",
                    enabled=True,
                    score_delta=-score,
                    confidence=0.92 if kind in {"expressway", "arterial", "secondary"} else 0.82,
                    category="road",
                    priority=road_priority[kind],
                    evidence={
                        "road_kind": kind,
                        "road_name": item["name"],
                        "distance_m": item["distance_m"],
                    },
                    explanation=f"{road_label[kind]}距离约 {item['distance_m']}m。",
                    display=DisplayPayload(
                        label=road_label[kind],
                        detail=f"{item['name']}｜{item['distance_m']}m",
                        value_text=f"-{score}",
                    ),
                )
            )

        poi_specs = [
            ("rail", "轨道", "rail", 70),
            ("school", "学校", "poi", 55),
            ("hospital", "医院", "poi", 50),
            ("commercial", "商业", "poi", 60),
            ("restaurant", "餐饮", "poi", 58),
        ]
        for key, label, category, priority in poi_specs:
            items = list(poi_results.get(key, []) or [])
            if not items:
                continue
            item = items[0]
            distance_m = _to_int_distance(item.get("distance"))
            score = self._poi_score(key, distance_m)
            if score <= 0:
                continue
            results.append(
                EngineResult(
                    engine="noise_point_engine",
                    enabled=True,
                    score_delta=-score,
                    confidence=0.85 if key in {"rail", "commercial", "restaurant"} else 0.78,
                    category=category,  # type: ignore[arg-type]
                    priority=priority,
                    evidence={
                        "poi_kind": key,
                        "poi_name": str(item.get("name", "")).strip() or label,
                        "distance_m": distance_m,
                    },
                    explanation=f"{label}距离约 {distance_m}m。",
                    display=DisplayPayload(
                        label=label,
                        detail=f"{str(item.get('name', '')).strip() or label}｜{distance_m}m",
                        value_text=f"-{score}",
                    ),
                )
            )

        return results
