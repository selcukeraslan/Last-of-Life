"""Kupon oluşturucu: saf JS hesapları (static/slip-calc.js) node ile test edilir; node yoksa atlanır."""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class SlipCalcJsTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node kurulu değil")
    def test_node_suite(self):
        run = subprocess.run(["node", "--test", "tests/js/slip_calc.test.js"], cwd=ROOT,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_assets_wired_into_page(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-tab="slip"', html)
        self.assertIn('id="tab-slip"', html)
        # slip.js, app.js'ten önce yüklenmeli (app.js açılışta Slip.button çağırır)
        order = [html.index(f"/static/{name}") for name in ("slip-calc.js", "slip.js", "app.js")]
        self.assertEqual(order, sorted(order))
        for name in ("slip-calc.js", "slip.js", "slip.css"):
            self.assertTrue((ROOT / "static" / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()
