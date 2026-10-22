"""Read-only frontend date tests; never rebuild or modify shared weather data."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parent
NODE = shutil.which("node") or "/Users/yyking/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"


class HeaderDateTest(unittest.TestCase):
    def test_published_and_source_html_identical(self):
        self.assertEqual((ROOT / "index.html").read_bytes(), (ROOT / "dist/index.html").read_bytes())

    def test_weather_date_never_falls_back_to_usda_snapshot(self):
        source = next(line.strip() for line in (ROOT / "index.html").read_text().splitlines()
                      if line.strip().startswith("function indicatorUpdateDate("))
        cases = [
            {"snapshot_as_of_date":"2026-09-16", "five_region_production_weighted_weather_stress_display":{"common_cutoff_date":"2026-10-21"}, "regions":[{"date":"2026-10-22"}]},
            {"snapshot_as_of_date":"2026-09-16", "regions":[{"date":"2026-10-22"},{"date":"2026-10-20"}]},
            {"snapshot_as_of_date":"2026-09-16", "regions":[]},
            json.loads((ROOT / "data.json").read_text()),
        ]
        code = source + ";let b='';process.stdin.on('data',x=>b+=x);process.stdin.on('end',()=>process.stdout.write(JSON.stringify(JSON.parse(b).map(indicatorUpdateDate))));"
        result = subprocess.run([NODE, "-e", code], input=json.dumps(cases), text=True, capture_output=True, check=True)
        expected = ["2026-10-21", "2026-10-20", "暂无", cases[-1]["five_region_production_weighted_weather_stress_display"]["common_cutoff_date"]]
        self.assertEqual(json.loads(result.stdout), expected)

    def test_date_labels_are_in_the_correct_sections(self):
        html = (ROOT / "index.html").read_text()
        topbar = re.search(r'<header class="topbar">(.*?)</header>', html).group(1)
        self.assertIn('指标更新日 ${escapeHtml(indicatorUpdateDate(DATA))}', topbar)
        self.assertNotIn('snapshot_as_of_date', topbar)
        self.assertNotIn('USDA', topbar)
        supply = html.split('<h2>官方供需明细</h2>', 1)[1].split('<div class="balance">', 1)[0]
        self.assertIn('<p class="supply-date-note">USDA供需截止日：${escapeHtml(DATA.snapshot_as_of_date)}</p>', supply)
        self.assertIn('.section-head .supply-date-note{margin-top:5px;color:var(--muted);font-size:.75rem;font-weight:400}', html)

    def test_all_inline_javascript_parses_without_touching_outputs(self):
        paths = [ROOT / "data.json", ROOT / "dist/data.json"]
        before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
        html = (ROOT / "index.html").read_text()
        for source in re.findall(r'<script>(.*?)</script>', html, flags=re.S):
            subprocess.run([NODE, "--check"], input=source, text=True, capture_output=True, check=True)
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths])


if __name__ == "__main__":
    unittest.main()
