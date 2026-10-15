from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from weather_revision_guard import RevisionEvidenceError, verify_frozen_revisions

ROOT = Path(__file__).resolve().parent


class WeatherRevisionGuardTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix=".revision_guard_tmp_", dir=ROOT)
        self.temp_root = Path(self.temp.name)
        self.automation = self.temp_root / "cotton" / "automation"
        (self.automation / "raw").mkdir(parents=True)
        (self.automation / "runs").mkdir()
        (self.automation / "pipeline_runs").mkdir()
        self.csv_path = self.temp_root / "points.csv"
        self._write_csv([{"point_id": "p1", "date": "2026-09-29", "tmax": "30", "tmin": "10", "precip": "1", "sw_rad": "20"}])
        self.config = {"G": {"path": self.csv_path, "points": ("p1",), "cutoff": date(2026, 9, 29)}}
        self.expected = {"G": self._hash([{ "point_id": "p1", "date": "2026-09-29", "tmax": "30", "tmin": "10", "precip": "1", "sw_rad": "20"}])}
        self.baseline = self.automation / "runs" / "20261013T003003Z.json"
        self._write_run(self.baseline, "20261013T003003Z", {"tmax": 30, "tmin": 10, "precip": 1, "sw_rad": 20}, "2026-10-13T00:30:05+00:00")
        self._write_run(self.automation / "runs" / "20261014T003005Z.json", "20261014T003005Z", {"tmax": 31, "tmin": 10, "precip": 1, "sw_rad": 20}, "2026-10-14T00:30:08+00:00")
        self._write_json(self.automation / "pipeline_runs" / "20261014T003005Z.json", {"steps": [{"name": "download_weather", "returncode": 0}]})
        self._write_csv([{"point_id": "p1", "date": "2026-09-29", "tmax": "31", "tmin": "10", "precip": "1", "sw_rad": "20"}])

    def tearDown(self):
        self.temp.cleanup()

    def _write_json(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, separators=(",", ":")), encoding="utf-8")

    def _write_csv(self, rows):
        with self.csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["point_id", "date", "tmax", "tmin", "precip", "sw_rad"])
            writer.writeheader()
            writer.writerows(rows)

    def _hash(self, rows):
        body = [{key: row[key] for key in ("point_id", "date", "tmax", "tmin", "precip", "sw_rad")} for row in rows]
        return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()

    def _semantic_hash(self, _config, rows):
        selected = [row for row in rows if row["date"] <= "2026-09-29"]
        return self._hash(selected)

    def _write_run(self, manifest_path, run_id, values, retrieved):
        run_dir = self.automation / "raw" / run_id / "r" / "p1"
        run_dir.mkdir(parents=True, exist_ok=True)
        raw_path = run_dir / "archive_reanalysis.json"
        api_values = {
            "temperature_2m_max": [values["tmax"]], "temperature_2m_min": [values["tmin"]],
            "precipitation_sum": [values["precip"]], "shortwave_radiation_sum": [values["sw_rad"]],
        }
        payload = {
            "latitude": 1, "longitude": 2, "timezone": "UTC",
            "daily_units": {"time": "iso8601", "temperature_2m_max": "°C", "temperature_2m_min": "°C", "precipitation_sum": "mm", "shortwave_radiation_sum": "MJ/m²"},
            "daily": {"time": ["2026-09-29"], **api_values},
        }
        raw_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        url = "https://archive-api.open-meteo.com/v1/archive?latitude=1&longitude=2&start_date=2026-09-29&end_date=2026-09-29&timezone=UTC&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,shortwave_radiation_sum"
        response = {
            "source_class": "archive_reanalysis", "http_status": 200,
            "output_path": f"cotton/automation/raw/{run_id}/r/p1/archive_reanalysis.json",
            "response_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
            "retrieved_at_utc": retrieved, "url": url,
            "requested_start": "2026-09-29", "requested_end": "2026-09-29",
            "timezone_requested": "UTC", "timezone_returned": "UTC",
            "daily_units": payload["daily_units"],
        }
        manifest = {"status": "success", "regions": [{"region": "r", "points": [{"point_id": "p1", "responses": {"archive_reanalysis": response}}]}]}
        self._write_json(manifest_path, manifest)

    def _verify(self):
        return verify_frozen_revisions(
            self.config, self.expected, self._semantic_hash,
            baseline_manifest=self.baseline, automation_root=self.automation,
        )

    def test_valid_revision_is_supported_and_reports_provenance(self):
        report = self._verify()
        self.assertEqual(report["regions"]["G"]["restored_frozen_semantic_sha256"], self.expected["G"])
        self.assertEqual(report["revision_count"], 1)
        source = report["regions"]["G"]["revisions"][0]["source"]
        raw = self.automation / "raw" / "20261014T003005Z" / "r" / "p1" / "archive_reanalysis.json"
        self.assertEqual(source["sha256"], hashlib.sha256(raw.read_bytes()).hexdigest())
        self.assertEqual(source["path"], str(raw))
        self.assertEqual((source["point_id"], source["region"], source["requested_latitude"]), ("p1", "r", 1))
        self.assertEqual(source["retrieved_at_utc"], "2026-10-14T00:30:08+00:00")

    def test_invalid_source_semantics_are_rejected(self):
        path = self.automation / "runs" / "20261014T003005Z.json"
        original = json.loads(path.read_text())
        mutations = {
            "path_escape": lambda e: e.update(output_path="../outside.json"),
            "wrong_point_path": lambda e: e.update(output_path=e["output_path"].replace("/p1/", "/p2/")),
            "units": lambda e: e["daily_units"].update(temperature_2m_max="°F"),
            "timezone": lambda e: e.update(timezone_returned="Asia/Shanghai"),
            "coordinates": lambda e: e.update(url=e["url"].replace("latitude=1", "latitude=3")),
            "out_of_range": lambda e: e.update(url=e["url"].replace("latitude=1", "latitude=100")),
            "calendar": lambda e: e.update(requested_end="2026-09-30", url=e["url"].replace("end_date=2026-09-29", "end_date=2026-09-30")),
            "naive_timestamp": lambda e: e.update(retrieved_at_utc="2026-10-14T00:30:08"),
            "daily_missing": lambda e: e.update(url=e["url"].replace("temperature_2m_max,", "")),
        }
        for name, change in mutations.items():
            doc = json.loads(json.dumps(original))
            change(doc["regions"][0]["points"][0]["responses"]["archive_reanalysis"])
            self._write_json(path, doc)
            with self.subTest(name=name), self.assertRaises(RevisionEvidenceError):
                self._verify()
        self._write_json(path, original)

    def test_missing_row_unknown_frozen_history_and_nonfinite_active_are_rejected(self):
        for rows in ([], [{"point_id": "p1", "date": "2026-09-28", "tmax": "31"}],
                     [{"point_id": "p1", "date": "2026-09-29", "tmax": "NaN", "tmin": "10", "precip": "1", "sw_rad": "20"}]):
            self._write_csv(rows)
            with self.subTest(rows=rows), self.assertRaises(RevisionEvidenceError):
                self._verify()

    def test_post_cutoff_append_does_not_change_frozen_revision_report(self):
        before = self._verify()
        with self.csv_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        rows.append({"point_id": "p1", "date": "2026-09-30", "tmax": "999", "tmin": "-99", "precip": "1", "sw_rad": "20"})
        self._write_csv(rows)
        self.assertEqual(self._verify(), before)

    def test_nonfinite_or_boolean_raw_cannot_authorize_revisions(self):
        for value in (float("inf"), True):
            self._write_run(self.automation / "runs" / "20261014T003005Z.json", "20261014T003005Z",
                            {"tmax": value, "tmin": 10, "precip": 1, "sw_rad": 20}, "2026-10-14T00:30:08+00:00")
            with self.subTest(value=value), self.assertRaises(RevisionEvidenceError):
                self._verify()

    def test_utc_gmt_provider_alias_is_accepted_without_changing_request_identity(self):
        path = self.automation / "runs" / "20261014T003005Z.json"
        doc = json.loads(path.read_text())
        evidence = doc["regions"][0]["points"][0]["responses"]["archive_reanalysis"]
        raw = self.temp_root / evidence["output_path"]
        payload = json.loads(raw.read_text())
        payload["timezone"] = "GMT"
        self._write_json(raw, payload)
        evidence["timezone_returned"] = "GMT"
        evidence["response_sha256"] = hashlib.sha256(raw.read_bytes()).hexdigest()
        self._write_json(path, doc)
        self.assertEqual(self._verify()["revision_count"], 1)

    def test_unattributed_active_change_is_rejected(self):
        self._write_csv([{ "point_id": "p1", "date": "2026-09-29", "tmax": "32", "tmin": "10", "precip": "1", "sw_rad": "20"}])
        with self.assertRaises(RevisionEvidenceError):
            self._verify()

    def test_tampered_archive_sha_is_rejected(self):
        raw = next((self.automation / "raw" / "20261014T003005Z").rglob("archive_reanalysis.json"))
        raw.write_text(raw.read_text(encoding="utf-8") + " ", encoding="utf-8")
        with self.assertRaises(RevisionEvidenceError):
            self._verify()

    def test_wrong_archive_endpoint_is_rejected(self):
        path = self.automation / "runs" / "20261014T003005Z.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["regions"][0]["points"][0]["responses"]["archive_reanalysis"]["url"] = "https://example.com/v1/archive?latitude=1&longitude=2&start_date=2026-09-29&end_date=2026-09-29&timezone=UTC"
        self._write_json(path, doc)
        with self.assertRaises(RevisionEvidenceError):
            self._verify()

    def test_later_reversion_rejects_matching_older_value(self):
        self._write_run(
            self.automation / "runs" / "20261015T003005Z.json", "20261015T003005Z",
            {"tmax": 30, "tmin": 10, "precip": 1, "sw_rad": 20}, "2026-10-15T00:30:08+00:00",
        )
        self._write_json(self.automation / "pipeline_runs" / "20261015T003005Z.json", {"steps": [{"name": "download_weather", "returncode": 0}]})
        with self.assertRaises(RevisionEvidenceError):
            self._verify()

    def test_source_null_cannot_authorize_changed_value(self):
        self._write_run(
            self.automation / "runs" / "20261015T003005Z.json", "20261015T003005Z",
            {"tmax": None, "tmin": 10, "precip": 1, "sw_rad": 20}, "2026-10-15T00:30:08+00:00",
        )
        self._write_json(self.automation / "pipeline_runs" / "20261015T003005Z.json", {"steps": [{"name": "download_weather", "returncode": 0}]})
        self._write_csv([{ "point_id": "p1", "date": "2026-09-29", "tmax": "", "tmin": "10", "precip": "1", "sw_rad": "20"}])
        with self.assertRaises(RevisionEvidenceError):
            self._verify()

    def test_duplicate_point_date_is_rejected(self):
        self._write_csv([
            {"point_id": "p1", "date": "2026-09-29", "tmax": "31", "tmin": "10", "precip": "1", "sw_rad": "20"},
            {"point_id": "p1", "date": "2026-09-29", "tmax": "31", "tmin": "10", "precip": "1", "sw_rad": "20"},
        ])
        with self.assertRaises(RevisionEvidenceError):
            self._verify()


if __name__ == "__main__":
    unittest.main()
