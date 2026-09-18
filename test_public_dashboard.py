#!/usr/bin/env python3
"""Independent source-to-payload checks for the public dashboard extension."""

from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from datetime import date
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
KEYS = []
cursor = date(2001, 1, 1)
while cursor.year == 2001:
    if cursor.month != 2 or cursor.day != 29:
        KEYS.append(cursor.strftime("%m-%d"))
    cursor = date.fromordinal(cursor.toordinal() + 1)


def digest(path: Path) -> str:
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    h = hashlib.sha256()
    for child in sorted(p for p in path.rglob("*") if p.is_file()):
        h.update(child.relative_to(path).as_posix().encode() + b"\0" + child.read_bytes() + b"\0")
    return h.hexdigest()


def protected_paths() -> tuple[Path, ...]:
    candidates = [
        COTTON / "au_weather",
        COTTON / "research/derived/australia_central_asia_cotton_variable_watch_v0_2.csv",
        COTTON / "research/derived/australia_central_asia_cotton_era5_daily_seasonality_v0_2.csv",
        COTTON / "research/derived/central_asia_cotton_current_weather_watch_v0_1.json",
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
        self.assertEqual(australia["point_coverage"], 0.875)
        self.assertEqual(australia["supply_risk_reading"], "未接入澳洲官方供需数量；天气指数未换算产量")
        factors = {factor["id"]: factor for factor in australia["factors"]}
        self.assertEqual(set(factors), {"low_temperature", "high_heat", "excess_rain", "high_vpd", "low_solar"})
        self.assertIsNone(factors["high_heat"]["score"])
        self.assertEqual(factors["high_heat"]["status"], "not_available_or_inactive")
        self.assertEqual(factors["low_temperature"]["score"], self.au_latest["low_temperature_score"])
        self.assertEqual(factors["low_solar"]["score"], self.au_latest["low_solar_score"])

    def test_existing_region_scores_and_null_factors_are_preserved(self):
        for region in self.payload["regions"][:4]:
            raw = json.loads(builder.REGION_PATHS[region["geography"]].read_text(encoding="utf-8"))
            self.assertEqual(region["score"], raw["theoretical_weather_stress_index"])
        brazil = next(region for region in self.payload["regions"] if region["id"] == "brazil")
        unavailable = [factor for factor in brazil["factors"] if factor["score"] is None]
        self.assertGreaterEqual(len(unavailable), 1)
        self.assertTrue(all(factor["status"] == "not_available_or_inactive" for factor in unavailable))

    def test_australia_seasonal_has_no_fabricated_history_and_daily_rebuild(self):
        seasonal = self.payload["seasonal"]["australia"]
        self.assertEqual(seasonal["current_year"], 2026)
        self.assertEqual(seasonal["last_year"], 2025)
        for metric in seasonal["metrics"].values():
            self.assertEqual(metric["history_year_count"], 0)
            self.assertTrue(all(value is None for value in metric["history_min"]))
            self.assertTrue(all(value is None for value in metric["history_max"]))
            self.assertEqual(len(metric["day_keys"]), 365)
        with builder.AUSTRALIA_DAILY_PATH.open(encoding="utf-8", newline="") as handle:
            daily = list(csv.DictReader(handle))
        score = seasonal["metrics"]["score"]
        expected = {row["date"]: row["theoretical_weather_stress_index"] for row in daily}
        index = score["day_keys"].index("09-10")
        self.assertEqual(score["current_year"][index], float(expected["2026-09-10"]))
        self.assertEqual(score["last_year"][index], float(expected["2025-09-10"]))
        self.assertIsNone(score["current_year"][score["day_keys"].index("09-11")])

    def test_central_asia_10_aois_240_fields_and_null_scores(self):
        watch = self.payload["central_asia_watch"]
        self.assertEqual(watch["aoi_count"], 10)
        self.assertEqual(watch["score_available_count"], 0)
        self.assertEqual(len(watch["aois"]), 10)
        source_by = {(row["country"], row["aoi_name"]): row for row in self.central_watch["aois"]}
        for actual in watch["aois"]:
            source = source_by[(actual["country"], actual["aoi_name"])]
            for variable in VARIABLES:
                for suffix in ("current", "change_yoy", "percentile", "band"):
                    field = variable + "_" + suffix
                    self.assertEqual(actual[field], source[field])
            self.assertIsNone(actual["weather_stress_score"])
        self.assertEqual(sum(1 for row in watch["aois"] for v in VARIABLES for s in ("current", "change_yoy", "percentile", "band") if row[v+"_"+s] is not None), 240)

    def test_central_seasonal_is_10_by_6_by_365_and_source_exact(self):
        seasonal = self.payload["central_asia_seasonal"]
        self.assertEqual(len(seasonal), 10)
        by_key = {(row["aoi_name"], row["month_day"]): row for row in self.central_seasonal_rows if row["country"] in {"Kazakhstan", "Kyrgyzstan", "Tajikistan", "Turkmenistan", "Uzbekistan"}}
        self.assertEqual(len(by_key), 10 * 366)
        for country, aoi, aoi_id in CENTRAL_AOI:
            item = seasonal[aoi_id]
            self.assertEqual(len(item["metrics"]), 6)
            self.assertEqual(item["gap_codes"], by_key[(aoi, "01-01")]["gap_codes"].split(";"))
            for variable in VARIABLES:
                metric = item["metrics"][variable]
                self.assertEqual(len(metric["day_keys"]), 365)
                for i, day in enumerate(KEYS):
                    src = by_key[(aoi, day)]
                    for out, field in (("history_min", variable+"_hist_min"), ("history_max", variable+"_hist_max"), ("last_year", variable+"_2025"), ("current_year", variable+"_2026")):
                        expected = None if src[field] == "" else float(src[field])
                        self.assertEqual(metric[out][i], expected, (aoi, variable, day, out))
                self.assertIsNone(metric["current_year"][metric["day_keys"].index("09-11")])

    def test_central_current_cards_and_daily_charts_use_distinct_labels(self):
        current_labels = {
            "temperature_2m_max": "14日平均最高温",
            "temperature_2m_min": "14日平均最低温",
            "precipitation_sum": "14日累计降水",
            "shortwave_radiation_sum": "14日累计短波辐射",
            "et0_fao_evapotranspiration": "14日累计参考蒸散",
            "vapour_pressure_deficit_max": "14日平均最大VPD",
        }
        daily_labels = {
            "temperature_2m_max": "日最高温",
            "temperature_2m_min": "日最低温",
            "precipitation_sum": "日降水",
            "shortwave_radiation_sum": "日短波辐射",
            "et0_fao_evapotranspiration": "日参考蒸散",
            "vapour_pressure_deficit_max": "日最大VPD",
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
        self.assertNotIn("precipitation_sum:'14日降水'", html)
        self.assertNotIn("shortwave_radiation_sum:'14日短波辐射'", html)
        self.assertNotIn("et0_fao_evapotranspiration:'14日参考蒸散'", html)

    def test_global_supply_and_comparability_gates(self):
        self.assertEqual(self.payload["scored_region_count"], 5)
        self.assertEqual(self.payload["descriptive_only_aoi_count"], 10)
        self.assertIsNone(self.payload["global_numeric_weather_score"])
        self.assertFalse(self.payload["cross_region_weather_comparable"])
        self.assertFalse(self.payload["weather_to_supply_conversion_performed"])

    def test_page_and_publish_files_are_synced_and_safe(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        for phrase in ("全球供需锚点", "五个棉区天气胁迫", "中亚五国天气观察", "10 个 AOI", "综合分 0/10 可用", "分项因子", "官方供需明细", "暂无可用值", "历史季节性图", "attachCharts"):
            self.assertIn(phrase, html)
        self.assertNotIn("bullish", html.lower())
        self.assertNotIn("bearish", html.lower())
        self.assertNotIn("NaN", html)
        self.assertNotIn("Infinity", html)
        self.assertEqual((ROOT / "index.html").read_bytes(), (ROOT / "dist/index.html").read_bytes())
        self.assertEqual((ROOT / "data.json").read_bytes(), (ROOT / "dist/data.json").read_bytes())
        payload_text = (ROOT / "data.json").read_text(encoding="utf-8")
        self.assertNotIn("NaN", payload_text)
        self.assertNotIn("Infinity", payload_text)

    def test_published_data_fetch_is_versioned_for_cache_busting(self):
        for page in (ROOT / "index.html", ROOT / "dist/index.html"):
            html = page.read_text(encoding="utf-8")
            self.assertIn("fetch('./data.json?v=20260918-v02')", html)
            self.assertNotIn("fetch('./data.json')", html)

    def test_temp_builder_is_deterministic(self):
        payload_a = builder.build()
        payload_b = builder.build()
        self.assertEqual((json.dumps(payload_a, ensure_ascii=False, indent=2) + "\n").encode(), (json.dumps(payload_b, ensure_ascii=False, indent=2) + "\n").encode())
        self.assertEqual((ROOT / "data.json").read_bytes(), (ROOT / "dist/data.json").read_bytes())


if __name__ == "__main__":
    unittest.main(verbosity=2)
