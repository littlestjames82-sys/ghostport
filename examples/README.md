# GhostPort examples

- `demo_project/` - a tiny unmigrated legacy Python project (3 files,
  3 pattern hits, a real dependency chain). Start here.
- `sample_port_plan/` - illustrative samples of what `plan` and `bundle`
  write (`PORT_PLAN.md`, `port-plan.json`, a `UNIT.md` checklist). These
  files are hand-written samples of the format, clearly labelled, not
  generated output.
- `ghostslice-profile-snippet.json` - the `port` section a project adds
  to its `.ghostslice.json` (pack choice, per-unit budget, manual
  reorder/merge override for dynamic-call cases the static graph can
  miss, as called out in PLAN.md).

Walkthrough (once the core is installed):

```bash
ghostport scan  examples/demo_project --pack python-upgrade
ghostport plan  examples/demo_project --pack python-upgrade
ghostport bundle examples/demo_project --unit unit-legacy-storage -o /tmp/port-unit-legacy-storage
ghostport status examples/demo_project
```
