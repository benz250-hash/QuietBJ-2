# app.py 核心替换片段

## 1）删掉这些导入与函数

- 删除 `zone_result as engine_zone_result`
- 删除 `score_signal_by_label`
- 删除 `refine_noise_summary`
- 删除任何在 `app.py` 里自己汇总 `traffic_penalty / local_life_penalty / external_environment_impact` 的逻辑

## 2）把 imports 改成

```python
from building_engine import building_year_result, density_result
from noise_point_engine import NoisePointEngine
from score_engine import ScoreEngine
from shielding_engine import (
    build_cache_export_payload,
    build_shielding_result,
    collect_cache_stats,
    load_building_cache,
    merge_cache_payload,
    normalize_import_payload,
    replace_cache_from_payload,
    save_building_cache,
    upsert_building_point,
)
```

## 3）替换 `build_engine_results`

```python
def build_engine_results(
    community_row: dict[str, Any],
    building_location_text: str,
    regeo: dict[str, Any] | None,
    poi_results: dict[str, list[dict[str, Any]]],
) -> list[EngineResult]:
    results: list[EngineResult] = []

    noise_results = NoisePointEngine().evaluate(regeo, poi_results)
    results.extend(noise_results)

    target_point = parse_location_text(building_location_text)
    community_name = str(community_row.get("community_name", "")).strip()
    target_building_token = str(community_row.get("_detail_token", "")).strip()

    for item in noise_results:
        if item.category != "road":
            continue
        road_point = road_point_for_engine_result(item, building_location_text, regeo)
        shield = build_shielding_result(
            road_result=item,
            target_point=target_point,
            road_point=road_point,
            community_name=community_name,
            target_building_token=target_building_token,
        )
        if shield:
            results.append(shield)

    results.append(building_year_result(community_row.get("build_year", "")))
    results.append(density_result(community_row.get("far_ratio", "")))
    return results
```

## 4）替换 `build_noise_summary_from_breakdown`

```python
def build_noise_summary_from_breakdown(breakdown: Any) -> dict[str, Any]:
    signals: list[dict[str, Any]] = []
    adopted_results = list(getattr(breakdown, "results", []) or [])

    for item in adopted_results:
        effective_value = int(getattr(item, "effective_score_delta", 0))
        raw_value = int(getattr(item, "raw_score_delta", 0))
        if raw_value == 0 and effective_value == 0:
            continue

        display = getattr(item, "display", {}) or {}
        evidence = getattr(item, "evidence", {}) or {}
        signals.append(
            {
                "label": display.get("label") or getattr(item, "engine", ""),
                "detail": display.get("detail") or getattr(item, "explanation", ""),
                "score_delta": effective_value,
                "raw_score_delta": raw_value,
                "value_text": display.get("value_text") or f"{effective_value:+d}",
                "distance_m": evidence.get("distance_m", "-"),
                "category": getattr(item, "category", ""),
                "engine": getattr(item, "engine", ""),
                "evidence": evidence,
            }
        )

    summary = getattr(breakdown, "summary", {}) or {}
    return {
        "signals": signals,
        "traffic_penalty": int(summary.get("traffic_penalty", 0)),
        "local_life_penalty": int(summary.get("local_life_penalty", 0)),
        "total_penalty": int(summary.get("external_environment_impact", 0)),
    }
```

## 5）替换 `result_dict_from_breakdown`

```python
def result_dict_from_breakdown(breakdown: Any) -> dict[str, Any]:
    summary = getattr(breakdown, "summary", {}) or {}
    return {
        "base_score": int(summary.get("base_score", getattr(breakdown, "base_score", DEFAULT_BASE_SCORE))),
        "build_bonus": max(0, int(summary.get("building_adjustment", 0))),
        "density_adjustment": min(0, int(summary.get("building_adjustment", 0))),
        "density_penalty": abs(min(0, int(summary.get("building_adjustment", 0)))),
        "traffic_penalty": int(summary.get("traffic_penalty", 0)),
        "local_life_penalty": int(summary.get("local_life_penalty", 0)),
        "noise_penalty": int(summary.get("external_environment_impact", 0)),
        "external_environment_impact": int(summary.get("external_environment_impact", 0)),
        "final_score": int(summary.get("final_score", getattr(breakdown, "final_score", DEFAULT_BASE_SCORE))),
        "breakdown": breakdown,
    }
```

## 6）替换 `compute_position_result`

```python
def compute_position_result(
    community_row: dict[str, Any],
    score_engine: ScoreEngine,
    engine_results: list[EngineResult],
) -> dict[str, Any]:
    breakdown = score_engine.aggregate(engine_results, base_score=DEFAULT_BASE_SCORE)
    return result_dict_from_breakdown(breakdown=breakdown)
```

## 7）UI 四卡文案

- 删除“楼栋位置调整”
- 改成：
  - 标准基准分
  - 本地生活噪音
  - 建筑条件调整
  - 交通环境影响

这里的数值全部来自 `result_dict_from_breakdown()`。
