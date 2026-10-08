import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app import db, match_insights
from app.config import LEAGUES


class MatchInsightsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for p in (patch.object(db, "DB_PATH", Path(self.tmp.name) / "t.db"), patch.object(db, "DATABASE_URL", None)):
            p.start()
            self.addCleanup(p.stop)
        db.init_db()
        self.lg = next(iter(LEAGUES))

    def _match(self, conn, mid, days, home, away, hg, ag, done=1):
        k = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
        conn.execute("INSERT INTO matches(id,league,kickoff,home,away,home_goals,away_goals,completed) VALUES(?,?,?,?,?,?,?,?)",
                     (mid, self.lg, k, home, away, hg, ag, done))

    def test_build(self):
        with db.session() as conn:
            self._match(conn, "a", -10, "A", "B", 2, 1)
            self._match(conn, "b", -5, "C", "A", 0, 0)
            self._match(conn, "n", 3, "A", "B", None, None, 0)
            conn.execute("INSERT INTO news(id,league,team,title,published,injury) VALUES('1',?,?,?,?,1)",
                         (self.lg, "A", "Yıldız sakat", datetime.now(timezone.utc).isoformat()))
        d = match_insights.build("n")
        self.assertEqual([g["res"] for g in d["form"]["home"]], ["B", "G"])
        self.assertEqual(d["h2h"][0]["score"], "2-1")
        self.assertEqual(d["goals"]["home"]["btts"], 50)
        self.assertEqual(d["goals"]["home"]["clean_sheet"], 50)
        self.assertTrue(d["news"]["home"][0]["injury"])
        self.assertEqual(d["odds"], {})

    def test_unknown_match_404(self):
        with self.assertRaises(HTTPException):
            match_insights.insights("nope")


if __name__ == "__main__":
    unittest.main()
