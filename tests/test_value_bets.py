import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app import db, value_bets as vb
from app.value_bets import collect, explain_empty, market_group
from app.value_bets import value_bets as value_bets_endpoint


def pred(mid, markets, kickoff="2026-10-17T14:00Z", league="eng.1"):
    return {"id": mid, "league": league, "kickoff": kickoff, "home": f"H{mid}", "away": f"A{mid}",
            "markets": {m: {"p": p, "suggested": round(1 / p, 2), "fair": round(1 / p, 2)} for m, p in markets.items()}}


def odds(**by_market):
    return {"event_id": "e", "updated_at": "2026-10-10T10:00:00+00:00", "odds": by_market}


class CollectTest(unittest.TestCase):
    def test_ev_formula_sorting_and_fields(self):
        preds = [pred(1, {"1": 0.50, "X": 0.25}), pred(2, {"Ü2.5": 0.60})]
        by_match = {"1": odds(**{"1": 2.20, "X": 3.60}), "2": odds(**{"Ü2.5": 1.75})}  # +%5
        r = collect(preds, by_match)
        self.assertEqual([(x["id"], x["selection"]) for x in r["items"]], [(1, "1"), (2, "Ü2.5")])
        first = r["items"][0]
        self.assertAlmostEqual(first["ev"], 0.5 * 2.2 - 1, places=4)  # +%10 (> +%5); X: 0.25*3.6-1 < 0 elenir
        self.assertAlmostEqual(first["implied_probability"], 1 / 2.2, places=4)
        self.assertEqual((first["market"], first["model_probability"], first["iddaa_odds"]), ("Maç Sonucu", 0.5, 2.2))
        self.assertEqual(r["items"][1]["market"], "Alt/Üst 2.5")
        self.assertEqual((r["matches"], r["matches_with_odds"], r["positive_ev_total"]), (2, 2, 2))

    def test_only_positive_ev(self):
        r = collect([pred(1, {"1": 0.5})], {"1": odds(**{"1": 2.0})})  # EV tam 0 -> değerli değil
        self.assertEqual(r["items"], [])
        self.assertEqual(r["positive_ev_total"], 0)

    def test_matches_or_markets_without_iddaa_odds_are_skipped(self):
        preds = [pred(1, {"1": 0.9, "X": 0.9}), pred(2, {"1": 0.9})]
        r = collect(preds, {"1": odds(**{"1": 1.5})})  # maç 2 eşleşmemiş; maç 1'de X için oran yok
        self.assertEqual([(x["id"], x["selection"]) for x in r["items"]], [(1, "1")])
        self.assertEqual(r["matches_with_odds"], 1)

    def test_small_league_predictions_are_excluded(self):
        small = {"id": "s", "league": "small:aland:premier", "small_league": True,
                 "kickoff": "2026-10-10T10:00:00+00:00", "home": "A", "away": "B",
                 "markets": {"1": {"p": 0.9}}}
        r = collect([small], {"s": odds(**{"1": 4.0})})
        self.assertEqual(r["items"], [])

    def test_small_league_predictions_are_excluded(self):
        small = {"id": "s", "league": "small:aland:premier", "small_league": True,
                 "kickoff": "2026-10-10T10:00:00+00:00", "home": "A", "away": "B",
                 "markets": {"1": {"p": 0.9}}}
        r = collect([small], {"s": {"updated_at": "t", "odds": {"1": 4.0}}})
        self.assertEqual(r["items"], [])

    def test_odds_not_above_one_and_unknown_markets_ignored(self):
        r = collect([pred(1, {"1": 0.9})], {"1": odds(**{"1": 1.0, "KG Var": 3.0})})
        self.assertEqual((r["items"], r["matches_with_odds"]), ([], 0))

    def test_min_prob_and_min_ev_filters(self):
        preds = [pred(1, {"1": 0.20, "2": 0.55})]
        by_match = {"1": odds(**{"1": 7.0, "2": 2.0})}  # 1: EV +%40 p .20 ; 2: EV +%10 p .55
        self.assertEqual(len(collect(preds, by_match)["items"]), 2)
        self.assertEqual([x["selection"] for x in collect(preds, by_match, min_prob=0.3)["items"]], ["2"])
        self.assertEqual([x["selection"] for x in collect(preds, by_match, min_ev=0.2)["items"]], ["1"])
        r = collect(preds, by_match, min_prob=0.3, min_ev=0.2)
        self.assertEqual((r["items"], r["positive_ev_total"]), ([], 2))

    def test_market_groups(self):
        self.assertEqual([market_group(s) for s in ("1", "X2", "KG Yok", "A3.5", "Ü1.5")],
                         ["Maç Sonucu", "Çifte Şans", "Karşılıklı Gol", "Alt/Üst 3.5", "Alt/Üst 1.5"])


class EmptyMessageTest(unittest.TestCase):
    def msg(self, matches, with_odds, positive):
        return explain_empty({"items": [], "matches": matches, "matches_with_odds": with_odds,
                              "positive_ev_total": positive}, 7, 0.3, 0.05)

    def test_each_reason_has_its_own_message(self):
        no_matches, no_odds, filtered, no_value = (self.msg(0, 0, 0), self.msg(5, 0, 0), self.msg(5, 3, 2), self.msg(5, 3, 0))
        self.assertIn("maç yok", no_matches)
        self.assertIn("iddaa.com oranı bulunamadı", no_odds)
        self.assertIn("filtrelerin", filtered)
        self.assertIn("%30", filtered)
        self.assertIn("EV > 0", no_value)
        self.assertEqual(len({no_matches, no_odds, filtered, no_value}), 4)

    def test_no_message_when_results_exist(self):
        self.assertIsNone(explain_empty({"items": [{}]}, 7, 0, 0))


class BuildValueBetsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        patcher = patch.object(db, "DB_PATH", Path(self.tmp.name) / "t.db")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)
        db.init_db()

    def fake_models(self, predictions):
        model = type("M", (), {"upcoming_predictions": lambda self, d: predictions})()
        return (patch.object(vb, "LEAGUES", {"eng.1": {"name": "Premier League"}}),
                patch.object(vb.engine, "get_model", lambda league: model))

    def test_end_to_end_with_db_odds_and_started_matches_skipped(self):
        now = datetime.now(timezone.utc)
        fmt = lambda t: t.strftime("%Y-%m-%dT%H:%MZ")
        preds = [pred("10", {"1": 0.55, "X": 0.25}, kickoff=fmt(now + timedelta(days=1))),
                 pred("11", {"1": 0.70}, kickoff=fmt(now - timedelta(minutes=30))),  # başlamış
                 pred("12", {"1": 0.40}, kickoff=fmt(now + timedelta(days=2)))]  # iddaa oranı yok
        with db.session() as conn:
            conn.execute("INSERT INTO iddaa_events(id, league, competition_id, kickoff, home, away, match_id, updated_at)"
                         " VALUES ('e10','eng.1',1,'2026-10-17T14:00:00+00:00','H10','A10','10','2026-10-10T10:00:00+00:00')")
            conn.execute("INSERT INTO iddaa_events(id, league, competition_id, kickoff, home, away, match_id, updated_at)"
                         " VALUES ('e11','eng.1',1,'2026-10-17T14:00:00+00:00','H11','A11','11','2026-10-10T10:00:00+00:00')")
            for event, market, odd in (("e10", "1", 2.0), ("e10", "X", 3.0), ("e11", "1", 2.0)):
                conn.execute("INSERT INTO iddaa_odds(event_id, market, odd) VALUES (?, ?, ?)", (event, market, odd))
            db.set_meta(conn, "iddaa_last_update", "2026-10-10T10:00:00+00:00")
        p1, p2 = self.fake_models(preds)
        with p1, p2:
            r = vb.build_value_bets(days=7, min_prob=0.3, min_ev=0.05)
        self.assertEqual([(x["id"], x["selection"]) for x in r["items"]], [("10", "1")])
        self.assertEqual((r["matches"], r["matches_with_odds"]), (2, 1))
        self.assertEqual((r["items"][0]["league_name"], r["iddaa_last_update"]), ("Premier League", "2026-10-10T10:00:00+00:00"))
        self.assertIsNone(r["message"])

    def test_empty_database_gives_explanatory_message(self):
        future = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%MZ")
        p1, p2 = self.fake_models([pred("10", {"1": 0.55}, kickoff=future)])
        with p1, p2:
            r = vb.build_value_bets()
        self.assertEqual((r["items"], r["matches"], r["matches_with_odds"]), ([], 1, 0))
        self.assertIn("iddaa.com oranı bulunamadı", r["message"])

    def test_endpoint_is_registered_and_params_are_bounded(self):
        from app.main import app
        self.assertIn("/api/value-bets", app.openapi()["paths"])
        with patch.object(vb, "build_value_bets", return_value={"items": []}) as build:
            self.assertEqual(value_bets_endpoint(days=3, min_prob=0.2, min_ev=0.1), {"items": []})
        build.assert_called_once_with(3, 0.2, 0.1)


if __name__ == "__main__":
    unittest.main()
