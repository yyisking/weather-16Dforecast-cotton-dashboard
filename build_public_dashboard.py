#!/usr/bin/env python3
"""Build the static data payload for the public cotton dashboard."""

from __future__ import annotations

import json
import csv
import hashlib
import importlib.util
import math
import sys
from functools import lru_cache
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


SITE_ROOT = Path(__file__).resolve().parent
COTTON_ROOT = SITE_ROOT.parent
DIST = SITE_ROOT / "dist"

BRIEF_PATH = COTTON_ROOT / "research/derived/cotton_current_supply_decision_brief_v0_2.json"
AUSTRALIA_LATEST_PATH = COTTON_ROOT / "au_weather/derived/australia_national_theoretical_weather_stress_index_v0_4_latest.json"
AUSTRALIA_DAILY_PATH = COTTON_ROOT / "au_weather/derived/australia_national_theoretical_weather_stress_index_v0_4_daily.csv"
NATIONAL_LATEST_PATHS = {
    "United States": COTTON_ROOT / "us_weather/derived/us_national_theoretical_weather_stress_index_v0_1_latest.json",
    "Brazil": COTTON_ROOT / "br_weather/derived/brazil_national_theoretical_weather_stress_index_v0_1_latest.json",
    "India": COTTON_ROOT / "in_weather/derived/india_national_theoretical_weather_stress_index_v0_1_latest.json",
    "Australia": AUSTRALIA_LATEST_PATH,
}
NATIONAL_DAILY_PATHS = {
    "United States": COTTON_ROOT / "us_weather/derived/us_national_theoretical_weather_stress_index_v0_1_daily.csv",
    "Brazil": COTTON_ROOT / "br_weather/derived/brazil_national_theoretical_weather_stress_index_v0_1_daily.csv",
    "India": COTTON_ROOT / "in_weather/derived/india_national_theoretical_weather_stress_index_v0_1_daily.csv",
    "Australia": AUSTRALIA_DAILY_PATH,
}
CENTRAL_ASIA_WATCH_PATH = COTTON_ROOT / "research/derived/central_asia_cotton_current_weather_watch_v0_3.json"
CENTRAL_ASIA_SEASONAL_PATH = COTTON_ROOT / "research/derived/australia_central_asia_cotton_era5_daily_seasonality_v0_2.csv"
CURRENT_AU_CENTRAL_OVERLAY_PATH = COTTON_ROOT / "automation/current/australia_central_asia_daily.csv"
XINJIANG_AREA_WEIGHT_PATH = COTTON_ROOT / "research/audits/xinjiang_dashboard_area_weight_proxy_v0_1.json"
REGION_PATHS = {
    "United States": COTTON_ROOT / "us_weather/derived/us_tx_theoretical_weather_stress_index_v0_2_refresh_2026_09_29_latest.json",
    "China": COTTON_ROOT / "cn_xj_weather/derived/xinjiang_theoretical_weather_stress_index_v0_2_latest.json",
    "India": COTTON_ROOT / "in_weather/derived/india_central_rainfed_theoretical_weather_stress_index_v0_1_refresh_2026_09_29_latest.json",
    "Brazil": COTTON_ROOT / "br_weather/derived/brazil_mt_theoretical_weather_stress_index_v0_2_refresh_2026_09_29_latest.json",
}

DAILY_PATHS = {
    "China": COTTON_ROOT / "cn_xj_weather/derived/xinjiang_theoretical_weather_stress_index_v0_2_daily.csv",
    "United States": COTTON_ROOT / "us_weather/derived/us_tx_theoretical_weather_stress_index_v0_2_refresh_2026_09_29_daily.csv",
    "Brazil": COTTON_ROOT / "br_weather/derived/brazil_mt_theoretical_weather_stress_index_v0_2_refresh_2026_09_29_daily.csv",
    "India": COTTON_ROOT / "in_weather/derived/india_central_rainfed_theoretical_weather_stress_index_v0_1_refresh_2026_09_29_daily.csv",
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
    "high_vpd": {"label": "高水汽压亏缺（VPD，空气干燥度）", "unit": "分", "window": "逐日因子分"},
    "low_solar_radiation": {"label": "低太阳辐射", "unit": "分", "window": "逐日因子分"},
    "hot_dry_compound": {"label": "高温干旱复合", "unit": "分", "window": "逐日因子分"},
    "excess_rain_waterlogging": {"label": "过量降雨／渍涝", "unit": "分", "window": "逐日因子分"},
}

REGION_META = {
    "China": {
        "id": "china",
        "name": "中国·新疆",
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
        "name": "美国",
        "short_name": "美国",
        "stage_display": "六类作制/产区日历代理；全国既有天气网络汇总",
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
        "name": "巴西",
        "short_name": "巴西",
        "stage_display": "MT二季棉、BA等首季/雨养混合作制分组代理",
        "factor_fields": [
            ("harvest_rain", "收获期降雨", "harvest_rain_score"),
            ("root_zone_dryness", "根区干旱", "root_zone_dryness_score"),
            ("high_temperature", "高温", "high_temperature_score"),
            ("high_vpd", "高水汽压亏缺（VPD，空气干燥度）", "high_vpd_score"),
            ("low_solar_radiation", "低太阳辐射", "low_solar_radiation_score"),
            ("low_temperature", "低温", "low_temperature_score"),
        ],
    },
    "India": {
        "id": "india",
        "name": "印度",
        "short_name": "印度",
        "stage_display": "北部灌溉、中部雨养混合、南部季风灌溉混合作制代理",
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
            ("high_vpd", "高水汽压亏缺（VPD，空气干燥度）", "high_vpd_score"),
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
    "United States": ("02-01", "11-30", "美国全国既有网络 02-01—11-30", "national_network_union_display_window"),
    "Brazil": ("01-01", "12-31", "巴西全国既有网络全年多作制联合窗口", "national_network_union_display_window"),
    "India": ("01-01", "12-31", "印度全国既有网络 05—12 月＋次年 1 月联合窗口", "national_network_union_display_window"),
}
CENTRAL_WINDOW = ("03-01", "10-31", "03-01—10-31（页面代理窗口；未核实当地作季）",
                  "display_window_proxy_not_verified_local_stage_calendar")
AUSTRALIA_WINDOW = ("09-01", "06-30", "澳洲 09-01—次年 06-30", "user_defined_cross_year_display_window")

# Chart-only cropping. The score arrays remain full length for audit/replay.
# Multi-period Australia excess-rain display intentionally concatenates two
# enabled spans; the note tells viewers that the time axis skips Nov–Feb.
CHART_DISPLAY_WINDOWS = {
    ("United States", "root_zone_dryness"): (("03-01", "09-30"),),
    ("United States", "high_heat"): (("04-01", "08-31"),),
    ("United States", "low_temperature"): (("02-01", "05-31"), ("07-01", "07-31"), ("09-01", "11-30")),
    ("United States", "establishment_excess_rain"): (("02-01", "06-30"),),
    ("United States", "harvest_rain"): (("07-01", "11-30"),),
    ("Brazil", "harvest_rain"): (("02-01", "09-30"),),
    ("Brazil", "root_zone_dryness"): (("01-01", "06-30"), ("09-01", "12-31")),
    ("Brazil", "high_temperature"): (("01-01", "06-30"), ("09-01", "12-31")),
    ("Brazil", "low_temperature"): (("01-01", "10-31"),),
    ("Brazil", "high_vpd"): (("01-01", "06-30"), ("09-01", "12-31")),
    ("Brazil", "low_solar_radiation"): (("01-01", "08-31"), ("10-01", "12-31")),
    ("India", "score"): (("05-01", "12-31"), ("01-01", "01-31")),
    ("India", "root_zone_dryness"): (("05-01", "12-31"), ("01-01", "01-31")),
    ("India", "hot_dry_compound"): (("05-01", "12-31"), ("01-01", "01-31")),
    ("India", "excess_rain_waterlogging"): (("05-01", "12-31"), ("01-01", "01-31")),
    ("Australia", "low_temperature"): (("09-01", "04-30"),),
    ("Australia", "high_heat"): (("09-01", "04-30"),),
    ("Australia", "excess_rain"): (("09-01", "10-31"), ("03-01", "04-30")),
    ("Australia", "high_vpd"): (("11-01", "02-28"),),
    ("Australia", "low_solar"): (("09-01", "04-30"),),
}

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
        "cutoff": date(2026, 9, 29),
        "history_years": list(range(2005, 2025)),
        "solar_status": "observed_only_excluded_pending_dedup",
    },
    "United States": {
        "path": COTTON_ROOT / "us_weather/points_daily.csv",
        "points": ("tx_hp_n", "tx_hp_c", "tx_hp_s", "tx_hp_w", "tx_hp_e", "tx_hp_sw", "tx_farwest", "tx_rolling", "tx_edwards", "tx_coastal", "tx_rgv", "tx_black"),
        "weights": {p: (0.64 / 6 if p.startswith("tx_hp_") else 0.36 / 6) for p in ("tx_hp_n", "tx_hp_c", "tx_hp_s", "tx_hp_w", "tx_hp_e", "tx_hp_sw", "tx_farwest", "tx_rolling", "tx_edwards", "tx_coastal", "tx_rgv", "tx_black")},
        "window": ("02-01", "11-30", "德州原始天气代表网络 02-01—11-30", "legacy_raw_network_display_window"),
        "cutoff": date(2026, 9, 29),
        "history_years": list(range(2005, 2025)),
        "solar_status": "observed_only_excluded_local_direction_gap",
    },
    "Brazil": {
        "path": COTTON_ROOT / "br_weather/points_daily.csv",
        "points": ("mt_campo_novo", "mt_campo_verde", "mt_diamantino", "mt_lucas", "mt_nova_mutum", "mt_nova_ubirata", "mt_primavera", "mt_rondonopolis", "mt_sapezal", "mt_sinop", "mt_sorriso", "mt_tangara"),
        "weights": {p: 1.0 / 12.0 for p in ("mt_campo_novo", "mt_campo_verde", "mt_diamantino", "mt_lucas", "mt_nova_mutum", "mt_nova_ubirata", "mt_primavera", "mt_rondonopolis", "mt_sapezal", "mt_sinop", "mt_sorriso", "mt_tangara")},
        "window": ("01-01", "09-30", "马托格罗索原始天气代表网络 01-01—09-30", "legacy_raw_network_display_window"),
        "cutoff": date(2026, 9, 28),
        "history_years": list(range(2005, 2025)),
        "solar_status": "included_in_model_contract",
    },
    "India": {
        "path": COTTON_ROOT / "in_weather/points_daily.csv",
        "points": ("gj_rajkot", "gj_surendranagar", "gj_bhavnagar", "gj_amreli", "gj_bharuch", "mh_akola", "mh_amravati", "mh_yavatmal", "mh_buldhana", "mh_jalgaon", "mh_jalna", "mp_khargone", "mp_dhar", "tg_adilabad", "tg_warangal", "tg_khammam"),
        "weights": {"GJ": 0.3404351768, "MH": 0.3739800544, "MP": 0.0643699003, "TG": 0.2212148685},
        "state_points": {"GJ": ("gj_rajkot", "gj_surendranagar", "gj_bhavnagar", "gj_amreli", "gj_bharuch"), "MH": ("mh_akola", "mh_amravati", "mh_yavatmal", "mh_buldhana", "mh_jalgaon", "mh_jalna"), "MP": ("mp_khargone", "mp_dhar"), "TG": ("tg_adilabad", "tg_warangal", "tg_khammam")},
        "window": ("06-01", "12-31", "印度中部原始天气代表网络 06-01—12-31", "legacy_raw_network_display_window"),
        "cutoff": date(2026, 9, 29),
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

PIPELINE_PATHS = {
    "China": COTTON_ROOT / "cn_xj_weather/pipelines/build_xinjiang_theoretical_weather_stress_index_v0_2.py",
    "United States": COTTON_ROOT / "us_weather/pipelines/build_us_national_theoretical_weather_stress_index_v0_1.py",
    "Brazil": COTTON_ROOT / "br_weather/pipelines/build_brazil_national_theoretical_weather_stress_index_v0_1.py",
    "India": COTTON_ROOT / "in_weather/pipelines/build_india_national_theoretical_weather_stress_index_v0_1.py",
    "Australia": COTTON_ROOT / "au_weather/pipelines/build_australia_national_theoretical_weather_stress_index_v0_4.py",
}

POINT_META_PATHS = {
    "China": COTTON_ROOT / "cn_xj_weather/meta.json",
    "United States": COTTON_ROOT / "us_weather/meta.json",
    "Brazil": COTTON_ROOT / "br_weather/meta.json",
    "India": COTTON_ROOT / "in_weather/meta.json",
}

POINT_DATA_PATHS = {
    geography: POINT_META_PATHS[geography].parent / "points_daily.csv"
    for geography in POINT_META_PATHS
}

SUBREGION_DISPLAY = {
    "United States": {
        "AL": "阿拉巴马州（AL）", "AR": "阿肯色州（AR）", "AZ": "亚利桑那州（AZ）",
        "CA": "加利福尼亚州（CA）", "GA": "佐治亚州（GA）", "KS": "堪萨斯州（KS）",
        "LA": "路易斯安那州（LA）", "MO": "密苏里州（MO）", "MS": "密西西比州（MS）",
        "NC": "北卡罗来纳州（NC）", "NM": "新墨西哥州（NM）", "OK": "俄克拉何马州（OK）",
        "SC": "南卡罗来纳州（SC）", "TN": "田纳西州（TN）", "TX": "德州（TX）",
        "VA": "弗吉尼亚州（VA）",
    },
    "India": {
        "AP": "安得拉邦（AP）", "GJ": "古吉拉特邦（GJ）", "HR": "哈里亚纳邦（HR）",
        "KA": "卡纳塔克邦（KA）", "MH": "马哈拉施特拉邦（MH）", "MP": "中央邦（MP）",
        "PB": "旁遮普邦（PB）", "RJ": "拉贾斯坦邦（RJ）", "TG": "特伦甘纳邦（TG）",
        "TN": "泰米尔纳德邦（TN）",
    },
    "Australia": {
        "Gwydir Valley (NSW)": "吉迪尔河谷（新南威尔士州）",
        "Namoi Valley (NSW)": "纳莫伊河谷（新南威尔士州）",
        "Macquarie Valley (NSW)": "麦夸里河谷（新南威尔士州）",
        "Murrumbidgee Valley (NSW)": "马兰比吉河谷（新南威尔士州）",
        "Darling Downs (QLD)": "达令草原（昆士兰州）",
        "St George (QLD)": "圣乔治（昆士兰州）",
        "Border Rivers / Macintyre Valley (QLD-NSW)": "边界河／麦金太尔河谷（昆士兰—新南威尔士）",
        "Central Highlands (Emerald/Theodore/Biloela, QLD)": "中央高地（昆士兰州）",
    },
}

XINJIANG_SUBREGIONS = {
    "north_shihezi_changji": {"name": "北疆·石河子—昌吉代理区", "points": ("xj_shihezi", "xj_shawan", "xj_changji", "xj_hutubi"), "model_group": "north"},
    "north_kuitun": {"name": "北疆·奎屯代理区", "points": ("xj_kuitun",), "model_group": "north"},
    "north_bozhou": {"name": "北疆·博州代理区", "points": ("xj_bole", "xj_jinghe"), "model_group": "north"},
    "kashgar": {"name": "喀什棉区", "points": ("xj_kashgar", "xj_shache", "xj_bachu"), "model_group": "south"},
    "aksu": {"name": "阿克苏棉区", "points": ("xj_aksu", "xj_awat", "xj_kuqa", "xj_shaya"), "model_group": "south"},
    "bayingol": {"name": "巴音郭楞棉区", "points": ("xj_korla", "xj_yuli", "xj_luntai"), "model_group": "south"},
    "turpan": {"name": "吐鲁番棉区", "points": ("xj_turpan",), "model_group": "east"},
}

POINT_DISPLAY = {
    "xj_shihezi": "石河子", "xj_shawan": "沙湾", "xj_kuitun": "奎屯", "xj_changji": "昌吉",
    "xj_hutubi": "呼图壁", "xj_bole": "博乐", "xj_jinghe": "精河", "xj_kashgar": "喀什",
    "xj_shache": "莎车", "xj_bachu": "巴楚", "xj_aksu": "阿克苏", "xj_awat": "阿瓦提",
    "xj_kuqa": "库车", "xj_shaya": "沙雅", "xj_korla": "库尔勒", "xj_yuli": "尉犁",
    "xj_luntai": "轮台", "xj_turpan": "吐鲁番",
}
AUSTRALIA_ERA5_FILES = (
    "01_moree_era5_daily.json", "02_narrabri_era5_daily.json", "03_narromine_era5_daily.json",
    "04_griffith_era5_daily.json", "05_dalby_era5_daily.json", "07_goondiwindi_era5_daily.json",
    "08_emerald_era5_daily.json",
)
AUSTRALIA_RAW_DIR = COTTON_ROOT / "research/raw/australia_central_asia_era5_daily_v0_1"
AUSTRALIA_MANIFEST_PATH = AUSTRALIA_RAW_DIR / "source_manifest_v0_1.json"
AUSTRALIA_ST_GEORGE_RAW_DIR = COTTON_ROOT / "research/raw/australia_st_george_era5_daily_v0_1"
AUSTRALIA_ST_GEORGE_MANIFEST_PATH = AUSTRALIA_ST_GEORGE_RAW_DIR / "source_manifest_v0_1.json"
CENTRAL_ASIA_RETRY_MANIFEST_PATH = COTTON_ROOT / "research/raw/central_asia_era5_gap_retry_v0_1/source_manifest_v0_1.json"
AUSTRALIA_CROSSWALK_PATH = COTTON_ROOT / "research/derived/australia_central_asia_cotton_point_crosswalk_v0_1.csv"
AUSTRALIA_EXPECTED_UNITS = {
    "temperature_2m_max": "°C", "temperature_2m_min": "°C", "precipitation_sum": "mm",
    "shortwave_radiation_sum": "MJ/m²", "et0_fao_evapotranspiration": "mm", "vapour_pressure_deficit_max": "kPa",
}
CENTRAL_ASIA_VARIABLES = tuple(AUSTRALIA_EXPECTED_UNITS)
CENTRAL_ASIA_MEAN_VARIABLES = frozenset((
    "temperature_2m_max", "temperature_2m_min", "vapour_pressure_deficit_max",
))


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def _load_current_au_central_overlay() -> dict[str, dict[date, dict[str, float | None]]]:
    """Read the mutable current overlay without altering frozen ERA5 history."""
    if not CURRENT_AU_CENTRAL_OVERLAY_PATH.exists():
        return {}
    result: dict[str, dict[date, dict[str, float | None]]] = defaultdict(dict)
    with CURRENT_AU_CENTRAL_OVERLAY_PATH.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            parsed = date.fromisoformat(row["date"][:10])
            result[row["aoi_name"]][parsed] = {
                field: _number(row.get(field))
                for field in (
                    "temperature_2m_max", "temperature_2m_min", "precipitation_sum",
                    "shortwave_radiation_sum", "et0_fao_evapotranspiration",
                    "vapor_pressure_deficit_max",
                )
            }
    return dict(result)


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


def _period_keys(keys: list[str], start: str, end: str) -> list[str]:
    """Return one period in the order of the chart axis, including cross-year axes."""
    if start not in keys or end not in keys:
        return []
    start_index, end_index = keys.index(start), keys.index(end)
    return keys[start_index:end_index + 1] if end_index >= start_index else keys[start_index:] + keys[:end_index + 1]


def _chart_period_intersection(keys: list[str], configured: tuple | list | None, active_periods: list[dict]) -> list[dict[str, str]]:
    """Intersect broad display windows with the metric's actual stage-enabled days.

    Configured windows preserve crop-season display order. Only structurally
    inactive days are removed; source gaps and future days inside an enabled
    period remain on the axis and keep their status.
    """
    active_keys = {
        key
        for period in active_periods
        for key in _period_keys(keys, period["start"], period["end"])
    }
    candidates = configured or tuple((period["start"], period["end"]) for period in active_periods)
    result: list[dict[str, str]] = []
    for start, end in candidates:
        sequence = _period_keys(keys, start, end)
        run: list[str] = []
        for key in sequence + [None]:
            if key is not None and key in active_keys:
                run.append(key)
            elif run:
                result.append({"start": run[0], "end": run[-1]})
                run = []
    return result


def _apply_chart_display_window(metric_payload: dict, geography: str, metric_id: str) -> None:
    keys = metric_payload.get("day_keys") or []
    active_periods = metric_payload.get("active_periods") or []
    configured = CHART_DISPLAY_WINDOWS.get((geography, metric_id))
    periods = _chart_period_intersection(keys, configured, active_periods)
    if not periods or (not configured and periods == [{"start": keys[0], "end": keys[-1]}]):
        return
    metric_payload.pop("chart_display_start", None)
    metric_payload.pop("chart_display_end", None)
    metric_payload.pop("chart_display_periods", None)
    if len(periods) == 1:
        start, end = periods[0]["start"], periods[0]["end"]
        metric_payload.update({
            "chart_display_start": start,
            "chart_display_end": end,
            "chart_display_note": f"图轴仅显示当地实际启用期 {start}—{end}；结构性未启用日期从横轴隐藏，真实源数据缺口仍保留。",
        })
    else:
        period_text = "、".join(f"{period['start']}—{period['end']}" for period in periods)
        note = f"图轴仅拼接显示当地实际启用期：{period_text}；结构性未启用日期从横轴隐藏，真实源数据缺口仍保留，横轴不连续。"
        if geography == "Australia" and metric_id == "excess_rain":
            note = "图轴拼接显示当地实际启用期 09-01—10-31 与 03-01—04-30；11月至次年2月结构性未启用并从横轴隐藏，真实源数据缺口仍保留。"
        metric_payload.update({
            "chart_display_periods": periods,
            "chart_display_note": note,
        })


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
    path = NATIONAL_DAILY_PATHS.get(geography, DAILY_PATHS[geography])
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
        if geography == "China" and metric in {"low_temperature", "high_heat"}:
            if metric == "low_temperature":
                primary = [{"start": "04-01", "end": "05-31"}, {"start": "09-01", "end": "11-30"}]
                secondary = [{"start": "06-01", "end": "08-31"}]
            else:
                primary = [{"start": "06-01", "end": "08-31"}]
                secondary = [{"start": "04-01", "end": "05-31"}, {"start": "09-01", "end": "11-30"}]
            meta.update({
                "display_role": "continuous_three_phase_temperature_factor_score",
                "blank_value_label": "今年线只画到数据截止日；空白只表示未来日期或真实源数据缺口，不是阶段排除。",
                "primary_weight_periods": primary,
                "secondary_weight_periods": secondary,
                "secondary_weight": 0.5,
                "stage_weight_note": "新疆V0.2全生长期连续计分；主要敏感阶段沿用原权重，其他阶段以0.5暂定次要权重纳入综合分。",
                "theoretical_not_calibrated": True,
            })
        if geography == "United States" and metric in {"low_temperature", "high_heat"}:
            meta.update({
                "display_role": "local_calendar_continuous_temperature_factor_score",
                "secondary_weight": 0.5,
                "stage_weight_note": "德州V0.2在各子区当地作季内连续监测高温与低温；V0.1原主权重保留，原硬排除方向以0.5暂定次要权重纳入。权重未校准。",
                "theoretical_not_calibrated": True,
            })
        if geography == "Brazil" and metric in {"low_temperature", "high_temperature"}:
            meta.update({
                "display_role": "local_calendar_continuous_temperature_factor_score",
                "secondary_weight": 0.5,
                "stage_weight_note": "巴西MT V0.2在1—9月当地模型窗口连续监测高温与低温；V0.1原主权重保留，原硬排除方向以0.5暂定次要权重纳入。权重未校准。",
                "theoretical_not_calibrated": True,
            })
        if geography == "China" and metric == "spring_wind":
            meta.update({
                "chart_display_start": "04-01",
                "chart_display_end": "05-31",
                "chart_display_note": "图轴仅显示春季风害评分启用期 04-01—05-31；6—11月不展示。",
            })
        _apply_chart_display_window(meta, geography, metric)
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
    historical_factor_bands = _australia_historical_factor_bands(keys)

    def season_trace(metric: str, season_start: int) -> list[float | None]:
        values = []
        for key in keys:
            month, day = (int(part) for part in key.split("-"))
            source_year = season_start if month >= 9 else season_start + 1
            values.append(year_map[metric].get(source_year, {}).get(key))
        return values

    def season_status(metric: str, season_start: int, values: list[float | None]) -> list[str]:
        active_keys = active_by_metric.get(metric, set())
        statuses = []
        for index, key in enumerate(keys):
            month, day = (int(part) for part in key.split("-"))
            if key not in active_keys:
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
        metric_payload = {
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
        if metric in AUSTRALIA_FACTOR_EXPOSURES:
            history = historical_factor_bands[metric]
            metric_payload.update({
                "history_min": history["history_min"],
                "history_max": history["history_max"],
                "history_years": list(AUSTRALIA_HISTORY_SEASON_STARTS),
                "history_year_count": len(AUSTRALIA_HISTORY_SEASON_STARTS),
                "history_year_semantics": "crop_season_start_year",
                "historical_band_note": "历史带为1991/92—2024/25 ERA5单因子回算（1991—2024同历日基准），属回顾性描述，非PIT，未校准。",
            })
        if metric in {"low_temperature", "high_heat"}:
            metric_payload.update({
                "display_role": "local_calendar_continuous_temperature_factor_score",
                "secondary_weight": 0.5,
                "stage_weight_note": "澳洲V0.2在9月至次年4月当地模型窗口连续监测高温与低温；V0.1原主权重保留，原硬排除方向以0.5暂定次要权重纳入。权重未校准。",
                "theoretical_not_calibrated": True,
            })
        _apply_chart_display_window(metric_payload, "Australia", metric)
        metrics[metric] = metric_payload
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


AUSTRALIA_HISTORY_SEASON_STARTS = tuple(range(1991, 2025))
AUSTRALIA_FACTOR_EXPOSURES = {
    "low_temperature": ("tmin", "mean", "low", frozenset((9, 10, 11, 12, 1, 2, 3, 4))),
    "high_heat": ("tmax", "mean", "high", frozenset((9, 10, 11, 12, 1, 2, 3, 4))),
    "excess_rain": ("precip", "sum", "high", frozenset((9, 10, 3, 4))),
    "high_vpd": ("vpd_max", "mean", "high", frozenset((11, 12, 1, 2))),
    "low_solar": ("sw_rad", "sum", "low", frozenset((9, 10, 11, 12, 1, 2, 3, 4))),
}


def _australia_historical_factor_bands(keys: list[str]) -> dict[str, dict[str, list[float | None]]]:
    """Rebuild retrospective Australian single-factor score bands from accepted ERA5.

    Each 14-day point exposure is scored against 1991–2024 same-calendar-day
    exposures with the V0.1 midrank adverse-tail rule. All eight validated AOIs
    contribute with the V0.3 production-allocation weights; valid production
    weight must be at least 0.60. The result is descriptive retrospective
    history, not a point-in-time replay or calibration.
    """
    records, _source_max = _load_australia_records()
    point_exposures = {
        point: {
            metric: _rolling_point_values(records[point], source, mode)
            for metric, (source, mode, _tail, _months) in AUSTRALIA_FACTOR_EXPOSURES.items()
        }
        for point in records
    }
    reference_samples = {
        metric: {
            point: {
                key: [
                    exposures[metric][date(year, int(key[:2]), int(key[3:]))]
                    for year in range(1991, 2025)
                    if (int(key[:2]), int(key[3:])) != (2, 29)
                    and date(year, int(key[:2]), int(key[3:])) in exposures[metric]
                    and exposures[metric][date(year, int(key[:2]), int(key[3:]))] is not None
                ]
                for key in set(keys)
            }
            for point, exposures in point_exposures.items()
        }
        for metric in AUSTRALIA_FACTOR_EXPOSURES
    }

    def midrank(current: float, reference: list[float], tail: str) -> float | None:
        if len(reference) < 20:
            return None
        percentile = (sum(value < current for value in reference) + 0.5 * sum(value == current for value in reference)) / len(reference)
        if tail == "high":
            return min(100.0, max(0.0, 200.0 * max(0.0, percentile - 0.5)))
        return min(100.0, max(0.0, 200.0 * max(0.0, 0.5 - percentile)))

    point_weights = _australia_point_weights(point_exposures)
    result: dict[str, dict[str, list[float | None]]] = {}
    for metric, (_source, _mode, tail, active_months) in AUSTRALIA_FACTOR_EXPOSURES.items():
        season_scores: list[list[float | None]] = []
        for season_start in AUSTRALIA_HISTORY_SEASON_STARTS:
            trace: list[float | None] = []
            for key in keys:
                month, day = (int(part) for part in key.split("-"))
                if month not in active_months:
                    trace.append(None)
                    continue
                target_year = season_start if month >= 9 else season_start + 1
                try:
                    target_day = date(target_year, month, day)
                except ValueError:
                    trace.append(None)
                    continue
                point_scores: dict[str, float] = {}
                for point, exposures in point_exposures.items():
                    value = exposures[metric].get(target_day)
                    if value is None:
                        continue
                    reference = reference_samples[metric][point][key]
                    scored = midrank(value, reference, tail)
                    if scored is not None:
                        point_scores[point] = scored
                valid_weight = math.fsum(point_weights[point] for point in point_scores)
                if valid_weight >= 0.60:
                    trace.append(round(math.fsum(point_weights[point] * score for point, score in point_scores.items()) / valid_weight, 2))
                else:
                    trace.append(None)
            season_scores.append(trace)
        history_min = []
        history_max = []
        for index in range(len(keys)):
            valid = [trace[index] for trace in season_scores if trace[index] is not None]
            history_min.append(min(valid) if valid else None)
            history_max.append(max(valid) if valid else None)
        result[metric] = {"history_min": history_min, "history_max": history_max}
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
    cutoff = source_max
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
        current, current_status = _raw_trace(aggregated[metric_id], 2026, keys, False, cutoff)
        prior, prior_status = _raw_trace(aggregated[metric_id], 2025, keys, False, None)
        history = {year: _raw_trace(aggregated[metric_id], year, keys, False, None)[0] for year in config["history_years"]}
        hist_min = [min((history[year][index] for year in config["history_years"] if history[year][index] is not None), default=None) for index in range(len(keys))]
        hist_max = [max((history[year][index] for year in config["history_years"] if history[year][index] is not None), default=None) for index in range(len(keys))]
        metric = _raw_meta_v05(label, unit, metric_id, config["solar_status"])
        cutoff_point_values = {point: point_exposures[point][metric_id].get(cutoff) for point in config["points"]}
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
            "display_cutoff_date": cutoff.isoformat(),
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
        "source_file_max_date": source_max.isoformat(), "display_cutoff_date": cutoff.isoformat(),
        "metrics": metrics, "solar_model_status": config["solar_status"],
    }


def _validated_australia_files() -> list[Path]:
    """Resolve seven crosswalk identities plus the separately validated St George response."""
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
    st_manifest = read_json(AUSTRALIA_ST_GEORGE_MANIFEST_PATH)
    st_path = AUSTRALIA_ST_GEORGE_RAW_DIR / "st_george_era5_daily.json"
    if (st_manifest.get("aoi_name") != "St George (QLD)" or st_manifest.get("status") != "complete_response"
            or st_manifest.get("source_start_date") != "1991-01-01" or st_manifest.get("source_end_date") != "2026-09-10"
            or st_manifest.get("raw_response_path") != "cotton/research/raw/australia_st_george_era5_daily_v0_1/st_george_era5_daily.json"
            or not st_path.is_file()):
        raise ValueError("St George ERA5 manifest/raw identity or date range mismatch")
    accepted.append(st_path)
    if len(accepted) != 8:
        raise ValueError("expected eight validated Australian raw responses")
    return accepted


AUSTRALIA_FILE_AOI = {
    "01_moree_era5_daily.json": "Gwydir Valley (NSW)",
    "02_narrabri_era5_daily.json": "Namoi Valley (NSW)",
    "03_narromine_era5_daily.json": "Macquarie Valley (NSW)",
    "04_griffith_era5_daily.json": "Murrumbidgee Valley (NSW)",
    "05_dalby_era5_daily.json": "Darling Downs (QLD)",
    "07_goondiwindi_era5_daily.json": "Border Rivers / Macintyre Valley (QLD-NSW)",
    "08_emerald_era5_daily.json": "Central Highlands (Emerald/Theodore/Biloela, QLD)",
    "st_george_era5_daily.json": "St George (QLD)",
}


def _australia_point_weights(points: dict | None = None) -> dict[str, float]:
    """V0.3 target-state production allocation split to named AOIs by its source weights."""
    components = read_json(AUSTRALIA_LATEST_PATH).get("aoi_components") or []
    weights = {row.get("aoi_name"): float(row.get("valid_weight_kt") or 0.0) for row in components}
    total = math.fsum(weights.values())
    normalized = {name: value / total for name, value in weights.items()} if total else {}
    return {name: value for name, value in normalized.items() if points is None or name in points}


@lru_cache(maxsize=1)
def _load_australia_records() -> tuple[dict[str, dict[date, dict[str, float | None]]], date]:
    au_sources = {
        "tmax": "temperature_2m_max", "tmin": "temperature_2m_min",
        "precip": "precipitation_sum", "sw_rad": "shortwave_radiation_sum",
        "vpd_max": "vapour_pressure_deficit_max",
    }
    records = {}
    for path in _validated_australia_files():
        payload = read_json(path)
        daily = payload["daily"]
        point = AUSTRALIA_FILE_AOI[path.name]
        if not daily.get("time") or daily["time"][0] != "1991-01-01" or daily["time"][-1] != "2026-09-10":
            raise ValueError(f"Australia raw date coverage changed: {path.name}")
        records[point] = {}
        for index, raw_date in enumerate(daily["time"]):
            parsed = date.fromisoformat(raw_date)
            records[point][parsed] = {field: _number(daily[source][index]) for field, source in au_sources.items()}
    overlay = _load_current_au_central_overlay()
    overlay_sources = {
        "tmax": "temperature_2m_max", "tmin": "temperature_2m_min",
        "precip": "precipitation_sum", "sw_rad": "shortwave_radiation_sum",
        "vpd_max": "vapor_pressure_deficit_max",
    }
    for point, rows in overlay.items():
        if point not in records:
            continue
        for parsed, values in rows.items():
            if parsed <= date(2026, 9, 10):
                continue
            records[point][parsed] = {field: _number(values.get(source)) for field, source in overlay_sources.items()}
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
    weights = _australia_point_weights(point_exposures)
    for day in all_dates:
        for metric_id in RAW_LABELS:
            point_values = {point: point_exposures[point][metric_id].get(day) for point in point_exposures}
            valid = [(weights[point], value) for point, value in point_values.items() if value is not None]
            coverage = math.fsum(weight for weight, _value in valid)
            aggregated[metric_id][day] = (math.fsum(weight * value for weight, value in valid) / coverage) if coverage >= 0.60 else None
    keys = _window_keys(AUSTRALIA_WINDOW[0], AUSTRALIA_WINDOW[1])
    metrics = {}
    for metric_id, (label, unit, _source_metric, _mode) in RAW_LABELS.items():
        current, current_status = _raw_trace(aggregated[metric_id], 2026, keys, True, source_max)
        prior, prior_status = _raw_trace(aggregated[metric_id], 2025, keys, True, None)
        history = {year: _raw_trace(aggregated[metric_id], year, keys, True, None)[0] for year in range(1991, 2025)}
        hist_min = [min((history[year][index] for year in history if history[year][index] is not None), default=None) for index in range(len(keys))]
        hist_max = [max((history[year][index] for year in history if history[year][index] is not None), default=None) for index in range(len(keys))]
        metric = _raw_meta_v05(label, unit, metric_id, "included_and_active_in_current_stage")
        cutoff_point_values = {point: point_exposures[point][metric_id].get(source_max) for point in point_exposures}
        valid_cutoff = [value for value in cutoff_point_values.values() if value is not None]
        cutoff_coverage = len(valid_cutoff) / len(point_exposures) if point_exposures else 0.0
        metric.update({
            "day_keys": keys, "history_min": hist_min, "history_max": hist_max,
            "last_year": prior, "current_year": current, "last_year_label": "2025/26", "current_year_label": "2026/27",
            "history_years": list(range(1991, 2025)), "history_year_count": 34,
            "status": "available", "last_year_status": prior_status, "current_year_status": current_status,
            "active_periods": [{"start": keys[0], "end": keys[-1]}],
            "source_file_max_date": source_max.isoformat(), "source_gap_count": prior_status.count("source_gap") + current_status.count("source_gap"),
            "display_cutoff_date": source_max.isoformat(),
            "status_counts": {"last_year": _status_counts(prior_status), "current_year": _status_counts(current_status)},
            "valid_current_point_count": len(valid_cutoff), "target_point_count": len(point_exposures), "current_spatial_coverage": cutoff_coverage, "spatial_coverage_gate": 0.60,
        })
        metrics[metric_id] = metric
    return {
        "status": "available", "source": str(AUSTRALIA_RAW_DIR.relative_to(COTTON_ROOT)), "seasonality_source": str(CENTRAL_ASIA_SEASONAL_PATH.relative_to(COTTON_ROOT)),
        "axis": "cross_year_month_day", "current_year": "2026/27", "last_year": "2025/26",
        "display_window_start": AUSTRALIA_WINDOW[0], "display_window_end": AUSTRALIA_WINDOW[1], "display_window_label": AUSTRALIA_WINDOW[2],
        "display_window_status": AUSTRALIA_WINDOW[3], "cross_year_axis": True, "source_file_max_date": source_max.isoformat(),
        "display_cutoff_date": source_max.isoformat(), "metrics": metrics, "solar_model_status": "included_and_active_in_current_stage",
        "point_count": len(point_exposures), "point_weight_method": "V0.3 official state production allocations; AOIs weighted by valid_weight_kt; weights renormalized over valid AOIs",
    }


def build_raw_weather() -> dict:
    result = {REGION_META[geo]["id"]: _raw_region_old(geo) for geo in ("China", "United States", "Brazil", "India")}
    result["australia"] = build_australia_raw_weather()
    return result


def _central_asia_raw_payloads() -> dict[str, dict]:
    """Load the ten frozen Central Asia ERA5 responses with manifest checks."""
    original = read_json(AUSTRALIA_MANIFEST_PATH)
    retry = read_json(CENTRAL_ASIA_RETRY_MANIFEST_PATH)
    if original.get("model") != "era5" or retry.get("model_requested") != "era5":
        raise ValueError("Central Asia raw manifests must declare ERA5")
    if original.get("source_start_date") != "1991-01-01" or original.get("source_end_date") != "2026-09-10":
        raise ValueError("Central Asia original manifest date coverage changed")
    if retry.get("date_start") != "1991-01-01" or retry.get("date_end") != "2026-09-10":
        raise ValueError("Central Asia retry manifest date coverage changed")

    entries: list[tuple[dict, str, str, str]] = []
    for entry in original.get("raw_responses", []):
        if entry.get("aoi_name") in CENTRAL_ASIA_IDS:
            entries.append((entry, "raw_response_path", "raw_response_bytes", "raw_response_sha256"))
    for entry in retry.get("targets", []):
        entries.append((entry, "output_path", "response_bytes", "response_sha256"))
    if {entry[0].get("aoi_name") for entry in entries} != set(CENTRAL_ASIA_IDS):
        raise ValueError("Central Asia raw bundle does not contain the frozen ten AOIs")

    payloads: dict[str, dict] = {}
    for entry, path_field, bytes_field, sha_field in entries:
        if entry.get("status") != "complete_response":
            raise ValueError(f"Central Asia response is not complete: {entry.get('aoi_name')}")
        raw_path = Path(entry[path_field])
        path = raw_path if raw_path.is_absolute() else COTTON_ROOT.parent / raw_path
        raw = path.read_bytes()
        if len(raw) != int(entry[bytes_field]) or hashlib.sha256(raw).hexdigest() != entry[sha_field]:
            raise ValueError(f"Central Asia raw response protection mismatch: {entry.get('aoi_name')}")
        payload = json.loads(raw.decode("utf-8"))
        daily = payload.get("daily", {})
        days = daily.get("time", [])
        if len(days) != 13037 or days[:1] != ["1991-01-01"] or days[-1:] != ["2026-09-10"]:
            raise ValueError(f"Central Asia raw date coverage changed: {entry.get('aoi_name')}")
        if len(set(days)) != len(days):
            raise ValueError(f"Central Asia raw dates are not unique: {entry.get('aoi_name')}")
        if payload.get("daily_units", {}).get("time") != "iso8601":
            raise ValueError(f"Central Asia time unit changed: {entry.get('aoi_name')}")
        for variable, unit in AUSTRALIA_EXPECTED_UNITS.items():
            values = daily.get(variable)
            if payload.get("daily_units", {}).get(variable) != unit or not isinstance(values, list) or len(values) != len(days):
                raise ValueError(f"Central Asia variable contract changed: {entry.get('aoi_name')}/{variable}")
        payloads[entry["aoi_name"]] = payload
    return payloads


def _central_rolling_value(daily: dict, indexes: dict[date, int], variable: str, end: date) -> float | None:
    """Rebuild one complete trailing-14-day statistic; never fill a gap with zero."""
    indexes_for_window = [indexes.get(end - timedelta(days=offset)) for offset in range(13, -1, -1)]
    if any(index is None for index in indexes_for_window):
        return None
    values = [daily[variable][index] for index in indexes_for_window]
    if any(value is None or isinstance(value, bool) or not isinstance(value, (int, float))
           or not math.isfinite(float(value)) for value in values):
        return None
    total = math.fsum(float(value) for value in values)
    return total / 14.0 if variable in CENTRAL_ASIA_MEAN_VARIABLES else total


def _central_midrank(value: float | None, history: list[float]) -> float | None:
    if value is None or len(history) != 34:
        return None
    less = sum(item < value for item in history)
    equal = sum(item == value for item in history)
    return 100.0 * (less + 0.5 * equal) / len(history)


def _central_anomaly_score(values: dict[str, float | None], history: dict[str, list[float]]) -> float | None:
    """Use displayed two-decimal percentiles and half-up two-decimal score."""
    percentiles = [_central_midrank(values.get(variable), history[variable]) for variable in CENTRAL_ASIA_VARIABLES]
    if any(value is None for value in percentiles):
        return None
    rounded_percentiles = [Decimal(f"{value:.2f}") for value in percentiles if value is not None]
    score = sum((Decimal("2") * abs(value - Decimal("50")) for value in rounded_percentiles), Decimal("0"))
    return float((score / Decimal(len(CENTRAL_ASIA_VARIABLES))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _central_anomaly_metric(payload: dict, keys: list[str], cutoff: date = date(2026, 9, 10)) -> dict:
    """Build the same six-variable local 14-day anomaly diagnostic for every display day."""
    daily = payload["daily"]
    indexes = {date.fromisoformat(day): index for index, day in enumerate(daily["time"])}
    aggregates: dict[int, dict[str, dict[str, float | None]]] = {}
    for year in range(1991, 2027):
        by_key: dict[str, dict[str, float | None]] = {}
        for key in keys:
            month, day = (int(part) for part in key.split("-"))
            end = date(year, month, day)
            by_key[key] = {
                variable: _central_rolling_value(daily, indexes, variable, end)
                for variable in CENTRAL_ASIA_VARIABLES
            }
        aggregates[year] = by_key

    history_scores: dict[int, list[float | None]] = {year: [] for year in range(1991, 2025)}
    last_year: list[float | None] = []
    current_year: list[float | None] = []
    current_status: list[str] = []
    for key in keys:
        baseline = {
            variable: [aggregates[year][key][variable] for year in range(1991, 2025)
                       if aggregates[year][key][variable] is not None]
            for variable in CENTRAL_ASIA_VARIABLES
        }
        for year in range(1991, 2025):
            history_scores[year].append(_central_anomaly_score(aggregates[year][key], baseline))
        last_year.append(_central_anomaly_score(aggregates[2025][key], baseline))
        month, day = (int(part) for part in key.split("-"))
        actual = date(2026, month, day)
        if actual > cutoff:
            current_year.append(None)
            current_status.append("future")
        else:
            value = _central_anomaly_score(aggregates[2026][key], baseline)
            current_year.append(value)
            current_status.append("available" if value is not None else "source_gap")

    history_min = [min((history_scores[year][index] for year in history_scores
                        if history_scores[year][index] is not None), default=None)
                   for index in range(len(keys))]
    history_max = [max((history_scores[year][index] for year in history_scores
                        if history_scores[year][index] is not None), default=None)
                   for index in range(len(keys))]
    last_status = ["available" if value is not None else "source_gap" for value in last_year]
    return {
        "label": "天气异常度",
        "unit": "分",
        "window": "截至当日过去14天",
        "aggregation": "六变量14天滚动值相对该AOI 1991—2024当地同期百分位的绝对偏离均值",
        "scale_type": "fixed_score_0_100", "scale_min": 0, "scale_max": 100,
        "value_semantics": "0—100当地天气异常度；不是棉花胁迫、减产或跨AOI排名",
        "blank_value_label": "空值＝今年尚未来临或源数据缺口；不代表0异常",
        "day_keys": keys, "history_min": history_min, "history_max": history_max,
        "last_year": last_year, "current_year": current_year,
        "last_year_label": "2025", "current_year_label": "2026",
        "history_years": list(range(1991, 2025)), "history_year_count": 34,
        "history_reference_mode": "in_sample_local_same_window_1991_2024_midrank",
        "percentile_input_rounding": "displayed_two_decimals_before_score",
        "score_rounding": "ROUND_HALF_UP_two_decimals",
        "status": "available", "last_year_status": last_status, "current_year_status": current_status,
        "status_counts": {"last_year": _status_counts(last_status), "current_year": _status_counts(current_status)},
        "display_cutoff_date": cutoff.isoformat(),
        "cross_region_comparable": False, "weather_stress_score": None,
    }


def _central_payload_with_current_overlay(payload: dict, aoi_name: str, cutoff: date) -> dict:
    """Append current overlay dates to a validated frozen Central Asia payload."""
    overlay = _load_current_au_central_overlay().get(aoi_name, {})
    if not overlay:
        return payload
    extended = dict(payload)
    daily = {key: list(value) if isinstance(value, list) else value for key, value in payload["daily"].items()}
    variable_map = {
        "temperature_2m_max": "temperature_2m_max",
        "temperature_2m_min": "temperature_2m_min",
        "precipitation_sum": "precipitation_sum",
        "shortwave_radiation_sum": "shortwave_radiation_sum",
        "et0_fao_evapotranspiration": "et0_fao_evapotranspiration",
        "vapour_pressure_deficit_max": "vapor_pressure_deficit_max",
    }
    for parsed in sorted(day for day in overlay if date(2026, 9, 10) < day <= cutoff):
        daily["time"].append(parsed.isoformat())
        for target, source in variable_map.items():
            daily[target].append(overlay[parsed][source])
    extended["daily"] = daily
    return extended


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
    raw_payloads = _central_asia_raw_payloads()
    current_overlay = _load_current_au_central_overlay()
    central_overlay = {aoi: rows for aoi, rows in current_overlay.items() if aoi in CENTRAL_ASIA_IDS}
    cutoff = min((max(rows) for rows in central_overlay.values()), default=date(2026, 9, 10))
    labels = {
        "temperature_2m_max": ("日最高温", "°C"), "temperature_2m_min": ("日最低温", "°C"),
        "precipitation_sum": ("日降水", "mm"), "shortwave_radiation_sum": ("日短波辐射", "MJ/m²"),
        "et0_fao_evapotranspiration": ("日参考蒸散", "mm"), "vapour_pressure_deficit_max": ("日最大水汽压亏缺（VPD）", "kPa"),
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
                actual = date(2026, *(int(part) for part in key.split("-")))
                overlay_source = "vapor_pressure_deficit_max" if variable == "vapour_pressure_deficit_max" else variable
                if actual <= cutoff and actual in central_overlay.get(aoi_name, {}):
                    current[index] = central_overlay[aoi_name][actual].get(overlay_source)
            current_status = []
            for index, key in enumerate(keys):
                actual = date(2026, *(int(part) for part in key.split("-")))
                if actual > cutoff:
                    current_status.append("future")
                elif current[index] is None:
                    current_status.append("source_gap")
                else:
                    current_status.append("available")
            metrics[variable] = {
                **_raw_meta(labels[variable][0], labels[variable][1]),
                "day_keys": keys, "history_min": hist_min, "history_max": hist_max,
                "last_year": prior, "current_year": current, "last_year_label": "2025",
                "current_year_label": "2026", "history_years": list(range(1991, 2025)),
                "history_year_count": 34, "status": "available",
                "current_year_status": current_status,
                "display_cutoff_date": cutoff.isoformat(),
                "lineage": first.get("gap_codes", ""),
            }
        extended_payload = _central_payload_with_current_overlay(raw_payloads[aoi_name], aoi_name, cutoff)
        metrics["weather_anomaly_score"] = _central_anomaly_metric(extended_payload, keys, cutoff)
        result[CENTRAL_ASIA_IDS[aoi_name]] = {
            "country": first["country"], "country_display_name": CENTRAL_COUNTRY_DISPLAY[first["country"]],
            "aoi_name": aoi_name, "aoi_display_name": CENTRAL_AOI_DISPLAY[aoi_name],
            "status": "available", "source": str(CENTRAL_ASIA_SEASONAL_PATH.relative_to(COTTON_ROOT)),
            "axis": "month_day", "current_year": 2026, "last_year": 2025,
            "display_window_start": window_start, "display_window_end": window_end,
            "display_window_label": window_label, "display_window_status": window_status,
            "cross_year_axis": False,
            "display_cutoff_date": cutoff.isoformat(),
            "metrics": metrics, "gap_codes": first.get("gap_codes", "").split(";") if first.get("gap_codes") else [],
        }
    return result


@lru_cache(maxsize=None)
def _load_pipeline(geography: str):
    """Load a frozen crop-region builder without executing its write entrypoint."""
    path = PIPELINE_PATHS[geography]
    module_name = f"cotton_public_dashboard_{geography.lower().replace(' ', '_')}_detail"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load regional pipeline: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _point_name(point_id: str) -> str:
    return POINT_DISPLAY.get(point_id, point_id)


def _point_groups(geography: str) -> dict[str, tuple[str, ...]]:
    if geography == "China":
        return {key: value["points"] for key, value in XINJIANG_SUBREGIONS.items()}
    meta = read_json(POINT_META_PATHS[geography])
    groups: dict[str, list[str]] = defaultdict(list)
    for point in meta.get("points", []):
        point_id = point.get("point_id")
        state = point.get("state") or point.get("region")
        if point_id and state:
            groups[str(state).upper()].append(point_id)
    return {key: tuple(values) for key, values in groups.items()}


def _csv_point_records(path: Path, point_ids: set[str], cutoff: date) -> dict[str, dict[date, dict[str, float | None]]]:
    records = {point: {} for point in point_ids}
    start = cutoff - timedelta(days=13)
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            point = row.get("point_id")
            if point not in records:
                continue
            try:
                day = date.fromisoformat((row.get("date") or "")[:10])
            except ValueError:
                continue
            if start <= day <= cutoff:
                records[point][day] = {
                    "tmax": _number(row.get("tmax")), "tmin": _number(row.get("tmin")),
                    "precip": _number(row.get("precip")), "sw_rad": _number(row.get("sw_rad")),
                }
    return records


def _raw_detail(records: dict[str, dict[date, dict[str, float | None]]], points: tuple[str, ...], cutoff: date) -> dict:
    metric_specs = {
        "tmax_14d_mean": ("tmax", "mean", "°C"),
        "tmin_14d_mean": ("tmin", "mean", "°C"),
        "precip_14d_sum": ("precip", "sum", "mm"),
        "sw_rad_14d_mean": ("sw_rad", "mean", "MJ/m²/日"),
    }
    days = [cutoff - timedelta(days=offset) for offset in range(13, -1, -1)]
    values, coverage = {}, {}
    for metric_id, (field, mode, unit) in metric_specs.items():
        point_values = []
        for point in points:
            daily = [records.get(point, {}).get(day, {}).get(field) for day in days]
            if any(value is None for value in daily):
                continue
            point_values.append(math.fsum(daily) if mode == "sum" else math.fsum(daily) / len(daily))
        ratio = len(point_values) / len(points) if points else 0.0
        coverage[metric_id] = ratio
        values[metric_id] = round(math.fsum(point_values) / len(point_values), 3) if point_values and ratio >= 0.60 else None
        values[f"{metric_id}_unit"] = unit
    return {
        "date": cutoff.isoformat(), "values": values,
        "valid_point_count": min((round(coverage[metric] * len(points)) for metric in metric_specs), default=0),
        "target_point_count": len(points), "coverage": min(coverage.values(), default=0.0),
        "aggregation": "complete trailing-14-day point exposure, then equal point mean within displayed subregion",
    }


def _old_network_raw_details(geography: str, cutoff: date) -> dict[str, dict]:
    groups = _point_groups(geography)
    all_points = {point for points in groups.values() for point in points}
    records = _csv_point_records(POINT_DATA_PATHS[geography], all_points, cutoff)
    return {group: _raw_detail(records, points, cutoff) for group, points in groups.items()}


def _factor_diagnostic(value: float | None, enabled: bool, *, mismatch: bool = False) -> dict[str, str]:
    if mismatch:
        return {
            "status": "source_revision_mismatch",
            "reason": "源修订导致快照不一致：当前点文件复算值与已发布地区总分不一致，暂不混用。",
        }
    if not enabled:
        return {"status": "inactive_stage", "reason": "当地当前生育阶段未启用该因子。"}
    if value is None:
        return {
            "status": "data_or_reference_gap",
            "reason": "该因子已启用，但14日天气窗口、点位覆盖或同期历史参考不足。",
        }
    if abs(float(value)) < 1e-12:
        return {"status": "available_zero", "reason": "已计算：当前未落入该因子的历史不利尾部。"}
    return {"status": "available_signal", "reason": "已计算：当前存在历史不利尾部信号。"}


def _score_diagnostic(score: float | None, factor_diagnostics: dict[str, dict[str, str]], *, mismatch: bool = False) -> dict[str, str]:
    if mismatch:
        return {
            "status": "published_score_factor_snapshot_mismatch",
            "reason": "地区总分沿用已发布快照；当前点文件已修订，单因子为避免混合新旧快照而暂不展示。",
        }
    if score is None:
        return {"status": "gap", "reason": "当前没有满足覆盖门的地区综合分；缺值不按0处理。"}
    if abs(float(score)) < 1e-12:
        enabled = [item for item in factor_diagnostics.values() if item["status"] not in {"inactive_stage", "source_revision_mismatch"}]
        if enabled and all(item["status"] == "available_zero" for item in enabled):
            return {"status": "available_zero", "reason": "已计算：当前所有启用因子均未落入各自历史不利尾部，因此综合分为0。"}
        return {"status": "available_zero", "reason": "已计算：启用因子的加权结果为0；不是缺失值。"}
    return {"status": "available_signal", "reason": "已计算：综合分由当前启用且可用的当地因子合成。"}


def _china_detail_components(cutoff: date) -> dict[str, dict]:
    successor = _load_pipeline("China")
    base = successor._load_base()
    base.WEIGHTS = successor._weights()
    weather, _source_max, _excluded = base.load_weather()
    exposures = {point: {} for point in base.FIELD_POINTS}
    for point, point_data in weather.items():
        for day in sorted(point_data):
            exposures[point][day] = base.trailing_exposure(point_data, day)
    results = {}
    for key, config in XINJIANG_SUBREGIONS.items():
        points = config["points"]
        group = config["model_group"]
        point_factors, components = {}, {}
        for point in points:
            point_factors[point], _history = base.historical_scores(exposures, point, cutoff)
            components[point] = base.point_component_score(point_factors[point], group, cutoff.month)
        valid = [components[point][0] for point in points if components[point][0] is not None]
        factor_scores = {}
        factor_diagnostics = {}
        for factor in base.FACTORS:
            enabled = base.WEIGHTS[group][cutoff.month].get(factor, 0) > 0
            factor_values = [point_factors[point][factor] for point in points
                             if enabled and point_factors[point][factor] is not None]
            factor_scores[factor] = math.fsum(factor_values) / len(factor_values) if factor_values else None
            factor_diagnostics[factor] = _factor_diagnostic(factor_scores[factor], enabled)
        results[key] = {
            "score": math.fsum(valid) / len(valid) if valid else None,
            "factor_scores": factor_scores,
            "factor_diagnostics": factor_diagnostics,
            "stage_proxy": base.STAGES[group][cutoff.month],
        }
    return results


def _us_detail_components(cutoff: date) -> dict[str, dict]:
    module = _load_pipeline("United States")
    registry = module.read_registry()
    by_point, all_dates, _input_hash = module.read_weather(registry)
    first_year = all_dates[0].year
    points_by_state: dict[str, list[str]] = defaultdict(list)
    for point, meta in registry.items():
        points_by_state[meta["state"]].append(point)
    results = {}
    for state, points in points_by_state.items():
        point_results = []
        enabled_by_factor = {factor: False for factor in module.FACTORS}
        for point in points:
            regime = module.POINT_REGIME[point]
            if cutoff.month not in module.STAGE[regime]:
                continue
            stage, weights = module.STAGE[regime][cutoff.month]
            factors = {}
            for factor in module.FACTORS:
                if weights.get(factor, 0.0) <= 0:
                    factors[factor] = None
                    continue
                enabled_by_factor[factor] = True
                target = module.calc_exposure(by_point[point], cutoff, factor)
                references = []
                if target is not None:
                    for year in range(first_year, cutoff.year):
                        try:
                            prior = cutoff.replace(year=year)
                        except ValueError:
                            continue
                        value = module.calc_exposure(by_point[point], prior, factor)
                        if value is not None:
                            references.append(value)
                factors[factor] = module.midrank_score(target, references, factor)
            score, _coverage, _valid, _configured, _contrib = module.combine_point(factors, weights)
            point_results.append({"score": score, "factors": factors, "stage": stage})
        valid_scores = [item["score"] for item in point_results if item["score"] is not None]
        factor_scores = {
            factor: (math.fsum(values) / len(values) if values else None)
            for factor in module.FACTORS
            for values in [[item["factors"][factor] for item in point_results if item["factors"][factor] is not None]]
        }
        results[state] = {
            "score": math.fsum(valid_scores) / len(valid_scores) if valid_scores else None,
            "factor_scores": factor_scores,
            "factor_diagnostics": {
                factor: _factor_diagnostic(factor_scores[factor], enabled_by_factor[factor])
                for factor in module.FACTORS
            },
            "stage_proxy": "；".join(sorted({item["stage"] for item in point_results})) if point_results else None,
        }
    return results


def _brazil_detail_components(cutoff: date) -> dict[str, dict]:
    module = _load_pipeline("Brazil")
    points, series, _max_date, _raw_hash = module.load_inputs()
    points_by_state: dict[str, list[str]] = {state: [] for state in module.REGIMES}
    for point_id, point in points.items():
        points_by_state[point["state"]].append(point_id)
    exposures = module.build_exposures(series)
    results = {}
    for state in module.REGIMES:
        result = module.state_day_result(state, cutoff, points_by_state, exposures)
        if result is None:
            factor_scores = {factor: None for factor in module.METRICS}
            results[state] = {"score": None, "factor_scores": factor_scores,
                              "factor_diagnostics": {factor: _factor_diagnostic(None, False) for factor in module.METRICS},
                              "stage_proxy": "当前月份未启用"}
        else:
            configured = module.REGIMES[state]["months"][cutoff.month][1]
            factor_scores = result["factor_scores"]
            results[state] = {"score": result["score"], "factor_scores": factor_scores,
                              "factor_diagnostics": {
                                  factor: _factor_diagnostic(factor_scores.get(factor), configured.get(factor, 0) > 0)
                                  for factor in module.METRICS
                              }, "stage_proxy": result["stage"]}
    return results


def _india_detail_components(cutoff: date) -> dict[str, dict]:
    module = _load_pipeline("India")
    point_state = module.load_target_points()
    weather, _source_max = module.load_weather(point_state=point_state)
    exposures = {point: {} for point in weather}
    for point, daily in weather.items():
        for day in daily:
            exposure = module.trailing_exposure(daily, day)
            if exposure is not None:
                exposures[point][day] = exposure
    results = {}
    for state in module.STATE_REGIME:
        regime = module.STATE_REGIME[state]
        weights = module.REGIMES[regime]["weights"].get(cutoff.month)
        points = [point for point, point_state_code in point_state.items() if point_state_code == state]
        if weights is None:
            factor_scores = {factor: None for factor in module.FACTORS}
            results[state] = {"score": None, "factor_scores": factor_scores,
                              "factor_diagnostics": {factor: _factor_diagnostic(None, False) for factor in module.FACTORS},
                              "stage_proxy": "当前月份未启用"}
            continue
        point_results = []
        for point in points:
            scores, _history = module.factor_scores(exposures, point, cutoff)
            score, _coverage, _valid, _configured = module.point_score(scores, weights)
            point_results.append({"score": score, "factors": scores})
        valid_scores = [item["score"] for item in point_results if item["score"] is not None]
        factor_scores = {
            factor: module._aggregate([item["factors"][factor] for item in point_results if item["factors"][factor] is not None])
            for factor in module.FACTORS
        }
        results[state] = {
            "score": module._aggregate(valid_scores), "factor_scores": factor_scores,
            "factor_diagnostics": {
                factor: _factor_diagnostic(factor_scores[factor], dict(zip(module.FACTORS, weights)).get(factor, 0) > 0)
                for factor in module.FACTORS
            },
            "stage_proxy": module.REGIMES[regime]["calendar"][cutoff.month],
        }
    return results


def _australia_raw_details(cutoff: date) -> dict[str, dict]:
    records, _source_max = _load_australia_records()
    return {aoi: _raw_detail(records, (aoi,), cutoff) for aoi in records}


def _season_dates(season_years: list[int] | range | tuple[int, ...], keys: list[str], cross_year: bool) -> list[date]:
    days = []
    for season_year in season_years:
        for key in keys:
            month, day = (int(part) for part in key.split("-"))
            actual_year = season_year + 1 if cross_year and month < 9 else season_year
            try:
                days.append(date(actual_year, month, day))
            except ValueError:
                pass
    return days


def _subregion_metric(
    values_by_date: dict[date, float | None], *, geography: str, metric_id: str,
    keys: list[str], history_years: list[int], cutoff: date, cross_year: bool,
    raw: bool,
) -> dict:
    """Turn one local daily series into the dashboard's common seasonal contract."""
    current, current_status = _raw_trace(values_by_date, 2026, keys, cross_year, cutoff)
    prior, prior_status = _raw_trace(values_by_date, 2025, keys, cross_year, None)
    history = {year: _raw_trace(values_by_date, year, keys, cross_year, None)[0] for year in history_years}
    history_min = [min((history[year][index] for year in history_years if history[year][index] is not None), default=None)
                   for index in range(len(keys))]
    history_max = [max((history[year][index] for year in history_years if history[year][index] is not None), default=None)
                   for index in range(len(keys))]
    active_keys = {
        key for index, key in enumerate(keys)
        if any(history[year][index] is not None for year in history_years)
        or prior[index] is not None or current[index] is not None
    }
    for index, key in enumerate(keys):
        if key not in active_keys:
            if current_status[index] != "future":
                current_status[index] = "inactive_stage"
            prior_status[index] = "inactive_stage"
    if raw:
        label, unit, _source, _mode = RAW_LABELS[metric_id]
        payload = _raw_meta_v05(label, unit, metric_id, "subregion_raw_display")
    else:
        payload = _score_meta(METRIC_META.get(metric_id, {"label": metric_id, "unit": "分", "window": "逐日因子分"}), metric_id)
    digits = 3 if raw else 2
    tidy = lambda values: [round(value, digits) if value is not None else None for value in values]
    payload.update({
        "day_keys": keys, "history_min": tidy(history_min), "history_max": tidy(history_max),
        "last_year": tidy(prior), "current_year": tidy(current),
        "last_year_label": "2025/26" if cross_year else "2025",
        "current_year_label": "2026/27" if cross_year else "2026",
        "history_years": history_years, "history_year_count": len(history_years),
        "status": "available" if any(value is not None for value in current + prior + history_min + history_max) else "gap",
        "last_year_status": prior_status, "current_year_status": current_status,
        "active_periods": _compress_periods(keys, active_keys),
        "display_cutoff_date": cutoff.isoformat(),
        "source_gap_count": prior_status.count("source_gap") + current_status.count("source_gap"),
        "status_counts": {"last_year": _status_counts(prior_status), "current_year": _status_counts(current_status)},
        "historical_band_note": "历史最大—最小带按该地区自身序列计算；不是国家曲线下放。",
    })
    if not raw:
        if geography == "China" and metric_id == "spring_wind":
            payload.update({
                "chart_display_start": "04-01", "chart_display_end": "05-31",
                "chart_display_note": "图轴仅显示春季风害评分启用期 04-01—05-31；6—11月不展示。",
            })
        _apply_chart_display_window(payload, geography, metric_id)
    return payload


def _load_full_point_records(geography: str) -> tuple[dict[str, dict[date, dict[str, float | None]]], date]:
    groups = _point_groups(geography)
    points = {point for group in groups.values() for point in group}
    records = {point: {} for point in points}
    with POINT_DATA_PATHS[geography].open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            point = row.get("point_id")
            if point not in records:
                continue
            try:
                day = date.fromisoformat((row.get("date") or "")[:10])
            except ValueError:
                continue
            records[point][day] = {
                "tmax": _number(row.get("tmax")), "tmin": _number(row.get("tmin")),
                "precip": _number(row.get("precip")), "sw_rad": _number(row.get("sw_rad")),
            }
    source_max = max(max(series) for series in records.values() if series)
    return records, source_max


@lru_cache(maxsize=None)
def _subregion_raw_seasonal(geography: str, cutoff: date) -> dict[str, dict[str, dict]]:
    cross_year = geography == "Australia"
    if cross_year:
        records, _source_max = _load_australia_records()
        groups = {aoi: (aoi,) for aoi in records}
        keys = _window_keys(AUSTRALIA_WINDOW[0], AUSTRALIA_WINDOW[1])
        history_years = list(range(1991, 2025))
    else:
        records, _source_max = _load_full_point_records(geography)
        groups = _point_groups(geography)
        keys = _window_keys(SEASON_WINDOWS[geography][0], SEASON_WINDOWS[geography][1])
        history_years = list(range(2005, 2025))
    point_exposures = {
        point: {
            metric_id: _rolling_point_values(records[point], source, mode)
            for metric_id, (_label, _unit, source, mode) in RAW_LABELS.items()
        }
        for point in records
    }
    result = {}
    for group, points in groups.items():
        metrics = {}
        all_dates = sorted({day for point in points for metric in point_exposures[point].values() for day in metric})
        for metric_id in RAW_LABELS:
            values_by_date = {}
            for day in all_dates:
                values = [point_exposures[point][metric_id].get(day) for point in points]
                valid = [value for value in values if value is not None]
                values_by_date[day] = math.fsum(valid) / len(valid) if values and len(valid) / len(values) >= 0.60 else None
            metrics[metric_id] = _subregion_metric(
                values_by_date, geography=geography, metric_id=metric_id, keys=keys,
                history_years=history_years, cutoff=cutoff, cross_year=cross_year, raw=True,
            )
        result[group] = metrics
    return result


@lru_cache(maxsize=None)
def _subregion_factor_series(geography: str, cutoff: date) -> dict[str, dict[str, dict[date, float | None]]]:
    """Recompute local score/factor daily series with each country's frozen model logic."""
    result: dict[str, dict[str, dict[date, float | None]]] = defaultdict(lambda: defaultdict(dict))
    keys = _window_keys(*(AUSTRALIA_WINDOW[:2] if geography == "Australia" else SEASON_WINDOWS[geography][:2]))
    cross_year = geography == "Australia"
    if geography == "China":
        successor = _load_pipeline("China")
        base = successor._load_base()
        base.WEIGHTS = successor._weights()
        weather, _source_max, _excluded = base.load_weather()
        exposures = {point: {} for point in base.FIELD_POINTS}
        for point, point_data in weather.items():
            for day in sorted(point_data):
                exposures[point][day] = base.trailing_exposure(point_data, day)
        available = set.intersection(*(set(series) for series in weather.values()))
        for day in (day for day in _season_dates(range(2015, 2027), keys, False) if day in available):
            for group_id, config in XINJIANG_SUBREGIONS.items():
                point_factors, point_scores = {}, []
                for point in config["points"]:
                    factors, _history = base.historical_scores(exposures, point, day)
                    point_factors[point] = factors
                    component = base.point_component_score(factors, config["model_group"], day.month)[0]
                    if component is not None:
                        point_scores.append(component)
                result[group_id]["score"][day] = math.fsum(point_scores) / len(point_scores) if point_scores else None
                for factor in base.FACTORS:
                    values = [point_factors[point][factor] for point in config["points"]
                              if base.WEIGHTS[config["model_group"]][day.month].get(factor, 0) > 0
                              and point_factors[point][factor] is not None]
                    result[group_id][factor][day] = math.fsum(values) / len(values) if values else None
        return result

    if geography == "United States":
        module = _load_pipeline(geography)
        registry = module.read_registry()
        by_point, all_dates, _input_hash = module.read_weather(registry)
        first_year = all_dates[0].year
        exposures = {point: {factor: {} for factor in module.FACTORS} for point in by_point}
        for point, series in by_point.items():
            for day in all_dates:
                for factor in module.FACTORS:
                    value = module.calc_exposure(series, day, factor)
                    if value is not None:
                        exposures[point][factor][day] = value
        points_by_state = _point_groups(geography)
        available_dates = set(all_dates)
        for day in (day for day in _season_dates(range(2015, 2027), keys, False) if day in available_dates):
            for state, points in points_by_state.items():
                point_results = []
                for point in points:
                    regime = module.POINT_REGIME[point]
                    if day.month not in module.STAGE[regime]:
                        continue
                    _stage, weights = module.STAGE[regime][day.month]
                    factors = {}
                    for factor in module.FACTORS:
                        if weights.get(factor, 0.0) <= 0:
                            factors[factor] = None
                            continue
                        target = exposures[point][factor].get(day)
                        refs = []
                        if target is not None:
                            for year in range(first_year, day.year):
                                try:
                                    ref_day = day.replace(year=year)
                                except ValueError:
                                    continue
                                value = exposures[point][factor].get(ref_day)
                                if value is not None:
                                    refs.append(value)
                        factors[factor] = module.midrank_score(target, refs, factor)
                    score = module.combine_point(factors, weights)[0]
                    point_results.append((score, factors))
                scores = [score for score, _factors in point_results if score is not None]
                result[state]["score"][day] = math.fsum(scores) / len(scores) if scores else None
                for factor in module.FACTORS:
                    values = [factors[factor] for _score, factors in point_results if factors[factor] is not None]
                    result[state][factor][day] = math.fsum(values) / len(values) if values else None
        return result

    if geography == "Brazil":
        module = _load_pipeline(geography)
        points, series, source_max, _raw_hash = module.load_inputs()
        points_by_state = {state: [] for state in module.REGIMES}
        for point_id, point in points.items():
            points_by_state[point["state"]].append(point_id)
        exposures = module.build_exposures(series)
        for day in (day for day in _season_dates(range(2015, 2027), keys, False) if day <= source_max):
            for state in module.REGIMES:
                item = module.state_day_result(state, day, points_by_state, exposures)
                result[state]["score"][day] = item["score"] if item else None
                for factor in module.METRICS:
                    result[state][factor][day] = item["factor_scores"].get(factor) if item else None
        return result

    if geography == "India":
        module = _load_pipeline(geography)
        point_state = module.load_target_points()
        weather, source_max = module.load_weather(point_state=point_state)
        exposures = {point: {} for point in weather}
        for point, daily in weather.items():
            for day in daily:
                exposure = module.trailing_exposure(daily, day)
                if exposure is not None:
                    exposures[point][day] = exposure
        points_by_state = _point_groups(geography)
        for day in (day for day in _season_dates(range(2015, 2027), keys, False) if day <= source_max):
            for state, points in points_by_state.items():
                regime = module.STATE_REGIME[state]
                weights = module.REGIMES[regime]["weights"].get(day.month)
                point_results = []
                if weights is not None:
                    for point in points:
                        factors, _history = module.factor_scores(exposures, point, day)
                        point_results.append((module.point_score(factors, weights)[0], factors))
                scores = [score for score, _factors in point_results if score is not None]
                result[state]["score"][day] = module._aggregate(scores)
                for factor in module.FACTORS:
                    result[state][factor][day] = module._aggregate(
                        [factors[factor] for _score, factors in point_results if factors[factor] is not None]
                    )
        return result

    if geography == "Australia":
        module = _load_pipeline(geography)
        raw_points = module._load_inputs(COTTON_ROOT.parent)[0]
        for day in _season_dates(range(1991, 2027), keys, True):
            if day.month not in module.MONTH_WEIGHTS:
                continue
            for aoi in module.EXPECTED_AOIS:
                item = module._score_point(raw_points[aoi]["values"], day)
                result[aoi]["score"][day] = item["score"]
                for factor in module.FACTOR_ORDER:
                    result[aoi][factor][day] = item["factor_scores"][factor]
        return result
    raise ValueError(f"unsupported subregion geography: {geography}")


def build_subregion_seasonal(regions: list[dict]) -> dict:
    """Build local-only score, factor and raw charts for every displayed subregion."""
    output = {}
    for geography in ("China", "United States", "Brazil", "India", "Australia"):
        region_id = REGION_META[geography]["id"]
        region = next(item for item in regions if item["id"] == region_id)
        cutoff = date.fromisoformat(region["date"][:10])
        cross_year = geography == "Australia"
        keys = _window_keys(*(AUSTRALIA_WINDOW[:2] if cross_year else SEASON_WINDOWS[geography][:2]))
        history_years = list(range(1991, 2025)) if cross_year else list(range(2015, 2025))
        raw_metrics = _subregion_raw_seasonal(geography, cutoff)
        factor_series = _subregion_factor_series(geography, cutoff)
        output[region_id] = {}
        for detail in region["network_details"]:
            sub_id = detail["id"]
            source_id = detail.get("source_name", sub_id)
            score_allowed = detail.get("factor_detail_status") != "source_revision_mismatch"
            metrics = {}
            if score_allowed:
                for metric_id, values in factor_series.get(source_id, {}).items():
                    metrics[metric_id] = _subregion_metric(
                        values, geography=geography, metric_id=metric_id, keys=keys,
                        history_years=history_years, cutoff=cutoff, cross_year=cross_year, raw=False,
                    )
            output[region_id][sub_id] = {
                "name": detail["name"], "status": "available" if score_allowed else "source_revision_mismatch",
                "score_factor_chart_note": detail.get("factor_detail_note"),
                "metrics": metrics, "raw_metrics": raw_metrics.get(source_id, {}),
                "axis": "cross_year_month_day" if cross_year else "month_day",
                "current_year": "2026/27" if cross_year else 2026,
                "last_year": "2025/26" if cross_year else 2025,
            }
    return output


def _enrich_network_details(geography: str, rows: list[dict], national: dict) -> list[dict]:
    """Attach current local raw values and local model-factor diagnostics."""
    cutoff = date.fromisoformat(str(national.get("date"))[:10])
    if geography == "China":
        raw = _old_network_raw_details(geography, cutoff)
        components = _china_detail_components(cutoff)
        area_weight_contract = read_json(XINJIANG_AREA_WEIGHT_PATH)
        area_groups = area_weight_contract["groups"]
        enriched = []
        for key, config in XINJIANG_SUBREGIONS.items():
            comp = components[key]
            area = area_groups[key]
            enriched.append({
                "id": key, "name": config["name"], "score": comp["score"],
                "valid_point_count": raw[key]["valid_point_count"], "target_point_count": len(config["points"]),
                "production_weight_share": area["weight_share_within_displayed_groups"],
                "weight_type": "official_cotton_area_proxy",
                "weight_area_10k_mu": area["area_10k_mu"],
                "weight_base": "2022_official_local_area_except_kuitun_2023_local_only",
                "weight_coverage_of_xinjiang_2022": area_weight_contract["represented_area_coverage_of_xinjiang_2022"],
                "status": "available" if comp["score"] is not None else "gap",
                "factor_scores": comp["factor_scores"], "factor_diagnostics": comp["factor_diagnostics"],
                "score_diagnostic": _score_diagnostic(comp["score"], comp["factor_diagnostics"]),
                "raw_weather": raw[key], "stage_proxy": comp["stage_proxy"],
                "point_names": [_point_name(point) for point in config["points"]],
                "coverage_semantics": "新疆田间代理点等权；面积权重仅为七个展示组内代理，约覆盖2022全疆官方棉花面积66.23%",
                "factor_detail_status": "available_same_model_recompute",
                "factor_detail_note": "按新疆 V0.2 同一权重与同期历史分布复算；仍为未校准理论胁迫分。面积权重不参与模型分数计算。",
            })
        return sorted(enriched, key=lambda row: (-float(row.get("production_weight_share") or 0), row["name"]))

    if geography == "Australia":
        raw = _australia_raw_details(cutoff)
        components = {item["aoi_name"]: item for item in national.get("aoi_components") or []}
        module = _load_pipeline("Australia")
        configured = module.MONTH_WEIGHTS.get(cutoff.month, {})
        enriched = []
        for row in rows:
            aoi = row["name"]
            component = components.get(aoi, {})
            factor_scores = component.get("factor_scores") or {}
            factor_diagnostics = {
                factor: _factor_diagnostic(factor_scores.get(factor), configured.get(factor, 0) > 0)
                for factor in module.FACTOR_ORDER
            }
            enriched.append({
                **row, "id": aoi, "name": SUBREGION_DISPLAY[geography].get(aoi, aoi),
                "source_name": aoi, "factor_scores": factor_scores,
                "factor_diagnostics": factor_diagnostics,
                "score_diagnostic": _score_diagnostic(row.get("score"), factor_diagnostics),
                "raw_weather": raw.get(aoi), "stage_proxy": national.get("stage_proxy"),
                "point_names": [aoi], "coverage_semantics": "单个城镇格点代理；不是 AOI 面平均",
                "factor_detail_status": "available_embedded_model_output",
                "factor_detail_note": "单因子直接来自澳大利亚 V0.3 已发布 AOI 组件；仍为未校准理论胁迫分。",
            })
        return sorted(enriched, key=lambda row: (-float(row.get("production_weight_share") or 0), row["name"]))

    raw = _old_network_raw_details(geography, cutoff)
    components = ({"United States": _us_detail_components, "Brazil": _brazil_detail_components,
                   "India": _india_detail_components}[geography])(cutoff)
    enriched = []
    for row in rows:
        code = row["name"].split("（", 1)[0] if geography == "Brazil" else row["name"]
        if geography == "Brazil":
            code_by_name = {"马托格罗索": "MT", "巴伊亚": "BA", "马拉尼昂": "MA", "皮奥伊": "PI",
                            "戈亚斯": "GO", "南马托格罗索": "MS", "米纳斯吉拉斯": "MG", "圣保罗": "SP",
                            "巴拉那": "PR", "帕拉": "PA", "托坎廷斯": "TO"}
            code = code_by_name.get(code, code)
        component = components.get(code, {})
        point_ids = _point_groups(geography).get(code, ())
        accepted_score = row.get("score")
        recomputed_score = component.get("score")
        snapshot_match = (
            accepted_score is None and recomputed_score is None
        ) or (
            accepted_score is not None and recomputed_score is not None
            and abs(float(accepted_score) - float(recomputed_score)) <= 0.02
        )
        factor_scores = component.get("factor_scores") or {}
        factor_diagnostics = component.get("factor_diagnostics") or {
            factor: _factor_diagnostic(value, value is not None) for factor, value in factor_scores.items()
        }
        if not snapshot_match:
            factor_scores = {factor: None for factor in factor_scores}
            factor_diagnostics = {factor: _factor_diagnostic(None, False, mismatch=True) for factor in factor_scores}
        enriched.append({
            **row, "id": code, "name": SUBREGION_DISPLAY.get(geography, {}).get(code, row["name"]),
            "factor_scores": factor_scores, "factor_diagnostics": factor_diagnostics,
            "score_diagnostic": _score_diagnostic(accepted_score, factor_diagnostics, mismatch=not snapshot_match),
            "raw_weather": raw.get(code),
            "stage_proxy": component.get("stage_proxy"), "point_names": [_point_name(point) for point in point_ids],
            "coverage_semantics": "州／邦内登记点等权；不是行政区面平均或完整农田覆盖",
            "factor_detail_status": "available_same_score_recompute" if snapshot_match else "source_revision_mismatch",
            "factor_detail_note": (
                "地区总分可从当前输入复算一致；单因子为同一地区模型口径的当前诊断。"
                if snapshot_match else
                "当前点文件已发生源修订，复算地区总分与已发布快照不一致；为避免混合快照，本地区单因子暂不展示。"
            ),
        })
    return sorted(enriched, key=lambda row: (
        row.get("production_weight_share") is None,
        -float(row.get("production_weight_share") or 0),
        row["name"],
    ))


def _national_details(geography: str, raw: dict) -> list[dict]:
    """Small, explicit state/AOI detail rows; null scores stay null."""
    display = {
        "MT": "马托格罗索（MT，二季棉为主）", "BA": "巴伊亚（BA，首季/混合作制）",
        "MA": "马拉尼昂（MA，Cerrado）", "PI": "皮奥伊（PI，Cerrado）", "GO": "戈亚斯（GO，Cerrado）",
        "MS": "南马托格罗索（MS，首季）", "MG": "米纳斯吉拉斯（MG，Cerrado）", "SP": "圣保罗（SP，南部/首季）",
        "PR": "巴拉那（PR，南部/首季）", "PA": "帕拉（PA，北部）", "TO": "托坎廷斯（TO，Cerrado）",
    }
    if geography == "China":
        return [{"name": "新疆（唯一代理，非中国全国）", "score": raw.get("theoretical_weather_stress_index"),
                 "valid_point_count": 18, "target_point_count": 18,
                 "production_weight_share": None, "status": "proxy_only"}]
    if geography == "Brazil":
        states = {state: dict(value) for state, value in (raw.get("state_details") or {}).items()}
        shares = raw.get("official_state_production_weights") or {}
        target_ids = raw.get("target_point_ids") or []
        for state in ("MT", "BA", "MA", "PI", "GO", "MS", "MG", "SP", "PR", "PA", "TO"):
            ids = [point for point in target_ids if point.startswith(state.lower() + "_")]
            value = states.get(state, {})
            states[state] = {**value, "target_point_count": len(ids), "point_ids": ids}
        return [{"name": display.get(state, state), "score": value.get("score"),
                 "valid_point_count": value.get("valid_point_count", 0), "target_point_count": value.get("target_point_count", 0),
                 "production_weight_share": shares.get(state),
                 "status": "available" if value.get("score") is not None else "inactive_or_gap"}
                for state, value in states.items()]
    if geography == "United States":
        states = raw.get("state_scores") or {}
        weights = raw.get("state_production_weights_1000_480lb_bales") or {}
        denominator = raw.get("usda_nass_network_production_1000_480lb_bales")
        point_ids = [point for points in (raw.get("point_ids_by_regime") or {}).values() for point in points]
        abbreviations = sorted(set(point.split("_", 1)[0].upper() for point in point_ids))
        return [{"name": state, "score": states.get(state), "valid_point_count": sum(1 for point in point_ids if point.startswith(state.lower() + "_")),
                 "target_point_count": sum(1 for point in point_ids if point.startswith(state.lower() + "_")),
                 "production_1000_480lb_bales": weights.get(state),
                 "production_weight_share": (weights.get(state) / denominator if weights.get(state) is not None and denominator else None),
                 "status": "available" if states.get(state) is not None else "gap"}
                for state in abbreviations]
    if geography == "India":
        components = {key[:2].upper(): raw.get(f"{key}_component_score") for key in ("pb", "hr", "rj", "gj", "mh", "mp", "tg", "ap", "ka", "tn")}
        weights = raw.get("state_production_weights_million_170kg_bales") or {}
        denominator = raw.get("active_target_production_weight_million_bales")
        return [{"name": state, "score": components.get(state), "valid_point_count": None, "target_point_count": None,
                 "production_weight_million_bales": weights.get(state),
                 "production_weight_share": (weights.get(state) / denominator if weights.get(state) is not None and denominator else None),
                 "status": "available" if components.get(state) is not None else "gap"}
                for state in sorted(set(components) | set(weights))]
    if geography == "Australia":
        rows = []
        denominator = raw.get("target_state_production_weight_kt")
        for item in raw.get("aoi_components") or []:
            rows.append({"name": item.get("aoi_name"), "score": item.get("score"), "valid_point_count": int(item.get("point_status") == "valid_era5_response"),
                         "target_point_count": 1,
                         "production_weight_share": (item.get("valid_weight_kt") / denominator if item.get("valid_weight_kt") is not None and denominator else None),
                         "status": item.get("point_status")})
        return rows
    return []


def build_region(geography: str, supply_row: dict | None = None) -> dict:
    raw = read_json(REGION_PATHS[geography])
    meta = REGION_META[geography]
    national = read_json(NATIONAL_LATEST_PATHS[geography]) if geography in NATIONAL_LATEST_PATHS else raw
    factors = []
    for factor_id, label, field in meta["factor_fields"]:
        value = factor_value(national, field)
        factors.append(
            {
                "id": factor_id,
                "label": label,
                "score": value,
                "status": "available" if value is not None else "not_available_or_inactive",
            }
        )

    details = _enrich_network_details(geography, _national_details(geography, national), national)
    return {
        "id": meta["id"],
        "name": meta["name"],
        "short_name": meta["short_name"],
        "geography": geography,
        "date": national.get("date"),
        "source_file_max_date": national.get("source_file_max_date", national.get("date")),
        "score": national.get("theoretical_weather_stress_index"),
        "band": national.get("stress_band"),
        "band_display": BAND_DISPLAY.get(national.get("stress_band"), "暂无"),
        "change_7d": national.get("change_7d"),
        "change_yoy": national.get("change_yoy", national.get("change_year")),
        "score_7d_ago": national.get("score_7d_ago"),
        "score_year_ago": national.get("score_year_ago"),
        "confidence": national.get("confidence"),
        "confidence_display": CONFIDENCE_DISPLAY.get(national.get("confidence"), "暂无"),
        "point_coverage": national.get("point_coverage"),
        "target_point_count": national.get("target_point_count", national.get("active_point_count", national.get("point_registry_expected_count", 18 if geography == "China" else None))),
        "valid_point_count": national.get("valid_point_count", 18 if geography == "China" else None),
        "production_weight_coverage": (None if geography == "China" else national.get("production_weight_coverage", national.get("production_weight_coverage_of_india", national.get("production_weight_coverage_us_total")))),
        "official_production_weight_coverage": (None if geography == "China" else national.get("official_production_weight_coverage", national.get("production_weight_coverage_of_india", national.get("production_weight_coverage_us_total")))),
        "factor_weight_coverage": national.get("factor_weight_coverage", national.get("point_factor_weight_coverage")),
        "stage_proxy": national.get("stage_proxy"),
        "stage_binding": national.get("stage_binding"),
        "stage_display": meta["stage_display"],
        "source_mode": source_mode(national),
        "model_version": national.get("model_version", "v0_1"),
        "source_path": str((NATIONAL_LATEST_PATHS.get(geography, REGION_PATHS[geography])).relative_to(COTTON_ROOT)),
        "coverage_name": meta["name"],
        "theoretical_not_calibrated": national.get("theoretical_not_calibrated"),
        "network_details": details,
        "production_weight_coverage_label": "中国全国生产权重覆盖不适用：仅以新疆代理" if geography == "China" else "官方/可确认全国生产权重覆盖",
        "raw_network_name": {"China": "新疆代理18点", "United States": "旧德州12点代表网络", "Brazil": "旧马托格罗索12点代表网络", "India": "旧中部雨养带16点代表网络"}.get(geography, meta["name"]),
        "raw_network_note": "当前原始天气仍来自区域代表点位网络，不能代表全国；仅综合分及模型单因子使用全国既有网络。" if geography in ("United States", "Brazil", "India") else "原始天气为新疆18点代理，不代表中国全国。" if geography == "China" else "原始天气为当前网络点位聚合。",
        "factors": factors,
        "drivers": raw.get("primary_stress_drivers") or [],
        "inactive": raw.get("countervailing_or_inactive_factors") or [],
        "gap_codes": (national.get("gap_codes") if isinstance(national.get("gap_codes"), list) else [part for part in (national.get("gap_codes") or "").split(";") if part]),
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
        "id": meta["id"], "name": "澳大利亚", "short_name": "澳大利亚",
        "geography": "Australia", "date": raw.get("date"), "source_file_max_date": raw.get("source_file_max_date"),
        "score": raw.get("theoretical_weather_stress_index"), "band": raw.get("stress_band"),
        "band_display": BAND_DISPLAY.get(raw.get("stress_band"), "暂无"), "change_7d": raw.get("change_7d"),
        "change_yoy": raw.get("change_yoy"), "score_7d_ago": raw.get("score_7d_ago"),
        "score_year_ago": raw.get("score_year_ago"), "confidence": raw.get("confidence"),
        "confidence_display": CONFIDENCE_DISPLAY.get(raw.get("confidence"), "暂无"),
        "point_coverage": raw.get("point_coverage"), "target_point_count": raw.get("configured_aoi_count", len(raw.get("point_ids") or [])),
        "valid_point_count": raw.get("valid_aoi_count", len([x for x in raw.get("aoi_components", []) if x.get("point_status") == "valid_era5_response"])),
        "production_weight_coverage": raw.get("production_weight_coverage_national"),
        "official_production_weight_coverage": raw.get("production_weight_coverage_national"),
        "production_weight_coverage_label": "澳大利亚官方全国产量权重覆盖",
        "network_details": _enrich_network_details("Australia", _national_details("Australia", raw), raw), "factor_weight_coverage": raw.get("factor_weight_coverage"),
        "model_version": raw.get("model_version", "v0_3"),
        "source_path": str(AUSTRALIA_LATEST_PATH.relative_to(COTTON_ROOT)),
        "coverage_name": "澳大利亚",
        "raw_network_name": "澳洲8 AOI 原始天气网络",
        "raw_network_note": "原始天气、综合分和模型单因子均使用含 St George 的 V0.3 八 AOI 网络；按 AOI 生产分配权重聚合，仍有全国未覆盖产量缺口。",
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
        enriched["confidence_display"] = "仅用作当地天气异常度观察" if row.get("confidence") == "low" else CONFIDENCE_DISPLAY.get(row.get("confidence"), "暂无")
        result.append(enriched)
    return result


PRODUCTION_WEIGHTED_ID = "five_region_production_weighted_weather_stress_display"
PRODUCTION_WEIGHTED_NAME = "全球棉花五大种植区域天气胁迫总评分（产区产量加权）"
PRODUCTION_WEIGHTED_REGIONS = ("China", "United States", "Brazil", "India", "Australia")
PRODUCTION_WEIGHTED_REGION_IDS = {
    "China": "china", "United States": "us", "Brazil": "brazil", "India": "india", "Australia": "australia",
}
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
            "name": "中国·新疆" if geo == "China" else GEO_DISPLAY[geo],
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


def _production_year_trace(year: int, daily: dict[str, dict[date, float | None]], weights: dict[str, float], cutoff: date, current: bool = False) -> tuple[list[float | None], list[float | None], list[list[str]], list[str]]:
    values, coverage, valid_ids, statuses = [], [], [], []
    for key in PRODUCTION_WEIGHTED_KEYS:
        month, day = (int(part) for part in key.split("-"))
        actual = date(year, month, day)
        if current and actual > cutoff:
            values.append(None); coverage.append(None); valid_ids.append([]); statuses.append("future"); continue
        local = {PRODUCTION_WEIGHTED_REGION_IDS[geo]: daily[PRODUCTION_WEIGHTED_REGION_IDS[geo]].get(actual) for geo in PRODUCTION_WEIGHTED_REGIONS}
        result = _weighted_production_day(local, weights)
        values.append(result["value"]); coverage.append(result["production_weight_coverage"]); valid_ids.append(result["valid_region_ids"]); statuses.append(result["status"])
    return values, coverage, valid_ids, statuses


def build_production_weighted_weather(brief: dict) -> dict:
    weight_rows, weights = _production_weights(brief)
    daily = {PRODUCTION_WEIGHTED_REGION_IDS[geo]: _score_daily_by_date(NATIONAL_DAILY_PATHS[geo] if geo in NATIONAL_DAILY_PATHS else DAILY_PATHS[geo]) for geo in PRODUCTION_WEIGHTED_REGIONS}
    latest_by_region = {
        region_id: max(day for day, value in values.items() if value is not None)
        for region_id, values in daily.items()
    }
    common_cutoff = min(latest_by_region.values())
    history_years = list(range(2015, 2025))
    history, history_coverage, history_ids, history_status = {}, {}, {}, {}
    for year in history_years:
        history[str(year)], history_coverage[str(year)], history_ids[str(year)], history_status[str(year)] = _production_year_trace(year, daily, weights, common_cutoff)
    last_year, last_coverage, last_ids, last_status = _production_year_trace(2025, daily, weights, common_cutoff)
    current_year, current_coverage, current_ids, current_status = _production_year_trace(2026, daily, weights, common_cutoff, current=True)
    history_min = [min((history[str(year)][idx] for year in history_years if history[str(year)][idx] is not None), default=None) for idx in range(len(PRODUCTION_WEIGHTED_KEYS))]
    history_max = [max((history[str(year)][idx] for year in history_years if history[str(year)][idx] is not None), default=None) for idx in range(len(PRODUCTION_WEIGHTED_KEYS))]
    coverage_values = [value for series in list(history_coverage.values()) + [last_coverage, current_coverage] for value in series if value is not None]
    status_counts = {
        "history": {status: sum(day_status.count(status) for day_status in history_status.values()) for status in ("available", "coverage_below_gate", "future")},
        "last_year": {status: last_status.count(status) for status in ("available", "coverage_below_gate", "future")},
        "current_year": {status: current_status.count(status) for status in ("available", "coverage_below_gate", "future")},
    }
    current_scores = {}
    for geo in PRODUCTION_WEIGHTED_REGIONS:
        current_scores[PRODUCTION_WEIGHTED_REGION_IDS[geo]] = daily[PRODUCTION_WEIGHTED_REGION_IDS[geo]].get(common_cutoff)
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
        "cross_year_axis": False, "common_cutoff_date": common_cutoff.isoformat(),
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
        "weights": weight_rows, "common_cutoff_date": common_cutoff.isoformat(),
        "latest_available_date_by_region": {region_id: day.isoformat() for region_id, day in latest_by_region.items()},
        "current_region_scores": current_scores, "current_score": current_result["value"],
        "weighted_production_coverage": current_result["production_weight_coverage"], "valid_region_ids": current_result["valid_region_ids"],
        "current_status": current_result["status"], "seasonal_metric": metric,
        "weather_input_paths": {
            geo: str((NATIONAL_DAILY_PATHS[geo] if geo in NATIONAL_DAILY_PATHS else DAILY_PATHS[geo]).relative_to(COTTON_ROOT))
            for geo in PRODUCTION_WEIGHTED_REGIONS
        },
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
    central_watch_payload = read_json(CENTRAL_ASIA_WATCH_PATH)
    subregion_seasonal = build_subregion_seasonal(regions)
    return {
        "dashboard_id": "cotton_public_supply_weather_dashboard_v0_7",
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
        "subregion_seasonal": subregion_seasonal,
        "central_asia_watch": {
            "as_of_weather_date": central_watch_payload["as_of_weather_date"],
            "source_model": central_watch_payload.get("historical_source_model", central_watch_payload.get("source_model", "era5")),
            "observed_reanalysis_only": central_watch_payload.get("observed_reanalysis_only", False),
            "forecast_included": central_watch_payload.get("forecast_included", True),
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
    # The dashboard payload contains hundreds of local seasonal traces. Keep
    # the public transfer compact; tests and browsers parse the same JSON.
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
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
