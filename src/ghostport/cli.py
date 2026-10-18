"""GhostPort CLI: scan / plan / bundle / claim / verify / status / packs.

Planner only: no command here rewrites project code. `claim` records a
ported-claimed claim. `verify` records verified ONLY from a GhostVerify
post report file. There is no flag to set verified by hand.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .bundle import build_unit_bundle
from .ledger import record_state, record_verified
from .patterns import PackError, load_pack
from .planning import build_plan, write_plan
from .profile import ProfileError
from .scanner import scan_project
from .status import build_status


def _pack(args, project):
    return load_pack(args.pack, Path(project))


def cmd_scan(args):
    pack = _pack(args, args.project)
    result = scan_project(Path(args.project), pack)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    p = result["pack"]
    print(f"GhostPort scan: pack {p['id']} v{p['version']} ({p['date']})")
    print(result["note"])
    for hit in result["hits"]:
        print(f"{hit['file']}:{hit['line']} [{hit['pattern_id']}] {hit['description']}")
    print(f"\n{len(result['hits'])} hit(s) in {len(result['files_with_hits'])} file(s); "
          f"{len(result['files_scanned'])} Python file(s) scanned, "
          f"{len(result['files_without_hits'])} with zero hits for this pack.")
    for lang, files in result["not_covered_languages"].items():
        print(f"NOT COVERED by this pack: {lang} ({len(files)} file(s))")
    for err in result["parse_errors"]:
        print(f"parse error: {err['file']}: {err['error']}")
    return 0


def cmd_plan(args):
    pack = _pack(args, args.project)
    plan, json_path, md_path = write_plan(Path(args.project), pack, args.out)
    # record planned for every unit
    from .ledger import append_record
    for unit in plan["units"]:
        try:
            record_state(Path(args.project), unit["id"], "planned",
                         pack=pack.id, pack_version=pack.version)
        except Exception:
            pass
    if args.json:
        print(json.dumps(plan, indent=2, sort_keys=True))
    else:
        print(f"Plan written: {md_path} + {json_path}")
        for u in plan["units"]:
            print(f"  {u['order']}. {u['id']}: {u['hit_count']} hit(s), est {u['estimated_tokens']} tokens")
        for b in plan["blockers"]:
            print(f"  BLOCKER cycle combined into {b['unit']}: {', '.join(b['files'])}")
    return 0


def cmd_bundle(args):
    pack = _pack(args, args.project)
    plan = build_plan(Path(args.project), pack)
    out = Path(args.out) if args.out else Path(args.project) / ".ghostport" / "bundles" / args.unit
    manifest = build_unit_bundle(Path(args.project), plan, args.unit, out)
    record_state(Path(args.project), args.unit, "bundled",
                 manifest_sha256=manifest["bundle_manifest_sha256"])
    print(f"Bundle written: {out} (manifest sha256 {manifest['bundle_manifest_sha256'][:16]}...)")
    print(f"Files: {len(manifest['files'])}, sliced est tokens: {manifest['total_sliced_tokens']}")
    return 0


def cmd_claim(args):
    record_state(Path(args.project), args.unit, "ported-claimed", by=args.by or "unspecified")
    print(f"Recorded CLAIM (not proof): unit {args.unit} ported-claimed")
    return 0


def cmd_verify(args):
    rec = record_verified(Path(args.project), args.unit, Path(args.report))
    print(f"Recorded VERIFIED for {args.unit} from GhostVerify report {args.report} "
          f"(report sha256 {rec['verify_report_sha256'][:16]}...)")
    return 0


def cmd_status(args):
    status = build_status(Path(args.project))
    if args.json:
        print(json.dumps(status, indent=2, sort_keys=True))
        return 0
    print(f"GhostPort status: {status['project']}")
    for row in status["units"]:
        print(f"  {row['order']}. {row['unit']}: {row['state']} (est {row['estimated_tokens']} tokens)")
    print(f"Verified units: {status['verified_units']}  Estimated tokens remaining: {status['estimated_tokens_remaining']}")
    print(f"Next unit: {status['next_unit']}")
    print(status["note"])
    return 0


def cmd_packs(args):
    from .patterns import pack_search_paths
    for p in pack_search_paths(args.pack or "python-upgrade"):
        print(f"{'[found]' if p.is_file() else '[missing]'} {p}")
    if args.pack:
        pack = load_pack(args.pack)
        print(f"{pack.id} v{pack.version} ({pack.date}): {pack.title}")
        for pat in pack.patterns:
            print(f"  {pat.id}: {pat.description} [ref: {pat.reference}, {pat.reference_date}]")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="ghostport", description="GhostPort: migration slicer (planner only, no codemods)")
    parser.add_argument("--version", action="version", version=f"ghostport {__version__}")
    sub = parser.add_subparsers(dest="cmd")
    for name, fn in (("scan", cmd_scan), ("plan", cmd_plan)):
        sp = sub.add_parser(name); sp.set_defaults(fn=fn)
        sp.add_argument("project"); sp.add_argument("--pack", default="python-upgrade")
        sp.add_argument("--json", action="store_true")
        if name == "plan":
            sp.add_argument("-o", "--out")
    sp = sub.add_parser("bundle"); sp.set_defaults(fn=cmd_bundle)
    sp.add_argument("project"); sp.add_argument("--unit", required=True)
    sp.add_argument("--pack", default="python-upgrade"); sp.add_argument("-o", "--out")
    sp = sub.add_parser("claim"); sp.set_defaults(fn=cmd_claim)
    sp.add_argument("project"); sp.add_argument("--unit", required=True); sp.add_argument("--by")
    sp = sub.add_parser("verify"); sp.set_defaults(fn=cmd_verify)
    sp.add_argument("project"); sp.add_argument("--unit", required=True); sp.add_argument("--report", required=True)
    sp = sub.add_parser("status"); sp.set_defaults(fn=cmd_status)
    sp.add_argument("project"); sp.add_argument("--json", action="store_true")
    sp = sub.add_parser("packs"); sp.set_defaults(fn=cmd_packs)
    sp.add_argument("--pack")
    args = parser.parse_args(argv)
    if not getattr(args, "fn", None):
        parser.print_help()
        return 2
    try:
        return args.fn(args)
    except (PackError, ProfileError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
