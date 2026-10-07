import unittest
from datetime import datetime, timezone

from app.model import report as R


def s(day, probs, actual):
    return {"day": day, "probs": probs, "actual": actual}


class ReportTest(unittest.TestCase):
    def test_metrics(self):
        m = R.metrics([s("2026-01-01", [0.6, 0.2, 0.2], 0), s("2026-01-02", [0.2, 0.3, 0.5], 0)])
        self.assertEqual(m["n"], 2)
        self.assertEqual(m["accuracy"], 0.5)
        self.assertEqual(m["home_baseline"], 1.0)
        self.assertAlmostEqual(m["brier"], (0.24 + (0.64 + 0.09 + 0.25)) / 2, places=3)

    def test_calibration_buckets(self):
        c = R.calibration([s("d", [1.0, 0.0, 0.0], 0), s("d", [0.55, 0.25, 0.2], 1)])
        self.assertEqual(len(c), 10)
        self.assertEqual(sum(b["n"] for b in c), 6)
        self.assertEqual(c[9]["actual"], 1.0)
        self.assertEqual(c[5]["actual"], 0.0)

    def test_trend_window(self):
        now = datetime(2026, 2, 1, tzinfo=timezone.utc)
        t = R.trend([s("2025-12-01", [1, 0, 0], 0), s("2026-01-20", [1, 0, 0], 0)], now)
        self.assertEqual([d["day"] for d in t], ["2026-01-20"])

    def test_empty(self):
        self.assertEqual(R.metrics([]), {"n": 0})


if __name__ == "__main__":
    unittest.main()
