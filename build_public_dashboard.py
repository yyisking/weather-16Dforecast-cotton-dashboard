#!/usr/bin/env python3
"""Build the static data payload for the public cotton dashboard."""

from __future__ import annotations

import json
from pathlib import Path


SITE_ROOT = Path(__file__).resolve().parent
COTTON_ROOT = SITE_ROOT.parent
DIST = SITE_ROOT / "dist"

BRIEF_PATH = COTTON_ROOT / "research/derived/cotton_current_supply_decision_brief_v0_1.json"
REGION_PATHS = {
    "United States": COTTON_ROOT / "us_weather/derived/us_tx_theoretical_weather_stress_index_v0_1_latest.json",
    "China": COTTON_ROOT / "cn_xj_weather/derived/xinjiang_theoretical_weather_stress_index_v0_1_latest.json",
    "India": COTTON_ROOT / "in_weather/derived/india_central_rainfed_theoretical_weather_stress_index_v0_1_latest.json",
    "Brazil": COTTON_ROOT / "br_weather/derived/brazil_mt_theoretical_weather_stress_index_v0_1_latest.json",
}

REGION_META = {
    "China": {
        "id": "china",
        "name": "中国 · 新疆",
        "short_name": "新疆",
        "stage_display": "北疆吐絮；南疆与东疆处于吐絮—采收期代理",
        "factor_fields": [
            ("high_heat", "高温", "high_heat_score"),
            ("low_temperature", "低温", "low_temperature_score"),
            ("excess_rain", "过量降雨", "excess_rain_score"),
            ("spring_wind", "春季风害", "spring_wind_score"),
        ],
    },
    "United States": {
        "id": "us",
        "name": "美国 · 得州",
        "short_name": "得州",
        "stage_display": "得州各分区典型作物日历代理",
        "factor_fields": [
            ("root_zone_dryness", "根区干旱", "root_zone_dryness_score"),
            ("high_heat", "高温", "high_heat_score"),
            ("low_temperature", "低温", "low_temperature_score"),
            ("establishment_excess_rain", "播种建苗期过量降雨", "establishment_excess_rain_score"),
            ("harvest_rain", "收获期降雨", "harvest_rain_score"),
        ],
    },
    "Brazil": {
        "id": "brazil",
        "name": "巴西 · 马托格罗索",
        "short_name": "马托格罗索",
        "stage_display": "典型当地作物日历代理 · C 阶段",
        "factor_fields": [
            ("harvest_rain", "收获期降雨", "harvest_rain_score"),
            ("root_zone_dryness", "根区干旱", "root_zone_dryness_score"),
            ("high_temperature", "高温", "high_temperature_score"),
            ("high_vpd", "高 VPD", "high_vpd_score"),
            ("low_solar_radiation", "低太阳辐射", "low_solar_radiation_score"),
            ("low_temperature", "低温", "low_temperature_score"),
        ],
    },
    "India": {
        "id": "india",
        "name": "印度 · 中部雨养带",
        "short_name": "中部雨养带",
        "stage_display": "中部与特伦加纳开花—结铃期代理",
        "factor_fields": [
            ("root_zone_dryness", "根区干旱", "root_zone_dryness_score"),
            ("hot_dry_compound", "高温干旱复合", "hot_dry_compound_score"),
            ("excess_rain_waterlogging", "过量降雨／渍涝", "excess_rain_waterlogging_score"),
        ],
    },
}

GEO_DISPLAY = {
    "World": "全球",
    "China": "中国",
    "United States": "美国",
    "Brazil": "巴西",
    "India": "印度",
}

BAND_DISPLAY = {"low": "低度", "mild": "轻度", "moderate": "中度", "high": "高度"}
CONFIDENCE_DISPLAY = {"low": "低", "medium": "中", "high": "高", "limited": "有限"}


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def factor_value(raw: dict, field: str):
    if field in raw:
        return raw[field]
    return (raw.get("factor_scores") or {}).get(field.removesuffix("_score"))


def source_mode(raw: dict) -> str:
    if raw.get("observed_only") is True:
        return "仅实况"
    if raw.get("forecast_included") is True:
        return "实况＋预报"
    return "混合来源；逐行来源暂不可分"


def build_region(geography: str, supply_row: dict) -> dict:
    raw = read_json(REGION_PATHS[geography])
    meta = REGION_META[geography]
    factors = []
    for factor_id, label, field in meta["factor_fields"]:
        value = factor_value(raw, field)
        factors.append(
            {
                "id": factor_id,
                "label": label,
                "score": value,
                "status": "available" if value is not None else "not_available_or_inactive",
            }
        )

    return {
        "id": meta["id"],
        "name": meta["name"],
        "short_name": meta["short_name"],
        "geography": geography,
        "date": raw.get("date"),
        "source_file_max_date": raw.get("source_file_max_date"),
        "score": raw.get("theoretical_weather_stress_index"),
        "band": raw.get("stress_band"),
        "band_display": BAND_DISPLAY.get(raw.get("stress_band"), "暂无"),
        "change_7d": raw.get("change_7d"),
        "change_yoy": raw.get("change_yoy"),
        "score_7d_ago": raw.get("score_7d_ago"),
        "score_year_ago": raw.get("score_year_ago"),
        "confidence": raw.get("confidence"),
        "confidence_display": CONFIDENCE_DISPLAY.get(raw.get("confidence"), "暂无"),
        "point_coverage": raw.get("point_coverage"),
        "factor_weight_coverage": raw.get("factor_weight_coverage"),
        "stage_proxy": raw.get("stage_proxy"),
        "stage_binding": raw.get("stage_binding"),
        "stage_display": meta["stage_display"],
        "source_mode": source_mode(raw),
        "theoretical_not_calibrated": raw.get("theoretical_not_calibrated"),
        "factors": factors,
        "drivers": raw.get("primary_stress_drivers") or [],
        "inactive": raw.get("countervailing_or_inactive_factors") or [],
        "gap_codes": [part for part in (raw.get("gap_codes") or "").split(";") if part],
        "supply_risk_reading": supply_row.get("local_weather_supply_risk_reading"),
        "production_change_pct": supply_row.get("production_change_pct"),
        "ending_stocks_change_pct": supply_row.get("ending_stocks_change_pct"),
    }


def build() -> dict:
    brief = read_json(BRIEF_PATH)
    rows = brief["rows"]
    row_by_geo = {row["geography"]: row for row in rows}
    supply = []
    for row in rows:
        supply.append(
            {
                "geography": row["geography"],
                "name": GEO_DISPLAY[row["geography"]],
                "direction": row["official_balance_direction"],
                "area_harvested": row["current_area_harvested_1000_ha"],
                "production": row["current_production_1000_480lb_bales"],
                "production_prior": row["prior_production_1000_480lb_bales"],
                "production_change": row["production_change_1000_480lb_bales"],
                "production_change_pct": row["production_change_pct"],
                "domestic_use": row["current_domestic_use_1000_480lb_bales"],
                "domestic_use_change_pct": row["domestic_use_change_pct"],
                "imports": row["current_imports_1000_480lb_bales"],
                "exports": row["current_exports_1000_480lb_bales"],
                "ending_stocks": row["current_ending_stocks_1000_480lb_bales"],
                "ending_stocks_change_pct": row["ending_stocks_change_pct"],
                "stocks_to_use": row["current_ending_stocks_to_total_use_pct"],
                "stocks_to_use_prior": row["prior_ending_stocks_to_total_use_pct"],
                "stocks_to_use_change_pp": row["ending_stocks_to_total_use_change_pp"],
            }
        )

    regions = [build_region(geo, row_by_geo[geo]) for geo in ("China", "United States", "Brazil", "India")]
    return {
        "dashboard_id": "cotton_public_supply_weather_dashboard_v0_1",
        "snapshot_as_of_date": brief["snapshot_as_of_date"],
        "official_report_month": brief["official_report_month"],
        "conclusion": brief["current_conclusion"],
        "tightening_weather_condition_met": brief["tightening_weather_condition_met"],
        "global_numeric_weather_score": None,
        "global_weather_conclusion": brief["global_weather_conclusion"],
        "cross_region_weather_comparable": False,
        "weather_to_supply_conversion_performed": False,
        "units": brief["unit_definitions"],
        "official_source": {
            "publisher": "USDA Foreign Agricultural Service",
            "title": "Cotton: World Markets and Trade",
            "url": "https://apps.fas.usda.gov/psdonline/circulars/cotton.pdf",
        },
        "supply": supply,
        "regions": regions,
        "limitations": brief["limitations"],
    }


def main() -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    payload = build()
    output = DIST / "data.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {output}")


if __name__ == "__main__":
    main()

