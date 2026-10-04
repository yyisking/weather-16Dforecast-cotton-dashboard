#!/usr/bin/env python3
"""Independent source-to-payload checks for the public dashboard extension."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta
import math
from pathlib import Path

import build_public_dashboard as builder

ROOT = Path(__file__).resolve().parent
COTTON = ROOT.parent
CENTRAL_AOI = (
    ("Kazakhstan", "Turkistan Region", "kazakhstan_turkistan"),
    ("Kyrgyzstan", "Jalal-Abad Oblast", "kyrgyzstan_jalal_abad"),
    ("Kyrgyzstan", "Osh Oblast", "kyrgyzstan_osh"),
    ("Tajikistan", "Khatlon Oblast", "tajikistan_khatlon"),
    ("Tajikistan", "Sughd Oblast", "tajikistan_sughd"),
    ("Turkmenistan", "Mary Velayat", "turkmenistan_mary"),
    ("Turkmenistan", "Dashoguz Velayat", "turkmenistan_dashoguz"),
    ("Uzbekistan", "Fergana Region", "uzbekistan_fergana"),
    ("Uzbekistan", "Syrdarya Region", "uzbekistan_syrdarya"),
    ("Uzbekistan", "Bukhara Region", "uzbekistan_bukhara"),
)
VARIABLES = (
    "temperature_2m_max", "temperature_2m_min", "precipitation_sum",
    "shortwave_radiation_sum", "et0_fao_evapotranspiration", "vapour_pressure_deficit_max",
)
COUNTRIES_DISPLAY = {
    "Kazakhstan": "哈萨克斯坦", "Kyrgyzstan": "吉尔吉斯斯坦", "Tajikistan": "塔吉克斯坦",
    "Turkmenistan": "土库曼斯坦", "Uzbekistan": "乌兹别克斯坦",
}
AOI_DISPLAY = {
    "Turkistan Region": "突厥斯坦州", "Jalal-Abad Oblast": "贾拉拉巴德州", "Osh Oblast": "奥什州",
    "Khatlon Oblast": "哈特隆州", "Sughd Oblast": "索格特州", "Mary Velayat": "马雷州",
    "Dashoguz Velayat": "达沙古兹州", "Fergana Region": "费尔干纳州", "Syrdarya Region": "锡尔河州",
    "Bukhara Region": "布哈拉州",
}
FROZEN_INPUT_SHAS = {
    COTTON / "research/raw/australia_central_asia_era5_daily_v0_1/source_manifest_v0_1.json": "1e74722ab611a8d980ce5d2d68f022f1b1f97c5119f461515b9b25e799906353",
    COTTON / "research/derived/australia_central_asia_cotton_point_crosswalk_v0_1.csv": "bf20f1fb7c4997853abdee508beb2987c4bf5945e1abdb8fc4f4992ef9e56faa",
    COTTON / "research/raw/australia_central_asia_era5_daily_v0_1/01_moree_era5_daily.json": "a10af801c90b7bdf6000dc0efa485805fcefd96ec2ed32c612f19b90ebfe9ad6",
    COTTON / "research/raw/australia_central_asia_era5_daily_v0_1/02_narrabri_era5_daily.json": "1f43308d9850a0a5ac55b18c48fd38b14fb6481e90d97c38c06e322b99243fc6",
    COTTON / "research/raw/australia_central_asia_era5_daily_v0_1/03_narromine_era5_daily.json": "f6de3ea88524897d5caa7f97a6805b59b6b51410903f4b5d659e7573811fb645",
    COTTON / "research/raw/australia_central_asia_era5_daily_v0_1/04_griffith_era5_daily.json": "f8b4d64841bc6adbbe4052e1add0da3021af572f62cd9ab402043134b8cd3f60",
    COTTON / "research/raw/australia_central_asia_era5_daily_v0_1/05_dalby_era5_daily.json": "bfea03ca211fedb3efe591fb13767049e6bcd64bb6dcd196982f90c890fa2482",
    COTTON / "research/raw/australia_central_asia_era5_daily_v0_1/07_goondiwindi_era5_daily.json": "4fb4f07fa04a153799f1ed948d59c9631125d8c153a2cade4ceff4fa59cf2611",
    COTTON / "research/raw/australia_central_asia_era5_daily_v0_1/08_emerald_era5_daily.json": "69a0b66c165dcbb0aaaed8652627a1f2f9e7151f12c1ce64cc08e7c409e833cb",
    COTTON / "research/derived/central_asia_cotton_current_weather_watch_v0_1.json": "477d7ff77b30def52694c3ade2ae6a8a46054ae0a7ecf4e2780195f28f419b71",
    COTTON / "research/derived/central_asia_cotton_current_weather_watch_v0_1.csv": "bfc128f330ceaf8349b27c30d18c3316aa0d573f82b6dd3336ed7b3184aef18a",
    COTTON / "research/derived/australia_central_asia_cotton_variable_watch_v0_2.csv": "04af922caca2617bec9ed389411a5a2904883733e4d3bb8ac13275e9883d25fd",
    COTTON / "research/derived/australia_central_asia_cotton_era5_daily_seasonality_v0_2.csv": "9ce46a2ab31981ccd8952fd328f5bfd230314857a84ede7a2f38f0bfc30be949",
    COTTON / "cn_xj_weather/derived/xinjiang_theoretical_weather_stress_index_v0_1_daily.csv": "3fe931e9de5e195835d7f211aefd8d52a5d95d68dad3713df6c0f646e94d561a",
    COTTON / "cn_xj_weather/derived/xinjiang_theoretical_weather_stress_index_v0_2_daily.csv": "ba7b6e2cf02fab2ee40e833d879cb4c15b2975b94aa7ec1cf5adad03023492da",
    # Re-frozen after the 2026-10-04 local-pipeline rehearsal exposed that
    # rerunning this retired predecessor no longer reproduced its historical
    # bytes. It is not a dashboard consumer and is excluded from daily builds.
    COTTON / "us_weather/derived/us_tx_theoretical_weather_stress_index_v0_2_daily.csv": "69ffe24cf0cbfaca23a2c49a92e9bb4de38215845ddd723aa25e2793cdb617eb",
    COTTON / "br_weather/derived/brazil_mt_theoretical_weather_stress_index_v0_2_daily.csv": "43cf7af726872dd3bffb877099d17f89ea51926caeb3dedf84fac47d3b5b9b9e",
    COTTON / "in_weather/derived/india_central_rainfed_theoretical_weather_stress_index_v0_1_daily.csv": "a7f852a54b1d94987c1a639a6aa5970683b2d62ca5892189732d07450dbc66e8",
    COTTON / "us_weather/derived/us_tx_theoretical_weather_stress_index_v0_2_refresh_2026_09_29_daily.csv": "c84748221e5719e831fb652a26e219a60225be4bd58eee585b69e90aa276f065",
    COTTON / "br_weather/derived/brazil_mt_theoretical_weather_stress_index_v0_2_refresh_2026_09_29_daily.csv": "e8500c236e69eb1e1005fa1478b65d95d905b106544cd4e976dfc7ad6d1a582d",
    COTTON / "in_weather/derived/india_central_rainfed_theoretical_weather_stress_index_v0_1_refresh_2026_09_29_daily.csv": "f7b56102ea878ad3572747c7bf5e56e07020d61e12cf8a42e4ffd76e07c506c4",
    COTTON / "au_weather/derived/australia_theoretical_weather_stress_index_v0_2_daily.csv": "693561f5558b240b2409cfd5e9f1b2cd0a12e5facfb50184da593ba27091cf25",
    COTTON / "research/raw/australia_st_george_era5_daily_v0_1/st_george_era5_daily.json": "6d249f9f5ae2fe390f3b0b183eabaf967f9dd6d32eba520f4d3e6220fc0a43f2",
    COTTON / "research/raw/australia_st_george_era5_daily_v0_1/source_manifest_v0_1.json": "0658498ca3e6ab473436228b705e49375a37401cc7baf2a3665d05ff9226551c",
    COTTON / "us_weather/derived/us_national_theoretical_weather_stress_index_v0_1_daily.csv": "acaefa10e8e87c97c11fd7ea005a4e26113fb32064d848954b8b516a677b6f5a",
    COTTON / "br_weather/derived/brazil_national_theoretical_weather_stress_index_v0_1_daily.csv": "0f5489fc0c48cba334556e17077cf4807a6e7d9304608cf606e3b2a25e32359d",
    COTTON / "in_weather/derived/india_national_theoretical_weather_stress_index_v0_1_daily.csv": "7d6002f4d0f07862b5169d25387febbe39df9219502c52fcf2fc68d774303ee4",
    COTTON / "au_weather/derived/australia_national_theoretical_weather_stress_index_v0_3_daily.csv": "1d3487ccaa13b041e82bec2a1a0e1c136c4e240c12b21da6cba0cec77e394beb",
    COTTON / "model_status.json": "b3fbabe71bd15c1bc0ef65d2b4e34f3621a184383c3f89d8a9320a896a2daf0d",
}
FROZEN_RAW_POINT_SEMANTIC_SHAS = {
    "China": "ecca890e61fc60e9542aa642f67e5fc5d99e440a74c835de14826f4ccf9ff814",
    "United States": "efa3f8830286e7b07767c811b500405f1295b9456922205e36407e3ac7775968",
    "Brazil": "afca7f119c6b1f8902ef64976d7523f7fb27d38e87b844f76ea7e8140120a739",
    "India": "24f8e724ab67d0d9c23cad6ac864e7d9abb346d02ec9482b4b4439b29a654437",
}
RAW_POINT_HASH_FIELDS = ("date", "tmax", "tmin", "precip", "sw_rad")
KEYS = []
cursor = date(2001, 1, 1)
while cursor.year == 2001:
    if cursor.month != 2 or cursor.day != 29:
        KEYS.append(cursor.strftime("%m-%d"))
    cursor = date.fromordinal(cursor.toordinal() + 1)


def window_keys(start: str, end: str) -> list[str]:
    start_i = KEYS.index(start)
    end_i = KEYS.index(end)
    return KEYS[start_i:end_i + 1] if end_i >= start_i else KEYS[start_i:] + KEYS[:end_i + 1]


def digest(path: Path) -> str:
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    h = hashlib.sha256()
    for child in sorted(
        p
        for p in path.rglob("*")
        if p.is_file()
        and "__pycache__" not in p.parts
        and p.suffix not in {".pyc", ".pyo"}
    ):
        h.update(child.relative_to(path).as_posix().encode() + b"\0" + child.read_bytes() + b"\0")
    return h.hexdigest()


def raw_point_semantic_hash(config: dict, source_rows: list[dict[str, str]]) -> str:
    """Hash exactly the point/day/weather semantics consumed by raw seasonality.

    The contract uses configured point IDs and date/tmax/tmin/precip/sw_rad only.
    It covers historical season years, the prior year, and current-year displayed
    dates through the frozen cutoff, including each exposure's preceding 13 days.
    Rows are canonicalized by point/date; absent or unusable values encode as
    the explicit token <NULL>. Rows after the cutoff are outside this hash.
    """
    start, end = config["window"][:2]
    display_keys = builder._window_keys(start, end)
    display_dates = set()
    for year in (*config["history_years"], 2025, 2026):
        for key in display_keys:
            month, day = (int(part) for part in key.split("-"))
            actual = date(year, month, day)
            if year == 2026 and actual > config["cutoff"]:
                continue
            display_dates.add(actual)
    required_dates = {
        displayed_day - timedelta(days=offset)
        for displayed_day in display_dates
        for offset in range(14)
    }
    if not required_dates or max(required_dates) > config["cutoff"]:
        raise AssertionError("raw semantic hash range exceeds the frozen display cutoff")

    points = tuple(sorted(config["points"]))
    dates = tuple(sorted(required_dates))
    records: dict[str, dict[date, dict[str, float | None]]] = {point: {} for point in points}
    point_set = set(points)
    for row in source_rows:
        point = row.get("point_id")
        if point not in point_set:
            continue
        try:
            parsed = date.fromisoformat((row.get("date") or "")[:10])
        except ValueError:
            continue
        if parsed not in required_dates:
            continue
        records[point][parsed] = {field: builder._number(row.get(field)) for field in RAW_POINT_HASH_FIELDS[1:]}

    contract = {
        "contract": "cotton-public-dashboard-raw-points-v1",
        "points": points,
        "fields": RAW_POINT_HASH_FIELDS,
        "required_dates": tuple(day.isoformat() for day in dates),
    }
    hasher = hashlib.sha256()
    hasher.update((json.dumps(contract, ensure_ascii=True, separators=(",", ":")) + "\n").encode("ascii"))
    for point in points:
        for day in dates:
            row = records[point].get(day, {})
            tokens = []
            for field in RAW_POINT_HASH_FIELDS[1:]:
                value = row.get(field)
                tokens.append("<NULL>" if value is None else float(value).hex())
            canonical = (point, day.isoformat(), *tokens)
            hasher.update((json.dumps(canonical, ensure_ascii=True, separators=(",", ":")) + "\n").encode("ascii"))
    return hasher.hexdigest()


def protected_paths() -> tuple[Path, ...]:
    candidates = [
        COTTON / "au_weather",
        COTTON / "research/derived/australia_central_asia_cotton_variable_watch_v0_2.csv",
        COTTON / "research/derived/australia_central_asia_cotton_era5_daily_seasonality_v0_2.csv",
        COTTON / "research/derived/central_asia_cotton_current_weather_watch_v0_1.json",
        COTTON / "research/derived/usda_fas_cotton_supply_distribution_2025_26_2026_27_v0_2.csv",
        COTTON / "research/derived/cotton_supply_balance_weather_overlay_v0_2.csv",
        COTTON / "research/derived/cotton_supply_balance_weather_overlay_v0_2.json",
        COTTON / "research/derived/cotton_current_supply_decision_brief_v0_2.json",
        COTTON / "research/raw/australia_central_asia_era5_daily_v0_1",
        COTTON / "research/raw/central_asia_era5_gap_retry_v0_1",
        COTTON / "research/derived/australia_central_asia_cotton_point_crosswalk_v0_1.csv",
        COTTON / "research/derived/australia_central_asia_cotton_era5_daily_seasonality_v0_1.csv",
        COTTON / "research/derived/australia_central_asia_cotton_variable_watch_v0_1.csv",
        ROOT / "cotton-dashboard-site.tgz",
    ]
    candidates.extend((COTTON / "research/derived").glob("cotton_regional_weather_stress_summary_v0_1.*"))
    candidates.extend((COTTON / "research/derived").glob("cotton_current_supply_decision_brief_v0_1.*"))
    candidates.extend((COTTON / "research/derived").glob("cotton_supply_balance_weather_overlay_v0_1.*"))
    return tuple(p for p in candidates if p.exists())


class PublicDashboardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protected = protected_paths()
        cls.protected_before = {str(p): digest(p) for p in cls.protected}
        cls.payload = builder.build()
        cls.brief = json.loads(builder.BRIEF_PATH.read_text(encoding="utf-8"))
        cls.au_latest = json.loads(builder.AUSTRALIA_LATEST_PATH.read_text(encoding="utf-8"))
        cls.central_watch = json.loads(builder.CENTRAL_ASIA_WATCH_PATH.read_text(encoding="utf-8"))
        with builder.CENTRAL_ASIA_SEASONAL_PATH.open(encoding="utf-8", newline="") as handle:
            cls.central_seasonal_rows = list(csv.DictReader(handle))

    @classmethod
    def tearDownClass(cls):
        after = {str(p): digest(p) for p in cls.protected}
        if after != cls.protected_before:
            raise AssertionError("input or prohibited asset changed during dashboard tests")

    def test_supply_rows_are_exact_source_values(self):
        source = {row["geography"]: row for row in self.brief["rows"]}
        self.assertEqual([row["geography"] for row in self.brief["rows"]], ["World", "China", "United States", "Brazil", "India", "Australia"])
        self.assertEqual(len(self.payload["supply"]), 6)
        self.assertEqual([row["geography"] for row in self.payload["supply"]], list(source))
        for row in self.payload["supply"]:
            raw = source[row["geography"]]
            self.assertEqual(row["production"], raw["current_production_1000_480lb_bales"])
            self.assertEqual(row["ending_stocks"], raw["current_ending_stocks_1000_480lb_bales"])
            self.assertEqual(row["stocks_to_use"], raw["current_ending_stocks_to_total_use_pct"])

    def test_five_regions_and_australia_latest_source_copy(self):
        self.assertEqual(len(self.payload["regions"]), 5)
        self.assertEqual([r["id"] for r in self.payload["regions"]], ["china", "us", "brazil", "india", "australia"])
        australia = self.payload["regions"][-1]
        self.assertEqual(australia["score"], self.au_latest["theoretical_weather_stress_index"])
        self.assertEqual(australia["change_7d"], self.au_latest["change_7d"])
        self.assertEqual(australia["change_yoy"], self.au_latest["change_yoy"])
        self.assertEqual(australia["point_coverage"], self.au_latest["point_coverage"])
        self.assertEqual(australia["confidence"], self.au_latest["confidence"])
        self.assertEqual(australia["gap_codes"], self.au_latest["gap_codes"])
        self.assertEqual(australia["point_coverage"], 1.0)
        self.assertEqual(australia["target_point_count"], 8)
        self.assertEqual(australia["valid_point_count"], 8)
        supply = next(row for row in self.brief["rows"] if row["geography"] == "Australia")
        official = australia["official_supply"]
        self.assertEqual(official["production_change_1000_480lb_bales"], supply["production_change_1000_480lb_bales"])
        self.assertEqual(official["production_change_pct"], supply["production_change_pct"])
        self.assertEqual(official["ending_stocks_change_1000_480lb_bales"], supply["ending_stocks_change_1000_480lb_bales"])
        self.assertEqual(official["ending_stocks_change_pct"], supply["ending_stocks_change_pct"])
        self.assertIsNone(official["domestic_use_change_pct"])
        self.assertEqual(australia["supply_detail"], "USDA 官方棉花产量变化 -1,500 千包（-33.33%）；期末库存变化 -1,400 千包（-36.21%）")
        self.assertIn("USDA 官方棉花产量变化", australia["supply_risk_reading"])
        factors = {factor["id"]: factor for factor in australia["factors"]}
        self.assertEqual(set(factors), {"low_temperature", "high_heat", "excess_rain", "high_vpd", "low_solar"})
        self.assertEqual(factors["high_heat"]["score"], self.au_latest["high_heat_score"])
        self.assertEqual(factors["high_heat"]["status"], "available")
        self.assertEqual(factors["low_temperature"]["score"], self.au_latest["low_temperature_score"])
        self.assertEqual(factors["low_solar"]["score"], self.au_latest["low_solar_score"])

    def test_existing_region_scores_and_null_factors_are_preserved(self):
        for region in self.payload["regions"][:4]:
            path = builder.NATIONAL_LATEST_PATHS.get(region["geography"], builder.REGION_PATHS[region["geography"]])
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(region["score"], raw["theoretical_weather_stress_index"])
            self.assertEqual(region["source_path"], str(path.relative_to(COTTON)))
        brazil = next(region for region in self.payload["regions"] if region["id"] == "brazil")
        unavailable = [factor for factor in brazil["factors"] if factor["score"] is None]
        self.assertGreaterEqual(len(unavailable), 1)
        self.assertTrue(all(factor["status"] == "not_available_or_inactive" for factor in unavailable))

    def test_v13_national_network_sources_coverage_and_china_proxy_are_explicit(self):
        regions = {region["geography"]: region for region in self.payload["regions"]}
        expected = {
            "United States": ("us_weather/derived/us_national_theoretical_weather_stress_index_v0_1_latest.json", 34, 16, 0.991744),
            "Brazil": ("br_weather/derived/brazil_national_theoretical_weather_stress_index_v0_1_latest.json", 30, 11, 0.9964990451941439),
            "India": ("in_weather/derived/india_national_theoretical_weather_stress_index_v0_1_latest.json", 26, 10, 0.9636608344549125),
            "Australia": ("au_weather/derived/australia_national_theoretical_weather_stress_index_v0_4_latest.json", 8, 8, 0.92252511),
        }
        for geography, (source_path, target, detail_count, production_coverage) in expected.items():
            region = regions[geography]
            source = json.loads((COTTON / source_path).read_text(encoding="utf-8"))
            self.assertEqual(region["source_path"], source_path)
            expected_valid = source.get("valid_point_count", source.get("valid_aoi_count"))
            self.assertEqual(region["valid_point_count"], expected_valid)
            self.assertEqual(region["target_point_count"], target)
            self.assertEqual(len(region["network_details"]), detail_count)
            self.assertAlmostEqual(region["official_production_weight_coverage"], production_coverage, places=9)
            self.assertAlmostEqual(
                math.fsum(row.get("production_weight_share") or 0.0 for row in region["network_details"]),
                1.0,
                places=8,
            )
            self.assertTrue(region["theoretical_not_calibrated"])

        china = regions["China"]
        self.assertEqual(china["name"], "中国·新疆")
        self.assertEqual([row["id"] for row in china["network_details"]], [
            "aksu", "north_shihezi_changji", "kashgar", "bayingol", "north_bozhou", "north_kuitun", "turpan",
        ])
        self.assertEqual(sum(row["target_point_count"] for row in china["network_details"]), 18)
        self.assertIsNone(china["official_production_weight_coverage"])
        self.assertAlmostEqual(math.fsum(row["production_weight_share"] for row in china["network_details"]), 1.0, places=12)
        self.assertTrue(all(row["weight_type"] == "official_cotton_area_proxy" for row in china["network_details"]))

        australia = regions["Australia"]
        self.assertEqual(australia["raw_network_name"], "澳洲8 AOI 原始天气网络")
        self.assertIn("含 St George", australia["raw_network_note"])
        self.assertNotIn("旧7点", australia["raw_network_note"])

        expected_daily = {
            "China": "cn_xj_weather/derived/xinjiang_theoretical_weather_stress_index_v0_2_daily.csv",
            "United States": "us_weather/derived/us_national_theoretical_weather_stress_index_v0_1_daily.csv",
            "Brazil": "br_weather/derived/brazil_national_theoretical_weather_stress_index_v0_1_daily.csv",
            "India": "in_weather/derived/india_national_theoretical_weather_stress_index_v0_1_daily.csv",
            "Australia": "au_weather/derived/australia_national_theoretical_weather_stress_index_v0_4_daily.csv",
        }
        composite = self.payload["five_region_production_weighted_weather_stress_display"]
        self.assertEqual(composite["weather_input_paths"], expected_daily)
        self.assertEqual(composite["common_cutoff_date"], min(composite["latest_available_date_by_region"].values()))
        self.assertTrue(composite["not_calibrated"])
        self.assertTrue(composite["not_unified_model"])

    def test_v15_subregion_drilldown_uses_local_raw_values_and_honest_factor_snapshot_gates(self):
        regions = {region["id"]: region for region in self.payload["regions"]}
        self.assertEqual({key: len(regions[key]["network_details"]) for key in regions}, {
            "china": 7, "us": 16, "brazil": 11, "india": 10, "australia": 8,
        })
        for region in regions.values():
            for row in region["network_details"]:
                self.assertIn("id", row)
                self.assertIn("raw_weather", row)
                self.assertIn("factor_scores", row)
                self.assertIn("factor_detail_status", row)
                self.assertIn("factor_detail_note", row)
                raw = row["raw_weather"]
                self.assertEqual(set(raw["values"]) & {
                    "tmax_14d_mean", "tmin_14d_mean", "precip_14d_sum", "sw_rad_14d_mean",
                }, {"tmax_14d_mean", "tmin_14d_mean", "precip_14d_sum", "sw_rad_14d_mean"})
                self.assertGreaterEqual(raw["coverage"], 0.0)
                self.assertLessEqual(raw["coverage"], 1.0)

        mismatch_ids = {
            (region["id"], row["id"])
            for region in regions.values()
            for row in region["network_details"]
            if row.get("factor_detail_status") == "source_revision_mismatch"
        }
        # A source-revision mismatch is a fail-closed transient state.  Once the
        # daily builders and raw files share a cutoff, the set may legitimately
        # be empty; any remaining mismatch must still null every factor.
        texas = next(item for item in regions["us"]["network_details"] if item["id"] == "TX")
        self.assertEqual(texas["name"], "德州（TX）")
        self.assertNotIn("得州", json.dumps(self.payload, ensure_ascii=False))
        self.assertNotIn("得州", (ROOT / "index.html").read_text(encoding="utf-8"))
        for region_id, row_id in mismatch_ids:
            row = next(item for item in regions[region_id]["network_details"] if item["id"] == row_id)
            self.assertTrue(row["factor_scores"])
            self.assertTrue(all(value is None for value in row["factor_scores"].values()))
            self.assertIn("不一致", row["factor_detail_note"])

        china_details = {row["id"]: row for row in regions["china"]["network_details"]}
        north = [china_details[key] for key in ("north_shihezi_changji", "north_kuitun", "north_bozhou")]
        self.assertEqual([row["name"] for row in north], ["北疆·石河子—昌吉代理区", "北疆·奎屯代理区", "北疆·博州代理区"])
        self.assertEqual(north[0]["point_names"], ["石河子", "沙湾", "昌吉", "呼图壁"])
        self.assertEqual(north[1]["point_names"], ["奎屯"])
        self.assertEqual(north[2]["point_names"], ["博乐", "精河"])
        self.assertEqual(sum(row["raw_weather"]["target_point_count"] for row in north), 7)
        self.assertTrue(all("high_heat" in row["factor_scores"] for row in north))

    def test_xinjiang_v02_three_phase_temperature_scores_are_independently_rebuilt(self):
        points = tuple(builder.RAW_POINT_CONFIG["China"]["points"])
        north = {"xj_shihezi", "xj_shawan", "xj_kuitun", "xj_changji", "xj_hutubi", "xj_bole", "xj_jinghe"}
        weights = {
            "north": {
                4: (2.5, .5, 1.0, 1.5), 5: (2.0, .5, 1.0, 1.0), 6: (.5, 1.5, .5, 0), 7: (.5, 2.5, .5, 0),
                8: (.5, 2.0, .5, 0), 9: (2.0, .5, 1.5, 0), 10: (2.5, .5, 2.0, 0), 11: (2.0, .5, 2.0, 0),
            },
            "other": {
                4: (2.0, .5, 1.0, 1.5), 5: (1.5, .5, 1.0, 1.0), 6: (.5, 2.0, .5, 0), 7: (.5, 2.5, .5, 0),
                8: (.5, 1.5, .5, 0), 9: (1.5, .5, 1.5, 0), 10: (2.0, .5, 2.0, 0), 11: (1.5, .5, 2.0, 0),
            },
        }
        records = {point: {} for point in points}
        with (COTTON / "cn_xj_weather/points_daily.csv").open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                point = row.get("point_id")
                if point in records:
                    records[point][date.fromisoformat(row["date"])] = {
                        field: (None if row.get(field, "") == "" else float(row[field]))
                        for field in ("tmax", "tmin", "precip", "gust_max")
                    }

        def exposure(point, day, field, mode):
            values = []
            for offset in range(13, -1, -1):
                row = records[point].get(day - timedelta(days=offset))
                value = None if row is None else row[field]
                if value is None:
                    return None
                values.append(value)
            if mode == "mean":
                return math.fsum(values) / 14
            if mode == "sum":
                return math.fsum(values)
            return max(values)

        def tail_score(value, references, direction):
            valid = [reference for reference in references if reference is not None]
            self.assertGreaterEqual(len(valid), 10)
            less = sum(reference < value for reference in valid)
            equal = sum(reference == value for reference in valid)
            percentile = (less + .5 * equal) / len(valid)
            return 200 * max(0, percentile - .5) if direction == "high" else 200 * max(0, .5 - percentile)

        output_rows = {}
        with builder.DAILY_PATHS["China"].open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["date"] in {"2026-04-15", "2026-07-15", "2026-09-13"}:
                    output_rows[row["date"]] = row
        factor_specs = (
            ("low_temperature", "tmin", "mean", "low"),
            ("high_heat", "tmax", "mean", "high"),
            ("excess_rain", "precip", "sum", "high"),
            ("spring_wind", "gust_max", "max", "high"),
        )
        for target in (date(2026, 4, 15), date(2026, 7, 15), date(2026, 9, 13)):
            point_scores = {}
            for point in points:
                point_scores[point] = []
                for _factor, field, mode, direction in factor_specs:
                    value = exposure(point, target, field, mode)
                    references = [exposure(point, date(year, target.month, target.day), field, mode) for year in range(2005, target.year)]
                    point_scores[point].append(tail_score(value, references, direction))
            component_scores = []
            for point in points:
                group = "north" if point in north else "other"
                month_weights = weights[group][target.month]
                component_scores.append(math.fsum(weight * score for weight, score in zip(month_weights, point_scores[point])) / math.fsum(month_weights))
            expected_total = math.fsum(component_scores) / len(component_scores)
            row = output_rows[target.isoformat()]
            self.assertAlmostEqual(float(row["theoretical_weather_stress_index"]), expected_total, places=9)
            for index, (factor, _field, _mode, _direction) in enumerate(factor_specs[:2]):
                expected_factor = math.fsum(point_scores[point][index] for point in points) / len(points)
                self.assertAlmostEqual(float(row[f"{factor}_score"]), expected_factor, places=9)
                self.assertNotEqual(row[f"{factor}_score"], "")
            self.assertEqual(float(row["factor_weight_coverage"]), 1.0)

        china = self.payload["seasonal"]["china"]["metrics"]
        for factor in ("low_temperature", "high_heat"):
            metric = china[factor]
            self.assertEqual(metric["display_role"], "continuous_three_phase_temperature_factor_score")
            self.assertEqual(metric["secondary_weight"], .5)
            self.assertEqual(metric["active_periods"], [{"start": "04-01", "end": "11-30"}])
            self.assertNotIn("inactive_stage", metric["current_year_status"])
            self.assertTrue(all(value is not None for value in metric["history_min"]))

    def test_australia_seasonal_rebuilds_real_factor_history_and_daily_values(self):
        seasonal = self.payload["seasonal"]["australia"]
        self.assertEqual(seasonal["current_year"], "2026/27")
        self.assertEqual(seasonal["last_year"], "2025/26")
        self.assertEqual(seasonal["display_window_start"], "09-01")
        self.assertEqual(seasonal["display_window_end"], "06-30")
        self.assertTrue(seasonal["cross_year_axis"])
        score = seasonal["metrics"]["score"]
        self.assertEqual(score["history_year_count"], 0)
        self.assertTrue(all(value is None for value in score["history_min"]))
        self.assertTrue(all(value is None for value in score["history_max"]))
        for metric_id in ("low_temperature", "high_heat", "excess_rain", "high_vpd", "low_solar"):
            metric = seasonal["metrics"][metric_id]
            self.assertEqual(metric["history_year_count"], 34)
            self.assertEqual(metric["history_years"], list(range(1991, 2025)))
            self.assertEqual(len(metric["day_keys"]), 303)
            self.assertTrue(any(value is not None for value in metric["history_min"]))
            self.assertTrue(any(value is not None for value in metric["history_max"]))
            self.assertIn("回顾性描述，非PIT，未校准", metric["historical_band_note"])
        with builder.AUSTRALIA_DAILY_PATH.open(encoding="utf-8", newline="") as handle:
            daily = list(csv.DictReader(handle))
        expected = {row["date"]: row["theoretical_weather_stress_index"] for row in daily}
        index = score["day_keys"].index("09-10")
        self.assertEqual(score["current_year"][index], float(expected["2026-09-10"]))
        self.assertEqual(score["last_year"][index], float(expected["2025-09-10"]))
        self.assertEqual(score["last_year"][score["day_keys"].index("01-01")], float(expected["2026-01-01"]))
        latest_key = self.au_latest["date"][5:]
        self.assertEqual(score["current_year"][score["day_keys"].index(latest_key)], float(expected[self.au_latest["date"]]))
        self.assertIsNone(score["last_year"][score["day_keys"].index("05-01")])

        # Reconstruct one day per factor independently from all eight raw ERA5
        # responses and the V0.3 AOI production allocations.
        manifest = json.loads(builder.AUSTRALIA_MANIFEST_PATH.read_text(encoding="utf-8"))
        raw_points = []
        for source in manifest["raw_responses"]:
            if source.get("country") != "Australia" or source.get("status") != "complete_response":
                continue
            raw = json.loads((COTTON.parent / source["raw_response_path"]).read_text(encoding="utf-8"))
            daily = raw["daily"]
            point = {}
            for index, day in enumerate(daily["time"]):
                point[date.fromisoformat(day)] = {
                    "tmin": daily["temperature_2m_min"][index],
                    "tmax": daily["temperature_2m_max"][index],
                    "precip": daily["precipitation_sum"][index],
                    "vpd": daily["vapour_pressure_deficit_max"][index],
                    "solar": daily["shortwave_radiation_sum"][index],
                }
            raw_points.append(point)
        st_manifest = json.loads(builder.AUSTRALIA_ST_GEORGE_MANIFEST_PATH.read_text(encoding="utf-8"))
        st_raw = json.loads((COTTON.parent / st_manifest["raw_response_path"]).read_text(encoding="utf-8"))
        daily = st_raw["daily"]
        raw_points.append({date.fromisoformat(day): {
            "tmin": daily["temperature_2m_min"][index], "tmax": daily["temperature_2m_max"][index],
            "precip": daily["precipitation_sum"][index], "vpd": daily["vapour_pressure_deficit_max"][index],
            "solar": daily["shortwave_radiation_sum"][index],
        } for index, day in enumerate(daily["time"])})
        self.assertEqual(len(raw_points), 8)
        point_names = list(builder.AUSTRALIA_FILE_AOI.values())
        latest = json.loads(builder.AUSTRALIA_LATEST_PATH.read_text(encoding="utf-8"))
        weight_by_name = {row["aoi_name"]: row["valid_weight_kt"] for row in latest["aoi_components"]}
        total_weight = math.fsum(weight_by_name.values())
        weights = [weight_by_name[name] / total_weight for name in point_names]

        def independent_exposure(point, day, source, mode):
            vals = [point.get(day - timedelta(days=offset), {}).get(source) for offset in range(13, -1, -1)]
            if any(value is None for value in vals):
                return None
            return math.fsum(vals) if mode == "sum" else math.fsum(vals) / 14.0

        samples = {
            "low_temperature": ("tmin", "mean", "low", "09-15"),
            "high_heat": ("tmax", "mean", "high", "01-15"),
            "excess_rain": ("precip", "sum", "high", "04-15"),
            "high_vpd": ("vpd", "mean", "high", "12-15"),
            "low_solar": ("solar", "sum", "low", "02-15"),
        }
        for metric_id, (source, mode, tail, key) in samples.items():
            month, daynum = (int(part) for part in key.split("-"))
            season_scores = []
            for season_start in range(1991, 2025):
                target_year = season_start if month >= 9 else season_start + 1
                target = date(target_year, month, daynum)
                point_scores = []
                for point_index, point in enumerate(raw_points):
                    value = independent_exposure(point, target, source, mode)
                    if value is None:
                        continue
                    reference = []
                    for year in range(1991, 2025):
                        ref_day = date(year, month, daynum)
                        ref_value = independent_exposure(point, ref_day, source, mode)
                        if ref_value is not None:
                            reference.append(ref_value)
                    if len(reference) < 20:
                        continue
                    percentile = (sum(v < value for v in reference) + 0.5 * sum(v == value for v in reference)) / len(reference)
                    score = min(100.0, max(0.0, 200.0 * max(0.0, percentile - 0.5) if tail == "high" else 200.0 * max(0.0, 0.5 - percentile)))
                    point_scores.append((weights[point_index], score))
                valid_weight = math.fsum(weight for weight, _score in point_scores)
                if valid_weight >= 0.60:
                    season_scores.append(round(math.fsum(weight * score for weight, score in point_scores) / valid_weight, 2))
            metric = seasonal["metrics"][metric_id]
            index = metric["day_keys"].index(key)
            self.assertEqual(metric["history_min"][index], min(season_scores), metric_id)
            self.assertEqual(metric["history_max"][index], max(season_scores), metric_id)
            self.assertEqual(len(season_scores), 34, metric_id)

    def test_central_asia_10_aois_240_fields_and_null_scores(self):
        watch = self.payload["central_asia_watch"]
        self.assertEqual(watch["aoi_count"], 10)
        self.assertEqual(watch["score_available_count"], 0)
        self.assertEqual(watch["weather_anomaly_score_available_count"], 10)
        self.assertEqual(watch["weather_stress_score_available_count"], 0)
        self.assertEqual(len(watch["aois"]), 10)
        self.assertTrue(all(row["confidence"] == "low" for row in watch["aois"]))
        self.assertTrue(all(row["confidence_display"] == "仅用作当地天气异常度观察" for row in watch["aois"]))
        source_by = {(row["country"], row["aoi_name"]): row for row in self.central_watch["aois"]}
        for actual in watch["aois"]:
            source = source_by[(actual["country"], actual["aoi_name"])]
            self.assertEqual(actual["country_display_name"], COUNTRIES_DISPLAY[actual["country"]])
            self.assertEqual(actual["aoi_display_name"], AOI_DISPLAY[actual["aoi_name"]])
            for variable in VARIABLES:
                for suffix in ("current", "change_yoy", "percentile", "band"):
                    field = variable + "_" + suffix
                    self.assertEqual(actual[field], source[field])
            self.assertIsNone(actual["weather_stress_score"])
            components = [Decimal("2") * abs(Decimal(actual[v+"_percentile"]) - Decimal("50")) for v in VARIABLES]
            expected_score = (sum(components, Decimal("0")) / Decimal("6")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            self.assertEqual(actual["weather_anomaly_score"], float(expected_score))
        self.assertEqual(sum(1 for row in watch["aois"] for v in VARIABLES for s in ("current", "change_yoy", "percentile", "band") if row[v+"_"+s] is not None), 240)

    def test_central_asia_country_then_aoi_hierarchy_is_complete_and_nonaggregating(self):
        expected_order = ["Kazakhstan", "Kyrgyzstan", "Tajikistan", "Turkmenistan", "Uzbekistan"]
        expected_counts = {
            "Kazakhstan": 1,
            "Kyrgyzstan": 2,
            "Tajikistan": 2,
            "Turkmenistan": 2,
            "Uzbekistan": 3,
        }
        aois = self.payload["central_asia_watch"]["aois"]
        grouped = {country: [row for row in aois if row["country"] == country] for country in expected_order}
        self.assertEqual([country for country in expected_order if grouped[country]], expected_order)
        self.assertEqual({country: len(rows) for country, rows in grouped.items()}, expected_counts)
        self.assertEqual(sum(expected_counts.values()), len(aois))
        self.assertEqual(len({row["id"] for row in aois}), 10)

        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("const centralCountryOrder=['Kazakhstan','Kyrgyzstan','Tajikistan','Turkmenistan','Uzbekistan']", html)
        self.assertIn("function centralCountryGroups(aois)", html)
        self.assertIn("data-central-country", html)
        self.assertIn("aria-label','切换中亚国家", html)
        self.assertIn("const countryAois=central.filter(item=>item.country===centralCountrySelected)", html)
        self.assertIn("centralSelected=first?.id||''", html)
        self.assertIn("不计算国家平均分或国家排名", html)
        self.assertIn("state.countryAois.length} 个州／区域", html)
        country_card_body = re.search(r"function centralCountryCard\(group\)\{(.*?)\}\n", html).group(1)
        self.assertNotIn("weather_anomaly_score", country_card_body)
        self.assertNotIn("central-anomaly", country_card_body)
        self.assertIn(".central-country-grid", html)
        self.assertIn(".region-grid,.central-country-grid,.central-grid{grid-template-columns:1fr}", html)

    def test_central_seasonal_is_10_by_6_raw_plus_anomaly_cropped_and_source_exact(self):
        seasonal = self.payload["central_asia_seasonal"]
        self.assertEqual(len(seasonal), 10)
        by_key = {(row["aoi_name"], row["month_day"]): row for row in self.central_seasonal_rows if row["country"] in {"Kazakhstan", "Kyrgyzstan", "Tajikistan", "Turkmenistan", "Uzbekistan"}}
        self.assertEqual(len(by_key), 10 * 366)
        cropped = window_keys("03-01", "10-31")
        for country, aoi, aoi_id in CENTRAL_AOI:
            item = seasonal[aoi_id]
            self.assertEqual(len(item["metrics"]), 7)
            self.assertIn("weather_anomaly_score", item["metrics"])
            self.assertFalse(item["cross_year_axis"])
            self.assertEqual(item["display_window_start"], "03-01")
            self.assertEqual(item["display_window_end"], "10-31")
            self.assertEqual(item["display_window_status"], "display_window_proxy_not_verified_local_stage_calendar")
            self.assertEqual(item["gap_codes"], by_key[(aoi, "01-01")]["gap_codes"].split(";"))
            for variable in VARIABLES:
                metric = item["metrics"][variable]
                self.assertEqual(len(metric["day_keys"]), 245)
                for i, day in enumerate(cropped):
                    src = by_key[(aoi, day)]
                    for out, field in (("history_min", variable+"_hist_min"), ("history_max", variable+"_hist_max"), ("last_year", variable+"_2025")):
                        expected = None if src[field] == "" else float(src[field])
                        self.assertEqual(metric[out][i], expected, (aoi, variable, day, out))
                cutoff = date.fromisoformat(metric["display_cutoff_date"])
                self.assertEqual(metric["current_year_status"][metric["day_keys"].index(cutoff.strftime("%m-%d"))], "available")
                overlay_field = "vapor_pressure_deficit_max" if variable == "vapour_pressure_deficit_max" else variable
                overlay_rows = builder._load_current_au_central_overlay()[aoi]
                self.assertEqual(
                    metric["current_year"][metric["day_keys"].index(cutoff.strftime("%m-%d"))],
                    overlay_rows[cutoff][overlay_field],
                )
                if cutoff < date(cutoff.year, 10, 31):
                    next_day = cutoff + timedelta(days=1)
                    self.assertEqual(metric["current_year_status"][metric["day_keys"].index(next_day.strftime("%m-%d"))], "future")

    def test_central_anomaly_seasonality_is_independently_rebuilt_from_raw(self):
        original_manifest = json.loads((COTTON / "research/raw/australia_central_asia_era5_daily_v0_1/source_manifest_v0_1.json").read_text(encoding="utf-8"))
        retry_manifest = json.loads((COTTON / "research/raw/central_asia_era5_gap_retry_v0_1/source_manifest_v0_1.json").read_text(encoding="utf-8"))
        entries = {}
        for entry in original_manifest["raw_responses"]:
            if entry["aoi_name"] in AOI_DISPLAY:
                entries[entry["aoi_name"]] = (entry, "raw_response_path", "raw_response_bytes", "raw_response_sha256")
        for entry in retry_manifest["targets"]:
            entries[entry["aoi_name"]] = (entry, "output_path", "response_bytes", "response_sha256")
        self.assertEqual(set(entries), set(AOI_DISPLAY))
        mean_variables = {"temperature_2m_max", "temperature_2m_min", "vapour_pressure_deficit_max"}
        cutoff = date(2026, 9, 10)

        for _country, aoi, aoi_id in CENTRAL_AOI:
            entry, path_field, bytes_field, sha_field = entries[aoi]
            raw_path = Path(entry[path_field])
            source_path = raw_path if raw_path.is_absolute() else COTTON.parent / raw_path
            raw = source_path.read_bytes()
            self.assertEqual(len(raw), int(entry[bytes_field]))
            self.assertEqual(hashlib.sha256(raw).hexdigest(), entry[sha_field])
            daily = json.loads(raw.decode("utf-8"))["daily"]
            indexes = {date.fromisoformat(day): index for index, day in enumerate(daily["time"])}

            def aggregate(year, key, variable):
                month, day = (int(part) for part in key.split("-"))
                end = date(year, month, day)
                values = [daily[variable][indexes[end - timedelta(days=offset)]] for offset in range(13, -1, -1)]
                self.assertTrue(all(value is not None and math.isfinite(float(value)) for value in values))
                total = math.fsum(float(value) for value in values)
                return total / 14.0 if variable in mean_variables else total

            metric = self.payload["central_asia_seasonal"][aoi_id]["metrics"]["weather_anomaly_score"]
            self.assertEqual(metric["day_keys"], window_keys("03-01", "10-31"))
            self.assertEqual(metric["history_years"], list(range(1991, 2025)))
            self.assertEqual(metric["history_year_count"], 34)
            self.assertEqual(metric["history_reference_mode"], "in_sample_local_same_window_1991_2024_midrank")
            self.assertEqual(len(metric["current_year"]), 245)

            for index, key in enumerate(metric["day_keys"]):
                history = {
                    variable: [aggregate(year, key, variable) for year in range(1991, 2025)]
                    for variable in VARIABLES
                }

                def score(year):
                    components = []
                    for variable in VARIABLES:
                        value = aggregate(year, key, variable)
                        baseline = history[variable]
                        less = sum(item < value for item in baseline)
                        equal = sum(item == value for item in baseline)
                        percentile = Decimal(f"{100.0 * (less + 0.5 * equal) / len(baseline):.2f}")
                        components.append(Decimal("2") * abs(percentile - Decimal("50")))
                    return float((sum(components, Decimal("0")) / Decimal("6")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

                expected_history = [score(year) for year in range(1991, 2025)]
                self.assertEqual(metric["history_min"][index], min(expected_history), (aoi, key, "history_min"))
                self.assertEqual(metric["history_max"][index], max(expected_history), (aoi, key, "history_max"))
                self.assertEqual(metric["last_year"][index], score(2025), (aoi, key, "last_year"))
                month, day = (int(part) for part in key.split("-"))
                actual = date(2026, month, day)
                dynamic_cutoff = date.fromisoformat(metric["display_cutoff_date"])
                if actual <= cutoff:
                    self.assertEqual(metric["current_year"][index], score(2026), (aoi, key, "current_year"))
                elif actual <= dynamic_cutoff:
                    self.assertIsNotNone(metric["current_year"][index], (aoi, key, "current_year overlay"))
                else:
                    self.assertIsNone(metric["current_year"][index], (aoi, key, "current_year future"))
                self.assertEqual(metric["current_year_status"][index], "available" if actual <= dynamic_cutoff else "future")

            watch = next(row for row in self.payload["central_asia_watch"]["aois"] if row["id"] == aoi_id)
            cutoff_index = metric["day_keys"].index(metric["display_cutoff_date"][5:])
            self.assertEqual(metric["current_year"][cutoff_index], watch["weather_anomaly_score"])

        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-chart-metric="weather_anomaly_score"', html)
        self.assertIn("点击异常度查看季节图", html)
        self.assertIn("天气异常度（14天滚动）", html)

    def test_calendar_and_cross_year_region_axes_are_explicit(self):
        for region_id in ("china", "us", "brazil"):
            self.assertFalse(self.payload["seasonal"][region_id]["cross_year_axis"], region_id)
        self.assertTrue(self.payload["seasonal"]["india"]["cross_year_axis"])
        self.assertTrue(self.payload["seasonal"]["australia"]["cross_year_axis"])

    def test_india_cross_year_axis_maps_january_to_next_calendar_year(self):
        metric = self.payload["seasonal"]["india"]["metrics"]["score"]
        self.assertEqual((metric["day_keys"][0], metric["day_keys"][-1]), ("05-01", "01-31"))
        self.assertEqual((metric["current_year_label"], metric["last_year_label"]), ("2026/27", "2025/26"))
        january_index = metric["day_keys"].index("01-15")
        self.assertIsNone(metric["current_year"][january_index])
        self.assertEqual(metric["current_year_status"][january_index], "future")
        with builder.NATIONAL_DAILY_PATHS["India"].open(encoding="utf-8", newline="") as handle:
            source = {
                row["date"]: float(row["theoretical_weather_stress_index"])
                for row in csv.DictReader(handle)
                if row.get("theoretical_weather_stress_index") not in (None, "", "null", "None")
            }
        self.assertEqual(metric["last_year"][january_index], source["2026-01-15"])

        for bundle in self.payload["subregion_seasonal"]["india"].values():
            self.assertTrue(bundle["cross_year_axis"])
            self.assertEqual((bundle["current_year"], bundle["last_year"]), ("2026/27", "2025/26"))
            for namespace in ("metrics", "raw_metrics"):
                for sub_metric in bundle[namespace].values():
                    self.assertEqual((sub_metric["day_keys"][0], sub_metric["day_keys"][-1]), ("05-01", "01-31"))
                    self.assertEqual((sub_metric["current_year_label"], sub_metric["last_year_label"]), ("2026/27", "2025/26"))
                    sub_january_index = sub_metric["day_keys"].index("01-15")
                    self.assertIsNone(sub_metric["current_year"][sub_january_index])
                    self.assertEqual(sub_metric["current_year_status"][sub_january_index], "future")

    def test_score_and_raw_metric_namespaces_are_separate_and_frozen(self):
        expected = {
            "china": {"score", "high_heat", "low_temperature", "excess_rain", "spring_wind"},
            "us": {"score", "root_zone_dryness", "high_heat", "low_temperature", "establishment_excess_rain", "harvest_rain"},
            "brazil": {"score", "harvest_rain", "root_zone_dryness", "high_temperature", "high_vpd", "low_solar_radiation", "low_temperature"},
            "india": {"score", "root_zone_dryness", "hot_dry_compound", "excess_rain_waterlogging"},
            "australia": {"score", "low_temperature", "high_heat", "excess_rain", "high_vpd", "low_solar"},
        }
        raw_ids = {"tmax_14d_mean", "tmin_14d_mean", "precip_14d_sum", "sw_rad_14d_mean"}
        for region_id, score_ids in expected.items():
            seasonal = self.payload["seasonal"][region_id]
            self.assertEqual(set(seasonal["metrics"]), score_ids)
            self.assertEqual(set(seasonal["raw_metrics"]), raw_ids)
            self.assertTrue(raw_ids.isdisjoint(seasonal["metrics"]))

    def test_score_scale_status_arrays_and_source_gap_counts_are_independent(self):
        region_inputs = {
            "China": ("china", builder.DAILY_PATHS["China"], {"score": "theoretical_weather_stress_index", **{x[0]: x[2] for x in builder.REGION_META["China"]["factor_fields"]}}),
            "United States": ("us", builder.NATIONAL_DAILY_PATHS["United States"], {"score": "theoretical_weather_stress_index", **{x[0]: x[2] for x in builder.REGION_META["United States"]["factor_fields"]}}),
            "Brazil": ("brazil", builder.NATIONAL_DAILY_PATHS["Brazil"], {"score": "theoretical_weather_stress_index", **{x[0]: x[2] for x in builder.REGION_META["Brazil"]["factor_fields"]}}),
            "India": ("india", builder.NATIONAL_DAILY_PATHS["India"], {"score": "theoretical_weather_stress_index", **{x[0]: x[2] for x in builder.REGION_META["India"]["factor_fields"]}}),
            "Australia": ("australia", builder.AUSTRALIA_DAILY_PATH, {"score": "theoretical_weather_stress_index", **{x[0]: x[2] for x in builder.REGION_META["Australia"]["factor_fields"]}}),
        }

        def compress(keys, active):
            indexes = [i for i, key in enumerate(keys) if key in active]
            result = []
            if not indexes:
                return result
            start = previous = indexes[0]
            for index in indexes[1:]:
                if index != previous + 1:
                    result.append({"start": keys[start], "end": keys[previous]})
                    start = index
                previous = index
            result.append({"start": keys[start], "end": keys[previous]})
            return result

        for geography, (region_id, path, fields) in region_inputs.items():
            with path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            by_year_key = {}
            active = {metric: set() for metric in fields}
            source_dates = []
            for row in rows:
                parsed = date.fromisoformat(row["date"][:10])
                if parsed.month == 2 and parsed.day == 29:
                    continue
                source_dates.append(parsed)
                for metric, field in fields.items():
                    value = row.get(field, "")
                    if value not in (None, ""):
                        by_year_key.setdefault((metric, parsed.year, parsed.strftime("%m-%d")), []).append(float(value))
                        active[metric].add(parsed.strftime("%m-%d"))
            source_max = max(source_dates)
            seasonal = self.payload["seasonal"][region_id]
            current_start = int(str(seasonal["current_year"])[:4])
            prior_start = current_start - 1
            for metric, field in fields.items():
                output = seasonal["metrics"][metric]
                self.assertEqual(output["scale_type"], "fixed_score_0_100")
                self.assertEqual(output["scale_min"], 0)
                self.assertEqual(output["scale_max"], 100)
                self.assertIn("不是气象原值", output["value_semantics"])
                keys = output["day_keys"]
                self.assertEqual(len(output["last_year"]), len(keys))
                self.assertEqual(len(output["current_year"]), len(keys))
                self.assertEqual(len(output["last_year_status"]), len(keys))
                self.assertEqual(len(output["current_year_status"]), len(keys))
                self.assertEqual(output["active_periods"], compress(keys, active[metric]))
                expected_gap_count = 0
                for year_label, year_start, values, statuses in (
                    ("last_year", prior_start, output["last_year"], output["last_year_status"]),
                    ("current_year", current_start, output["current_year"], output["current_year_status"]),
                ):
                    for index, key in enumerate(keys):
                        month, day = (int(part) for part in key.split("-"))
                        source_year = year_start
                        if (geography == "Australia" and month < 9) or (geography == "India" and month < 5):
                            source_year += 1
                        source_values = by_year_key.get((metric, source_year, key), [])
                        expected_value = sum(source_values) / len(source_values) if source_values else None
                        if expected_value is None:
                            self.assertIsNone(values[index], (geography, metric, year_label, key))
                        else:
                            self.assertEqual(values[index], expected_value, (geography, metric, year_label, key))
                        if key not in active[metric]:
                            expected_status = "inactive_stage"
                        elif year_label == "current_year" and date(source_year, month, day) > source_max:
                            expected_status = "future"
                        elif expected_value is None:
                            expected_status = "source_gap"
                        else:
                            expected_status = "available"
                        self.assertEqual(statuses[index], expected_status, (geography, metric, year_label, key))
                        expected_gap_count += expected_status == "source_gap"
                self.assertEqual(output["source_gap_count"], expected_gap_count, (geography, metric))

        xinjiang = self.payload["seasonal"]["china"]
        self.assertEqual(xinjiang["metrics"]["high_heat"]["active_periods"], [{"start": "04-01", "end": "11-30"}])
        self.assertEqual(xinjiang["metrics"]["low_temperature"]["active_periods"], [{"start": "04-01", "end": "11-30"}])
        china_score = xinjiang["metrics"]["score"]
        china_available = [key for key, status in zip(china_score["day_keys"], china_score["current_year_status"]) if status == "available"]
        china_cutoff = date(2026, *(int(part) for part in china_available[-1].split("-")))
        self.assertEqual(china_score["current_year_status"][china_score["day_keys"].index(china_available[-1])], "available")
        self.assertEqual(china_score["current_year_status"][china_score["day_keys"].index((china_cutoff + timedelta(days=1)).strftime("%m-%d"))], "future")
        australia = self.payload["seasonal"]["australia"]
        self.assertEqual(australia["metrics"]["low_temperature"]["active_periods"], [{"start": "09-01", "end": "04-30"}])
        self.assertEqual(australia["metrics"]["high_heat"]["active_periods"], [{"start": "09-01", "end": "04-30"}])
        self.assertEqual(australia["metrics"]["score"]["current_year_status"][australia["metrics"]["score"]["day_keys"].index("05-01")], "inactive_stage")
        au_score = australia["metrics"]["score"]
        au_available = [key for key, status in zip(au_score["day_keys"], au_score["current_year_status"]) if status == "available"]
        au_cutoff = date(2026, *(int(part) for part in au_available[-1].split("-")))
        self.assertEqual(au_score["current_year_status"][au_score["day_keys"].index(au_available[-1])], "available")
        self.assertEqual(au_score["current_year_status"][au_score["day_keys"].index((au_cutoff + timedelta(days=1)).strftime("%m-%d"))], "future")

    def test_raw_weather_anchors_units_cutoffs_and_solar_statuses(self):
        self.assertEqual(
            {metric_id: metric["unit"] for metric_id, metric in self.payload["seasonal"]["china"]["raw_metrics"].items()},
            {"tmax_14d_mean": "°C", "tmin_14d_mean": "°C", "precip_14d_sum": "mm", "sw_rad_14d_mean": "MJ/m²/日"},
        )
        """Independent point/day recomputation of the five frozen raw anchors."""
        configs = {
            "china": (COTTON / "cn_xj_weather/points_daily.csv", ("xj_shihezi", "xj_shawan", "xj_kuitun", "xj_changji", "xj_hutubi", "xj_bole", "xj_jinghe", "xj_kashgar", "xj_shache", "xj_bachu", "xj_aksu", "xj_awat", "xj_kuqa", "xj_shaya", "xj_korla", "xj_yuli", "xj_luntai", "xj_turpan")),
            "us": (COTTON / "us_weather/points_daily.csv", ("tx_hp_n", "tx_hp_c", "tx_hp_s", "tx_hp_w", "tx_hp_e", "tx_hp_sw", "tx_farwest", "tx_rolling", "tx_edwards", "tx_coastal", "tx_rgv", "tx_black")),
            "brazil": (COTTON / "br_weather/points_daily.csv", ("mt_campo_novo", "mt_campo_verde", "mt_diamantino", "mt_lucas", "mt_nova_mutum", "mt_nova_ubirata", "mt_primavera", "mt_rondonopolis", "mt_sapezal", "mt_sinop", "mt_sorriso", "mt_tangara")),
            "india": (COTTON / "in_weather/points_daily.csv", ("gj_rajkot", "gj_surendranagar", "gj_bhavnagar", "gj_amreli", "gj_bharuch", "mh_akola", "mh_amravati", "mh_yavatmal", "mh_buldhana", "mh_jalgaon", "mh_jalna", "mp_khargone", "mp_dhar", "tg_adilabad", "tg_warangal", "tg_khammam")),
        }
        def point_anchor(path, points, cutoff):
            rows = {point: {} for point in points}
            with path.open(encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    if row.get("point_id") in rows:
                        rows[row["point_id"]][date.fromisoformat(row["date"][:10])] = row
            result = []
            for field, mode in (("tmax", "mean"), ("tmin", "mean"), ("precip", "sum"), ("sw_rad", "mean")):
                values = []
                for point in points:
                    window = [rows[point][cutoff - timedelta(days=i)][field] for i in range(13, -1, -1)]
                    values.append(sum(float(v) for v in window) / 14 if mode == "mean" else sum(float(v) for v in window))
                if path.name.startswith("points_daily") and path.parent.name == "us_weather":
                    hp = sum(values[:6]) / 6; other = sum(values[6:]) / 6; result.append(.64 * hp + .36 * other)
                elif path.parent.name == "in_weather":
                    state_points = ((0, 5, .3404351768), (5, 11, .3739800544), (11, 13, .0643699003), (13, 16, .2212148685))
                    result.append(sum(weight * (sum(values[start:end]) / (end - start)) for start, end, weight in state_points))
                else:
                    result.append(sum(values) / len(values))
            return result
        for region_id, (path, points) in configs.items():
            raw = self.payload["seasonal"][region_id]["raw_metrics"]
            display_cutoff = date.fromisoformat(raw["tmax_14d_mean"]["display_cutoff_date"])
            available_keys = [key for key, value in zip(raw["tmax_14d_mean"]["day_keys"], raw["tmax_14d_mean"]["current_year"]) if value is not None]
            cutoff = date(2026, *(int(part) for part in available_keys[-1].split("-")))
            actual = point_anchor(path, points, cutoff)
            key = cutoff.strftime("%m-%d")
            for metric_id, value in zip(("tmax_14d_mean", "tmin_14d_mean", "precip_14d_sum", "sw_rad_14d_mean"), actual):
                metric = raw[metric_id]
                self.assertAlmostEqual(metric["current_year"][metric["day_keys"].index(key)], value, places=3)
                self.assertEqual(metric["scale_type"], "auto_unit")
                self.assertIn(metric["unit"], {"°C", "mm", "MJ/m²/日"})
                self.assertEqual(metric["display_cutoff_date"], display_cutoff.isoformat())
                self.assertEqual(metric["valid_current_point_count"], len(points))
                self.assertAlmostEqual(metric["current_spatial_coverage"], 1.0)
        australia = self.payload["seasonal"]["australia"]["raw_metrics"]
        self.assertEqual(
            [australia[k]["current_year"][australia[k]["day_keys"].index("09-10")] for k in ("tmax_14d_mean", "tmin_14d_mean", "precip_14d_sum", "sw_rad_14d_mean")],
            [24.66575012898245, 9.22891650974228, 0.318339133125972, 19.271064705932012],
        )
        self.assertEqual(australia["tmax_14d_mean"]["valid_current_point_count"], 8)
        self.assertEqual(australia["tmax_14d_mean"]["target_point_count"], 8)
        for region_id, status in (("china", "observed_only_excluded_pending_dedup"), ("us", "observed_only_excluded_local_direction_gap"), ("brazil", "included_in_model_contract"), ("india", "observed_only_excluded_pending_dedup"), ("australia", "included_and_active_in_current_stage")):
            self.assertEqual(self.payload["seasonal"][region_id]["raw_metrics"]["sw_rad_14d_mean"]["solar_model_status"], status)
        solar_labels = {
            "china": "仅展示原值；暂未计分（等待与其他因子去重）", "us": "仅展示原值；暂未计分（当地影响方向证据不足）",
            "brazil": "已纳入模型；当前9月阶段未启用", "india": "仅展示原值；暂未计分（等待与其他因子去重）", "australia": "已纳入模型；当前阶段启用",
        }
        for region_id, label in solar_labels.items():
            self.assertEqual(self.payload["seasonal"][region_id]["raw_metrics"]["sw_rad_14d_mean"]["solar_display_status"], label)
            self.assertTrue(self.payload["seasonal"][region_id]["raw_metrics"]["precip_14d_sum"]["nonnegative"])
            self.assertTrue(self.payload["seasonal"][region_id]["raw_metrics"]["sw_rad_14d_mean"]["nonnegative"])
        au_tmax = self.payload["seasonal"]["australia"]["raw_metrics"]["tmax_14d_mean"]
        self.assertIsNotNone(au_tmax["current_year"][au_tmax["day_keys"].index(au_tmax["display_cutoff_date"][5:])])

    def test_raw_missing_point_window_and_coverage_gate_semantics(self):
        # Exercise the production rolling and spatial functions directly.
        cutoff = date(2026, 9, 13)
        records = {cutoff - timedelta(days=i): {"tmax": 10.0, "tmin": 5.0, "precip": 1.0, "sw_rad": 20.0} for i in range(14)}
        records[cutoff - timedelta(days=7)]["tmax"] = None
        rolled = builder._rolling_point_values(records, "tmax", "mean")
        self.assertIsNone(rolled[cutoff])
        rolled_ok = builder._rolling_point_values({day: {**row, "tmax": 10.0} for day, row in records.items()}, "tmax", "mean")
        self.assertEqual(rolled_ok[cutoff], 10.0)
        china_config = builder.RAW_POINT_CONFIG["China"]
        sparse = {point: (10.0 if index < 10 else None) for index, point in enumerate(china_config["points"])}
        aggregate, coverage = builder._spatial_raw(china_config, sparse, "tmax_14d_mean")
        self.assertIsNone(aggregate)
        self.assertLess(coverage, 0.60)
        dense = {point: (10.0 if index < 11 else 20.0) for index, point in enumerate(china_config["points"])}
        aggregate, coverage = builder._spatial_raw(china_config, dense, "tmax_14d_mean")
        self.assertGreaterEqual(coverage, 0.60)
        self.assertAlmostEqual(aggregate, (11 * 10.0 + 7 * 20.0) / 18.0)
        tx_config = builder.RAW_POINT_CONFIG["United States"]
        tx_values = {point: (10.0 if point.startswith("tx_hp_") else 20.0) for point in tx_config["points"]}
        aggregate, coverage = builder._spatial_raw(tx_config, tx_values, "tmax_14d_mean")
        self.assertAlmostEqual(aggregate, 13.6)
        self.assertAlmostEqual(coverage, 1.0)

        # Independent gate check: two of five equal points are not enough;
        # four valid points are reweighted over the valid spatial network.
        values = {"p1": 10.0, "p2": 20.0, "p3": None, "p4": None, "p5": None}
        valid_weight = 2 / 5
        self.assertLess(valid_weight, 0.60)
        self.assertIsNone(None if valid_weight < 0.60 else 15.0)
        values = {"p1": 10.0, "p2": 20.0, "p3": 30.0, "p4": 40.0, "p5": None}
        coverage = 4 / 5
        expected = sum(values[p] for p in ("p1", "p2", "p3", "p4")) / 4
        self.assertGreaterEqual(coverage, 0.60)
        self.assertEqual(expected, 25.0)
        for region_id in ("china", "us", "brazil", "india"):
            raw = self.payload["seasonal"][region_id]["raw_metrics"]
            self.assertTrue(all(metric["history_year_count"] == 20 for metric in raw.values()))
        australia = self.payload["seasonal"]["australia"]["raw_metrics"]["tmax_14d_mean"]
        self.assertEqual(australia["history_year_count"], 34)
        keys = australia["day_keys"]
        statuses = australia["current_year_status"]
        au_available = [key for key, status in zip(keys, statuses) if status == "available"]
        au_cutoff = date(2026, *(int(part) for part in au_available[-1].split("-")))
        self.assertEqual(statuses[keys.index(au_available[-1])], "available")
        self.assertEqual(statuses[keys.index((au_cutoff + timedelta(days=1)).strftime("%m-%d"))], "future")
        self.assertEqual(statuses[keys.index("11-01")], "future")

    def test_australia_manifest_crosswalk_identity_and_raw_anchor_rebuild(self):
        manifest_path = COTTON / "research/raw/australia_central_asia_era5_daily_v0_1/source_manifest_v0_1.json"
        crosswalk_path = COTTON / "research/derived/australia_central_asia_cotton_point_crosswalk_v0_1.csv"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_by_aoi = {row["aoi_name"]: row for row in manifest["raw_responses"]}
        with crosswalk_path.open(encoding="utf-8", newline="") as handle:
            rows = [row for row in csv.DictReader(handle) if row["country"] == "Australia"]
        self.assertEqual(len(rows), 8)
        self.assertEqual(next(row for row in rows if row["aoi_name"] == "St George (QLD)")["point_status"], "gap_ambiguous_or_unmatched")
        accepted = []
        for row in rows:
            if row["aoi_name"] == "St George (QLD)":
                continue
            source = manifest_by_aoi[row["aoi_name"]]
            self.assertEqual(source["country"], "Australia")
            self.assertEqual(source["status"], "complete_response")
            self.assertEqual(row["anchor_name"], source["anchor_name"])
            accepted.append(COTTON.parent / Path(source["raw_response_path"]))
        st_manifest = json.loads(builder.AUSTRALIA_ST_GEORGE_MANIFEST_PATH.read_text(encoding="utf-8"))
        accepted.append(COTTON.parent / st_manifest["raw_response_path"])
        self.assertEqual(len(accepted), 8)
        source_fields = ("temperature_2m_max", "temperature_2m_min", "precipitation_sum", "shortwave_radiation_sum")
        cutoff = date(2026, 9, 10)
        point_values = {field: {} for field in source_fields}
        point_names = [builder.AUSTRALIA_FILE_AOI[path.name] for path in accepted]
        latest_weights = {row["aoi_name"]: row["valid_weight_kt"] for row in self.au_latest["aoi_components"]}
        total_weight = math.fsum(latest_weights.values())
        for path, point_name in zip(accepted, point_names):
            payload = json.loads(path.read_text(encoding="utf-8"))
            daily = payload["daily"]
            self.assertEqual(daily["time"][0], manifest["source_start_date"])
            self.assertEqual(daily["time"][-1], manifest["source_end_date"])
            by_day = {date.fromisoformat(day): index for index, day in enumerate(daily["time"])}
            for field in source_fields:
                window = [float(daily[field][by_day[cutoff - timedelta(days=i)]]) for i in range(13, -1, -1)]
                point_values[field][point_name] = sum(window) / 14 if field != "precipitation_sum" else sum(window)
        raw = self.payload["seasonal"]["australia"]["raw_metrics"]
        for field, metric_id in zip(source_fields, ("tmax_14d_mean", "tmin_14d_mean", "precip_14d_sum", "sw_rad_14d_mean")):
            rebuilt = math.fsum(point_values[field][name] * latest_weights[name] / total_weight for name in point_names)
            metric = raw[metric_id]
            self.assertAlmostEqual(metric["current_year"][metric["day_keys"].index("09-10")], rebuilt, places=12)

    def test_central_raw_units_and_segmented_history_band_contract(self):
        expected_units = {
            "temperature_2m_max": "°C", "temperature_2m_min": "°C", "precipitation_sum": "mm",
            "shortwave_radiation_sum": "MJ/m²", "et0_fao_evapotranspiration": "mm", "vapour_pressure_deficit_max": "kPa",
        }
        for item in self.payload["central_asia_seasonal"].values():
            self.assertEqual(set(item["metrics"]), set(expected_units) | {"weather_anomaly_score"})
            for variable in expected_units:
                metric = item["metrics"][variable]
                self.assertEqual(metric["scale_type"], "auto_unit")
                self.assertIsNone(metric["scale_min"])
                self.assertIsNone(metric["scale_max"])
                self.assertIn("气象原值", metric["value_semantics"])
                self.assertEqual(metric["unit"], expected_units[variable])
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("scale_type==='fixed_score_0_100'", html)
        self.assertIn("const bandPaths=", html)
        self.assertIn("end-start>=1", html)
        self.assertIn("source_gap", html)
        self.assertIn("灰色＝该阶段未启用", html)

    def test_central_raw_blank_label_and_scored_scale_metadata(self):
        raw_blank_label = "空值＝源数据缺口；不转换为棉花胁迫分"
        for item in self.payload["central_asia_seasonal"].values():
            for variable in VARIABLES:
                metric = item["metrics"][variable]
                self.assertEqual(metric["blank_value_label"], raw_blank_label)
                self.assertEqual(metric["scale_type"], "auto_unit")
            anomaly = item["metrics"]["weather_anomaly_score"]
            self.assertEqual(anomaly["scale_type"], "fixed_score_0_100")
            self.assertEqual((anomaly["scale_min"], anomaly["scale_max"]), (0, 100))
            self.assertIn("不是棉花胁迫", anomaly["value_semantics"])
            self.assertFalse(anomaly["cross_region_comparable"])
            self.assertIsNone(anomaly["weather_stress_score"])
        score_metric_ids = {"score", "root_zone_dryness", "high_heat", "low_temperature", "excess_rain", "spring_wind", "establishment_excess_rain", "harvest_rain", "high_temperature", "high_vpd", "low_solar", "hot_dry_compound", "excess_rain_waterlogging", "low_solar_radiation"}
        for region in self.payload["seasonal"].values():
            for metric_id, metric in region["metrics"].items():
                if metric_id not in score_metric_ids:
                    continue
                self.assertEqual(metric["scale_type"], "fixed_score_0_100")
                self.assertEqual(metric["scale_min"], 0)
                self.assertEqual(metric["scale_max"], 100)

    def test_null_band_and_status_change_boundaries_are_real_segments(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("const finiteValue=v=>v!==null&&v!==undefined&&Number.isFinite(Number(v));", html)
        self.assertIn("const valid=finiteValue(upper[i])&&finiteValue(lower[i])", html)
        self.assertIn("if(next!==current)", html)
        self.assertIn("statusRuns(M.current_year_status||[]).filter(run=>run[2]==='inactive_stage')", html)
        self.assertIn("模型启用时段：", html)
        self.assertIn("不是气象原始数据缺失", html)
        self.assertIn("完整气象值请看“天气因子原始数据”", html)
        self.assertIn("continuous_three_phase_temperature_factor_score", html)
        self.assertIn("全生长期连续计分", html)
        self.assertIn("暂定次要权重纳入综合分", html)
        self.assertIn("权重未校准", html)

        australia = self.payload["seasonal"]["australia"]["metrics"]["low_temperature"]
        keys = australia["day_keys"]
        status = australia["current_year_status"]
        status_runs = []
        start = 0
        current = status[0]
        for index in range(1, len(status) + 1):
            next_status = status[index] if index < len(status) else None
            if next_status != current:
                status_runs.append((keys[start], keys[index - 1], current))
                start = index
                current = next_status
        available_keys = [key for key, value in zip(keys, status) if value == "available"]
        cutoff_key = available_keys[-1]
        cutoff_date = date(2026, *(int(part) for part in cutoff_key.split("-")))
        next_key = (cutoff_date + timedelta(days=1)).strftime("%m-%d")
        self.assertEqual(status_runs, [
            ("09-01", cutoff_key, "available"),
            (next_key, "04-30", "future"),
            ("05-01", "06-30", "inactive_stage"),
        ])

        xinjiang = self.payload["seasonal"]["china"]["metrics"]["low_temperature"]
        history_runs = []
        start = None
        for index, value in enumerate(xinjiang["history_min"] + [None]):
            finite = value is not None
            if finite and start is None:
                start = index
            if not finite and start is not None:
                history_runs.append((xinjiang["day_keys"][start], xinjiang["day_keys"][index - 1]))
                start = None
        self.assertEqual(history_runs, [("04-01", "11-30")])

    def test_central_current_cards_and_daily_charts_use_distinct_labels(self):
        current_labels = {
            "temperature_2m_max": "14日平均日最高温",
            "temperature_2m_min": "14日平均日最低温",
            "precipitation_sum": "TP累计降水量（14天累计滚动值）",
            "shortwave_radiation_sum": "SW累计短波辐射（14天累计滚动值）",
            "et0_fao_evapotranspiration": "14日累计参考蒸散",
            "vapour_pressure_deficit_max": "14日平均最大水汽压亏缺（VPD）",
        }
        daily_labels = {
            "temperature_2m_max": "日最高温",
            "temperature_2m_min": "日最低温",
            "precipitation_sum": "日降水",
            "shortwave_radiation_sum": "日短波辐射",
            "et0_fao_evapotranspiration": "日参考蒸散",
            "vapour_pressure_deficit_max": "日最大水汽压亏缺（VPD）",
        }
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        for item in self.payload["central_asia_seasonal"].values():
            for variable, label in daily_labels.items():
                self.assertEqual(item["metrics"][variable]["label"], label)
        for label in current_labels.values():
            self.assertIn(label, html)
        for label in daily_labels.values():
            self.assertIn(label, html)
        self.assertIn("dailyLabel=(m&&m.label)||centralDailyVariableLabels[v]", html)
        self.assertIn("data-chart-title", html)
        self.assertIn("<span>当前 ${escapeHtml(a[v+'_current'])} ${escapeHtml(unit)}</span>", html)
        self.assertIn("温度和VPD取14日平均，降水、短波辐射和参考蒸散取14日累计", html)
        self.assertIn("${nextYear?'次年':''}${month}月", html)
        self.assertNotIn("precipitation_sum:'14日降水'", html)
        self.assertNotIn("shortwave_radiation_sum:'14日短波辐射'", html)
        self.assertNotIn("et0_fao_evapotranspiration:'14日参考蒸散'", html)

    def test_global_supply_and_comparability_gates(self):
        self.assertEqual(self.payload["scored_region_count"], 5)
        self.assertEqual(self.payload["descriptive_only_aoi_count"], 10)
        self.assertIsNone(self.payload["global_numeric_weather_score"])
        self.assertFalse(self.payload["cross_region_weather_comparable"])
        self.assertFalse(self.payload["weather_to_supply_conversion_performed"])

    def test_v07_production_weighted_composite_is_independently_rebuilt(self):
        composite = self.payload["five_region_production_weighted_weather_stress_display"]
        source_rows = {row["geography"]: row for row in self.brief["rows"]}
        geographies = ("China", "United States", "Brazil", "India", "Australia")
        ids = {"China": "china", "United States": "us", "Brazil": "brazil", "India": "india", "Australia": "australia"}
        productions = {geo: float(source_rows[geo]["current_production_1000_480lb_bales"]) for geo in geographies}
        total = math.fsum(productions.values())
        weights = {ids[geo]: productions[geo] / total for geo in geographies}
        self.assertEqual(total, 92201.0)
        self.assertEqual(composite["production_total_1000_480lb_bales"], 92201)
        for row in composite["weights"]:
            self.assertAlmostEqual(row["production_weight"], weights[row["region_id"]], places=15)
        daily = {}
        for geo in geographies:
            path = builder.NATIONAL_DAILY_PATHS[geo] if geo in builder.NATIONAL_DAILY_PATHS else builder.DAILY_PATHS[geo]
            with path.open(encoding="utf-8", newline="") as handle:
                daily[ids[geo]] = {date.fromisoformat(row["date"]): (None if row.get("theoretical_weather_stress_index", "") == "" else float(row["theoretical_weather_stress_index"])) for row in csv.DictReader(handle)}
        latest_by_region = {
            rid: max(day for day, value in rows.items() if value is not None)
            for rid, rows in daily.items()
        }
        cutoff = min(latest_by_region.values())
        current_scores = {rid: daily[rid][cutoff] for rid in ids.values()}
        expected = math.fsum(weights[rid] * current_scores[rid] for rid in ids.values())
        self.assertEqual(composite["common_cutoff_date"], cutoff.isoformat())
        self.assertEqual(composite["current_score"], expected)
        self.assertAlmostEqual(composite["current_score"], expected, places=12)
        self.assertEqual(composite["weighted_production_coverage"], 1.0)
        self.assertEqual(composite["current_region_scores"], current_scores)
        metric = composite["seasonal_metric"]
        self.assertEqual(metric["display_window_start"], "04-01")
        self.assertEqual(metric["display_window_end"], "11-30")
        self.assertEqual(metric["scale_min"], 0)
        self.assertEqual(metric["scale_max"], 100)
        self.assertEqual(metric["coverage_max"], 1.0)
        self.assertEqual(max(v for values in metric["history_production_weight_coverage"].values() for v in values if v is not None), 0.9674623919480266)
        for index, key in enumerate(metric["day_keys"]):
            month, day = map(int, key.split("-"))
            actual = date(2026, month, day)
            if actual > cutoff:
                self.assertIsNone(metric["current_year"][index]); self.assertEqual(metric["current_year_status"][index], "future"); self.assertIsNone(metric["current_year_production_weight_coverage"][index]); continue
            vals = {rid: daily[rid].get(actual) for rid in ids.values()}
            valid = [rid for rid, value in vals.items() if value is not None]
            coverage = math.fsum(weights[rid] for rid in valid)
            self.assertEqual(metric["current_year_production_weight_coverage"][index], coverage)
            self.assertEqual(metric["current_year_valid_region_ids"][index], valid)
            if coverage < .60:
                self.assertIsNone(metric["current_year"][index]); self.assertEqual(metric["current_year_status"][index], "coverage_below_gate")
            else:
                self.assertEqual(metric["current_year"][index], math.fsum(weights[rid] * vals[rid] for rid in valid) / coverage)
                self.assertEqual(metric["current_year_status"][index], "available")
        # Rebuild the prior year and every history-band day from the five source CSVs.
        history_expected = {str(year): [] for year in range(2015, 2025)}
        for year in list(range(2015, 2025)) + [2025]:
            coverage_key = str(year) if year != 2025 else None
            coverage_array = metric["history_production_weight_coverage"][coverage_key] if coverage_key else metric["last_year_production_weight_coverage"]
            ids_array = metric["history_valid_region_ids"][coverage_key] if coverage_key else metric["last_year_valid_region_ids"]
            status_array = metric["history_status"][coverage_key] if coverage_key else metric["last_year_status"]
            value_array = metric["last_year"] if year == 2025 else None
            for index, key in enumerate(metric["day_keys"]):
                month, day = map(int, key.split("-")); actual = date(year, month, day)
                vals = {rid: daily[rid].get(actual) for rid in ids.values()}
                valid = [rid for rid, value in vals.items() if value is not None]
                coverage = math.fsum(weights[rid] for rid in valid)
                self.assertEqual(coverage_array[index], coverage)
                self.assertEqual(ids_array[index], valid)
                if coverage < .60:
                    expected_value = None; expected_status = "coverage_below_gate"
                else:
                    expected_value = math.fsum(weights[rid] * vals[rid] for rid in valid) / coverage; expected_status = "available"
                self.assertEqual(status_array[index], expected_status)
                if value_array is not None: self.assertEqual(value_array[index], expected_value)
                if year != 2025: history_expected[str(year)].append(expected_value)
        self.assertEqual(metric["history_min"], [min((history_expected[str(year)][i] for year in range(2015, 2025) if history_expected[str(year)][i] is not None), default=None) for i in range(len(metric["day_keys"]))])
        self.assertEqual(metric["history_max"], [max((history_expected[str(year)][i] for year in range(2015, 2025) if history_expected[str(year)][i] is not None), default=None) for i in range(len(metric["day_keys"]))])

    def test_v07_weighted_gate_and_missing_region_do_not_fill_zero(self):
        weights = {"China": .36, "United States": .14, "Brazil": .20, "India": .26, "Australia": .04}
        below = builder._weighted_production_day({"china": None, "us": 10.0, "brazil": None, "india": None, "australia": None}, weights)
        self.assertIsNone(below["value"]); self.assertEqual(below["status"], "coverage_below_gate")
        available = builder._weighted_production_day({"china": 20.0, "us": 10.0, "brazil": None, "india": 40.0, "australia": None}, weights)
        self.assertGreaterEqual(available["production_weight_coverage"], .60)
        self.assertEqual(available["value"], math.fsum(weights[r] * v for r, v in (("China", 20.0), ("United States", 10.0), ("India", 40.0))) / available["production_weight_coverage"])
        self.assertNotIn("brazil", available["valid_region_ids"])
        self.assertFalse(self.payload["five_region_production_weighted_weather_stress_display"]["not_unified_model"] is False)

    def test_v07_frontend_contract_and_cache_key(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("five_region_production_weighted_weather_stress_display", html)
        self.assertIn("全球棉花五大种植区域天气胁迫总评分（产区产量加权）", html)
        self.assertIn("中国棉花种植区以新疆为代表，未包含中国疆外种棉区", html)
        self.assertNotIn("中国天气输入仅为新疆代理，并非中国全国网络", html)
        self.assertIn("历史带不含补造的澳洲历史分", self.payload["five_region_production_weighted_weather_stress_display"]["seasonal_metric"]["historical_band_note"])
        self.assertIn("覆盖不足不按0处理", html)
        self.assertIn("M.nonnegative?Math.max(0,lo-extra):lo-extra", html)
        self.assertIn("data.json?ts=${Date.now()}", html)
        self.assertIn("cache:'no-store'", html)
        self.assertNotIn("v=20260923-v05-raw-weather", html)
        self.assertIn("data-chart-region=\"${weightedId}\"", html)
        self.assertIn("const first=app.querySelector('.hero')", html)
        self.assertIn("M.solar_display_status", html)

    def test_xinjiang_spring_wind_chart_is_cropped_to_active_window_only(self):
        metric = self.payload["seasonal"]["china"]["metrics"]["spring_wind"]
        self.assertEqual(metric["chart_display_start"], "04-01")
        self.assertEqual(metric["chart_display_end"], "05-31")
        self.assertIn("结构性未启用日期从横轴隐藏", metric["chart_display_note"])
        self.assertEqual(metric["day_keys"][0], "04-01")
        self.assertEqual(metric["day_keys"][-1], "11-30")
        self.assertEqual(len(metric["day_keys"]), len(metric["current_year_status"]))

        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("function chartMetricForDisplay(metric)", html)
        self.assertIn("metric.chart_display_periods", html)
        self.assertIn("indexes.map(index=>value[index])", html)
        self.assertIn("M=chartMetricForDisplay(M)", html)

    def test_requested_factor_charts_crop_only_the_configured_enabled_spans(self):
        expected = {
            "us": {"root_zone_dryness": (("03-01", "09-30"),), "high_heat": (("04-01", "08-31"),), "low_temperature": (("02-01", "05-31"), ("07-01", "07-31"), ("09-01", "11-30")), "establishment_excess_rain": (("02-01", "06-30"),), "harvest_rain": (("07-01", "11-30"),)},
            "brazil": {"harvest_rain": (("02-01", "09-30"),), "root_zone_dryness": (("01-01", "06-30"), ("09-01", "12-31")), "high_temperature": (("01-01", "06-30"), ("09-01", "12-31")), "low_temperature": (("01-01", "10-31"),), "high_vpd": (("01-01", "06-30"), ("09-01", "12-31")), "low_solar_radiation": (("01-01", "08-31"), ("10-01", "12-31"))},
            "india": {"score": (("05-01", "01-31"),), "root_zone_dryness": (("05-01", "01-31"),), "hot_dry_compound": (("05-01", "01-31"),), "excess_rain_waterlogging": (("05-01", "01-31"),)},
            "australia": {"low_temperature": (("09-01", "04-30"),), "high_heat": (("09-01", "04-30"),), "excess_rain": (("09-01", "10-31"), ("03-01", "04-30")), "high_vpd": (("11-01", "02-28"),), "low_solar": (("09-01", "04-30"),)},
        }
        for region_id, metrics in expected.items():
            for metric_id, periods in metrics.items():
                metric = self.payload["seasonal"][region_id]["metrics"][metric_id]
                actual_periods = metric.get("chart_display_periods")
                if actual_periods is None:
                    actual_periods = [{"start": metric["chart_display_start"], "end": metric["chart_display_end"]}]
                self.assertEqual(actual_periods, [{"start": start, "end": end} for start, end in periods], (region_id, metric_id))
                self.assertEqual(len(metric["day_keys"]), len(metric["current_year_status"]))
                self.assertEqual(len(metric["day_keys"]), len(metric["history_min"]))
                self.assertTrue(metric["chart_display_note"])
        brazil_vpd = self.payload["seasonal"]["brazil"]["metrics"]["high_vpd"]
        australia_vpd = self.payload["seasonal"]["australia"]["metrics"]["high_vpd"]
        self.assertEqual(brazil_vpd["label"], "高水汽压亏缺（VPD，空气干燥度）")
        self.assertEqual(australia_vpd["label"], "高水汽压亏缺（VPD，空气干燥度）")
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("高水汽压亏缺（VPD，空气干燥度）", html)
        self.assertIn("M.historical_band_note", html)
        self.assertIn("confidence_display||a.confidence", html)

    def test_india_january_note_requires_a_cropped_india_score_metric_with_january(self):
        note = "次年1月仅南部棉区晚期采摘／作物结束阶段参与评分；不是全印度统一启用，也不是下一季。"
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn(note, html)
        self.assertIn("function indiaJanuaryScoreNote(regionId,metric)", html)
        self.assertIn("regionId==='india'&&metric?.scale_type==='fixed_score_0_100'&&hasJanuary", html)
        self.assertIn("String(key).startsWith('01-')", html)
        self.assertIn("M=chartMetricForDisplay(M);\n        const indiaJanuaryNote=indiaJanuaryScoreNote(rid,M);", html)
        self.assertIn("inactiveText,indiaJanuaryNote].filter(Boolean).join(' ')", html)

        def displayed_metric(metric):
            keys = metric["day_keys"]
            start, end = metric.get("chart_display_start"), metric.get("chart_display_end")
            if not start or not end:
                return metric
            first, last = keys.index(start), keys.index(end)
            if last < first:
                return metric
            indexes = range(first, last + 1)
            return {
                **metric,
                "day_keys": [keys[index] for index in indexes],
            }

        def eligible(region_id, metric):
            shown = displayed_metric(metric)
            return (
                region_id == "india"
                and shown.get("scale_type") == "fixed_score_0_100"
                and any(key.startswith("01-") for key in shown.get("day_keys", []))
            )

        india_score = self.payload["seasonal"]["india"]["metrics"]["score"]
        self.assertTrue(eligible("india", india_score))
        southern_score = self.payload["subregion_seasonal"]["india"]["AP"]["metrics"]["score"]
        north_central_score = self.payload["subregion_seasonal"]["india"]["MH"]["metrics"]["score"]
        self.assertTrue(eligible("india", southern_score))
        self.assertFalse(eligible("india", north_central_score))
        india_raw = self.payload["seasonal"]["india"]["raw_metrics"]["tmax_14d_mean"]
        self.assertFalse(eligible("india", india_raw))
        brazil_score = self.payload["seasonal"]["brazil"]["metrics"]["root_zone_dryness"]
        self.assertFalse(eligible("brazil", brazil_score))

    def test_every_score_chart_hides_structurally_inactive_days_but_keeps_real_gaps(self):
        def display_indexes(metric):
            keys = metric["day_keys"]
            periods = metric.get("chart_display_periods")
            if periods is None and metric.get("chart_display_start"):
                periods = [{"start": metric["chart_display_start"], "end": metric["chart_display_end"]}]
            if not periods:
                return list(range(len(keys)))
            indexes = []
            for period in periods:
                start, end = keys.index(period["start"]), keys.index(period["end"])
                indexes.extend(range(start, end + 1) if end >= start else list(range(start, len(keys))) + list(range(0, end + 1)))
            return indexes

        score_metrics = []
        for bundle in self.payload["seasonal"].values():
            score_metrics.extend(bundle.get("metrics", {}).values())
        for subregions in self.payload["subregion_seasonal"].values():
            for bundle in subregions.values():
                score_metrics.extend(bundle.get("metrics", {}).values())
        self.assertGreater(len(score_metrics), 100)
        for metric in score_metrics:
            self.assertEqual(metric["scale_type"], "fixed_score_0_100")
            indexes = display_indexes(metric)
            self.assertTrue(indexes)
            self.assertFalse(
                any(metric["current_year_status"][index] == "inactive_stage" for index in indexes),
                (metric["label"], metric.get("chart_display_periods"), metric.get("active_periods")),
            )
            # Future and genuine source-gap statuses are intentionally not used
            # to crop the axis; only structural inactive-stage days are hidden.
            active_keys = {
                key
                for period in metric.get("active_periods", [])
                for key in window_keys(period["start"], period["end"])
            }
            meaningful_blank_statuses = {
                status
                for key, status in zip(metric["day_keys"], metric["current_year_status"])
                if key in active_keys and status in {"future", "source_gap"}
            }
            if meaningful_blank_statuses:
                retained = {metric["current_year_status"][index] for index in indexes}
                self.assertTrue(retained & meaningful_blank_statuses)

        al = self.payload["subregion_seasonal"]["us"]["AL"]["metrics"]
        self.assertEqual(
            (al["root_zone_dryness"]["chart_display_start"], al["root_zone_dryness"]["chart_display_end"]),
            ("05-01", "08-31"),
        )
        self.assertEqual(
            (al["harvest_rain"]["chart_display_start"], al["harvest_rain"]["chart_display_end"]),
            ("09-01", "11-30"),
        )
        # Raw-weather charts keep their full crop-season axis: missing raw data
        # must remain visible as a gap rather than being silently cropped.
        for subregions in self.payload["subregion_seasonal"].values():
            for bundle in subregions.values():
                for metric in bundle.get("raw_metrics", {}).values():
                    self.assertNotIn("chart_display_start", metric)
                    self.assertNotIn("chart_display_periods", metric)

    def test_v07_label_score_titles_raw_explanation_and_collapsed_weights(self):
        title = "全球棉花五大种植区域天气胁迫总评分（产区产量加权）"
        composite = self.payload["five_region_production_weighted_weather_stress_display"]
        self.assertEqual(composite["id"], "five_region_production_weighted_weather_stress_display")
        self.assertEqual(composite["label"], title)
        self.assertEqual(composite["seasonal_metric"]["label"], title)
        self.assertGreaterEqual(composite["current_score"], 0.0)
        self.assertLessEqual(composite["current_score"], 100.0)

        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("<title>棉花供需与天气胁迫看板 V0.7</title>", html)
        self.assertIn("<h1>棉花供需与天气胁迫看板 V0.7</h1>", html)
        self.assertIn('"dashboard_id": "cotton_public_supply_weather_dashboard_v0_7"', json.dumps(self.payload, ensure_ascii=False))
        self.assertIn("${r.name} · 国家／新疆整体天气因子原始数据", html)
        self.assertIn("${r.name} · 国家／新疆整体模型单因子评分", html)
        self.assertNotIn("当前原始天气（14日）", html)
        self.assertNotIn("模型天气胁迫因子", html)
        self.assertIn("温度/短波辐射为截至当日过去14天日值平均；降水为截至当日过去14天累计。", html)
        self.assertIn("四项均先按点位计算，再按代表网络空间聚合", html)
        self.assertIn("tmax_14d_mean:'Tmax日最高温度（14天移动平均）'", html)
        self.assertIn("tmin_14d_mean:'Tmin日最低温度（14天移动平均）'", html)
        self.assertIn("precip_14d_sum:'TP累计降水量（14天累计滚动值）'", html)
        self.assertIn("sw_rad_14d_mean:'SWd日短波辐射（14日移动平均）'", html)
        self.assertIn("const displayLabel=rawMetricDisplayLabels[metricId]||M.label", html)
        self.assertIn('data-chart-title="${escapeHtml(r.name)} · ${escapeHtml(displayLabel)}"', html)
        self.assertIn("class=\"chartable production-weighted-score\"", html)
        self.assertIn("class=\"production-score-value\"", html)
        self.assertIn("class=\"production-score-denominator\">/ 100", html)
        self.assertIn("font-size:clamp(4rem,6.6vw,5.35rem)", html)
        self.assertIn("font-size:clamp(3.4rem,16vw,4.3rem)", html)
        self.assertIn("panel.classList.add('cotton-score-hero')", html)
        self.assertIn("天气胁迫 · 五区产量加权展示分", html)
        self.assertIn("（产区产量加权 · 未校准）", html)
        self.assertIn("分数越高，表示当地天气理论胁迫越强；不是减产百分比，也未做产量校准", html)
        self.assertIn("查看总分季节图", html)
        self.assertIn("<span>覆盖产区</span>", html)
        self.assertIn("<span>加权口径</span><b>USDA 当前产量</b>", html)
        self.assertIn("Math.max(0,Math.min(100,Number(c.current_score)))", html)
        self.assertNotIn("0–39", html)
        self.assertNotIn("40–69", html)
        self.assertNotIn("70–100", html)
        self.assertIn('class="chart-shell"', html)
        self.assertIn('class="chart-meta-row"', html)
        self.assertIn('class="chart-meta-unit"', html)
        self.assertIn('class="chart-meta-note"', html)
        self.assertIn("H=270,padL=48,padR=16,padT=32,padB=34", html)
        self.assertIn("#chart-pop .chart-meta-row{display:block", html)
        self.assertIn("@media(max-width:1000px){.chart-modal .chart-meta-row{display:block", html)
        self.assertIn("flex:0 1 46%;max-width:46%", html)
        self.assertNotIn('y="17" font-size="11" fill="#64748b" text-anchor="end">单位：', html)
        self.assertIn("supplyAnchor.className='supply-anchor'", html)
        self.assertIn("supplyTable.insertAdjacentElement('beforebegin',supplyAnchor)", html)
        self.assertIn("classList.add('supply-table-section')", html)
        self.assertIn("<details class=\"production-weighted-details\"><summary>产量加权详情</summary>", html)
        self.assertIn("当地完整日；其他${currentRegionCount}区已更新至", html)
        self.assertIn("<span>最新地区日</span>", html)
        details_markup = re.search(r'<details class="production-weighted-details">(.*?)</details>', html, flags=re.DOTALL)
        self.assertIsNotNone(details_markup)
        self.assertIn("<table>", details_markup.group(1))
        self.assertNotIn("open", details_markup.group(0).split(">", 1)[0])
        self.assertIn('data-chart-title="${productionWeightedLabel}"', html)

    def test_all_frozen_contract_input_hashes_unchanged(self):
        mutable_daily_successors = {
            COTTON / "cn_xj_weather/derived/xinjiang_theoretical_weather_stress_index_v0_2_daily.csv",
            COTTON / "us_weather/derived/us_national_theoretical_weather_stress_index_v0_1_daily.csv",
            COTTON / "br_weather/derived/brazil_national_theoretical_weather_stress_index_v0_1_daily.csv",
            COTTON / "in_weather/derived/india_national_theoretical_weather_stress_index_v0_1_daily.csv",
        }
        for path, expected in FROZEN_INPUT_SHAS.items():
            if path in mutable_daily_successors:
                continue
            self.assertEqual(digest(path), expected, str(path))

    def test_frozen_raw_point_semantic_hashes_and_cutoff_append_invariance(self):
        for geography, expected in FROZEN_RAW_POINT_SEMANTIC_SHAS.items():
            config = builder.RAW_POINT_CONFIG[geography]
            with config["path"].open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            actual = raw_point_semantic_hash(config, rows)
            self.assertEqual(actual, expected, geography)

            point = config["points"][0]
            virtual_append = {
                "point_id": point,
                "date": (config["cutoff"] + timedelta(days=1)).isoformat(),
                "tmax": "999", "tmin": "-999", "precip": "888", "sw_rad": "777",
            }
            self.assertEqual(
                raw_point_semantic_hash(config, rows + [virtual_append]),
                actual,
                f"post-cutoff append changed the frozen raw semantic hash for {geography}",
            )

    def test_v07_payload_matches_predecessor_outside_declared_v02_successors_and_new_anomaly_series(self):
        previous = json.loads(subprocess.check_output(["git", "show", "20b703f:data.json"], cwd=ROOT, text=True))
        self.assertEqual(previous["supply"], self.payload["supply"])
        self.assertEqual(previous["limitations"], self.payload["limitations"])
        old_dates = {row["id"]: row["date"] for row in previous["regions"]}
        new_dates = {row["id"]: row["date"] for row in self.payload["regions"]}
        for region_id in old_dates:
            self.assertGreaterEqual(new_dates[region_id], old_dates[region_id])
        self.assertGreaterEqual(
            self.payload["five_region_production_weighted_weather_stress_display"]["common_cutoff_date"],
            previous["five_region_production_weighted_weather_stress_display"]["common_cutoff_date"],
        )

    def test_xinjiang_official_area_proxy_weights_are_explicit_and_reproducible(self):
        contract = json.loads(builder.XINJIANG_AREA_WEIGHT_PATH.read_text(encoding="utf-8"))
        china = next(region for region in self.payload["regions"] if region["id"] == "china")
        details = {row["id"]: row for row in china["network_details"]}
        self.assertEqual(set(details), set(builder.XINJIANG_SUBREGIONS))
        self.assertAlmostEqual(sum(row["production_weight_share"] for row in details.values()), 1.0, places=12)
        self.assertAlmostEqual(contract["represented_area_coverage_of_xinjiang_2022"], 2480.42 / (2496.89 * 1.5), places=12)
        for key, row in details.items():
            source = contract["groups"][key]
            self.assertEqual(row["weight_type"], "official_cotton_area_proxy")
            self.assertEqual(row["weight_area_10k_mu"], source["area_10k_mu"])
            self.assertEqual(row["production_weight_share"], source["weight_share_within_displayed_groups"])
            self.assertAlmostEqual(row["weight_coverage_of_xinjiang_2022"], contract["represented_area_coverage_of_xinjiang_2022"], places=12)

    def test_every_subregion_has_local_raw_seasonality_and_honest_score_status(self):
        expected_counts = {"china": 7, "us": 16, "brazil": 11, "india": 10, "australia": 8}
        self.assertEqual({key: len(value) for key, value in self.payload["subregion_seasonal"].items()}, expected_counts)
        for region in self.payload["regions"]:
            shares = [row["production_weight_share"] for row in region["network_details"] if row["production_weight_share"] is not None]
            self.assertEqual(shares, sorted(shares, reverse=True), region["id"])
            bundles = self.payload["subregion_seasonal"][region["id"]]
            for detail in region["network_details"]:
                bundle = bundles[detail["id"]]
                self.assertEqual(set(bundle["raw_metrics"]), set(builder.RAW_LABELS))
                for metric in bundle["raw_metrics"].values():
                    self.assertEqual(len(metric["day_keys"]), len(metric["current_year"]))
                    self.assertEqual(len(metric["day_keys"]), len(metric["history_min"]))
                if detail.get("factor_detail_status") == "source_revision_mismatch":
                    self.assertEqual(bundle["status"], "source_revision_mismatch")
                    self.assertEqual(bundle["metrics"], {})
                else:
                    self.assertEqual(bundle["status"], "available")
                    self.assertIn("score", bundle["metrics"])
                    self.assertTrue(any(value is not None for value in bundle["metrics"]["score"]["history_min"]))
        for region_id, subregion_id in (("us", "TX"), ("brazil", "MT"), ("india", "GJ")):
            self.assertIn("score", self.payload["subregion_seasonal"][region_id][subregion_id]["metrics"])

    def test_subregion_chart_current_values_match_displayed_local_values(self):
        for region in self.payload["regions"]:
            bundles = self.payload["subregion_seasonal"][region["id"]]
            for detail in region["network_details"]:
                bundle = bundles[detail["id"]]
                for metric_id, displayed in (detail.get("raw_weather") or {}).get("values", {}).items():
                    if metric_id.endswith("_unit") or metric_id not in bundle["raw_metrics"] or displayed is None:
                        continue
                    metric = bundle["raw_metrics"][metric_id]
                    key = metric["display_cutoff_date"][5:]
                    self.assertAlmostEqual(metric["current_year"][metric["day_keys"].index(key)], displayed, places=3)
                if bundle["status"] != "available":
                    continue
                score_metric = bundle["metrics"]["score"]
                key = score_metric["display_cutoff_date"][5:]
                self.assertAlmostEqual(score_metric["current_year"][score_metric["day_keys"].index(key)], detail["score"], places=2)

    def test_subregion_missing_and_zero_factor_reasons_are_specific(self):
        allowed = {"inactive_stage", "data_or_reference_gap", "source_revision_mismatch", "available_zero", "available_signal"}
        for region in self.payload["regions"]:
            for detail in region["network_details"]:
                self.assertIn("score_diagnostic", detail)
                self.assertTrue(detail["score_diagnostic"]["reason"])
                diagnostics = detail.get("factor_diagnostics") or {}
                self.assertEqual(set(diagnostics), set(detail.get("factor_scores") or {}))
                for factor, value in (detail.get("factor_scores") or {}).items():
                    diagnostic = diagnostics[factor]
                    self.assertIn(diagnostic["status"], allowed)
                    self.assertTrue(diagnostic["reason"])
                    if value is None:
                        self.assertIn(diagnostic["status"], {"inactive_stage", "data_or_reference_gap", "source_revision_mismatch"})
                    elif abs(float(value)) < 1e-12:
                        self.assertEqual(diagnostic["status"], "available_zero")
                        self.assertIn("未落入", diagnostic["reason"])

        # Daily refreshes can legitimately move a factor from zero to signal or
        # clear a prior source-revision mismatch.  The generic assertions above
        # validate each current diagnostic against its actual value.

    def test_page_and_publish_files_are_synced_and_safe(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        for phrase in ("全球供需锚点", "五个棉区天气胁迫", "分区域查看", "查看区域详情", "当前国家／地区", "国家内部产区", "选择地区查看具体因子", "当前所选地区", "展开完整州／邦／AOI 表格", "全球棉花五大种植区域天气胁迫总评分（产区产量加权）", "产量加权详情", "共同截止", "中亚五国天气观察", "10 个 AOI", "天气异常度 10/10 可用", "棉花胁迫分 0/10 可用", "官方供需明细", "暂无可用值", "历史季节性图", "attachCharts", "澳大利亚 USDA 官方供需变化已接入", "USDA产量变化", "USDA期末库存变化", "国内消费变化率", "看板 V0.7", "USDA供需截止", "天气因子原始数据", "模型天气胁迫单因子评分", "Tmax日最高温度（14天移动平均）", "Tmin日最低温度（14天移动平均）", "TP累计降水量（14天累计滚动值）", "SWd日短波辐射（14日移动平均）", "MJ/m²/日", "天气原值与理论分数均未换算为 USDA 产量", "太阳辐射模型状态："):
            self.assertIn(phrase, html)
        self.assertIn("<title>棉花供需与天气胁迫看板 V0.7</title>", html)
        self.assertNotIn("看板 V0.5", html)
        self.assertIn("正式 global_numeric_weather_score 仍未生成；上方五区产量加权分仅为展示合成，未执行天气到供给数量的换算。", html)
        self.assertIn("M.solar_display_status", html)
        self.assertIn("displayDate=M.display_cutoff_date||r.date||''", html)
        self.assertIn("data-chart-subregion", html)
        self.assertIn("DATA.subregion_seasonal", html)
        self.assertIn("官方面积代理权重", html)
        self.assertIn("当地当前生育阶段未启用该因子", (ROOT / "data.json").read_text(encoding="utf-8"))
        self.assertIn("0.00 是已计算且未落入历史不利尾部", html)
        self.assertIn("first.insertAdjacentHTML('beforebegin',weightedPanel(c))", html)
        self.assertNotIn("澳大利亚未接入官方供需数量", html)
        self.assertNotIn("bullish", html.lower())
        self.assertNotIn("bearish", html.lower())
        self.assertNotIn("NaN", html)
        self.assertNotIn("Infinity", html)
        self.assertEqual((ROOT / "index.html").read_bytes(), (ROOT / "dist/index.html").read_bytes())
        self.assertEqual((ROOT / "data.json").read_bytes(), (ROOT / "dist/data.json").read_bytes())
        payload_text = (ROOT / "data.json").read_text(encoding="utf-8")
        self.assertNotIn("NaN", payload_text)
        self.assertNotIn("Infinity", payload_text)

    def test_inline_javascript_is_syntax_valid_when_node_is_available(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is not installed")
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        scripts = re.findall(r"<script>(.*?)</script>", html, flags=re.DOTALL)
        self.assertGreaterEqual(len(scripts), 2)
        with tempfile.TemporaryDirectory() as temp_dir:
            script_path = Path(temp_dir) / "dashboard_inline.js"
            script_path.write_text("\n".join(scripts), encoding="utf-8")
            result = subprocess.run([node, "--check", str(script_path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_published_data_fetch_is_versioned_for_cache_busting(self):
        for page in (ROOT / "index.html", ROOT / "dist/index.html"):
            html = page.read_text(encoding="utf-8")
            self.assertIn("fetch(`./data.json?ts=${Date.now()}`,{cache:'no-store'})", html)
            self.assertNotIn("fetch('./data.json')", html)

    def test_temp_builder_is_deterministic(self):
        payload_a = builder.build()
        payload_b = builder.build()
        self.assertEqual((json.dumps(payload_a, ensure_ascii=False, indent=2) + "\n").encode(), (json.dumps(payload_b, ensure_ascii=False, indent=2) + "\n").encode())
        self.assertEqual((ROOT / "data.json").read_bytes(), (ROOT / "dist/data.json").read_bytes())


if __name__ == "__main__":
    unittest.main(verbosity=2)
