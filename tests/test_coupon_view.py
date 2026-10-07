import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class CouponViewJsTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node kurulu değil")
    def test_node_suite(self):
        run = subprocess.run(["node", "--test", "tests/js/coupon_view.test.js"], cwd=ROOT,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_view_module_loads_before_app(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        order = [html.index(f"/static/{name}") for name in ("coupon-view.js", "app.js")]
        self.assertEqual(order, sorted(order))
        self.assertTrue((ROOT / "static" / "coupon-view.js").is_file())


if __name__ == "__main__":
    unittest.main()
