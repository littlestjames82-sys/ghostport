"""Pattern pack format + loader.

A pack is a JSON data file. Every pattern MUST carry an id, a plain-words
description, a source reference and a reference_date. An undated or
unreferenced pattern is a bug and pack loading refuses it (PLAN: Risks).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

KINDS = {"import_module", "import_from", "attribute", "attribute_or_name"}


class PackError(ValueError):
    pass


@dataclass
class Pattern:
    id: str
    description: str
    reference: str
    reference_date: str
    reference_url: str
    matcher: dict

    def to_dict(self):
        return {"id": self.id, "description": self.description,
                "reference": self.reference, "reference_date": self.reference_date,
                "reference_url": self.reference_url, "matcher": self.matcher}


@dataclass
class Pack:
    id: str
    title: str
    version: str
    date: str
    language: str
    target: str
    patterns: list = field(default_factory=list)
    source_path: str = ""

    def to_dict(self):
        return {"id": self.id, "title": self.title, "version": self.version,
                "date": self.date, "language": self.language, "target": self.target,
                "patterns": [p.to_dict() for p in self.patterns]}


def _builtin_pack_path(pack_id: str) -> Path:
    return Path(__file__).parent / "packs" / f"{pack_id}.json"


def pack_search_paths(pack_id: str, project: Path | None = None):
    paths = []
    if project is not None:
        paths.append(Path(project) / "patterns" / f"{pack_id}.json")
        paths.append(Path(project) / f"{pack_id}.json")
    here = Path(__file__).resolve().parents[2]  # repo root (src layout checkout)
    paths.append(here / "patterns" / f"{pack_id}.json")
    paths.append(_builtin_pack_path(pack_id))
    return paths


def load_pack(pack_id: str, project: Path | None = None) -> Pack:
    for candidate in pack_search_paths(pack_id, project):
        if candidate.is_file():
            return load_pack_file(candidate)
    raise PackError(f"pack not found: {pack_id} (searched: "
                    + ", ".join(str(p) for p in pack_search_paths(pack_id, project)) + ")")


def load_pack_file(path: Path) -> Pack:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PackError(f"cannot load pack {path}: {exc}") from exc
    return validate_pack(data, str(path))


def validate_pack(data: dict, source: str = "") -> Pack:
    if not isinstance(data, dict):
        raise PackError("pack: top level is not an object")
    for key in ("id", "title", "version", "date", "language", "target", "patterns"):
        if key not in data:
            raise PackError(f"pack: missing '{key}'")
    if not str(data["date"]).strip():
        raise PackError("pack: pack itself must be dated")
    raw = data["patterns"]
    if not isinstance(raw, list) or not raw:
        raise PackError("pack: 'patterns' must be a non-empty list")
    seen, patterns = set(), []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise PackError(f"pack patterns[{i}]: not an object")
        pid = item.get("id")
        if not pid or not isinstance(pid, str):
            raise PackError(f"pack patterns[{i}]: missing id")
        if pid in seen:
            raise PackError(f"pack: duplicate pattern id {pid}")
        seen.add(pid)
        for key in ("description", "reference", "reference_date", "reference_url", "matcher"):
            if not item.get(key):
                raise PackError(f"pattern {pid}: missing '{key}' (every pattern must be dated and referenced)")
        matcher = item["matcher"]
        if not isinstance(matcher, dict) or matcher.get("kind") not in KINDS:
            raise PackError(f"pattern {pid}: matcher.kind must be one of {sorted(KINDS)}")
        patterns.append(Pattern(pid, item["description"], item["reference"],
                                item["reference_date"], item["reference_url"], matcher))
    return Pack(data["id"], data["title"], data["version"], data["date"],
                data["language"], data["target"], patterns, source)
