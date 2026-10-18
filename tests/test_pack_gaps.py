"""Known-gap tests against the v1.0.0 pack (documented in REPORT_B.md).

These two tests encode behaviour the PLAN's verification bar implies
(a pattern must hit the real-world form of the deprecated API) but that
core v1.0.0's matchers miss, found by Agent B while reconciling the
fixtures to Agent A's pack on Oct 14, 2026:

1. PYUP005 (distutils) uses an ``import_module`` matcher. Core's scanner
   matches ``from X import ...`` only when the module equals the listed
   name exactly, so the idiomatic ``from distutils.core import setup``
   produces NO hit.
2. PYUP007 (threading camelCase) lists currentThread / activeCount /
   isDaemon / setDaemon, but not ``isAlive`` - ``Thread.isAlive()`` was
   removed in Python 3.10 on the same cleanup the pattern cites.

Both tests are expected to FAIL until the pack/matchers are fixed by
the core owner. They are kept in the suite, unskipped, so the failure
stays visible instead of being silently absorbed. Fixes belong in
patterns/** / src/**, which are outside Agent B's file ownership.
"""
from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _helpers import CORE_AVAILABLE, PACK_ID, SKIP_CORE, run_cli  # noqa: E402


@unittest.skipUnless(CORE_AVAILABLE, SKIP_CORE)
class TestKnownPackGaps(unittest.TestCase):
    def _scan_single_file(self, source: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            proj = pathlib.Path(tmp)
            (proj / "only.py").write_text(source, encoding="utf-8")
            proc = run_cli(["scan", str(proj), "--pack", PACK_ID])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return proc.stdout + proc.stderr

    def test_distutils_from_import_form_is_hit(self):
        out = self._scan_single_file(
            "from distutils.core import setup\n\nsetup(name='x')\n"
        )
        self.assertIn("PYUP005", out)

    def test_threading_isalive_is_hit(self):
        out = self._scan_single_file(
            "import threading\n\n\ndef f(t):\n    return t.isAlive()\n"
        )
        self.assertIn("PYUP007", out)


if __name__ == "__main__":
    unittest.main()
