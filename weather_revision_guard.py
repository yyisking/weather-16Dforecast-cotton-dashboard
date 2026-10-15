"""Read-only proof that revised archive values preserve the frozen baseline."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlsplit


ARCHIVE_ENDPOINT = "https://archive-api.open-meteo.com/v1/archive"
FIELD_API = {
    "tmax": ("temperature_2m_max", "°C"),
    "tmin": ("temperature_2m_min", "°C"),
    "precip": ("precipitation_sum", "mm"),
    "sw_rad": ("shortwave_radiation_sum", "MJ/m²"),
}


class RevisionEvidenceError(ValueError):
    pass


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RevisionEvidenceError(f"invalid JSON evidence {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RevisionEvidenceError(f"JSON evidence is not an object: {path}")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise RevisionEvidenceError("boolean is not a weather measurement")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise RevisionEvidenceError(f"non-numeric weather value: {value!r}") from exc
    if not math.isfinite(number):
        raise RevisionEvidenceError(f"non-finite weather value: {value!r}")
    return number


def _response_evidence(
    response: dict[str, Any], automation_root: Path, point_id: str, *, expected_region: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    if response.get("source_class") != "archive_reanalysis" or response.get("http_status") != 200:
        raise RevisionEvidenceError(f"not a successful Archive response for {point_id}")
    rel = Path(str(response.get("output_path", "")))
    raw_root = (automation_root / "raw").resolve()
    raw_path = (automation_root.parent.parent / rel).resolve()
    if raw_root not in raw_path.parents or not raw_path.is_file():
        raise RevisionEvidenceError(f"Archive raw path missing or escaped raw/: {rel}")
    if _sha(raw_path) != response.get("response_sha256"):
        raise RevisionEvidenceError(f"Archive raw SHA mismatch: {rel}")
    payload = _json(raw_path)
    url = str(response.get("url", ""))
    parsed = urlsplit(url)
    if (parsed.scheme, parsed.netloc, parsed.path) != ("https", "archive-api.open-meteo.com", "/v1/archive"):
        raise RevisionEvidenceError(f"unexpected Archive endpoint: {url}")
    if parsed.fragment:
        raise RevisionEvidenceError("Archive URL has a fragment")
    query = parse_qs(parsed.query)
    if any(len(values) != 1 for values in query.values()):
        raise RevisionEvidenceError("ambiguous Archive request parameters")
    for key, expected in (("start_date", response.get("requested_start")), ("end_date", response.get("requested_end")), ("timezone", response.get("timezone_requested"))):
        if query.get(key) != [str(expected)]:
            raise RevisionEvidenceError(f"Archive request {key} mismatch in {rel}")
    try:
        latitude, longitude = float(query["latitude"][0]), float(query["longitude"][0])
    except (KeyError, ValueError, IndexError) as exc:
        raise RevisionEvidenceError(f"Archive request location missing: {rel}") from exc
    if not math.isfinite(latitude) or not math.isfinite(longitude) or not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise RevisionEvidenceError(f"invalid Archive request coordinates: {rel}")
    if payload.get("timezone") != response.get("timezone_returned"):
        raise RevisionEvidenceError(f"Archive timezone mismatch: {rel}")
    returned_lat, returned_lon = _finite(payload.get("latitude")), _finite(payload.get("longitude"))
    if returned_lat is None or returned_lon is None or not -90 <= returned_lat <= 90 or not -180 <= returned_lon <= 180:
        raise RevisionEvidenceError(f"Archive payload coordinates missing: {rel}")
    timezone_alias = {"UTC": "UTC", "GMT": "UTC", "Etc/UTC": "UTC", "Etc/GMT": "UTC"}
    requested_zone = response.get("timezone_requested")
    returned_zone = payload.get("timezone")
    if requested_zone != "auto" and timezone_alias.get(returned_zone, returned_zone) != timezone_alias.get(requested_zone, requested_zone):
        raise RevisionEvidenceError(f"Archive returned timezone differs from requested: {rel}")
    try:
        retrieved = datetime.fromisoformat(str(response.get("retrieved_at_utc", "")))
        if retrieved.tzinfo is None or retrieved.utcoffset() != timedelta(0):
            raise ValueError("retrieval time must be UTC")
        first, last = date.fromisoformat(response["requested_start"]), date.fromisoformat(response["requested_end"])
    except (ValueError, KeyError, TypeError) as exc:
        raise RevisionEvidenceError(f"invalid Archive dates in {rel}") from exc
    if first > last or (last - first).days > 10000:
        raise RevisionEvidenceError(f"invalid Archive date range: {rel}")
    # Open-Meteo snaps requested coordinates to the returned grid cell; the request
    # URL remains the authoritative exact point identity and is checked per run.
    daily, units = payload.get("daily"), payload.get("daily_units")
    if not isinstance(daily, dict) or not isinstance(units, dict):
        raise RevisionEvidenceError(f"Archive daily payload malformed: {rel}")
    times = daily.get("time")
    if not isinstance(times, list) or len(times) != len(set(times)):
        raise RevisionEvidenceError(f"Archive dates missing or duplicated: {rel}")
    if times != [(first + timedelta(days=ix)).isoformat() for ix in range((last - first).days + 1)]:
        raise RevisionEvidenceError(f"Archive calendar differs from request: {rel}")
    requested_daily = set(query.get("daily", [""])[0].split(","))
    if query.get("temperature_unit", ["celsius"]) != ["celsius"] or query.get("precipitation_unit", ["mm"]) != ["mm"]:
        raise RevisionEvidenceError(f"Archive requested units mismatch: {rel}")
    for csv_field, (api_field, unit) in FIELD_API.items():
        if api_field not in requested_daily:
            raise RevisionEvidenceError(f"Archive requested field missing {api_field}: {rel}")
        if response.get("daily_units", {}).get(api_field) != unit or units.get(api_field) != unit:
            raise RevisionEvidenceError(f"Archive unit mismatch {api_field} in {rel}")
        values = daily.get(api_field)
        if not isinstance(values, list) or len(values) != len(times):
            raise RevisionEvidenceError(f"Archive field alignment mismatch {api_field} in {rel}")
        for value in values:
            _finite(value)
    return payload, {
        "path": str(raw_path), "sha256": response["response_sha256"], "url": url,
        "retrieved_at_utc": retrieved.astimezone(timezone.utc).isoformat(), "region": expected_region,
        "point_id": point_id, "requested_latitude": latitude, "requested_longitude": longitude,
        "timezone_requested": response.get("timezone_requested"),
        "daily_units": dict(response.get("daily_units") or {}),
        "output_path": str(rel),
    }


def _manifest_responses(manifest_path: Path, automation_root: Path, *, after: str | None = None):
    manifest = _json(manifest_path)
    region_entries = manifest.get("regions")
    if not isinstance(region_entries, list):
        raise RevisionEvidenceError(f"run manifest has no region list: {manifest_path}")
    found = []
    seen = set()
    for region in region_entries:
        if not isinstance(region, dict):
            continue
        region_key = region.get("region")
        for point in region.get("points", []):
            if not isinstance(point, dict):
                continue
            evidence = (point.get("responses") or {}).get("archive_reanalysis")
            if not isinstance(evidence, dict):
                continue
            point_key = (str(region_key), str(point.get("point_id")))
            if point_key in seen:
                raise RevisionEvidenceError(f"duplicate region/point in manifest: {point_key}")
            seen.add(point_key)
            expected_path = f"cotton/automation/raw/{manifest_path.stem}/{point_key[0]}/{point_key[1]}/archive_reanalysis.json"
            if evidence.get("output_path") != expected_path:
                raise RevisionEvidenceError(f"Archive raw path does not match run/region/point: {expected_path}")
            retrieved = str(evidence.get("retrieved_at_utc", ""))
            if after is not None and retrieved <= after:
                continue
            payload, citation = _response_evidence(evidence, automation_root, str(point.get("point_id")), expected_region=str(region_key))
            found.append((citation["retrieved_at_utc"], str(region_key), str(point.get("point_id")), payload, citation, evidence))
    return manifest, found


def _successful_download(manifest_path: Path, automation_root: Path) -> bool:
    manifest = _json(manifest_path)
    if manifest.get("status") != "success":
        return False
    ledger_path = automation_root / "pipeline_runs" / manifest_path.name
    if not ledger_path.is_file():
        return False
    ledger = _json(ledger_path)
    return any(step.get("name") == "download_weather" and step.get("returncode") == 0 for step in ledger.get("steps", []) if isinstance(step, dict))


def verify_frozen_revisions(
    configs: dict[str, dict[str, Any]],
    frozen_hashes: dict[str, str],
    semantic_hash: Callable[[dict[str, Any], list[dict[str, str]]], str],
    *,
    baseline_manifest: Path,
    automation_root: Path,
    runs_root: Path | None = None,
) -> dict[str, Any]:
    """Reconstruct the frozen baseline in memory, then prove all active changes.

    CSVs, raw responses, manifests, and canonical outputs are read only.  The
    returned report includes source citations for each permitted revised cell.
    """
    baseline_manifest = baseline_manifest.resolve()
    automation_root = automation_root.resolve()
    if not baseline_manifest.is_file() or baseline_manifest.resolve().parent != (automation_root / "runs").resolve():
        raise RevisionEvidenceError("baseline run manifest is not the fixed runs/ artifact")
    _base_doc, base_responses = _manifest_responses(baseline_manifest, automation_root)
    baseline_by_region_point = {(region, point): (payload, citation, evidence) for _time, region, point, payload, citation, evidence in base_responses}
    runs_root = runs_root.resolve() if runs_root else (automation_root / "runs").resolve()
    candidates = []
    for manifest_path in sorted(runs_root.glob("*.json")):
        if manifest_path.resolve() == baseline_manifest:
            continue
        if not _successful_download(manifest_path, automation_root):
            continue
        _doc, responses = _manifest_responses(manifest_path, automation_root)
        candidates.extend(responses)
    candidates.sort(key=lambda item: item[0])
    candidates_by_point_day = {}
    for item in candidates:
        for day in item[3]["daily"]["time"]:
            candidates_by_point_day.setdefault((item[2], day), []).append(item)

    result: dict[str, Any] = {"regions": {}, "revision_count": 0, "baseline_manifest": str(baseline_manifest)}
    for geography, config in configs.items():
        path = Path(config["path"]).resolve()
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        restored = [dict(row) for row in rows]
        cfg_points = set(config["points"])
        cutoff = config["cutoff"].isoformat()
        index: dict[tuple[str, str], dict[str, str]] = {}
        active_index: dict[tuple[str, str], dict[str, str]] = {}
        for row, active_row in zip(restored, rows):
            point_id, raw_day = row.get("point_id"), str(row.get("date", ""))[:10]
            if point_id in cfg_points and raw_day and raw_day <= cutoff:
                key = (point_id, raw_day)
                if key in index:
                    raise RevisionEvidenceError(f"duplicate point/date in active CSV: {geography}/{point_id}/{raw_day}")
                index[key] = row
                active_index[key] = active_row
        baseline_citations = []
        for (region, point_id), (payload, citation, evidence) in baseline_by_region_point.items():
            if point_id not in cfg_points:
                continue
            if not Path(evidence["output_path"]).as_posix().startswith(f"cotton/automation/raw/{baseline_manifest.stem}/"):
                raise RevisionEvidenceError(f"baseline raw is not from frozen run for {point_id}")
            daily = payload["daily"]
            for ix, raw_day in enumerate(daily["time"]):
                if raw_day > cutoff or (point_id, raw_day) not in index:
                    continue
                target = index[(point_id, raw_day)]
                for field, (api, _unit) in FIELD_API.items():
                    target[field] = "" if daily[api][ix] is None else str(daily[api][ix])
            baseline_citations.append(citation)
        original_hash = semantic_hash(config, rows)
        restored_hash = semantic_hash(config, restored)
        expected_hash = frozen_hashes[geography]
        if restored_hash != expected_hash:
            raise RevisionEvidenceError(f"restored frozen raw semantic hash mismatch: {geography}: {restored_hash}")

        revised = []
        for (point_id, raw_day), base_row in index.items():
            if raw_day > cutoff or point_id not in cfg_points:
                continue
            active_row = active_index.get((point_id, raw_day))
            if active_row is None:
                raise RevisionEvidenceError(f"baseline point/date is missing from active CSV: {geography}/{point_id}/{raw_day}")
            for field, (_api, _unit) in FIELD_API.items():
                old_value, new_value = _finite(base_row.get(field)), _finite(active_row.get(field))
                eligible = []
                for retrieved, region, src_point, payload, citation, evidence in candidates_by_point_day.get((point_id, raw_day), []):
                    if src_point != point_id:
                        continue
                    base_entry = baseline_by_region_point.get((region, point_id))
                    if base_entry is None:
                        continue
                    _base_payload, base_citation, _base_evidence = base_entry
                    if not retrieved or retrieved <= str(_base_evidence.get("retrieved_at_utc", "")):
                        continue
                    if (
                        citation["requested_latitude"] != base_citation["requested_latitude"]
                        or citation["requested_longitude"] != base_citation["requested_longitude"]
                        or citation["timezone_requested"] != base_citation["timezone_requested"]
                        or citation["daily_units"] != base_citation["daily_units"]
                    ):
                        continue
                    if raw_day not in payload.get("daily", {}).get("time", []):
                        continue
                    api, _unit = FIELD_API[field]
                    ix = payload["daily"]["time"].index(raw_day)
                    source_value = _finite(payload["daily"][api][ix])
                    eligible.append((retrieved, citation, source_value))
                if not eligible:
                    if old_value == new_value:
                        continue
                    raise RevisionEvidenceError(f"active value lacks exact later Archive evidence: {geography}/{point_id}/{raw_day}/{field}")
                retrieved, citation, source_value = max(eligible, key=lambda item: item[0])
                if source_value is None:
                    if old_value == new_value:
                        # A missing later value does not erase the frozen value.
                        continue
                    raise RevisionEvidenceError(f"latest Archive value is null for changed active cell: {geography}/{point_id}/{raw_day}/{field}")
                if new_value is None or source_value != new_value:
                    raise RevisionEvidenceError(f"active value is not the latest Archive value: {geography}/{point_id}/{raw_day}/{field}")
                if old_value == new_value:
                    continue
                revised.append({"point_id": point_id, "date": raw_day, "field": field, "baseline": old_value, "active": source_value, "retrieved_at_utc": retrieved, "source": citation})
        result["regions"][geography] = {
            "original_active_semantic_sha256": original_hash,
            "restored_frozen_semantic_sha256": restored_hash,
            "expected_frozen_semantic_sha256": expected_hash,
            "baseline_raw_count": len(baseline_citations),
            "revision_count": len(revised),
            "revisions": revised,
            "baseline_sources": baseline_citations,
        }
        result["revision_count"] += len(revised)
    return result
