"""AST pattern scanner for Python projects.

Static only: files are parsed with ast, never imported or executed.
Findings are (file, line, pattern id, description) - no source text is
quoted into reports, matching the Ghost family redaction-safe habit.
"""
from __future__ import annotations

import ast
from pathlib import Path

from .patterns import Pack

SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", "dist",
             "build", ".tox", ".mypy_cache", ".ghostport", ".claude_context"}
LANG_BY_EXT = {".js": "javascript", ".ts": "typescript", ".go": "go",
               ".rs": "rust", ".java": "java", ".rb": "ruby", ".php": "php",
               ".cs": "csharp", ".kt": "kotlin", ".swift": "swift"}


def iter_project_files(project: Path):
    project = Path(project)
    py_files, other_langs = [], {}
    for path in sorted(project.rglob("*")):
        if any(part in SKIP_DIRS for part in path.relative_to(project).parts):
            continue
        if not path.is_file():
            continue
        if path.suffix == ".py":
            py_files.append(path)
        elif path.suffix in LANG_BY_EXT:
            other_langs.setdefault(LANG_BY_EXT[path.suffix], []).append(
                path.relative_to(project).as_posix())
    return py_files, other_langs


def dotted_name(node) -> str | None:
    parts = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return None


def _matches(matcher: dict, tree: ast.AST) -> list[int]:
    """Return sorted line numbers where this matcher hits in the tree."""
    kind = matcher["kind"]
    lines = []
    for node in ast.walk(tree):
        if kind == "import_module":
            mods = matcher.get("modules", [])
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in mods or any(alias.name.startswith(m + ".") for m in mods):
                        lines.append(node.lineno)
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module in mods or any(node.module.startswith(m + ".") for m in mods):
                    lines.append(node.lineno)
        elif kind == "import_from":
            if isinstance(node, ast.ImportFrom) and node.module == matcher.get("module"):
                names = {a.name for a in node.names}
                if names & set(matcher.get("names", [])):
                    lines.append(node.lineno)
        elif kind in ("attribute", "attribute_or_name"):
            names = matcher.get("names", [])
            if isinstance(node, ast.Attribute):
                full = dotted_name(node)
                leaf = node.attr
                if matcher.get("attr_only"):
                    hit = leaf in names
                else:
                    hit = (full in names) or (leaf in names if kind == "attribute_or_name" else False)
                if hit:
                    lines.append(node.lineno)
            elif kind == "attribute_or_name" and isinstance(node, ast.Name):
                if node.id in names:
                    lines.append(node.lineno)
    return sorted(set(lines))


def scan_file(path: Path, pack: Pack) -> tuple[list[dict], str | None]:
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [], f"syntax error: {exc.msg} (line {exc.lineno})"
    hits = []
    for pattern in pack.patterns:
        for line in _matches(pattern.matcher, tree):
            hits.append({"file": None, "line": line, "pattern_id": pattern.id,
                         "description": pattern.description})
    return hits, None


def scan_project(project: Path, pack: Pack) -> dict:
    project = Path(project)
    py_files, other_langs = iter_project_files(project)
    all_hits, parse_errors, clean_files = [], [], []
    for path in py_files:
        rel = path.relative_to(project).as_posix()
        hits, err = scan_file(path, pack)
        if err:
            parse_errors.append({"file": rel, "error": err})
        for hit in hits:
            hit["file"] = rel
            all_hits.append(hit)
        if not hits and not err:
            clean_files.append(rel)
    all_hits.sort(key=lambda h: (h["file"], h["line"], h["pattern_id"]))
    return {
        "project": str(project),
        "pack": {"id": pack.id, "version": pack.version, "date": pack.date,
                 "title": pack.title},
        "hits": all_hits,
        "files_scanned": [p.relative_to(project).as_posix() for p in py_files],
        "files_with_hits": sorted({h["file"] for h in all_hits}),
        "files_without_hits": clean_files,
        "parse_errors": parse_errors,
        "not_covered_languages": {lang: files for lang, files in sorted(other_langs.items())},
        "note": (f"Results are hits for pack {pack.id} version {pack.version} only. "
                 "Zero hits does NOT mean this project is ready to upgrade."),
    }
