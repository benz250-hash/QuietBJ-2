# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from engine_schema import DisplayPayload, EngineResult

CACHE_FILE = Path("community_building_cache.json")


def _norm_text(text: str) -> str:
    return "".join(str(text or "").lower().split())


def load_building_cache(path: str | Path = CACHE_FILE) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def save_building_cache(cache: dict[str, Any], path: str | Path = CACHE_FILE) -> None:
    Path(path).write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def collect_cache_stats(cache: dict[str, Any]) -> dict[str, Any]:
    community_count = len(cache or {})
    building_count = sum(len(list((entry or {}).get("buildings", []) or [])) for entry in (cache or {}).values())
    return {"community_count": community_count, "building_count": building_count}


def build_cache_export_payload(cache: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "quietbj_cache_v1",
        "exported_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stats": collect_cache_stats(cache),
        "communities": cache or {},
    }


def normalize_import_payload(payload: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    if not isinstance(payload, dict):
        return False, "导入文件不是合法 JSON 对象。", {}
    communities = payload.get("communities", {})
    if not isinstance(communities, dict):
        return False, "communities 字段格式不正确。", {}
    return True, "OK", communities


def merge_cache_payload(current_cache: dict[str, Any], import_payload: dict[str, Any]) -> dict[str, Any]:
    ok, msg, imported = normalize_import_payload(import_payload)
    if not ok:
        raise ValueError(msg)
    merged = dict(current_cache or {})
    merged.update(imported)
    return merged


def replace_cache_from_payload(import_payload: dict[str, Any]) -> dict[str, Any]:
    ok, msg, imported = normalize_import_payload(import_payload)
    if not ok:
        raise ValueError(msg)
    return imported


def _community_aliases(name: str) -> list[str]:
    text = str(name or "").strip()
    return [text] if text else []


def _find_best_cache_key(cache: dict[str, Any], community_name: str) -> str | None:
    aliases = set(_community_aliases(community_name))
    for key in cache.keys():
        if key in aliases:
            return key
    return None


def get_cached_buildings(cache: dict[str, Any], community_name: str) -> list[dict[str, Any]]:
    key = _find_best_cache_key(cache, community_name)
    if not key:
        return []
    return list((cache.get(key, {}) or {}).get("buildings", []) or [])


def upsert_building_point(
    cache: dict[str, Any],
    community_name: str,
    building: dict[str, Any],
    source: str = "query_trace",
    updated_at: str = "",
) -> dict[str, Any]:
    cache = dict(cache or {})
    entry = dict(cache.get(community_name, {}))
    buildings = list(entry.get("buildings", []) or [])
    target_token = _norm_text(str(building.get("building_token", "")))
    replaced = False
    for idx, item in enumerate(buildings):
        item_token = _norm_text(str(item.get("building_token", "")))
        if target_token and item_token == target_token:
            buildings[idx] = {**item, **building}
            replaced = True
            break
    if not replaced:
        buildings.append(building)
    entry["source"] = source
    entry["updated_at"] = updated_at or datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    entry["buildings"] = buildings
    cache[community_name] = entry
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


def _distance_point_to_segment_m(p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    px, py = _to_local_xy(p, a)
    bx, by = _to_local_xy(b, a)
    ab2 = bx * bx + by * by
    if ab2 == 0:
        return math.hypot(px, py)
    t = max(0.0, min(1.0, (px * bx + py * by) / ab2))
    cx = t * bx
    cy = t * by
    return math.hypot(px - cx, py - cy)


def _is_between_target_and_road(blocker: tuple[float, float], target: tuple[float, float], road: tuple[float, float]) -> bool:
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
        token_norm = _norm_text(str(item.get("building_token", "")))
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
    if target_point is None or road_point is None or road_result.category != "road":
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
    if shielding["shielding_level"] == "none":
        return None
    return EngineResult(
        engine="shielding_engine",
        enabled=True,
        score_delta=0,
        confidence=0.76,
        category="shielding",
        priority=80,
        evidence={
            "road_name": road_result.evidence.get("road_name", ""),
            "road_kind": road_result.evidence.get("road_kind", "secondary"),
            "shielding_level": shielding["shielding_level"],
            "blocker_count": shielding["blocker_count"],
            "blocker_names": shielding["blocker_names"],
        },
        explanation="识别到前排遮挡证据。",
        display=DisplayPayload(
            label="遮挡证据",
            detail=f"{shielding['shielding_level']}｜挡住 {shielding['blocker_count']} 栋",
            value_text="",
        ),
        tags=["evidence_only", "shielding"],
    )
