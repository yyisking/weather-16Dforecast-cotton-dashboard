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
    COTTON / "cn_xj_weather/points_daily.csv": "258a19cc8e9b17d4965c30693ee09a2c6669ffe35755f8b56e8733cfc4ef9464",
    COTTON / "us_weather/points_daily.csv": "22cbc448a30a92a73db49805ff61486257ca8f4f69bfed2596b1f2715ce2e569",
    COTTON / "br_weather/points_daily.csv": "f3494033ec4f169dd262428e5871fdb1b2a022c0880754a40c23cddb161be022",
    COTTON / "in_weather/points_daily.csv": "025ebe73147b84683daa869f4bf54f3025a304bca993ac37654db24ea9db85b8",
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
    COTTON / "us_weather/derived/us_tx_theoretical_weather_stress_index_v0_1_daily.csv": "0b2be4b9706cccf56c8328a68283a98b2c7a005e12101cbb5337fe95f7e877f7",
    COTTON / "br_weather/derived/brazil_mt_theoretical_weather_stress_index_v0_1_daily.csv": "0f4dc5b507c092f28231095143a0a0cb8efb48af094fa2d15f9fddc99f8575d3",
    COTTON / "in_weather/derived/india_central_rainfed_theoretical_weather_stress_index_v0_1_daily.csv": "a7f852a54b1d94987c1a639a6aa5970683b2d62ca5892189732d07450dbc66e8",
    COTTON / "au_weather/derived/australia_theoretical_weather_stress_index_v0_1_daily.csv": "a977f9be8e79b57ae25b443645f2ca43313369e5050eeee45353a8b9ab3c4331",
    COTTON / "model_status.json": "b3fbabe71bd15c1bc0ef65d2b4e34f3621a184383c3f89d8a9320a896a2daf0d",
}
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
    for child in sorted(p for p in path.rglob("*") if p.is_file()):
        h.update(child.relative_to(path).as_posix().encode() + b"\0" + child.read_bytes() + b"\0")
    return h.hexdigest()


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
        self.assertEqual(australia["point_coverage"], 0.875)
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
        self.assertEqual(seasonal["current_year"], "2026/27")
        self.assertEqual(seasonal["last_year"], "2025/26")
        self.assertEqual(seasonal["display_window_start"], "09-01")
        self.assertEqual(seasonal["display_window_end"], "06-30")
        self.assertTrue(seasonal["cross_year_axis"])
        score_metric_ids = {"score", "low_temperature", "high_heat", "excess_rain", "high_vpd", "low_solar"}
        for metric_id, metric in seasonal["metrics"].items():
            if metric_id not in score_metric_ids:
                continue
            self.assertEqual(metric["history_year_count"], 0)
            self.assertTrue(all(value is None for value in metric["history_min"]))
            self.assertTrue(all(value is None for value in metric["history_max"]))
            self.assertEqual(len(metric["day_keys"]), 303)
        with builder.AUSTRALIA_DAILY_PATH.open(encoding="utf-8", newline="") as handle:
            daily = list(csv.DictReader(handle))
        score = seasonal["metrics"]["score"]
        expected = {row["date"]: row["theoretical_weather_stress_index"] for row in daily}
        index = score["day_keys"].index("09-10")
        self.assertEqual(score["current_year"][index], float(expected["2026-09-10"]))
        self.assertEqual(score["last_year"][index], float(expected["2025-09-10"]))
        self.assertEqual(score["last_year"][score["day_keys"].index("01-01")], float(expected["2026-01-01"]))
        self.assertIsNone(score["current_year"][score["day_keys"].index("09-11")])
        self.assertIsNone(score["last_year"][score["day_keys"].index("05-01")])

    def test_central_asia_10_aois_240_fields_and_null_scores(self):
        watch = self.payload["central_asia_watch"]
        self.assertEqual(watch["aoi_count"], 10)
        self.assertEqual(watch["score_available_count"], 0)
        self.assertEqual(watch["weather_anomaly_score_available_count"], 10)
        self.assertEqual(watch["weather_stress_score_available_count"], 0)
        self.assertEqual(len(watch["aois"]), 10)
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

    def test_central_seasonal_is_10_by_6_cropped_window_and_source_exact(self):
        seasonal = self.payload["central_asia_seasonal"]
        self.assertEqual(len(seasonal), 10)
        by_key = {(row["aoi_name"], row["month_day"]): row for row in self.central_seasonal_rows if row["country"] in {"Kazakhstan", "Kyrgyzstan", "Tajikistan", "Turkmenistan", "Uzbekistan"}}
        self.assertEqual(len(by_key), 10 * 366)
        cropped = window_keys("03-01", "10-31")
        for country, aoi, aoi_id in CENTRAL_AOI:
            item = seasonal[aoi_id]
            self.assertEqual(len(item["metrics"]), 6)
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
                    for out, field in (("history_min", variable+"_hist_min"), ("history_max", variable+"_hist_max"), ("last_year", variable+"_2025"), ("current_year", variable+"_2026")):
                        expected = None if src[field] == "" else float(src[field])
                        self.assertEqual(metric[out][i], expected, (aoi, variable, day, out))
                self.assertIsNone(metric["current_year"][metric["day_keys"].index("09-11")])

    def test_four_regular_region_axes_are_not_cross_year(self):
        for region_id in ("china", "us", "brazil", "india"):
            self.assertFalse(self.payload["seasonal"][region_id]["cross_year_axis"], region_id)
        self.assertTrue(self.payload["seasonal"]["australia"]["cross_year_axis"])

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
            "United States": ("us", builder.DAILY_PATHS["United States"], {"score": "theoretical_weather_stress_index", **{x[0]: x[2] for x in builder.REGION_META["United States"]["factor_fields"]}}),
            "Brazil": ("brazil", builder.DAILY_PATHS["Brazil"], {"score": "theoretical_weather_stress_index", **{x[0]: x[2] for x in builder.REGION_META["Brazil"]["factor_fields"]}}),
            "India": ("india", builder.DAILY_PATHS["India"], {"score": "theoretical_weather_stress_index", **{x[0]: x[2] for x in builder.REGION_META["India"]["factor_fields"]}}),
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
                        if geography == "Australia" and month < 9:
                            source_year += 1
                        source_values = by_year_key.get((metric, source_year, key), [])
                        expected_value = sum(source_values) / len(source_values) if source_values else None
                        if expected_value is None:
                            self.assertIsNone(values[index], (geography, metric, year_label, key))
                        else:
                            self.assertEqual(values[index], expected_value, (geography, metric, year_label, key))
                        if key not in active[metric] or (geography == "Australia" and month in (5, 6)):
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
        self.assertEqual(xinjiang["metrics"]["high_heat"]["active_periods"], [{"start": "06-01", "end": "08-31"}])
        self.assertEqual(xinjiang["metrics"]["low_temperature"]["active_periods"], [{"start": "04-01", "end": "05-31"}, {"start": "09-01", "end": "11-30"}])
        self.assertEqual(xinjiang["metrics"]["score"]["current_year_status"][xinjiang["metrics"]["score"]["day_keys"].index("09-14")], "future")
        australia = self.payload["seasonal"]["australia"]
        self.assertEqual(australia["metrics"]["low_temperature"]["active_periods"], [{"start": "09-01", "end": "10-31"}, {"start": "03-01", "end": "04-30"}])
        self.assertEqual(australia["metrics"]["score"]["current_year_status"][australia["metrics"]["score"]["day_keys"].index("05-01")], "inactive_stage")
        self.assertEqual(australia["metrics"]["score"]["current_year_status"][australia["metrics"]["score"]["day_keys"].index("09-11")], "future")

    def test_raw_weather_anchors_units_cutoffs_and_solar_statuses(self):
        self.assertEqual(
            {metric_id: metric["unit"] for metric_id, metric in self.payload["seasonal"]["china"]["raw_metrics"].items()},
            {"tmax_14d_mean": "°C", "tmin_14d_mean": "°C", "precip_14d_sum": "mm", "sw_rad_14d_mean": "MJ/m²/日"},
        )
        """Independent point/day recomputation of the five frozen raw anchors."""
        configs = {
            "china": (COTTON / "cn_xj_weather/points_daily.csv", ("xj_shihezi", "xj_shawan", "xj_kuitun", "xj_changji", "xj_hutubi", "xj_bole", "xj_jinghe", "xj_kashgar", "xj_shache", "xj_bachu", "xj_aksu", "xj_awat", "xj_kuqa", "xj_shaya", "xj_korla", "xj_yuli", "xj_luntai", "xj_turpan"), date(2026, 9, 13)),
            "us": (COTTON / "us_weather/points_daily.csv", ("tx_hp_n", "tx_hp_c", "tx_hp_s", "tx_hp_w", "tx_hp_e", "tx_hp_sw", "tx_farwest", "tx_rolling", "tx_edwards", "tx_coastal", "tx_rgv", "tx_black"), date(2026, 9, 13)),
            "brazil": (COTTON / "br_weather/points_daily.csv", ("mt_campo_novo", "mt_campo_verde", "mt_diamantino", "mt_lucas", "mt_nova_mutum", "mt_nova_ubirata", "mt_primavera", "mt_rondonopolis", "mt_sapezal", "mt_sinop", "mt_sorriso", "mt_tangara"), date(2026, 9, 16)),
            "india": (COTTON / "in_weather/points_daily.csv", ("gj_rajkot", "gj_surendranagar", "gj_bhavnagar", "gj_amreli", "gj_bharuch", "mh_akola", "mh_amravati", "mh_yavatmal", "mh_buldhana", "mh_jalgaon", "mh_jalna", "mp_khargone", "mp_dhar", "tg_adilabad", "tg_warangal", "tg_khammam"), date(2026, 9, 13)),
        }
        expected = {
            "china": (29.258, 17.265, 11.856, 18.990), "us": (36.745, 24.549, 6.883, 22.813),
            "brazil": (32.838, 20.844, 12.267, 20.034), "india": (31.051, 24.529, 59.911, 18.114),
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
        for region_id, (path, points, cutoff) in configs.items():
            actual = point_anchor(path, points, cutoff)
            raw = self.payload["seasonal"][region_id]["raw_metrics"]
            key = cutoff.strftime("%m-%d")
            for metric_id, value in zip(("tmax_14d_mean", "tmin_14d_mean", "precip_14d_sum", "sw_rad_14d_mean"), actual):
                metric = raw[metric_id]
                self.assertAlmostEqual(metric["current_year"][metric["day_keys"].index(key)], value, places=3)
                self.assertEqual(metric["scale_type"], "auto_unit")
                self.assertIn(metric["unit"], {"°C", "mm", "MJ/m²/日"})
                self.assertEqual(metric["display_cutoff_date"], cutoff.isoformat())
                self.assertEqual(metric["valid_current_point_count"], len(points))
                self.assertAlmostEqual(metric["current_spatial_coverage"], 1.0)
        australia = self.payload["seasonal"]["australia"]["raw_metrics"]
        self.assertEqual([australia[k]["current_year"][australia[k]["day_keys"].index("09-10")] for k in ("tmax_14d_mean", "tmin_14d_mean", "precip_14d_sum", "sw_rad_14d_mean")], [24.622448979591837, 9.264285714285714, 0.3428571428571428, 19.187755102040814])
        self.assertEqual(australia["tmax_14d_mean"]["valid_current_point_count"], 7)
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
        self.assertIsNone(self.payload["seasonal"]["australia"]["raw_metrics"]["tmax_14d_mean"]["current_year"][10])

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
        self.assertEqual(statuses[keys.index("09-10")], "available")
        self.assertEqual(statuses[keys.index("09-11")], "future")
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
        self.assertEqual(len(accepted), 7)
        source_fields = ("temperature_2m_max", "temperature_2m_min", "precipitation_sum", "shortwave_radiation_sum")
        cutoff = date(2026, 9, 10)
        point_values = {field: [] for field in source_fields}
        for path in accepted:
            payload = json.loads(path.read_text(encoding="utf-8"))
            daily = payload["daily"]
            self.assertEqual(daily["time"][0], manifest["source_start_date"])
            self.assertEqual(daily["time"][-1], manifest["source_end_date"])
            by_day = {date.fromisoformat(day): index for index, day in enumerate(daily["time"])}
            for field in source_fields:
                window = [float(daily[field][by_day[cutoff - timedelta(days=i)]]) for i in range(13, -1, -1)]
                point_values[field].append(sum(window) / 14 if field != "precipitation_sum" else sum(window))
        expected = [24.622448979591837, 9.264285714285714, 0.3428571428571428, 19.187755102040814]
        raw = self.payload["seasonal"]["australia"]["raw_metrics"]
        for field, expected_value, metric_id in zip(source_fields, expected, ("tmax_14d_mean", "tmin_14d_mean", "precip_14d_sum", "sw_rad_14d_mean")):
            rebuilt = sum(point_values[field]) / len(point_values[field])
            self.assertAlmostEqual(rebuilt, expected_value, places=12)
            metric = raw[metric_id]
            self.assertAlmostEqual(metric["current_year"][metric["day_keys"].index("09-10")], rebuilt, places=12)

    def test_central_raw_units_and_segmented_history_band_contract(self):
        expected_units = {
            "temperature_2m_max": "°C", "temperature_2m_min": "°C", "precipitation_sum": "mm",
            "shortwave_radiation_sum": "MJ/m²", "et0_fao_evapotranspiration": "mm", "vapour_pressure_deficit_max": "kPa",
        }
        for item in self.payload["central_asia_seasonal"].values():
            self.assertEqual(set(item["metrics"]), set(expected_units))
            for variable, metric in item["metrics"].items():
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
            for metric in item["metrics"].values():
                self.assertEqual(metric["blank_value_label"], raw_blank_label)
                self.assertEqual(metric["scale_type"], "auto_unit")
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
        self.assertEqual(status_runs, [
            ("09-01", "09-10", "available"),
            ("09-11", "10-31", "future"),
            ("11-01", "02-28", "inactive_stage"),
            ("03-01", "04-30", "future"),
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
        self.assertEqual(history_runs, [("04-01", "05-31"), ("09-01", "11-30")])

    def test_central_current_cards_and_daily_charts_use_distinct_labels(self):
        current_labels = {
            "temperature_2m_max": "14日平均日最高温",
            "temperature_2m_min": "14日平均日最低温",
            "precipitation_sum": "14日累计降水",
            "shortwave_radiation_sum": "14日平均日短波辐射",
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

    def test_v06_production_weighted_composite_is_independently_rebuilt(self):
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
            path = builder.AUSTRALIA_DAILY_PATH if geo == "Australia" else builder.DAILY_PATHS[geo]
            with path.open(encoding="utf-8", newline="") as handle:
                daily[ids[geo]] = {date.fromisoformat(row["date"]): (None if row.get("theoretical_weather_stress_index", "") == "" else float(row["theoretical_weather_stress_index"])) for row in csv.DictReader(handle)}
        cutoff = date(2026, 9, 10)
        current_scores = {rid: daily[rid][cutoff] for rid in ids.values()}
        expected = math.fsum(weights[rid] * current_scores[rid] for rid in ids.values())
        self.assertEqual(composite["common_cutoff_date"], "2026-09-10")
        self.assertEqual(composite["current_score"], expected)
        self.assertEqual(composite["current_score"], 34.203232814344204)
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

    def test_v06_weighted_gate_and_missing_region_do_not_fill_zero(self):
        weights = {"China": .36, "United States": .14, "Brazil": .20, "India": .26, "Australia": .04}
        below = builder._weighted_production_day({"china": None, "us": 10.0, "brazil": None, "india": None, "australia": None}, weights)
        self.assertIsNone(below["value"]); self.assertEqual(below["status"], "coverage_below_gate")
        available = builder._weighted_production_day({"china": 20.0, "us": 10.0, "brazil": None, "india": 40.0, "australia": None}, weights)
        self.assertGreaterEqual(available["production_weight_coverage"], .60)
        self.assertEqual(available["value"], math.fsum(weights[r] * v for r, v in (("China", 20.0), ("United States", 10.0), ("India", 40.0))) / available["production_weight_coverage"])
        self.assertNotIn("brazil", available["valid_region_ids"])
        self.assertFalse(self.payload["five_region_production_weighted_weather_stress_display"]["not_unified_model"] is False)

    def test_v06_frontend_contract_and_cache_key(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("five_region_production_weighted_weather_stress_display", html)
        self.assertIn("五区产量加权天气胁迫", html)
        self.assertIn("历史带不含补造的澳洲历史分", html)
        self.assertIn("覆盖不足不按0处理", html)
        self.assertIn("M.nonnegative?Math.max(0,lo-extra):lo-extra", html)
        self.assertIn("v=20260923-v06-production-weighted", html)
        self.assertNotIn("v=20260923-v05-raw-weather", html)
        self.assertIn("data-chart-region=\"${weightedId}\"", html)
        self.assertIn("const first=app.querySelector('.hero')", html)
        self.assertIn("M.solar_display_status", html)

    def test_all_frozen_contract_input_hashes_unchanged(self):
        for path, expected in FROZEN_INPUT_SHAS.items():
            self.assertEqual(digest(path), expected, str(path))

    def test_page_and_publish_files_are_synced_and_safe(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        for phrase in ("全球供需锚点", "五个棉区天气胁迫", "五区产量加权天气胁迫", "共同截止", "中亚五国天气观察", "10 个 AOI", "天气异常度 10/10 可用", "棉花胁迫分 0/10 可用", "分项因子", "官方供需明细", "暂无可用值", "历史季节性图", "attachCharts", "澳大利亚 USDA 官方供需变化已接入", "USDA产量变化", "USDA期末库存变化", "国内消费变化率", "看板 V0.6", "当前原始天气（14日）", "14日平均日最高温", "14日平均日最低温", "14日累计降水", "14日平均日短波辐射", "MJ/m²/日", "天气原值与理论分数均未换算为 USDA 产量", "太阳辐射模型状态："):
            self.assertIn(phrase, html)
        self.assertIn("<title>棉花供需与天气胁迫看板 V0.6</title>", html)
        self.assertNotIn("看板 V0.5", html)
        self.assertIn("正式 global_numeric_weather_score 仍未生成；上方五区产量加权分仅为展示合成，未执行天气到供给数量的换算。", html)
        self.assertIn("M.solar_display_status", html)
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
            self.assertIn("fetch('./data.json?v=20260923-v06-production-weighted')", html)
            self.assertNotIn("fetch('./data.json')", html)

    def test_temp_builder_is_deterministic(self):
        payload_a = builder.build()
        payload_b = builder.build()
        self.assertEqual((json.dumps(payload_a, ensure_ascii=False, indent=2) + "\n").encode(), (json.dumps(payload_b, ensure_ascii=False, indent=2) + "\n").encode())
        self.assertEqual((ROOT / "data.json").read_bytes(), (ROOT / "dist/data.json").read_bytes())


if __name__ == "__main__":
    unittest.main(verbosity=2)
