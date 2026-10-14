import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db
from app.model import players
from app.scrapers import espn_players as ep


def roster(match_id, rows):
    return [{"match_id": match_id, "player_id": pid, "name": pid.title(), "position": pos, "minutes": mins,
             "goals": goals} for pid, pos, mins, goals in rows]


def season(n=10):
    """Forvet 'striker' 90 dk/maç, her 2 maçta 1 gol; orta saha 'mid' 1 gol; savunmacı hiç; yedek az oynar."""
    matches = [{"id": str(i)} for i in range(n, 0, -1)]
    rows = []
    for i in range(n, 0, -1):
        rows += roster(str(i), [("striker", "CF", 90, 1 if i % 2 == 0 else 0), ("mid", "AM", 90, 1 if i == 3 else 0),
                                ("back", "CD-L", 90, 0), ("keeper", "G", 90, 0)])
    rows += roster("10", [("sub", "CF", 15, 1)])
    return matches, rows


class EstimateTest(unittest.TestCase):
    def test_ranking_and_team_share(self):
        matches, rows = season()
        out = players.estimate(matches, rows, 1.6)
        self.assertTrue(out["available"])
        names = [p["name"] for p in out["players"]]
        self.assertEqual(names[0], "Striker")
        self.assertNotIn("Keeper", names)  # kaleci ~0
        total_lambda = sum(-math.log(1 - p["p"]) for p in out["players"])
        self.assertLessEqual(total_lambda, 1.6 * players.SHARE + 1e-3)  # takım xG'sini aşmaz
        self.assertGreater(out["players"][0]["p"], out["players"][1]["p"])
        self.assertAlmostEqual(out["players"][0]["fair"], 1 / out["players"][0]["p"], delta=0.01)

    def test_more_team_goals_raise_probability(self):
        matches, rows = season()
        low = players.estimate(matches, rows, 0.8)["players"][0]["p"]
        high = players.estimate(matches, rows, 2.4)["players"][0]["p"]
        self.assertGreater(high, low)

    def test_low_data_flag_and_shrinkage(self):
        matches, rows = season()
        rows += roster("9", [("rookie", "CF", 20, 1)])  # 20 dk 1 gol: oran 4.5/90 ham, büzülmeli
        out = {p["name"]: p for p in players.estimate(matches, rows, 1.6, top=10)["players"]}
        self.assertTrue(out["Rookie"]["low_data"])
        self.assertFalse(out["Striker"]["low_data"])
        self.assertLess(out["Rookie"]["rate90"], 1.0)

    def test_player_absent_from_recent_matches_is_dropped(self):
        matches, rows = season(12)
        rows += roster("1", [("old", "CF", 90, 5)])  # son 6 maçta yok
        names = [p["name"] for p in players.estimate(matches, rows, 1.6, top=10)["players"]]
        self.assertNotIn("Old", names)

    def test_not_enough_matches(self):
        matches, rows = season(2)
        self.assertFalse(players.estimate(matches[:2], rows, 1.5)["available"])

    def test_position_groups(self):
        self.assertEqual([players.position_group(a) for a in ("CF", "LF", "AM-L", "CM", "CD-R", "LB", "G", None)],
                         ["F", "F", "M", "M", "D", "D", "G", "D"])


class ParseTest(unittest.TestCase):
    def entry(self, pid, **kw):
        base = {"athlete": {"id": pid, "displayName": f"P{pid}"}, "starter": True, "subbedOut": False,
                "subbedIn": False, "position": {"abbreviation": "CF"},
                "stats": [{"name": "totalGoals", "value": 1.0}, {"name": "totalShots", "value": 3.0},
                          {"name": "shotsOnTarget", "value": 2.0}, {"name": "ownGoals", "value": 0.0}],
                "plays": []}
        base.update(kw)
        return base

    def test_minutes_and_stats(self):
        sub_out = {"substitution": True, "clock": {"displayValue": "61'"}}
        sub_in = {"substitution": True, "clock": {"displayValue": "70'"}}
        data = {"rosters": [{"team": {"id": "7"}, "roster": [
            self.entry("1"), self.entry("2", subbedOut=True, plays=[sub_out]),
            self.entry("3", starter=False, subbedIn=True, plays=[sub_in]),
            self.entry("4", starter=False)]}]}
        rows = {r["player_id"]: r for r in ep.parse_summary(data)}
        self.assertEqual(set(rows), {"1", "2", "3"})  # kulübedekiler yok
        self.assertEqual((rows["1"]["minutes"], rows["2"]["minutes"], rows["3"]["minutes"]), (90, 61, 20))
        self.assertEqual((rows["1"]["goals"], rows["1"]["shots"], rows["1"]["shots_on_target"]), (1, 3, 2))
        self.assertEqual(rows["1"]["team_id"], "7")


class StoreTest(unittest.TestCase):
    def test_for_match_is_time_safe(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for p in (patch.object(db, "DB_PATH", Path(tmp.name) / "t.db"), patch.object(db, "DATABASE_URL", None)):
            p.start()
            self.addCleanup(p.stop)
        db.init_db()
        with db.session() as conn:
            for i in range(1, 9):
                conn.execute("INSERT INTO matches(id, league, kickoff, home, away, home_id, away_id, home_goals, "
                             "away_goals, completed) VALUES(?, 'eng.1', ?, 'h', 'a', 't1', 't2', 1, 0, 1)",
                             (str(i), f"2026-01-{i:02d}T12:00Z"))
                ep.store(conn, str(i), [{"player_id": "s", "team_id": "t1", "name": "Striker", "position": "CF",
                                         "starter": 1, "minutes": 90.0, "goals": 1, "shots": 2,
                                         "shots_on_target": 1}], "now")
            match = {"kickoff": "2026-01-06T12:00Z", "home_id": "t1", "away_id": "t2"}
            out = players.for_match(conn, match, 1.5, 1.0)
            self.assertEqual(out["home"]["matches"], 5)  # 06'dan önceki 5 maç; sonrası sızmaz
            self.assertEqual(out["home"]["players"][0]["goals"], 5)
            self.assertFalse(out["away"]["available"])
            self.assertEqual(ep.pending_matches(conn, 10), [])


if __name__ == "__main__":
    unittest.main()
