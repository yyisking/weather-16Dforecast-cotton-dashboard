#!/usr/bin/env python3
"""Build the static data payload for the public cotton dashboard."""

from __future__ import annotations

import json
import csv
import math
from collections import defaultdict
from datetime import date
from pathlib import Path


SITE_ROOT = Path(__file__).resolve().parent
COTTON_ROOT = SITE_ROOT.parent
DIST = SITE_ROOT / "dist"

BRIEF_PATH = COTTON_ROOT / "research/derived/cotton_current_supply_decision_brief_v0_2.json"
AUSTRALIA_LATEST_PATH = COTTON_ROOT / "au_weather/derived/australia_theoretical_weather_stress_index_v0_1_latest.json"
AUSTRALIA_DAILY_PATH = COTTON_ROOT / "au_weather/derived/australia_theoretical_weather_stress_index_v0_1_daily.csv"
CENTRAL_ASIA_WATCH_PATH = COTTON_ROOT / "research/derived/central_asia_cotton_current_weather_watch_v0_2.json"
CENTRAL_ASIA_SEASONAL_PATH = COTTON_ROOT / "research/derived/australia_central_asia_cotton_era5_daily_seasonality_v0_2.csv"
REGION_PATHS = {
    "United States": COTTON_ROOT / "us_weather/derived/us_tx_theoretical_weather_stress_index_v0_1_latest.json",
    "China": COTTON_ROOT / "cn_xj_weather/derived/xinjiang_theoretical_weather_stress_index_v0_1_latest.json",
    "India": COTTON_ROOT / "in_weather/derived/india_central_rainfed_theoretical_weather_stress_index_v0_1_latest.json",
    "Brazil": COTTON_ROOT / "br_weather/derived/brazil_mt_theoretical_weather_stress_index_v0_1_latest.json",
}

DAILY_PATHS = {
    "China": COTTON_ROOT / "cn_xj_weather/derived/xinjiang_theoretical_weather_stress_index_v0_1_daily.csv",
    "United States": COTTON_ROOT / "us_weather/derived/us_tx_theoretical_weather_stress_index_v0_1_daily.csv",
    "Brazil": COTTON_ROOT / "br_weather/derived/brazil_mt_theoretical_weather_stress_index_v0_1_daily.csv",
    "India": COTTON_ROOT / "in_weather/derived/india_central_rainfed_theoretical_weather_stress_index_v0_1_daily.csv",
}

CENTRAL_ASIA_IDS = {
    "Turkistan Region": "kazakhstan_turkistan",
    "Jalal-Abad Oblast": "kyrgyzstan_jalal_abad",
    "Osh Oblast": "kyrgyzstan_osh",
    "Khatlon Oblast": "tajikistan_khatlon",
    "Sughd Oblast": "tajikistan_sughd",
    "Mary Velayat": "turkmenistan_mary",
    "Dashoguz Velayat": "turkmenistan_dashoguz",
    "Fergana Region": "uzbekistan_fergana",
    "Syrdarya Region": "uzbekistan_syrdarya",
    "Bukhara Region": "uzbekistan_bukhara",
}
CENTRAL_COUNTRY_DISPLAY = {
    "Kazakhstan": "哈萨克斯坦", "Kyrgyzstan": "吉尔吉斯斯坦", "Tajikistan": "塔吉克斯坦",
    "Turkmenistan": "土库曼斯坦", "Uzbekistan": "乌兹别克斯坦",
}
CENTRAL_AOI_DISPLAY = {
    "Turkistan Region": "突厥斯坦州", "Jalal-Abad Oblast": "贾拉拉巴德州", "Osh Oblast": "奥什州",
    "Khatlon Oblast": "哈特隆州", "Sughd Oblast": "索格特州", "Mary Velayat": "马雷州",
    "Dashoguz Velayat": "达沙古兹州", "Fergana Region": "费尔干纳州", "Syrdarya Region": "锡尔河州",
    "Bukhara Region": "布哈拉州",
}

METRIC_META = {
    "score": {"label": "综合天气胁迫", "unit": "分", "window": "逐日指数"},
    "root_zone_dryness": {"label": "根区干旱", "unit": "分", "window": "逐日因子分"},
    "high_heat": {"label": "高温", "unit": "分", "window": "逐日因子分"},
    "low_temperature": {"label": "低温", "unit": "分", "window": "逐日因子分"},
    "excess_rain": {"label": "过量降雨", "unit": "分", "window": "逐日因子分"},
    "spring_wind": {"label": "春季风害", "unit": "分", "window": "逐日因子分"},
    "establishment_excess_rain": {"label": "播种建苗期过量降雨", "unit": "分", "window": "逐日因子分"},
    "harvest_rain": {"label": "收获期降雨", "unit": "分", "window": "逐日因子分"},
    "high_temperature": {"label": "高温", "unit": "分", "window": "逐日因子分"},
    "high_vpd": {"label": "高 VPD", "unit": "分", "window": "逐日因子分"},
    "low_solar_radiation": {"label": "低太阳辐射", "unit": "分", "window": "逐日因子分"},
    "hot_dry_compound": {"label": "高温干旱复合", "unit": "分", "window": "逐日因子分"},
    "excess_rain_waterlogging": {"label": "过量降雨／渍涝", "unit": "分", "window": "逐日因子分"},
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
    "Australia": {
        "id": "australia",
        "name": "澳大利亚 · 东部棉区",
        "short_name": "东部棉区",
        "stage_display": "典型当地种植季代理；DD1532 仅作热量进程语境",
        "factor_fields": [
            ("low_temperature", "低温", "low_temperature_score"),
            ("high_heat", "高温", "high_heat_score"),
            ("excess_rain", "过量降雨", "excess_rain_score"),
            ("high_vpd", "高 VPD", "high_vpd_score"),
            ("low_solar", "低太阳辐射", "low_solar_score"),
        ],
    },
}

GEO_DISPLAY = {
    "World": "全球",
    "China": "中国",
    "United States": "美国",
    "Brazil": "巴西",
    "India": "印度",
    "Australia": "澳大利亚",
}

BAND_DISPLAY = {"low": "低度", "mild": "轻度", "moderate": "中度", "high": "高度"}
CONFIDENCE_DISPLAY = {"low": "低", "medium": "中", "high": "高", "limited": "有限"}

SEASON_WINDOWS = {
    "China": ("04-01", "11-30", "新疆 04-01—11-30", "verified_stage_scoring_window"),
    "United States": ("02-01", "11-30", "得州 02-01—11-30", "verified_stage_scoring_window"),
    "Brazil": ("01-01", "09-30", "巴西 MT 01-01—09-30", "verified_stage_scoring_window"),
    "India": ("06-01", "12-31", "印度中部雨养带 06-01—12-31", "verified_stage_scoring_window"),
}
CENTRAL_WINDOW = ("03-01", "10-31", "03-01—10-31（页面代理窗口；未核实当地作季）",
                  "display_window_proxy_not_verified_local_stage_calendar")
AUSTRALIA_WINDOW = ("09-01", "06-30", "澳洲 09-01—次年 06-30", "user_defined_cross_year_display_window")


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


def _calendar_keys() -> list[str]:
    """Return leap-safe month-day keys for a 365-day seasonal axis."""
    keys = []
    cursor = date(2001, 1, 1)
    while cursor.year == 2001:
        if cursor.month != 2 or cursor.day != 29:
            keys.append(cursor.strftime("%m-%d"))
        cursor = cursor.fromordinal(cursor.toordinal() + 1)
    return keys


def _window_keys(start: str, end: str) -> list[str]:
    """Return inclusive month-day keys, with no February 29."""
    start_month, start_day = (int(part) for part in start.split("-"))
    end_month, end_day = (int(part) for part in end.split("-"))
    all_keys = _calendar_keys()
    start_index = all_keys.index(start)
    if (end_month, end_day) >= (start_month, start_day):
        end_index = all_keys.index(end)
        return all_keys[start_index:end_index + 1]
    return all_keys[start_index:] + all_keys[:all_keys.index(end) + 1]


def _crop(values: list[float | None], all_keys: list[str], wanted: list[str]) -> list[float | None]:
    by_key = dict(zip(all_keys, values))
    return [by_key.get(key) for key in wanted]


def build_seasonal(geography: str) -> dict:
    """Build daily seasonal bands and current/prior year traces from approved daily files."""
    path = DAILY_PATHS[geography]
    if not path.exists():
        return {"status": "gap", "source": str(path), "metrics": {}}
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return {"status": "gap", "source": str(path), "metrics": {}}

    all_keys = _calendar_keys()
    window_start, window_end, window_label, window_status = SEASON_WINDOWS[geography]
    keys = _window_keys(window_start, window_end)
    by_metric_year_day: dict[str, dict[int, dict[str, list[float]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    metric_fields = {"score": "theoretical_weather_stress_index"}
    for _factor_id, _label, field in REGION_META[geography]["factor_fields"]:
        metric_fields[_factor_id] = field
    years = set()
    for row in rows:
        raw_date = row.get("date") or ""
        try:
            parsed = date.fromisoformat(raw_date[:10])
        except ValueError:
            continue
        if parsed.month == 2 and parsed.day == 29:
            continue
        years.add(parsed.year)
        day_key = parsed.strftime("%m-%d")
        for metric, field in metric_fields.items():
            value = row.get(field)
            if value in (None, "", "null", "None"):
                continue
            try:
                numeric = float(value)
                if math.isfinite(numeric):
                    by_metric_year_day[metric][parsed.year][day_key].append(numeric)
            except (TypeError, ValueError):
                continue
    if not years:
        return {"status": "gap", "source": str(path), "metrics": {}}

    current_year = max(years)
    prior_year = current_year - 1
    metrics = {}
    for metric in metric_fields:
        year_map = by_metric_year_day.get(metric, {})

        def year_trace(year: int) -> list[float | None]:
            return [
                (sum(year_map.get(year, {}).get(key, [])) / len(year_map[year][key]))
                if year_map.get(year, {}).get(key)
                else None
                for key in all_keys
            ]

        current = year_trace(current_year)
        prior = year_trace(prior_year)
        historical_years = sorted(year for year in year_map if year not in {current_year, prior_year})
        hist_min, hist_max = [], []
        for key in all_keys:
            values = [
                sum(year_map[year][key]) / len(year_map[year][key])
                for year in historical_years
                if year_map[year].get(key)
            ]
            hist_min.append(min(values) if values else None)
            hist_max.append(max(values) if values else None)
        if not any(value is not None for value in current + prior + hist_min + hist_max):
            continue
        meta = dict(METRIC_META.get(metric, {"label": metric, "unit": "分", "window": "逐日因子分"}))
        meta.update(
            {
                "day_keys": keys,
                "history_min": _crop(hist_min, all_keys, keys),
                "history_max": _crop(hist_max, all_keys, keys),
                "last_year": _crop(prior, all_keys, keys),
                "current_year": _crop(current, all_keys, keys),
                "last_year_label": str(prior_year),
                "current_year_label": str(current_year),
                "history_years": historical_years,
                "history_year_count": len(historical_years),
                "status": "available" if any(value is not None for value in current) else "historical_only",
            }
        )
        metrics[metric] = meta
    return {
        "status": "available" if metrics else "gap",
        "source": str(path.relative_to(COTTON_ROOT)),
        "axis": "month_day",
        "current_year": current_year,
        "last_year": prior_year,
        "display_window_start": window_start,
        "display_window_end": window_end,
        "display_window_label": window_label,
        "display_window_status": window_status,
        "cross_year_axis": False,
        "metrics": metrics,
    }


def build_australia_seasonal() -> dict:
    """Build the Australia 2026/27 and 2025/26 cross-year display axis."""
    if not AUSTRALIA_DAILY_PATH.exists():
        return {"status": "gap", "source": str(AUSTRALIA_DAILY_PATH), "metrics": {}}
    with AUSTRALIA_DAILY_PATH.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    keys = _window_keys(AUSTRALIA_WINDOW[0], AUSTRALIA_WINDOW[1])
    metric_fields = {
        "score": "theoretical_weather_stress_index",
        "low_temperature": "low_temperature_score",
        "high_heat": "high_heat_score",
        "excess_rain": "excess_rain_score",
        "high_vpd": "high_vpd_score",
        "low_solar": "low_solar_score",
    }
    year_map: dict[str, dict[int, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    years: set[int] = set()
    for row in rows:
        raw_date = row.get("date", "")
        try:
            parsed = date.fromisoformat(raw_date[:10])
        except ValueError:
            continue
        if parsed.month == 2 and parsed.day == 29:
            continue
        years.add(parsed.year)
        for metric, field in metric_fields.items():
            value = row.get(field, "")
            if value not in (None, "", "null", "None"):
                try:
                    numeric = float(value)
                    if math.isfinite(numeric):
                        year_map[metric][parsed.year][parsed.strftime("%m-%d")] = numeric
                except (TypeError, ValueError):
                    pass
    metrics = {}
    all_keys = _calendar_keys()

    def season_trace(metric: str, season_start: int) -> list[float | None]:
        values = []
        for key in keys:
            month, day = (int(part) for part in key.split("-"))
            source_year = season_start if month >= 9 else season_start + 1
            # The frozen V0.1 scoring contract has no May–June score values.
            if month in (5, 6):
                values.append(None)
            else:
                values.append(year_map[metric].get(source_year, {}).get(key))
        return values

    current_year = "2026/27"
    prior_year = "2025/26"
    for metric, meta in ((m, METRIC_META.get(m, {"label": m, "unit": "分", "window": "逐日因子分"})) for m in metric_fields):
        current = season_trace(metric, 2026)
        prior = season_trace(metric, 2025)
        metrics[metric] = {
            **dict(meta), "day_keys": keys, "history_min": [None] * len(keys), "history_max": [None] * len(keys),
            "last_year": prior, "current_year": current, "last_year_label": str(prior_year),
            "current_year_label": str(current_year), "history_years": [], "history_year_count": 0,
            "status": "available" if any(v is not None for v in current) else "gap",
        }
    return {
        "status": "available" if metrics else "gap", "source": str(AUSTRALIA_DAILY_PATH.relative_to(COTTON_ROOT)),
        "axis": "cross_year_month_day", "current_year": current_year, "last_year": prior_year,
        "display_window_start": AUSTRALIA_WINDOW[0], "display_window_end": AUSTRALIA_WINDOW[1],
        "display_window_label": AUSTRALIA_WINDOW[2], "display_window_status": AUSTRALIA_WINDOW[3],
        "cross_year_axis": True,
        "metrics": metrics,
    }


def build_central_asia_seasonal() -> dict:
    """Copy each Central Asia AOI/variable daily row directly from V0.2 seasonality."""
    if not CENTRAL_ASIA_SEASONAL_PATH.exists():
        return {}
    all_keys = _calendar_keys()
    window_start, window_end, window_label, window_status = CENTRAL_WINDOW
    keys = _window_keys(window_start, window_end)
    rows_by_aoi: dict[str, list[dict[str, str]]] = defaultdict(list)
    with CENTRAL_ASIA_SEASONAL_PATH.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("country") in {"Kazakhstan", "Kyrgyzstan", "Tajikistan", "Turkmenistan", "Uzbekistan"}:
                rows_by_aoi[row["aoi_name"]].append(row)
    labels = {
        "temperature_2m_max": ("日最高温", "°C"), "temperature_2m_min": ("日最低温", "°C"),
        "precipitation_sum": ("日降水", "mm"), "shortwave_radiation_sum": ("日短波辐射", "MJ/m²"),
        "et0_fao_evapotranspiration": ("日参考蒸散", "mm"), "vapour_pressure_deficit_max": ("日最大VPD", "kPa"),
    }
    result = {}
    for aoi_name, rows in rows_by_aoi.items():
        if not rows:
            continue
        first = rows[0]
        metrics = {}
        for variable in labels:
            current = [None] * len(keys)
            prior = [None] * len(keys)
            hist_min = [None] * len(keys)
            hist_max = [None] * len(keys)
            for index, key in enumerate(keys):
                source = next(item for item in rows if item["month_day"] == key)
                def numeric(field: str):
                    value = source.get(field, "")
                    return None if value in (None, "") else float(value)
                hist_min[index] = numeric(f"{variable}_hist_min")
                hist_max[index] = numeric(f"{variable}_hist_max")
                prior[index] = numeric(f"{variable}_2025")
                current[index] = numeric(f"{variable}_2026")
            metrics[variable] = {
                "label": labels[variable][0], "unit": labels[variable][1], "window": "日值",
                "day_keys": keys, "history_min": hist_min, "history_max": hist_max,
                "last_year": prior, "current_year": current, "last_year_label": "2025",
                "current_year_label": "2026", "history_years": list(range(1991, 2025)),
                "history_year_count": 34, "status": "available",
                "lineage": first.get("gap_codes", ""),
            }
        result[CENTRAL_ASIA_IDS[aoi_name]] = {
            "country": first["country"], "country_display_name": CENTRAL_COUNTRY_DISPLAY[first["country"]],
            "aoi_name": aoi_name, "aoi_display_name": CENTRAL_AOI_DISPLAY[aoi_name],
            "status": "available", "source": str(CENTRAL_ASIA_SEASONAL_PATH.relative_to(COTTON_ROOT)),
            "axis": "month_day", "current_year": 2026, "last_year": 2025,
            "display_window_start": window_start, "display_window_end": window_end,
            "display_window_label": window_label, "display_window_status": window_status,
            "cross_year_axis": False,
            "metrics": metrics, "gap_codes": first.get("gap_codes", "").split(";") if first.get("gap_codes") else [],
        }
    return result


def build_region(geography: str, supply_row: dict | None = None) -> dict:
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
        "supply_risk_reading": (supply_row or {}).get("local_weather_supply_risk_reading"),
        "production_change_pct": (supply_row or {}).get("production_change_pct"),
        "ending_stocks_change_pct": (supply_row or {}).get("ending_stocks_change_pct"),
    }


def build_australia_region(supply_row: dict) -> dict:
    raw = read_json(AUSTRALIA_LATEST_PATH)
    meta = REGION_META["Australia"]
    official_supply = {
        "prior_source_table": supply_row["prior_source_table"],
        "current_source_table": supply_row["current_source_table"],
        "prior_value_status": supply_row["prior_value_status"],
        "current_value_status": supply_row["current_value_status"],
        "area_harvested_1000_ha": supply_row["current_area_harvested_1000_ha"],
        "current_production_1000_480lb_bales": supply_row["current_production_1000_480lb_bales"],
        "production_change_1000_480lb_bales": supply_row["production_change_1000_480lb_bales"],
        "production_change_pct": supply_row["production_change_pct"],
        "current_domestic_use_1000_480lb_bales": supply_row["current_domestic_use_1000_480lb_bales"],
        "domestic_use_change_pct": supply_row["domestic_use_change_pct"],
        "current_exports_1000_480lb_bales": supply_row["current_exports_1000_480lb_bales"],
        "current_ending_stocks_1000_480lb_bales": supply_row["current_ending_stocks_1000_480lb_bales"],
        "ending_stocks_change_1000_480lb_bales": supply_row["ending_stocks_change_1000_480lb_bales"],
        "ending_stocks_change_pct": supply_row["ending_stocks_change_pct"],
        "current_ending_stocks_to_total_use_pct": supply_row["current_ending_stocks_to_total_use_pct"],
        "ending_stocks_to_total_use_change_pp": supply_row["ending_stocks_to_total_use_change_pp"],
        "derived_metric_gap_codes": supply_row["derived_metric_gap_codes"],
    }
    prod_change = official_supply["production_change_1000_480lb_bales"]
    prod_pct = official_supply["production_change_pct"]
    stocks_change = official_supply["ending_stocks_change_1000_480lb_bales"]
    stocks_pct = official_supply["ending_stocks_change_pct"]
    supply_detail = (
        f"USDA 官方棉花产量变化 {prod_change:+,} 千包（{prod_pct:+.2f}%）；"
        f"期末库存变化 {stocks_change:+,} 千包（{stocks_pct:+.2f}%）"
    )
    factors = []
    for factor_id, label, field in meta["factor_fields"]:
        value = factor_value(raw, field)
        factors.append({"id": factor_id, "label": label, "score": value,
                        "status": "available" if value is not None else "not_available_or_inactive"})
    gap_codes = [part for part in (raw.get("gap_codes") or []) if part]
    return {
        "id": meta["id"], "name": meta["name"], "short_name": meta["short_name"],
        "geography": "Australia", "date": raw.get("date"), "source_file_max_date": raw.get("source_file_max_date"),
        "score": raw.get("theoretical_weather_stress_index"), "band": raw.get("stress_band"),
        "band_display": BAND_DISPLAY.get(raw.get("stress_band"), "暂无"), "change_7d": raw.get("change_7d"),
        "change_yoy": raw.get("change_yoy"), "score_7d_ago": raw.get("score_7d_ago"),
        "score_year_ago": raw.get("score_year_ago"), "confidence": raw.get("confidence"),
        "confidence_display": CONFIDENCE_DISPLAY.get(raw.get("confidence"), "暂无"),
        "point_coverage": raw.get("point_coverage"), "factor_weight_coverage": raw.get("factor_weight_coverage"),
        "stage_proxy": raw.get("stage_proxy"), "stage_binding": raw.get("stage_binding"),
        "stage_display": meta["stage_display"], "source_mode": source_mode(raw),
        "theoretical_not_calibrated": raw.get("theoretical_not_calibrated"), "factors": factors,
        "drivers": raw.get("primary_stress_drivers") or [], "inactive": raw.get("countervailing_or_inactive_factors") or [],
        "gap_codes": gap_codes,
        "supply_risk_reading": supply_row["local_weather_supply_risk_reading"],
        "production_change_pct": supply_row["production_change_pct"],
        "ending_stocks_change_pct": supply_row["ending_stocks_change_pct"],
        "official_supply": official_supply,
        "supply_detail": supply_detail,
        "supply_risk_reading": f"{supply_row['local_weather_supply_risk_reading']}；{supply_detail}；天气指数未换算产量",
    }


def build_central_asia_watch() -> list[dict]:
    payload = read_json(CENTRAL_ASIA_WATCH_PATH)
    result = []
    for row in payload.get("aois", []):
        enriched = dict(row)
        enriched["id"] = CENTRAL_ASIA_IDS[row["aoi_name"]]
        enriched["country_label"] = row["country"]
        result.append(enriched)
    return result


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

    region_geographies = ("China", "United States", "Brazil", "India")
    regions = [build_region(geo, row_by_geo[geo]) for geo in region_geographies]
    regions.append(build_australia_region(row_by_geo["Australia"]))
    seasonal = {REGION_META[geo]["id"]: build_seasonal(geo) for geo in region_geographies}
    seasonal["australia"] = build_australia_seasonal()
    central_watch = build_central_asia_watch()
    return {
        "dashboard_id": "cotton_public_supply_weather_dashboard_v0_3",
        "snapshot_as_of_date": brief["snapshot_as_of_date"],
        "official_report_month": brief["official_report_month"],
        "supply_snapshot_id": brief["source_snapshot_id"],
        "conclusion": brief["current_conclusion"],
        "tightening_weather_condition_met": brief["tightening_weather_condition_met"],
        "global_numeric_weather_score": None,
        "global_weather_conclusion": brief["global_weather_conclusion"],
        "cross_region_weather_comparable": False,
        "weather_to_supply_conversion_performed": False,
        "scored_region_count": 5,
        "descriptive_only_aoi_count": 10,
        "units": brief["unit_definitions"],
        "official_source": {
            "publisher": "USDA Foreign Agricultural Service",
            "title": "Cotton: World Markets and Trade",
            "url": "https://apps.fas.usda.gov/psdonline/circulars/cotton.pdf",
        },
        "supply": supply,
        "regions": regions,
        "seasonal": seasonal,
        "central_asia_watch": {
            "as_of_weather_date": "2026-09-10", "source_model": "era5",
            "observed_reanalysis_only": True, "forecast_included": False,
            "cross_region_comparable": False, "score_available_count": 0,
            "weather_anomaly_score_available_count": 10, "weather_stress_score_available_count": 0,
            "aoi_count": 10, "interpretation_warning": "异常度高只表示当地天气偏离自身常态，不代表更不利、减产更多或可跨 AOI 排名；棉花胁迫分 0/10 可用。",
            "aois": central_watch,
        },
        "central_asia_seasonal": build_central_asia_seasonal(),
        "limitations": brief["limitations"],
    }


def main() -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    payload = build()
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    for output in (SITE_ROOT / "data.json", DIST / "data.json"):
        output.write_text(serialized, encoding="utf-8")
        print(f"wrote {output}")
    root_index = SITE_ROOT / "index.html"
    dist_index = DIST / "index.html"
    if root_index.exists():
        dist_index.write_bytes(root_index.read_bytes())
        print(f"synced {dist_index} from {root_index}")


if __name__ == "__main__":
    main()
