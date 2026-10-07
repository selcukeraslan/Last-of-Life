"""Oran düşüşü UI'sinin küçük liglerde 404 isteği atmaması."""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class OddsDropsUiTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node kurulu değil")
    def test_node_suite(self):
        run = subprocess.run(["node", "--test", "tests/js/odds_drops.test.js"], cwd=ROOT,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main()
