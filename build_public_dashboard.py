#!/usr/bin/env python3
"""Build the static data payload for the public cotton dashboard."""

from __future__ import annotations

import json
import csv
import math
from collections import defaultdict
from datetime import date, timedelta
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

# V0.5 raw-weather display inputs.  These are deliberately separate from the
# score daily files above: the score contract is copied unchanged and the raw
# layer is rebuilt from point/day weather so a raw value can never masquerade
# as a 0--100 stress score.
RAW_POINT_CONFIG = {
    "China": {
        "path": COTTON_ROOT / "cn_xj_weather/points_daily.csv",
        "points": ("xj_shihezi", "xj_shawan", "xj_kuitun", "xj_changji", "xj_hutubi", "xj_bole", "xj_jinghe", "xj_kashgar", "xj_shache", "xj_bachu", "xj_aksu", "xj_awat", "xj_kuqa", "xj_shaya", "xj_korla", "xj_yuli", "xj_luntai", "xj_turpan"),
        "weights": {p: 1.0 / 18.0 for p in ("xj_shihezi", "xj_shawan", "xj_kuitun", "xj_changji", "xj_hutubi", "xj_bole", "xj_jinghe", "xj_kashgar", "xj_shache", "xj_bachu", "xj_aksu", "xj_awat", "xj_kuqa", "xj_shaya", "xj_korla", "xj_yuli", "xj_luntai", "xj_turpan")},
        "window": SEASON_WINDOWS["China"],
        "cutoff": date(2026, 9, 13),
        "history_years": list(range(2005, 2025)),
        "solar_status": "observed_only_excluded_pending_dedup",
    },
    "United States": {
        "path": COTTON_ROOT / "us_weather/points_daily.csv",
        "points": ("tx_hp_n", "tx_hp_c", "tx_hp_s", "tx_hp_w", "tx_hp_e", "tx_hp_sw", "tx_farwest", "tx_rolling", "tx_edwards", "tx_coastal", "tx_rgv", "tx_black"),
        "weights": {p: (0.64 / 6 if p.startswith("tx_hp_") else 0.36 / 6) for p in ("tx_hp_n", "tx_hp_c", "tx_hp_s", "tx_hp_w", "tx_hp_e", "tx_hp_sw", "tx_farwest", "tx_rolling", "tx_edwards", "tx_coastal", "tx_rgv", "tx_black")},
        "window": SEASON_WINDOWS["United States"],
        "cutoff": date(2026, 9, 13),
        "history_years": list(range(2005, 2025)),
        "solar_status": "observed_only_excluded_local_direction_gap",
    },
    "Brazil": {
        "path": COTTON_ROOT / "br_weather/points_daily.csv",
        "points": ("mt_campo_novo", "mt_campo_verde", "mt_diamantino", "mt_lucas", "mt_nova_mutum", "mt_nova_ubirata", "mt_primavera", "mt_rondonopolis", "mt_sapezal", "mt_sinop", "mt_sorriso", "mt_tangara"),
        "weights": {p: 1.0 / 12.0 for p in ("mt_campo_novo", "mt_campo_verde", "mt_diamantino", "mt_lucas", "mt_nova_mutum", "mt_nova_ubirata", "mt_primavera", "mt_rondonopolis", "mt_sapezal", "mt_sinop", "mt_sorriso", "mt_tangara")},
        "window": SEASON_WINDOWS["Brazil"],
        "cutoff": date(2026, 9, 16),
        "history_years": list(range(2005, 2025)),
        "solar_status": "included_in_model_contract",
    },
    "India": {
        "path": COTTON_ROOT / "in_weather/points_daily.csv",
        "points": ("gj_rajkot", "gj_surendranagar", "gj_bhavnagar", "gj_amreli", "gj_bharuch", "mh_akola", "mh_amravati", "mh_yavatmal", "mh_buldhana", "mh_jalgaon", "mh_jalna", "mp_khargone", "mp_dhar", "tg_adilabad", "tg_warangal", "tg_khammam"),
        "weights": {"GJ": 0.3404351768, "MH": 0.3739800544, "MP": 0.0643699003, "TG": 0.2212148685},
        "state_points": {"GJ": ("gj_rajkot", "gj_surendranagar", "gj_bhavnagar", "gj_amreli", "gj_bharuch"), "MH": ("mh_akola", "mh_amravati", "mh_yavatmal", "mh_buldhana", "mh_jalgaon", "mh_jalna"), "MP": ("mp_khargone", "mp_dhar"), "TG": ("tg_adilabad", "tg_warangal", "tg_khammam")},
        "window": SEASON_WINDOWS["India"],
        "cutoff": date(2026, 9, 13),
        "history_years": list(range(2005, 2025)),
        "solar_status": "observed_only_excluded_pending_dedup",
    },
}
RAW_LABELS = {
    "tmax_14d_mean": ("14日平均日最高温", "°C", "tmax", "mean"),
    "tmin_14d_mean": ("14日平均日最低温", "°C", "tmin", "mean"),
    "precip_14d_sum": ("14日累计降水", "mm", "precip", "sum"),
    "sw_rad_14d_mean": ("14日平均日短波辐射", "MJ/m²/日", "sw_rad", "mean"),
}
AUSTRALIA_ERA5_FILES = (
    "01_moree_era5_daily.json", "02_narrabri_era5_daily.json", "03_narromine_era5_daily.json",
    "04_griffith_era5_daily.json", "05_dalby_era5_daily.json", "07_goondiwindi_era5_daily.json",
    "08_emerald_era5_daily.json",
)
AUSTRALIA_RAW_DIR = COTTON_ROOT / "research/raw/australia_central_asia_era5_daily_v0_1"
AUSTRALIA_MANIFEST_PATH = AUSTRALIA_RAW_DIR / "source_manifest_v0_1.json"
AUSTRALIA_CROSSWALK_PATH = COTTON_ROOT / "research/derived/australia_central_asia_cotton_point_crosswalk_v0_1.csv"
AUSTRALIA_EXPECTED_UNITS = {
    "temperature_2m_max": "°C", "temperature_2m_min": "°C", "precipitation_sum": "mm",
    "shortwave_radiation_sum": "MJ/m²", "et0_fao_evapotranspiration": "mm", "vapour_pressure_deficit_max": "kPa",
}


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


STATUS_LABELS = {
    "available": "有值",
    "inactive_stage": "该阶段未启用",
    "future": "今年尚未来临",
    "source_gap": "源数据缺口",
}


def _compress_periods(keys: list[str], active_keys: set[str]) -> list[dict[str, str]]:
    """Compress active month-day keys into contiguous display-axis periods."""
    indices = [index for index, key in enumerate(keys) if key in active_keys]
    periods: list[dict[str, str]] = []
    if not indices:
        return periods
    start = previous = indices[0]
    for index in indices[1:]:
        if index != previous + 1:
            periods.append({"start": keys[start], "end": keys[previous]})
            start = index
        previous = index
    periods.append({"start": keys[start], "end": keys[previous]})
    return periods


def _status_counts(values: list[str]) -> dict[str, int]:
    return {status: values.count(status) for status in STATUS_LABELS}


def _score_meta(meta: dict, metric: str) -> dict:
    result = dict(meta)
    result.update(
        {
            "unit": "分",
            "scale_type": "fixed_score_0_100",
            "scale_min": 0,
            "scale_max": 100,
            "value_semantics": "0—100天气胁迫分；不是气象原值",
            "blank_value_label": "按状态显示：该阶段未启用／今年尚未来临／源数据缺口",
            "status_labels": STATUS_LABELS,
        }
    )
    return result


def _raw_meta(label: str, unit: str) -> dict:
    return {
        "label": label,
        "unit": unit,
        "window": "日值",
        "scale_type": "auto_unit",
        "scale_min": None,
        "scale_max": None,
        "value_semantics": "ERA5当地气象原值；不是0—100天气胁迫分",
        "blank_value_label": "空值＝源数据缺口；不转换为棉花胁迫分",
    }


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
    active_by_metric: dict[str, set[str]] = defaultdict(set)
    metric_fields = {"score": "theoretical_weather_stress_index"}
    for _factor_id, _label, field in REGION_META[geography]["factor_fields"]:
        metric_fields[_factor_id] = field
    years = set()
    source_dates: list[date] = []
    for row in rows:
        raw_date = row.get("date") or ""
        try:
            parsed = date.fromisoformat(raw_date[:10])
        except ValueError:
            continue
        if parsed.month == 2 and parsed.day == 29:
            continue
        years.add(parsed.year)
        source_dates.append(parsed)
        day_key = parsed.strftime("%m-%d")
        for metric, field in metric_fields.items():
            value = row.get(field)
            if value in (None, "", "null", "None"):
                continue
            try:
                numeric = float(value)
                if math.isfinite(numeric):
                    by_metric_year_day[metric][parsed.year][day_key].append(numeric)
                    active_by_metric[metric].add(day_key)
            except (TypeError, ValueError):
                continue
    if not years:
        return {"status": "gap", "source": str(path), "metrics": {}}

    current_year = max(years)
    prior_year = current_year - 1
    source_max_date = max(source_dates)
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
        active_keys = active_by_metric.get(metric, set())
        current_status = []
        prior_status = []
        for index, key in enumerate(all_keys):
            month, day = (int(part) for part in key.split("-"))
            if key not in active_keys:
                current_status.append("inactive_stage")
                prior_status.append("inactive_stage")
                continue
            current_date = date(current_year, month, day)
            if current_date > source_max_date:
                current_status.append("future")
            elif current[index] is None:
                current_status.append("source_gap")
            else:
                current_status.append("available")
            prior_status.append("available" if prior[index] is not None else "source_gap")
        current_status = _crop(current_status, all_keys, keys)
        prior_status = _crop(prior_status, all_keys, keys)
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
        meta = _score_meta(METRIC_META.get(metric, {"label": metric, "unit": "分", "window": "逐日因子分"}), metric)
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
                "last_year_status": prior_status,
                "current_year_status": current_status,
                "active_periods": _compress_periods(keys, active_keys),
                "source_file_max_date": source_max_date.isoformat(),
                "status_counts": {"last_year": _status_counts(prior_status), "current_year": _status_counts(current_status)},
                "source_gap_count": prior_status.count("source_gap") + current_status.count("source_gap"),
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
        "source_file_max_date": source_max_date.isoformat(),
        "source_gap_count": sum(metric.get("source_gap_count", 0) for metric in metrics.values()),
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
    active_by_metric: dict[str, set[str]] = defaultdict(set)
    years: set[int] = set()
    source_dates: list[date] = []
    for row in rows:
        raw_date = row.get("date", "")
        try:
            parsed = date.fromisoformat(raw_date[:10])
        except ValueError:
            continue
        if parsed.month == 2 and parsed.day == 29:
            continue
        years.add(parsed.year)
        source_dates.append(parsed)
        for metric, field in metric_fields.items():
            value = row.get(field, "")
            if value not in (None, "", "null", "None"):
                try:
                    numeric = float(value)
                    if math.isfinite(numeric):
                        year_map[metric][parsed.year][parsed.strftime("%m-%d")] = numeric
                        active_by_metric[metric].add(parsed.strftime("%m-%d"))
                except (TypeError, ValueError):
                    pass
    metrics = {}
    source_max_date = max(source_dates)

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

    def season_status(metric: str, season_start: int, values: list[float | None]) -> list[str]:
        active_keys = active_by_metric.get(metric, set())
        statuses = []
        for index, key in enumerate(keys):
            month, day = (int(part) for part in key.split("-"))
            if month in (5, 6) or key not in active_keys:
                statuses.append("inactive_stage")
                continue
            source_year = season_start if month >= 9 else season_start + 1
            absolute_date = date(source_year, month, day)
            if season_start == 2026 and absolute_date > source_max_date:
                statuses.append("future")
            elif values[index] is None:
                statuses.append("source_gap")
            else:
                statuses.append("available")
        return statuses

    current_year = "2026/27"
    prior_year = "2025/26"
    for metric, meta in ((m, METRIC_META.get(m, {"label": m, "unit": "分", "window": "逐日因子分"})) for m in metric_fields):
        current = season_trace(metric, 2026)
        prior = season_trace(metric, 2025)
        current_status = season_status(metric, 2026, current)
        prior_status = season_status(metric, 2025, prior)
        metrics[metric] = {
            **_score_meta(meta, metric), "day_keys": keys, "history_min": [None] * len(keys), "history_max": [None] * len(keys),
            "last_year": prior, "current_year": current, "last_year_label": str(prior_year),
            "current_year_label": str(current_year), "history_years": [], "history_year_count": 0,
            "status": "available" if any(v is not None for v in current) else "gap",
            "last_year_status": prior_status, "current_year_status": current_status,
            "active_periods": _compress_periods(keys, active_by_metric.get(metric, set())),
            "source_file_max_date": source_max_date.isoformat(),
            "status_counts": {"last_year": _status_counts(prior_status), "current_year": _status_counts(current_status)},
            "source_gap_count": prior_status.count("source_gap") + current_status.count("source_gap"),
        }
    return {
        "status": "available" if metrics else "gap", "source": str(AUSTRALIA_DAILY_PATH.relative_to(COTTON_ROOT)),
        "axis": "cross_year_month_day", "current_year": current_year, "last_year": prior_year,
        "display_window_start": AUSTRALIA_WINDOW[0], "display_window_end": AUSTRALIA_WINDOW[1],
        "display_window_label": AUSTRALIA_WINDOW[2], "display_window_status": AUSTRALIA_WINDOW[3],
        "cross_year_axis": True,
        "source_file_max_date": source_max_date.isoformat(),
        "source_gap_count": sum(metric.get("source_gap_count", 0) for metric in metrics.values()),
        "metrics": metrics,
    }


def _number(value):
    if value in (None, "", "null", "None"):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _rolling_point_values(records: dict[date, dict[str, float | None]], metric: str, mode: str) -> dict[date, float | None]:
    """Return complete trailing-14-day point exposures with no zero filling."""
    result = {}
    for day in sorted(records):
        values = []
        complete = True
        for offset in range(13, -1, -1):
            row = records.get(day - timedelta(days=offset))
            value = row.get(metric) if row else None
            if value is None:
                complete = False
                break
            values.append(value)
        if complete:
            result[day] = math.fsum(values) if mode == "sum" else math.fsum(values) / 14.0
        else:
            result[day] = None
    return result


def _load_old_point_records(config: dict) -> tuple[dict[str, dict[date, dict[str, float | None]]], date]:
    points = set(config["points"])
    records = {point: {} for point in points}
    with config["path"].open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            point = row.get("point_id")
            if point not in points:
                continue
            try:
                parsed = date.fromisoformat((row.get("date") or "")[:10])
            except ValueError:
                continue
            records[point][parsed] = {field: _number(row.get(field)) for field in ("tmax", "tmin", "precip", "sw_rad")}
    source_max = max(max(values) for values in records.values() if values)
    return records, source_max


def _spatial_raw(config: dict, point_values: dict[str, float | None], metric: str) -> tuple[float | None, float]:
    """Aggregate valid point exposures and apply the frozen 60% coverage gate."""
    if "state_points" not in config:
        weights = config["weights"]
    else:
        weights = {
            point: config["weights"][state] / len(points)
            for state, points in config["state_points"].items()
            for point in points
        }
    configured = math.fsum(weights.values())
    valid = [(weights[point], value) for point, value in point_values.items() if value is not None]
    coverage = math.fsum(weight for weight, _value in valid) / configured if configured else 0.0
    if coverage < 0.60 or not valid:
        return None, coverage
    return math.fsum(weight * value for weight, value in valid) / math.fsum(weight for weight, _value in valid), coverage


def _raw_meta_v05(label: str, unit: str, metric_id: str, solar_status: str) -> dict:
    solar_display_status = {
        "observed_only_excluded_pending_dedup": "仅展示原值；暂未计分（等待与其他因子去重）",
        "observed_only_not_scored_evidence_gap": "仅展示原值；暂未计分（当地影响方向证据不足）",
        "observed_only_excluded_local_direction_gap": "仅展示原值；暂未计分（当地影响方向证据不足）",
        "included_in_model_contract": "已纳入模型；当前9月阶段未启用",
        "stage_inactive_but_model_contract": "已纳入模型；当前9月阶段未启用",
        "included_and_active_in_current_stage": "已纳入模型；当前阶段启用",
    }
    return {
        "label": label,
        "unit": unit,
        "window": "trailing 14 days",
        "aggregation": "point-level trailing 14-day exposure, then frozen spatial aggregate",
        "scale_type": "auto_unit",
        "scale_min": None,
        "scale_max": None,
        "value_semantics": "棉区点位网络气象原值；不是0—100天气胁迫分，不是单站实测",
        "blank_value_label": "空值＝源数据缺口；不转换为棉花胁迫分",
        "source_metric": RAW_LABELS[metric_id][2],
        "solar_model_status": solar_status if metric_id == "sw_rad_14d_mean" else None,
        "solar_display_status": solar_display_status.get(solar_status) if metric_id == "sw_rad_14d_mean" else None,
        "nonnegative": metric_id in {"precip_14d_sum", "sw_rad_14d_mean"},
    }


def _raw_trace(values_by_date: dict[date, float | None], season_year: int, keys: list[str], cross_year: bool, cutoff: date | None) -> tuple[list[float | None], list[str]]:
    values, statuses = [], []
    for key in keys:
        month, day = (int(part) for part in key.split("-"))
        actual_year = season_year + 1 if cross_year and month < 9 else season_year
        actual = date(actual_year, month, day)
        value = values_by_date.get(actual)
        if cutoff is not None and season_year == 2026 and actual > cutoff:
            values.append(None)
            statuses.append("future")
        elif value is None:
            values.append(None)
            statuses.append("source_gap")
        else:
            values.append(value)
            statuses.append("available")
    return values, statuses


def _raw_region_old(geography: str) -> dict:
    config = RAW_POINT_CONFIG[geography]
    records, source_max = _load_old_point_records(config)
    point_exposures = {
        point: {
            metric_id: _rolling_point_values(records[point], source_metric, mode)
            for metric_id, (_label, _unit, source_metric, mode) in RAW_LABELS.items()
        }
        for point in config["points"]
    }
    aggregated = {metric_id: {} for metric_id in RAW_LABELS}
    all_dates = sorted({day for point in point_exposures.values() for values in point.values() for day in values})
    for day in all_dates:
        for metric_id in RAW_LABELS:
            point_values = {point: point_exposures[point][metric_id].get(day) for point in config["points"]}
            aggregated[metric_id][day], _coverage = _spatial_raw(config, point_values, metric_id)
    window_start, window_end, window_label, window_status = config["window"]
    keys = _window_keys(window_start, window_end)
    metrics = {}
    for metric_id, (label, unit, _source_metric, _mode) in RAW_LABELS.items():
        current, current_status = _raw_trace(aggregated[metric_id], 2026, keys, False, config["cutoff"])
        prior, prior_status = _raw_trace(aggregated[metric_id], 2025, keys, False, None)
        history = {year: _raw_trace(aggregated[metric_id], year, keys, False, None)[0] for year in config["history_years"]}
        hist_min = [min((history[year][index] for year in config["history_years"] if history[year][index] is not None), default=None) for index in range(len(keys))]
        hist_max = [max((history[year][index] for year in config["history_years"] if history[year][index] is not None), default=None) for index in range(len(keys))]
        metric = _raw_meta_v05(label, unit, metric_id, config["solar_status"])
        cutoff_point_values = {point: point_exposures[point][metric_id].get(config["cutoff"]) for point in config["points"]}
        _cutoff_value, cutoff_coverage = _spatial_raw(config, cutoff_point_values, metric_id)
        cutoff_valid_count = sum(value is not None for value in cutoff_point_values.values())
        metric.update({
            "day_keys": keys, "history_min": hist_min, "history_max": hist_max,
            "last_year": prior, "current_year": current, "last_year_label": "2025", "current_year_label": "2026",
            "history_years": config["history_years"], "history_year_count": len(config["history_years"]),
            "status": "available" if any(value is not None for value in current) else "gap",
            "last_year_status": prior_status, "current_year_status": current_status,
            "active_periods": [{"start": keys[0], "end": keys[-1]}],
            "source_file_max_date": source_max.isoformat(),
            "display_cutoff_date": config["cutoff"].isoformat(),
            "source_gap_count": prior_status.count("source_gap") + current_status.count("source_gap"),
            "status_counts": {"last_year": _status_counts(prior_status), "current_year": _status_counts(current_status)},
            "valid_current_point_count": cutoff_valid_count,
            "current_spatial_coverage": cutoff_coverage,
            "spatial_coverage_gate": 0.60,
        })
        metrics[metric_id] = metric
    return {
        "status": "available", "source": str(config["path"].relative_to(COTTON_ROOT)), "axis": "month_day",
        "current_year": 2026, "last_year": 2025, "display_window_start": window_start, "display_window_end": window_end,
        "display_window_label": window_label, "display_window_status": window_status, "cross_year_axis": False,
        "source_file_max_date": source_max.isoformat(), "display_cutoff_date": config["cutoff"].isoformat(),
        "metrics": metrics, "solar_model_status": config["solar_status"],
    }


def _validated_australia_files() -> list[Path]:
    """Resolve accepted Australian files from manifest + crosswalk identities."""
    manifest = read_json(AUSTRALIA_MANIFEST_PATH)
    if manifest.get("complete_response_count") != 14 or manifest.get("rate_limit_gap_count") != 3:
        raise ValueError("unexpected Australia/central Asia manifest counts")
    if manifest.get("daily_variable_units") != AUSTRALIA_EXPECTED_UNITS:
        raise ValueError("Australia ERA5 manifest units changed")
    if manifest.get("source_start_date") != "1991-01-01" or manifest.get("source_end_date") != "2026-09-10":
        raise ValueError("Australia ERA5 manifest date coverage changed")
    manifest_by_aoi = {row["aoi_name"]: row for row in manifest.get("raw_responses", [])}
    with AUSTRALIA_CROSSWALK_PATH.open("r", encoding="utf-8", newline="") as handle:
        crosswalk = [row for row in csv.DictReader(handle) if row.get("country") == "Australia"]
    if len(crosswalk) != 8:
        raise ValueError("expected eight Australian crosswalk rows")
    st_george = next((row for row in crosswalk if row.get("aoi_name") == "St George (QLD)"), None)
    if not st_george or st_george.get("point_status") != "gap_ambiguous_or_unmatched":
        raise ValueError("St George must remain a crosswalk gap")
    accepted = []
    for row in crosswalk:
        aoi = row.get("aoi_name")
        if aoi == "St George (QLD)":
            continue
        if row.get("point_status") != "accepted_point_proxy":
            raise ValueError(f"unexpected Australian point status: {aoi}")
        manifest_row = manifest_by_aoi.get(aoi)
        if not manifest_row or manifest_row.get("country") != "Australia" or manifest_row.get("status") != "complete_response":
            raise ValueError(f"manifest identity mismatch: {aoi}")
        if str(row.get("row_order")) != str(manifest_row.get("row_order")) or row.get("anchor_name") != manifest_row.get("anchor_name"):
            raise ValueError(f"crosswalk/manifest point identity mismatch: {aoi}")
        manifest_path = Path(manifest_row["raw_response_path"]).name
        path = AUSTRALIA_RAW_DIR / manifest_path
        if not path.is_file():
            raise ValueError(f"missing accepted Australian raw response: {path}")
        accepted.append(path)
    if len(accepted) != 7:
        raise ValueError("expected seven accepted Australian raw responses")
    return accepted


def _load_australia_records() -> tuple[dict[str, dict[date, dict[str, float | None]]], date]:
    au_sources = {
        "tmax": "temperature_2m_max", "tmin": "temperature_2m_min",
        "precip": "precipitation_sum", "sw_rad": "shortwave_radiation_sum",
    }
    records = {}
    for path in _validated_australia_files():
        payload = read_json(path)
        daily = payload["daily"]
        point = path.stem.split("_")[1]
        if not daily.get("time") or daily["time"][0] != "1991-01-01" or daily["time"][-1] != "2026-09-10":
            raise ValueError(f"Australia raw date coverage changed: {path.name}")
        records[point] = {}
        for index, raw_date in enumerate(daily["time"]):
            parsed = date.fromisoformat(raw_date)
            records[point][parsed] = {source: _number(daily[au_sources[source]][index]) for _label, _unit, source, _mode in RAW_LABELS.values()}
    source_max = max(max(values) for values in records.values())
    return records, source_max


def build_australia_raw_weather() -> dict:
    records, source_max = _load_australia_records()
    point_exposures = {
        point: {metric_id: _rolling_point_values(records[point], source_metric, mode) for metric_id, (_label, _unit, source_metric, mode) in RAW_LABELS.items()}
        for point in records
    }
    aggregated = {metric_id: {} for metric_id in RAW_LABELS}
    all_dates = sorted({day for point in point_exposures.values() for values in point.values() for day in values})
    weights = {point: 1.0 / len(point_exposures) for point in point_exposures}
    for day in all_dates:
        for metric_id in RAW_LABELS:
            point_values = {point: point_exposures[point][metric_id].get(day) for point in point_exposures}
            valid = [(weights[point], value) for point, value in point_values.items() if value is not None]
            coverage = math.fsum(weight for weight, _value in valid)
            aggregated[metric_id][day] = (math.fsum(weight * value for weight, value in valid) / coverage) if coverage >= 0.60 else None
    keys = _window_keys(AUSTRALIA_WINDOW[0], AUSTRALIA_WINDOW[1])
    metrics = {}
    for metric_id, (label, unit, _source_metric, _mode) in RAW_LABELS.items():
        current, current_status = _raw_trace(aggregated[metric_id], 2026, keys, True, date(2026, 9, 10))
        prior, prior_status = _raw_trace(aggregated[metric_id], 2025, keys, True, None)
        history = {year: _raw_trace(aggregated[metric_id], year, keys, True, None)[0] for year in range(1991, 2025)}
        hist_min = [min((history[year][index] for year in history if history[year][index] is not None), default=None) for index in range(len(keys))]
        hist_max = [max((history[year][index] for year in history if history[year][index] is not None), default=None) for index in range(len(keys))]
        metric = _raw_meta_v05(label, unit, metric_id, "included_and_active_in_current_stage")
        cutoff_point_values = {point: point_exposures[point][metric_id].get(date(2026, 9, 10)) for point in point_exposures}
        valid_cutoff = [value for value in cutoff_point_values.values() if value is not None]
        cutoff_coverage = len(valid_cutoff) / len(point_exposures) if point_exposures else 0.0
        metric.update({
            "day_keys": keys, "history_min": hist_min, "history_max": hist_max,
            "last_year": prior, "current_year": current, "last_year_label": "2025/26", "current_year_label": "2026/27",
            "history_years": list(range(1991, 2025)), "history_year_count": 34,
            "status": "available", "last_year_status": prior_status, "current_year_status": current_status,
            "active_periods": [{"start": keys[0], "end": keys[-1]}],
            "source_file_max_date": source_max.isoformat(), "source_gap_count": prior_status.count("source_gap") + current_status.count("source_gap"),
            "display_cutoff_date": "2026-09-10",
            "status_counts": {"last_year": _status_counts(prior_status), "current_year": _status_counts(current_status)},
            "valid_current_point_count": len(valid_cutoff), "current_spatial_coverage": cutoff_coverage, "spatial_coverage_gate": 0.60,
        })
        metrics[metric_id] = metric
    return {
        "status": "available", "source": str(AUSTRALIA_RAW_DIR.relative_to(COTTON_ROOT)), "seasonality_source": str(CENTRAL_ASIA_SEASONAL_PATH.relative_to(COTTON_ROOT)),
        "axis": "cross_year_month_day", "current_year": "2026/27", "last_year": "2025/26",
        "display_window_start": AUSTRALIA_WINDOW[0], "display_window_end": AUSTRALIA_WINDOW[1], "display_window_label": AUSTRALIA_WINDOW[2],
        "display_window_status": AUSTRALIA_WINDOW[3], "cross_year_axis": True, "source_file_max_date": source_max.isoformat(),
        "display_cutoff_date": "2026-09-10", "metrics": metrics, "solar_model_status": "included_and_active_in_current_stage",
    }


def build_raw_weather() -> dict:
    result = {REGION_META[geo]["id"]: _raw_region_old(geo) for geo in ("China", "United States", "Brazil", "India")}
    result["australia"] = build_australia_raw_weather()
    return result


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
                **_raw_meta(labels[variable][0], labels[variable][1]),
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


PRODUCTION_WEIGHTED_ID = "five_region_production_weighted_weather_stress_display"
PRODUCTION_WEIGHTED_NAME = "五区产量加权天气胁迫"
PRODUCTION_WEIGHTED_REGIONS = ("China", "United States", "Brazil", "India", "Australia")
PRODUCTION_WEIGHTED_REGION_IDS = {
    "China": "china", "United States": "us", "Brazil": "brazil", "India": "india", "Australia": "australia",
}
PRODUCTION_WEIGHTED_CUTOFF = date(2026, 9, 10)
PRODUCTION_WEIGHTED_KEYS = _window_keys("04-01", "11-30")


def _production_weights(brief: dict) -> tuple[list[dict], dict[str, float]]:
    """Read the five frozen production values from the supply brief only."""
    by_geo = {row["geography"]: row for row in brief["rows"]}
    productions = {geo: float(by_geo[geo]["current_production_1000_480lb_bales"]) for geo in PRODUCTION_WEIGHTED_REGIONS}
    total = math.fsum(productions.values())
    weights = {geo: productions[geo] / total for geo in PRODUCTION_WEIGHTED_REGIONS}
    rows = []
    for geo in PRODUCTION_WEIGHTED_REGIONS:
        rows.append({
            "region_id": PRODUCTION_WEIGHTED_REGION_IDS[geo],
            "geography": geo,
            "name": GEO_DISPLAY[geo],
            "production_1000_480lb_bales": int(productions[geo]),
            "production_weight": weights[geo],
            "production_weight_pct": weights[geo] * 100.0,
        })
    return rows, weights


def _score_daily_by_date(path: Path) -> dict[date, float | None]:
    values = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            raw_date = row.get("date")
            if not raw_date:
                continue
            raw_value = row.get("theoretical_weather_stress_index")
            values[date.fromisoformat(raw_date)] = None if raw_value in (None, "") else float(raw_value)
    return values


def _weighted_production_day(values_by_region: dict[str, float | None], weights: dict[str, float]) -> dict:
    valid_ids = [PRODUCTION_WEIGHTED_REGION_IDS[geo] for geo in PRODUCTION_WEIGHTED_REGIONS if values_by_region.get(PRODUCTION_WEIGHTED_REGION_IDS[geo]) is not None]
    coverage = math.fsum(weights[geo] for geo in PRODUCTION_WEIGHTED_REGIONS if values_by_region.get(PRODUCTION_WEIGHTED_REGION_IDS[geo]) is not None)
    if coverage < 0.60 or not valid_ids:
        return {"value": None, "production_weight_coverage": coverage, "valid_region_ids": valid_ids, "status": "coverage_below_gate"}
    numerator = math.fsum(
        weights[geo] * float(values_by_region[PRODUCTION_WEIGHTED_REGION_IDS[geo]])
        for geo in PRODUCTION_WEIGHTED_REGIONS
        if values_by_region.get(PRODUCTION_WEIGHTED_REGION_IDS[geo]) is not None
    )
    return {"value": numerator / coverage, "production_weight_coverage": coverage, "valid_region_ids": valid_ids, "status": "available"}


def _production_year_trace(year: int, daily: dict[str, dict[date, float | None]], weights: dict[str, float], current: bool = False) -> tuple[list[float | None], list[float | None], list[list[str]], list[str]]:
    values, coverage, valid_ids, statuses = [], [], [], []
    for key in PRODUCTION_WEIGHTED_KEYS:
        month, day = (int(part) for part in key.split("-"))
        actual = date(year, month, day)
        if current and actual > PRODUCTION_WEIGHTED_CUTOFF:
            values.append(None); coverage.append(None); valid_ids.append([]); statuses.append("future"); continue
        local = {PRODUCTION_WEIGHTED_REGION_IDS[geo]: daily[PRODUCTION_WEIGHTED_REGION_IDS[geo]].get(actual) for geo in PRODUCTION_WEIGHTED_REGIONS}
        result = _weighted_production_day(local, weights)
        values.append(result["value"]); coverage.append(result["production_weight_coverage"]); valid_ids.append(result["valid_region_ids"]); statuses.append(result["status"])
    return values, coverage, valid_ids, statuses


def build_production_weighted_weather(brief: dict) -> dict:
    weight_rows, weights = _production_weights(brief)
    daily = {PRODUCTION_WEIGHTED_REGION_IDS[geo]: _score_daily_by_date(AUSTRALIA_DAILY_PATH if geo == "Australia" else DAILY_PATHS[geo]) for geo in PRODUCTION_WEIGHTED_REGIONS}
    history_years = list(range(2015, 2025))
    history, history_coverage, history_ids, history_status = {}, {}, {}, {}
    for year in history_years:
        history[str(year)], history_coverage[str(year)], history_ids[str(year)], history_status[str(year)] = _production_year_trace(year, daily, weights)
    last_year, last_coverage, last_ids, last_status = _production_year_trace(2025, daily, weights)
    current_year, current_coverage, current_ids, current_status = _production_year_trace(2026, daily, weights, current=True)
    history_min = [min((history[str(year)][idx] for year in history_years if history[str(year)][idx] is not None), default=None) for idx in range(len(PRODUCTION_WEIGHTED_KEYS))]
    history_max = [max((history[str(year)][idx] for year in history_years if history[str(year)][idx] is not None), default=None) for idx in range(len(PRODUCTION_WEIGHTED_KEYS))]
    coverage_values = [value for series in list(history_coverage.values()) + [last_coverage, current_coverage] for value in series if value is not None]
    status_counts = {
        "history": {status: sum(day_status.count(status) for day_status in history_status.values()) for status in ("available", "coverage_below_gate", "future")},
        "last_year": {status: last_status.count(status) for status in ("available", "coverage_below_gate", "future")},
        "current_year": {status: current_status.count(status) for status in ("available", "coverage_below_gate", "future")},
    }
    cutoff_index = PRODUCTION_WEIGHTED_KEYS.index("09-10")
    current_scores = {}
    for geo in PRODUCTION_WEIGHTED_REGIONS:
        current_scores[PRODUCTION_WEIGHTED_REGION_IDS[geo]] = daily[PRODUCTION_WEIGHTED_REGION_IDS[geo]].get(PRODUCTION_WEIGHTED_CUTOFF)
    metric = {
        "id": PRODUCTION_WEIGHTED_ID, "label": PRODUCTION_WEIGHTED_NAME, "unit": "分", "window": "逐日产量权重展示合成",
        "scale_type": "fixed_score_0_100", "scale_min": 0, "scale_max": 100,
        "value_semantics": "五个当地理论天气胁迫分的产量权重展示合成；不是统一模型、减产比例或产量预测",
        "blank_value_label": "覆盖不足不按0处理；地区组合变化可能同时影响曲线",
        "day_keys": PRODUCTION_WEIGHTED_KEYS, "history_min": history_min, "history_max": history_max,
        "last_year": last_year, "current_year": current_year, "last_year_label": "2025", "current_year_label": "2026",
        "history_years": history_years, "history_year_count": len(history_years),
        "history_production_weight_coverage": history_coverage, "history_valid_region_ids": history_ids, "history_status": history_status,
        "last_year_production_weight_coverage": last_coverage, "current_year_production_weight_coverage": current_coverage,
        "last_year_valid_region_ids": last_ids, "current_year_valid_region_ids": current_ids,
        "last_year_status": last_status, "current_year_status": current_status, "status_counts": status_counts,
        "display_window_start": "04-01", "display_window_end": "11-30", "display_window_label": "04-01—11-30",
        "cross_year_axis": False, "common_cutoff_date": PRODUCTION_WEIGHTED_CUTOFF.isoformat(),
        "historical_band_note": "历史带不含补造的澳洲历史分；覆盖不足不按0处理；地区组合变化可能同时影响曲线",
        "coverage_min": min(coverage_values) if coverage_values else None, "coverage_max": max(coverage_values) if coverage_values else None,
        "usable_day_counts": {
            "history_total": sum(value is not None for series in history.values() for value in series),
            "history_axis": sum(value is not None for value in history_min),
            "last_year": sum(value is not None for value in last_year),
            "current_year": sum(value is not None for value in current_year),
        },
    }
    current_result = _weighted_production_day(current_scores, weights)
    return {
        "id": PRODUCTION_WEIGHTED_ID, "label": PRODUCTION_WEIGHTED_NAME, "display_only": True,
        "not_calibrated": True, "not_loss_percent": True, "not_unified_model": True,
        "unit": "分", "score_axis": "0—100", "production_total_1000_480lb_bales": int(math.fsum(row["production_1000_480lb_bales"] for row in weight_rows)),
        "weights": weight_rows, "common_cutoff_date": PRODUCTION_WEIGHTED_CUTOFF.isoformat(),
        "current_region_scores": current_scores, "current_score": current_result["value"],
        "weighted_production_coverage": current_result["production_weight_coverage"], "valid_region_ids": current_result["valid_region_ids"],
        "current_status": current_result["status"], "seasonal_metric": metric,
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

    region_geographies = ("China", "United States", "Brazil", "India")
    regions = [build_region(geo, row_by_geo[geo]) for geo in region_geographies]
    regions.append(build_australia_region(row_by_geo["Australia"]))
    seasonal = {REGION_META[geo]["id"]: build_seasonal(geo) for geo in region_geographies}
    seasonal["australia"] = build_australia_seasonal()
    raw_weather = build_raw_weather()
    production_weighted = build_production_weighted_weather(brief)
    for region_id, raw in raw_weather.items():
        seasonal[region_id]["raw_metrics"] = raw["metrics"]
        seasonal[region_id]["raw_weather"] = raw
    central_watch = build_central_asia_watch()
    return {
        "dashboard_id": "cotton_public_supply_weather_dashboard_v0_6",
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
        PRODUCTION_WEIGHTED_ID: production_weighted,
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
