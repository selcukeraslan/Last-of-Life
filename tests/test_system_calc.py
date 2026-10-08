"""Sistem kuponu / kupon defteri / favoriler: saf JS hesapları node ile test edilir; node yoksa atlanır."""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class SystemCalcJsTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node kurulu değil")
    def test_node_suite(self):
        run = subprocess.run(["node", "--test", "tests/js/system_calc.test.js"], cwd=ROOT,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_assets_wired_into_page(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-tab="ledger"', html)
        self.assertIn('id="tab-ledger"', html)
        order = [html.index(f"/static/{n}") for n in ("system-calc.js", "slip.js", "extras.js", "app.js")]
        self.assertEqual(order, sorted(order))


if __name__ == "__main__":
    unittest.main()
