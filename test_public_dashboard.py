#!/usr/bin/env python3
"""Independent source-to-payload checks for the public dashboard extension."""

from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from decimal import Decimal, ROUND_HALF_UP
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
        for metric in seasonal["metrics"].values():
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

    def test_central_raw_units_and_segmented_history_band_contract(self):
        for item in self.payload["central_asia_seasonal"].values():
            for metric in item["metrics"].values():
                self.assertEqual(metric["scale_type"], "auto_unit")
                self.assertIsNone(metric["scale_min"])
                self.assertIsNone(metric["scale_max"])
                self.assertIn("气象原值", metric["value_semantics"])
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
        for region in self.payload["seasonal"].values():
            for metric in region["metrics"].values():
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

    def test_all_frozen_contract_input_hashes_unchanged(self):
        for path, expected in FROZEN_INPUT_SHAS.items():
            self.assertEqual(digest(path), expected, str(path))

    def test_page_and_publish_files_are_synced_and_safe(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        for phrase in ("全球供需锚点", "五个棉区天气胁迫", "中亚五国天气观察", "10 个 AOI", "天气异常度 10/10 可用", "棉花胁迫分 0/10 可用", "分项因子", "官方供需明细", "暂无可用值", "历史季节性图", "attachCharts", "澳大利亚 USDA 官方供需变化已接入", "USDA产量变化", "USDA期末库存变化", "国内消费变化率", "看板 V0.4"):
            self.assertIn(phrase, html)
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

    def test_published_data_fetch_is_versioned_for_cache_busting(self):
        for page in (ROOT / "index.html", ROOT / "dist/index.html"):
            html = page.read_text(encoding="utf-8")
            self.assertIn("fetch('./data.json?v=20260923-v04-seasonal')", html)
            self.assertNotIn("fetch('./data.json')", html)

    def test_temp_builder_is_deterministic(self):
        payload_a = builder.build()
        payload_b = builder.build()
        self.assertEqual((json.dumps(payload_a, ensure_ascii=False, indent=2) + "\n").encode(), (json.dumps(payload_b, ensure_ascii=False, indent=2) + "\n").encode())
        self.assertEqual((ROOT / "data.json").read_bytes(), (ROOT / "dist/data.json").read_bytes())


if __name__ == "__main__":
    unittest.main(verbosity=2)
