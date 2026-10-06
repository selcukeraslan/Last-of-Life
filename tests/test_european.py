import random
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from app import db
from app.model import engine, european
from app.model.european import CupElo, build_ratings, fit_offsets


def synthetic_games(true_a, true_b, n, seed=1):
    """A ligi ile B ligi ortak ölçekte true_a/true_b ofsetli; takım gücü 1500 civarı."""
    rng = random.Random(seed)
    games = []
    for _ in range(n):
        hr, ar = rng.gauss(1500, 60), rng.gauss(1500, 60)
        home_a = rng.random() < 0.5
        hl, al = ("a", "b") if home_a else ("b", "a")
        offs = {"a": true_a, "b": true_b}
        p = 1 / (1 + 10 ** (-(hr + offs[hl] + 60 - ar - offs[al]) / 400))
        s = 1.0 if rng.random() < p * 0.8 else 0.5 if rng.random() < 0.4 else 0.0
        games.append((hr, hl, ar, al, s))
    return games


class OffsetFitTests(unittest.TestCase):
    def test_no_data_returns_prior(self):
        prior = {"a": 100.0, "b": -40.0}
        self.assertEqual(fit_offsets([], prior), prior)

    def test_data_moves_offsets_toward_truth_but_stays_shrunk(self):
        prior = {"a": 0.0, "b": 0.0}
        games = synthetic_games(true_a=120.0, true_b=0.0, n=600)
        fitted = fit_offsets(games, prior)
        self.assertGreater(fitted["a"] - fitted["b"], 40)  # A ligi daha güçlü bulundu
        self.assertLess(fitted["a"] - fitted["b"], 200)    # önsel büzülmesi aşırı uca gitmeyi engeller

    def test_few_games_stay_close_to_prior(self):
        prior = {"a": 50.0, "b": 0.0}
        fitted = fit_offsets(synthetic_games(-200.0, 0.0, n=3), prior)
        self.assertLess(abs(fitted["a"] - 50.0), 30)


def match(i, home, away, hid, aid, hg, ag, league="uefa.champions", days_ago=30):
    ts = datetime.now(timezone.utc) - timedelta(days=days_ago, minutes=i)
    return {"id": f"{league}-{i}", "league": league, "ts": ts, "kickoff": ts.isoformat(timespec="seconds"),
            "home": home, "away": away, "home_id": hid, "away_id": aid, "home_goals": hg, "away_goals": ag,
            "completed": 1}


class RatingTests(unittest.TestCase):
    def test_league_offset_separates_equal_domestic_ratings(self):
        info = {"1": ("eng.1", 1500.0), "2": ("tur.1", 1500.0)}
        ratings, off, adj = build_ratings([], info, {"1": "Chelsea", "2": "Konya"})
        self.assertGreater(ratings["Chelsea"] - ratings["Konya"], 200)
        self.assertEqual(adj, {})

    def test_unknown_league_team_learns_from_cup_results(self):
        info = {"1": ("eng.1", 1500.0)}
        games = [match(i, "Arsenal", "Kairat", "1", "9", 0, 1, days_ago=60 - i) for i in range(4)]
        ratings, off, adj = build_ratings(games, info, {"1": "Arsenal", "9": "Kairat"})
        self.assertGreater(adj["9"], 20)
        self.assertLess(adj["1"], 0)

    def test_cup_elo_interface(self):
        elo = CupElo({"A": 1600.0}, default=1480.0)
        self.assertEqual(elo.get("Z"), 1480.0)
        self.assertGreater(elo.expected("A", "Z"), 0.6)


class CupModelTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for p in (patch.object(db, "DB_PATH", Path(tmp.name) / "t.db"), patch.object(db, "DATABASE_URL", None)):
            p.start()
            self.addCleanup(p.stop)
        db.init_db()
        engine.invalidate()
        self.addCleanup(engine.invalidate)
        self.patch_refresh = patch.object(engine, "_refresh_if_stale")
        self.patch_refresh.start()
        self.addCleanup(self.patch_refresh.stop)

    def insert(self, m, completed=1):
        with db.session() as conn:
            conn.execute(
                "INSERT INTO matches(id, league, kickoff, home, away, home_id, away_id, home_goals, away_goals, "
                "completed, status) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (m["id"], m["league"], m["kickoff"], m["home"], m["away"], m["home_id"], m["away_id"],
                 m["home_goals"], m["away_goals"], completed, "FT" if completed else "sched"))

    def test_cross_league_prediction(self):
        teams = {"eng.1": [("1", "Chelsea"), ("2", "Burnley")], "tur.1": [("3", "Konyaspor"), ("4", "Rizespor")]}
        n = 0
        for lg, ((ha, home), (aa, away)) in teams.items():
            for i in range(12):  # güçlü ev sahibi her ligde aynı seviyede (iç lig sonuçları aynı)
                n += 1
                self.insert(match(n, home, away, ha, aa, 2, 0, league=lg, days_ago=100 - i))
                n += 1
                self.insert(match(n, away, home, aa, ha, 0, 1, league=lg, days_ago=90 - i))
        # Kupada İngiliz takımı Türk takımını yeniyor
        for i, (hg, ag) in enumerate([(2, 0), (3, 1), (2, 0)]):
            n += 1
            self.insert(match(n, "Chelsea", "Konyaspor", "1", "3", hg, ag, days_ago=40 - i))
        n += 1
        fixture = match(n, "Konyaspor", "Chelsea", "3", "1", None, None, days_ago=-3)
        self.insert(fixture, completed=0)

        model = engine.get_model("uefa.champions")
        self.assertIsInstance(model, european.CupModel)
        pred = model.predict("Konyaspor", "Chelsea", fixture["ts"])
        p = pred["markets"]
        self.assertGreater(p["2"]["p"], p["1"]["p"])  # deplasmandaki İngiliz takımı favori
        self.assertAlmostEqual(p["1"]["p"] + p["X"]["p"] + p["2"]["p"], 1.0, places=2)
        cross = pred["factors"]["cross_league"]
        self.assertEqual(cross["home"]["league"], "tur.1")
        self.assertEqual(cross["away"]["league"], "eng.1")
        self.assertGreater(model.elo.get("Chelsea"), model.elo.get("Konyaspor") + 100)

    def test_cup_model_works_with_no_data(self):
        model = engine.get_model("uefa.europa")
        self.assertEqual(model.upcoming_predictions(), [])

    def test_backtest_skips_cups(self):
        with patch.object(engine, "backtest", return_value={"n": 0}) as bt:
            engine.run_backtests()
        called = {c.args[0] for c in bt.call_args_list}
        self.assertNotIn("uefa.champions", called)
        self.assertIn("tur.2", called)


if __name__ == "__main__":
    unittest.main()
