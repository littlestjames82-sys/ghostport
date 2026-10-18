# GhostPort

**Port a codebase one proven slice at a time.**

Version and framework migrations fail in a predictable way: the surface
that actually needs changing is a small fraction of the repo, but an
agent (or a person) handed the whole repo makes unrelated edits, and a
single file handed over alone loses the call graph, so a migrated callee
breaks an unmigrated caller at run time.

GhostPort is the migration slicer and workbench paired with
[GhostSlice](https://github.com/littlestjames82-sys/ghostslice). It
scans a project for migration patterns, groups the hits into units,
orders the units leaves-first over the dependency graph, and exports one
GhostSlice bundle per unit: the unit in full, already-ported
dependencies as stable context, not-yet-ported callers as signatures,
and a checklist tied to the unit's tests.

By Ghost Developer Studio. MIT licensed (planned). **Zero dependencies**
(Python standard library only), **local-first**: no network calls, no
telemetry, your code never leaves the machine.

Position in the Ghost stack: GhostSlice builds task bundles,
GhostPort builds *migration* bundles from pattern state,
GhostVerify checks each ported unit when it comes back.

> Status: v0.1 is in build (Oct 14, 2026). This README describes the
> v0.1 scope in `PLAN.md`. Nothing here is a claim that a release exists
> yet; check the repo's releases before relying on install steps.

## What GhostPort does not do

- It **never performs the migration**: no code rewriting, no auto-fixes,
  no codemods. Port prepares and sequences; agents and humans port.
- It does **not run your tests**. That is GhostVerify's post step, in a
  temporary copy, with its own guardrails.
- A scan with no hits says **"no hits for pack X version Y"**, never
  "this project is ready to upgrade". A pattern pack only finds what
  its patterns know, and the scan names the languages it does not cover.

## Install (once v0.1 lands)

```bash
pip install .
ghostport --help
```

Requires Python 3.10 or newer. Until then, run from a checkout with
`PYTHONPATH=src python3 -m ghostport --help` if `src/` is present.

## Quickstart

```bash
ghostport scan  ~/my-project --pack python-upgrade
ghostport plan  ~/my-project --pack python-upgrade
ghostport bundle ~/my-project --unit unit-legacy-storage -o /tmp/port-unit-001
ghostport status ~/my-project
```

1. **scan** lists every pattern hit (file, line, pattern id, plain-words
   description, unit), the files scanned with zero hits, and the
   languages in the project the pack does not cover. It also prints the
   pack version and date, so a stale pack looks stale.
2. **plan** writes `PORT_PLAN.md` and `port-plan.json`: units in
   dependency order (leaves first), covering tests attached where known
   (method labelled), per-unit estimated token totals, and blockers.
   A cycle in the touched set is combined into one unit and named,
   never silently ordered.
3. **bundle** exports one unit as a GhostSlice bundle plus `UNIT.md`:
   patterns to fix with locations, contract notes (callers included at
   signatures that must keep working), the test command from the
   profile if any, and a state box. The bundle validates with
   `ghostslice check`.
4. **status** is the resumption view for a migration that spans weeks:
   units planned / bundled / ported-claimed / verified, estimated tokens
   remaining, and the next unit in order.

## The first pack: `python-upgrade`

One pack, done well, beats five packs done badly. The first pack is a
Python version-upgrade pattern set. Every pattern carries an id, a
plain-words description, and a dated source reference; an undated
pattern is a bug.

The pack as shipped in `patterns/python-upgrade.json` (v1.0.0,
2026-10-14) has twelve patterns, ids `PYUP001` to `PYUP012`:

| ID | Pattern |
|---|---|
| PYUP001 | ABCs imported from `collections` instead of `collections.abc` (removed 3.10) |
| PYUP002 | `asyncio.coroutine` decorator (removed 3.11) |
| PYUP003 | `inspect.getargspec` (removed 3.11) |
| PYUP004 | `imp` module (removed 3.12) |
| PYUP005 | `distutils` (removed 3.12, PEP 632) |
| PYUP006 | `configparser.SafeConfigParser` / `readfp` (removed 3.12) |
| PYUP007 | `threading` camelCase aliases (`currentThread`, `activeCount`, ...) |
| PYUP008 | `unittest` legacy aliases (`failUnless`, `assertEquals`, ...) (removed 3.12) |
| PYUP009 | `ssl.wrap_socket` / `ssl.match_hostname` (removed 3.12) |
| PYUP010 | `typing.io` / `typing.re` pseudo-modules (removed 3.12) |
| PYUP011 | `locale.getdefaultlocale` (deprecated 3.11, scheduled for removal) |
| PYUP012 | `datetime.utcnow` / `utcfromtimestamp` (deprecated 3.12) |

Pattern hits are findings only: file + line + pattern id, in the same
redaction-safe style as GhostSlice's secrets guard.

Known v1.0.0 pack gaps, pinned by tests in `tests/test_pack_gaps.py`
and recorded in `REPORT_B.md`: the idiomatic
`from distutils.core import setup` form is not hit by PYUP005's
matcher, and `Thread.isAlive()` is not in PYUP007's name list.
`fractions.gcd` (removed 3.9) is a proposed thirteenth pattern, with a
fixture pair in the test suite, but is **not** in pack v1.0.0.

## State, the ledger, and the word "verified"

Progress lives in one local file in the project,
`.ghostport-history.jsonl`. Each entry records a unit, its bundle hash,
a state change (`planned`, `bundled`, `ported-claimed`, `verified`),
and, for verified units, the GhostVerify report it rests on.

**Verified is not a claim.** `ported-claimed` is a user or agent saying
the work is done. `verified` can only be written from a GhostVerify post
report referenced in the ledger. A project whose ledger has claims but
no Verify report shows **zero verified units** in `status`, which is
the correct answer.

## Profile

GhostPort reads a `port` section in the project's `.ghostslice.json`:

```json
{
  "port": {
    "pack": "python-upgrade",
    "unit_budget_tokens": 20000,
    "test_command": null,
    "overrides": { "merge_units": [], "order_after": {} }
  }
}
```

Static graphs miss dynamic calls (registries, string dispatch), so the
profile supports a manual reorder/merge override. When an override is
used, the plan says so. See `examples/ghostslice-profile-snippet.json`.

Token totals and costs are **estimates** from GhostSlice's estimator
and its local, dated price table, labelled as estimates everywhere,
never presented as live prices or billed amounts.

## Examples

`examples/demo_project/` is a three-file legacy project with one hit
per file and a real dependency chain; `examples/sample_port_plan/`
holds labelled sample outputs. See `examples/README.md`.

## Tests

```bash
python3 -m unittest discover -s tests
```

The suite is stdlib `unittest` only. Layer 1 validates the fixtures
themselves (a positive and a look-alike negative file per pattern, an
ordering chain, a two-node cycle, a resume ledger whose verified count
must be zero). Layer 2 drives the real CLI (`scan` / `plan` / `bundle`
/ `status`) against copies of those fixtures.

## Layout (planned v0.1)

```
src/ghostport/   core: scanner/pattern engine, unit formation, graph
                 sequencing, bundle export, ledger, CLI
patterns/        pattern packs as data files (id, description, dated
                 reference per pattern)
tests/           unittest suite + fixtures
examples/        demo project, sample plan outputs, profile snippet
PLAN.md          the v0.1 plan this README follows
```

## Licence

MIT, planned with the v0.1 release, same pattern as GhostSlice,
Agent Seatbelt, and Ghost Hands. No paid layer is decided; additional
maintained pattern packs are the only paid candidate named in the
plan, and nothing is priced.
