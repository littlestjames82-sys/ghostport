"""Resumption view: plan + ledger -> status."""
from __future__ import annotations

import json
from pathlib import Path

from .ledger import read_records, unit_states


def build_status(project: Path, plan: dict | None = None) -> dict:
    project = Path(project)
    plan_path = project / "port-plan.json"
    if plan is None and plan_path.is_file():
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    units = plan.get("units", []) if plan else []
    states = unit_states(project)
    rows, remaining = [], 0
    counts = {"planned": 0, "bundled": 0, "ported-claimed": 0, "verified": 0, "unrecorded": 0}
    next_unit = None
    for u in units:
        state = states.get(u["id"])
        if state is None:
            # a unit in a written plan counts as planned-by-plan, unrecorded in ledger
            state_label = "planned (in plan, no ledger record)"
            counts["unrecorded"] += 1
        else:
            state_label = state
            counts[state] = counts.get(state, 0) + 1
        verified = state_label == "verified"
        if not verified:
            remaining += u["estimated_tokens"]
            if next_unit is None and state != "ported-claimed":
                next_unit = u["id"]
        rows.append({"unit": u["id"], "order": u["order"], "state": state_label,
                     "estimated_tokens": u["estimated_tokens"]})
    return {"project": str(project), "units": rows, "counts": counts,
            "estimated_tokens_remaining": remaining,
            "verified_units": counts.get("verified", 0),
            "next_unit": next_unit,
            "ledger_records": len(read_records(project)),
            "note": "verified is only ever recorded from a GhostVerify post report."}
