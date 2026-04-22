# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from engine_schema import DisplayPayload, EngineResult


CACHE_FILE = Path("community_building_cache.json")

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


def _norm_text(value: str) -> str:
    return "".join(ch for ch in str(value or "").strip().lower() if ch not in " \t\r\n-—_·•,，。/｜|（）()【】[]{}<>:：")


def _community_aliases(name: str) -> list[str]:
    raw = str(name or "").strip()
    if not raw:
        return []
    base = _norm_text(raw)
    aliases = {base}
    for suffix in ["东区", "西区", "南区", "北区", "一区", "二区", "三区", "四区", "五区", "六区"]:
        if raw.endswith(suffix):
            aliases.add(_norm_text(raw[: -len(suffix)]))
    return [x for x in aliases if x]


def load_building_cache(path: str | Path = CACHE_FILE) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_building_cache(data: dict[str, Any], path: str | Path = CACHE_FILE) -> None:
    file_path = Path(path)
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def collect_cache_stats(cache: dict[str, Any]) -> dict[str, int]:
    community_count = 0
    building_count = 0
    for _, value in (cache or {}).items():
        community_count += 1
        building_count += len(list((value or {}).get("buildings", []) or []))
    return {
        "community_count": community_count,
        "building_count": building_count,
    }


def build_cache_export_payload(
    cache: dict[str, Any],
    app_version: str = "v513",
) -> dict[str, Any]:
    stats = collect_cache_stats(cache)
    return {
        "schema_version": "quietbj_cache_v1",
        "exported_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "app_version": app_version,
        "stats": stats,
        "communities": cache or {},
    }


def normalize_import_payload(payload: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    if not isinstance(payload, dict):
        return False, "导入文件不是合法的 JSON 对象。", {}
    schema_version = str(payload.get("schema_version", "")).strip()
    if schema_version != "quietbj_cache_v1":
        return False, f"schema_version 不匹配：当前只支持 quietbj_cache_v1，收到的是 {schema_version or '空值'}。", {}
    communities = payload.get("communities", {})
    if not isinstance(communities, dict):
        return False, "communities 字段格式不正确，必须是对象。", {}
    normalized: dict[str, Any] = {}
    for community_name, entry in communities.items():
        if not isinstance(entry, dict):
            continue
        buildings = list(entry.get("buildings", []) or [])
        clean_buildings: list[dict[str, Any]] = []
        for item in buildings:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            token = str(item.get("building_token", "")).strip()
            try:
                lon = float(item.get("lon"))
                lat = float(item.get("lat"))
            except Exception:
                continue
            if not token:
                continue
            clean_buildings.append({
                "name": name or f"{community_name}{token}",
                "building_token": token,
                "lon": lon,
                "lat": lat,
            })
        normalized[str(community_name).strip()] = {
            "source": str(entry.get("source", "import")).strip() or "import",
            "updated_at": str(entry.get("updated_at", "")).strip() or datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "buildings": clean_buildings,
        }
    return True, "OK", normalized


def merge_cache_payload(
    current_cache: dict[str, Any],
    import_payload: dict[str, Any],
) -> dict[str, Any]:
    ok, msg, imported = normalize_import_payload(import_payload)
    if not ok:
        raise ValueError(msg)

    merged = dict(current_cache or {})
    for community_name, entry in imported.items():
        for building in list(entry.get("buildings", []) or []):
            merged = upsert_building_point(
                cache=merged,
                community_name=community_name,
                building=building,
                source="import_merge",
                updated_at=entry.get("updated_at", ""),
            )
    return merged


def replace_cache_from_payload(import_payload: dict[str, Any]) -> dict[str, Any]:
    ok, msg, imported = normalize_import_payload(import_payload)
    if not ok:
        raise ValueError(msg)
    return imported


def _find_best_cache_key(cache: dict[str, Any], community_name: str) -> str | None:
    aliases = set(_community_aliases(community_name))
    if not aliases:
        return None
    best_key = None
    best_score = -1
    for key in cache.keys():
        key_aliases = set(_community_aliases(key))
        score = 0
        if aliases & key_aliases:
            score = 100
        else:
            for a in aliases:
                for b in key_aliases:
                    if a and b and (a in b or b in a):
                        score = max(score, min(len(a), len(b)))
        if score > best_score:
            best_score = score
            best_key = key
    return best_key if best_score > 0 else None


def get_cached_buildings(cache: dict[str, Any], community_name: str) -> list[dict[str, Any]]:
    best_key = _find_best_cache_key(cache, community_name)
    if not best_key:
        return []
    return list(cache.get(best_key, {}).get("buildings", []))


def upsert_building_point(
    cache: dict[str, Any],
    community_name: str,
    building: dict[str, Any],
    source: str = "query_trace",
    updated_at: str = "",
) -> dict[str, Any]:
    cache = dict(cache)
    best_key = _find_best_cache_key(cache, community_name)
    save_key = best_key or community_name
    entry = dict(cache.get(save_key, {}))
    buildings = list(entry.get("buildings", []))

    target_token = _norm_text(str(building.get("building_token", "")).strip())
    target_name = _norm_text(str(building.get("name", "")).strip())

    replaced = False
    for idx, item in enumerate(buildings):
        item_token = _norm_text(str(item.get("building_token", "")).strip())
        item_name = _norm_text(str(item.get("name", "")).strip())
        if target_token and item_token == target_token:
            buildings[idx] = {**item, **building}
            replaced = True
            break
        if target_name and item_name == target_name:
            buildings[idx] = {**item, **building}
            replaced = True
            break

    if not replaced:
        buildings.append(building)

    entry["source"] = entry.get("source", source) or source
    entry["updated_at"] = updated_at or entry.get("updated_at", "")
    entry["buildings"] = buildings
    cache[save_key] = entry
    return cache


def _to_point(item: dict[str, Any]) -> tuple[float, float] | None:
    try:
        return float(item["lon"]), float(item["lat"])
    except Exception:
        return None


def _meters_per_degree(lat: float) -> tuple[float, float]:
    lat_rad = math.radians(lat)
    m_per_deg_lat = 111132.92 - 559.82 * math.cos(2 * lat_rad) + 1.175 * math.cos(4 * lat_rad)
    m_per_deg_lon = 111412.84 * math.cos(lat_rad) - 93.5 * math.cos(3 * lat_rad)
    return m_per_deg_lon, m_per_deg_lat


def _to_local_xy(point: tuple[float, float], origin: tuple[float, float]) -> tuple[float, float]:
    m_lon, m_lat = _meters_per_degree(origin[1])
    return (point[0] - origin[0]) * m_lon, (point[1] - origin[1]) * m_lat


def _distance_point_to_segment_m(
    p: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
) -> float:
    px, py = _to_local_xy(p, a)
    bx, by = _to_local_xy(b, a)
    ab2 = bx * bx + by * by
    if ab2 == 0:
        return math.hypot(px, py)
    t = max(0.0, min(1.0, (px * bx + py * by) / ab2))
    cx = t * bx
    cy = t * by
    return math.hypot(px - cx, py - cy)


def _is_between_target_and_road(
    blocker: tuple[float, float],
    target: tuple[float, float],
    road: tuple[float, float],
) -> bool:
    bx, by = _to_local_xy(blocker, target)
    rx, ry = _to_local_xy(road, target)
    br = bx * rx + by * ry
    rr = rx * rx + ry * ry
    return br > 0 and br < rr


def infer_shielding(
    target_point: tuple[float, float],
    road_point: tuple[float, float],
    building_points: list[dict[str, Any]],
    target_building_token: str = "",
    corridor_width_m: float = 20.0,
) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    target_token_norm = _norm_text(target_building_token)
    for item in building_points:
        point = _to_point(item)
        if point is None:
            continue
        token_norm = _norm_text(str(item.get("building_token", "")).strip())
        if target_token_norm and token_norm == target_token_norm:
            continue
        if not _is_between_target_and_road(point, target_point, road_point):
            continue
        offset_m = _distance_point_to_segment_m(point, target_point, road_point)
        if offset_m > corridor_width_m:
            continue
        blockers.append({
            "name": str(item.get("name", "")).strip(),
            "building_token": str(item.get("building_token", "")).strip(),
            "offset_m": round(offset_m, 1),
        })
    count = len(blockers)
    level = "none" if count == 0 else "partial" if count == 1 else "strong"
    return {
        "shielding_level": level,
        "blocker_count": count,
        "blocker_names": [x["name"] for x in blockers[:3]],
    }


def build_shielding_result(
    road_result: EngineResult,
    target_point: tuple[float, float] | None,
    road_point: tuple[float, float] | None,
    community_name: str,
    target_building_token: str,
    cache_path: str | Path = CACHE_FILE,
) -> EngineResult | None:
    if target_point is None or road_point is None:
        return None
    if road_result.category != "road":
        return None

    cache = load_building_cache(cache_path)
    building_points = get_cached_buildings(cache, community_name)
    if not building_points:
        return None

    shielding = infer_shielding(
        target_point=target_point,
        road_point=road_point,
        building_points=building_points,
        target_building_token=target_building_token,
        corridor_width_m=20.0,
    )

    level = shielding["shielding_level"]
    if level == "none":
        return None

    road_kind = str(road_result.evidence.get("road_kind", "arterial")).strip()
    return EngineResult(
        engine="shielding_engine",
        enabled=True,
        score_delta=0,
        confidence=0.76 if level == "strong" else 0.82,
        category="shielding",
        priority=80,
        evidence={
            "road_engine_label": road_result.display.label,
            "road_name": road_result.evidence.get("road_name", ""),
            "road_kind": road_kind,
            "road_distance_m": road_result.evidence.get("distance_m"),
            "shielding_level": level,
            "blocker_count": shielding["blocker_count"],
            "blocker_names": shielding["blocker_names"],
        },
        explanation="识别到前排遮挡证据。",
        display=DisplayPayload(
            label="遮挡证据",
            detail=f"{level}｜挡住 {shielding['blocker_count']} 栋",
            value_text="",
        ),
        weight_hint=1.0,
    )
