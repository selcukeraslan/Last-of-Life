import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app import api_odds_history, db, odds_history
from app.scrapers import iddaa

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
FUTURE = (NOW + timedelta(days=2)).isoformat()


def event(eid="e1", odds=None, kickoff=FUTURE, home="Fenerbahçe", away="Beşiktaş"):
    return {"id": eid, "league": "tur.1", "competition_id": 584, "kickoff": kickoff,
            "home": home, "away": away, "odds": odds or {"1": 2.10, "X": 3.2, "2": 3.8}}


def bulletin(*events):
    """sync_odds'un beklediği iddaa JSON'u (parse_event'in ters işlemi: yalnız 1X2 pazarı)."""
    out = []
    for e in events:
        o = e["odds"]
        out.append({"i": e["id"], "ci": e["competition_id"], "hn": e["home"], "an": e["away"],
                    "d": int(datetime.fromisoformat(e["kickoff"]).timestamp()),
                    "m": [{"t": 1, "st": 1, "s": 1, "o": [{"no": 1, "odd": o["1"]}, {"no": 2, "odd": o["X"]},
                                                          {"no": 3, "odd": o["2"]}]}]})
    return {"isSuccess": True, "data": {"events": out}}


class OddsHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for p in (patch.object(db, "DB_PATH", Path(self.tmp.name) / "t.db"), patch.object(db, "DATABASE_URL", None)):
            p.start()
            self.addCleanup(p.stop)
        db.init_db()
        with db.session() as conn:
            conn.execute("INSERT INTO matches(id, league, kickoff, home, away, completed) "
                         "VALUES('m1','tur.1',?, 'Fenerbahçe','Beşiktaş',0)", (FUTURE,))

    def sync(self, *events):
        with patch.object(iddaa, "fetch_json", return_value=bulletin(*events)), db.session() as conn:
            iddaa.sync_odds(conn)

    def rows(self, where="1=1"):
        with db.session() as conn:
            return [dict(r) for r in conn.execute(
                f"SELECT * FROM iddaa_odds_history WHERE {where} ORDER BY captured_at, market")]

    def test_unchanged_odds_are_not_written_again(self):
        with db.session() as conn:
            self.assertEqual(odds_history.record_snapshot(conn, [event()], "2026-10-10T10:00:00+00:00"), 3)
            self.assertEqual(odds_history.record_snapshot(conn, [event()], "2026-10-10T10:10:00+00:00"), 0)
            changed = event(odds={"1": 1.85, "X": 3.2, "2": 3.8})
            self.assertEqual(odds_history.record_snapshot(conn, [changed], "2026-10-10T10:20:00+00:00"), 1)
        self.assertEqual([(r["market"], r["odd"]) for r in self.rows("market='1'")], [("1", 2.1), ("1", 1.85)])
        self.assertEqual(len(self.rows()), 4)

    def test_sync_appends_history_while_current_odds_are_replaced(self):
        self.sync(event())
        self.sync(event())
        self.assertEqual(len(self.rows()), 3)
        self.sync(event(odds={"1": 1.85, "X": 3.2, "2": 3.8}))
        with db.session() as conn:
            current = conn.execute("SELECT odd FROM iddaa_odds WHERE market='1'").fetchall()
            self.assertEqual([r["odd"] for r in current], [1.85])
        self.assertEqual([r["odd"] for r in self.rows("market='1'")], [2.1, 1.85])

    def test_movement_shows_opening_vs_current_for_changed_markets_only(self):
        self.sync(event())
        self.sync(event(odds={"1": 1.85, "X": 3.2, "2": 4.0}))
        with db.session() as conn:
            mv = odds_history.movements_for_matches(conn, ["m1"])["m1"]
        self.assertEqual(set(mv), {"1", "2"})  # "X" değişmedi
        self.assertEqual((mv["1"]["open"], mv["1"]["current"], mv["1"]["direction"]), (2.1, 1.85, "down"))
        self.assertEqual(mv["1"]["change_pct"], -11.9)
        self.assertEqual(mv["2"]["direction"], "up")

    def test_history_for_match_returns_series_per_market(self):
        self.sync(event())
        self.sync(event(odds={"1": 1.95, "X": 3.2, "2": 3.8}))
        self.sync(event(odds={"1": 1.85, "X": 3.2, "2": 3.8}))
        # A market can disappear from the current bulletin; its historical series remains useful.
        with db.session() as conn:
            conn.execute("DELETE FROM iddaa_odds WHERE market='X'")
        with db.session() as conn:
            data = odds_history.history_for_match(conn, "m1")
            self.assertIsNone(odds_history.history_for_match(conn, "yok"))
        self.assertEqual([p["odd"] for p in data["markets"]["1"]], [2.1, 1.95, 1.85])
        self.assertEqual(len(data["markets"]["X"]), 1)

    def test_drops_use_ten_percent_threshold_and_ignore_rises(self):
        self.sync(event("e1", {"1": 2.0, "X": 3.0, "2": 4.0}), event("e2", {"1": 2.0, "X": 3.0, "2": 4.0},
                                                                         home="Galatasaray", away="Trabzonspor"))
        self.sync(event("e1", {"1": 1.8, "X": 3.5, "2": 3.7}),  # 1: -10% (dahil), X: yükseliş, 2: -7.5%
                  event("e2", {"1": 1.82, "X": 3.0, "2": 4.0}, home="Galatasaray", away="Trabzonspor"))  # -9%
        with db.session() as conn:
            result = odds_history.drops(conn, now=NOW)
            self.assertEqual(odds_history.drops(conn, league="eng.1", now=NOW), [])
            self.assertEqual(len(odds_history.drops(conn, min_pct=5, now=NOW)), 2)
        self.assertEqual([m["event_id"] for m in result], ["e1"])
        self.assertEqual([x["market"] for x in result[0]["markets"]], ["1"])
        self.assertEqual(result[0]["match_id"], "m1")
        self.assertEqual(result[0]["max_drop_pct"], 10.0)

    def test_drops_skip_matches_already_kicked_off(self):
        past = (NOW - timedelta(hours=3)).isoformat()
        self.sync(event(kickoff=past, odds={"1": 2.0, "X": 3.0, "2": 4.0}))
        self.sync(event(kickoff=past, odds={"1": 1.5, "X": 3.0, "2": 4.0}))
        with db.session() as conn:
            self.assertEqual(odds_history.drops(conn, now=NOW), [])

    def test_prune_removes_only_finished_events_older_than_30_days(self):
        old, recent = (NOW - timedelta(days=31)).isoformat(), (NOW - timedelta(days=29)).isoformat()
        with db.session() as conn:
            odds_history.record_snapshot(conn, [event("old", kickoff=old), event("recent", kickoff=recent),
                                                event("live", kickoff=old)], "2026-08-01T00:00:00+00:00")
            conn.execute("INSERT INTO iddaa_events(id, league, competition_id, kickoff, home, away, updated_at) "
                         "VALUES('live','tur.1',584,?, 'A','B','x')", (old,))  # hâlâ bültende -> korunur
            removed = odds_history.prune(conn, now=NOW)
        self.assertEqual(removed, 3)
        self.assertEqual({r["event_id"] for r in self.rows()}, {"recent", "live"})

    def test_prune_keeps_whole_series_of_event_with_recent_kickoff(self):
        kickoff = (NOW - timedelta(days=5)).isoformat()
        with db.session() as conn:  # 40 gün önce ilk kayıt, maç 5 gün önce oynandı
            odds_history.record_snapshot(conn, [event("e", kickoff=kickoff)], (NOW - timedelta(days=40)).isoformat())
            self.assertEqual(odds_history.prune(conn, now=NOW), 0)
        self.assertEqual(len(self.rows()), 3)

    def test_endpoints(self):
        self.sync(event(odds={"1": 2.0, "X": 3.0, "2": 4.0}))
        self.sync(event(odds={"1": 1.7, "X": 3.0, "2": 4.0}))
        self.assertEqual(api_odds_history.match_history("m1")["event_id"], "e1")
        with self.assertRaises(HTTPException) as ctx:
            api_odds_history.match_history("yok")
        self.assertEqual(ctx.exception.status_code, 404)
        with patch.object(odds_history, "datetime") as dt:  # kickoff gelecekte kalsın
            dt.now.return_value = NOW
            drops = api_odds_history.odds_drops(min_pct=10, league="tur.1", limit=5)["matches"]
        self.assertEqual(drops[0]["markets"][0]["change_pct"], -15.0)
        with self.assertRaises(HTTPException):
            api_odds_history.odds_drops(min_pct=10, league="xx.9", limit=5)


if __name__ == "__main__":
    unittest.main()
