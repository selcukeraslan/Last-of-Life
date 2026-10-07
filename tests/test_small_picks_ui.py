"""Küçük lig Öneriler UI'sinin HTML öznitelik kaçışını doğrula."""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class SmallPicksUiTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node kurulu değil")
    def test_node_suite(self):
        run = subprocess.run(["node", "--test", "tests/js/small_picks_ui.test.js"], cwd=ROOT,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main()
