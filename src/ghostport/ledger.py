"""Local ledger: <project>/.ghostport-history.jsonl

States: planned, bundled, ported-claimed, verified.
HARD RULE (PLAN): `verified` may only be recorded from a GhostVerify post
report: a JSON file whose shape includes a bundle/project identity and a
passing verdict. There is deliberately no CLI flag to set verified by
hand; the only writer of a verified record is record_verified(), which
validates the report file first.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

LEDGER_NAME = ".ghostport-history.jsonl"
STATES = ("planned", "bundled", "ported-claimed", "verified")


def ledger_path(project: Path) -> Path:
    return Path(project) / LEDGER_NAME


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_record(project: Path, record: dict) -> dict:
    record = {"ts": _now(), **record}
    path = ledger_path(project)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def read_records(project: Path) -> list[dict]:
    path = ledger_path(project)
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def record_state(project: Path, unit_id: str, state: str, **extra) -> dict:
    if state == "verified":
        raise ValueError("verified state cannot be set directly; "
                         "use record_verified() with a GhostVerify report")
    if state not in STATES:
        raise ValueError(f"unknown state: {state}")
    label = "claim" if state == "ported-claimed" else "event"
    return append_record(project, {"unit": unit_id, "state": state,
                                   "state_kind": label, **extra})


def validate_verify_report(report_path: Path) -> dict:
    """Accept a GhostVerify post report: JSON object with ok/verdict pass.

    Accepted shapes: {"ok": true, ...} or {"verdict": "pass"/"sufficient"}
    plus a subject (bundle or project or unit). Anything else is refused.
    """
    try:
        data = json.loads(Path(report_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"verify report: cannot parse ({exc})") from exc
    if not isinstance(data, dict):
        raise ValueError("verify report: not a JSON object")
    passed = data.get("ok") is True or str(data.get("verdict", "")).lower() in ("pass", "passed", "sufficient")
    if not passed:
        raise ValueError("verify report: does not record a passing verdict")
    return data


def record_verified(project: Path, unit_id: str, report_path: Path) -> dict:
    report = validate_verify_report(Path(report_path))
    digest = hashlib.sha256(Path(report_path).read_bytes()).hexdigest()
    return append_record(project, {
        "unit": unit_id, "state": "verified", "state_kind": "verified",
        "verify_report": str(report_path), "verify_report_sha256": digest,
        "verify_verdict": report.get("verdict", "ok")})


def unit_states(project: Path) -> dict[str, str]:
    """Latest state per unit, in ledger order."""
    states = {}
    for rec in read_records(project):
        if "unit" in rec and "state" in rec:
            states[rec["unit"]] = rec["state"]
    return states
