#!/usr/bin/env python3

import json
import unittest
from pathlib import Path

import build_public_dashboard as builder


class PublicDashboardTest(unittest.TestCase):
    def setUp(self):
        self.payload = builder.build()
        self.brief = json.loads(builder.BRIEF_PATH.read_text(encoding="utf-8"))

    def test_supply_rows_are_exact_source_values(self):
        source = {row["geography"]: row for row in self.brief["rows"]}
        for row in self.payload["supply"]:
            raw = source[row["geography"]]
            self.assertEqual(row["production"], raw["current_production_1000_480lb_bales"])
            self.assertEqual(row["ending_stocks"], raw["current_ending_stocks_1000_480lb_bales"])
            self.assertEqual(row["stocks_to_use"], raw["current_ending_stocks_to_total_use_pct"])

    def test_region_scores_and_null_factors_are_preserved(self):
        for region in self.payload["regions"]:
            raw = json.loads(builder.REGION_PATHS[region["geography"]].read_text(encoding="utf-8"))
            self.assertEqual(region["score"], raw["theoretical_weather_stress_index"])
        brazil = next(region for region in self.payload["regions"] if region["id"] == "brazil")
        unavailable = [factor for factor in brazil["factors"] if factor["score"] is None]
        self.assertGreaterEqual(len(unavailable), 1)
        self.assertTrue(all(factor["status"] == "not_available_or_inactive" for factor in unavailable))

    def test_no_global_numeric_weather_score_or_supply_conversion(self):
        self.assertIsNone(self.payload["global_numeric_weather_score"])
        self.assertFalse(self.payload["cross_region_weather_comparable"])
        self.assertFalse(self.payload["weather_to_supply_conversion_performed"])

    def test_page_exposes_required_sections_and_null_copy(self):
        html = (builder.DIST / "index.html").read_text(encoding="utf-8")
        for phrase in ("全球供需锚点", "四大棉区天气胁迫", "分项因子", "官方供需明细", "暂无可用值"):
            self.assertIn(phrase, html)


if __name__ == "__main__":
    unittest.main()

