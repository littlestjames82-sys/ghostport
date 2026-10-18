"""Read the `port` section of a project's .ghostslice.json, if present.

Supported keys (all optional): pack, budget_tokens (per-unit), merge
(list of lists of unit ids/files to combine), pin_first (unit ids that a
human orders first, breaking ties only - never dependency order),
order (explicit unit order override applied as a tie-breaker),
test_command (recorded in UNIT.md, never run by GhostPort).
Unknown keys fail loudly.
"""
from __future__ import annotations

import json
from pathlib import Path

KNOWN = {"pack", "budget_tokens", "merge", "pin_first", "order", "test_command", "pattern_overrides"}


class ProfileError(ValueError):
    pass


def load_port_profile(project: Path) -> dict:
    path = Path(project) / ".ghostslice.json"
    out = {"pack": None, "budget_tokens": None, "merge": [], "pin_first": [],
           "order": [], "test_command": None, "pattern_overrides": {}}
    if not path.is_file():
        return out
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProfileError(f".ghostslice.json: cannot parse ({exc})") from exc
    section = data.get("port") if isinstance(data, dict) else None
    if section is None:
        return out
    if not isinstance(section, dict):
        raise ProfileError(".ghostslice.json: 'port' section is not an object")
    unknown = sorted(set(section) - KNOWN)
    if unknown:
        raise ProfileError(f".ghostslice.json port section: unknown keys {unknown}")
    for key in out:
        if key in section:
            out[key] = section[key]
    return out
