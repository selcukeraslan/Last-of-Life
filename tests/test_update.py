import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from app import db, updater
from app.db import Connection, get_meta, set_meta


def iso(delta_minutes=0):
    return (datetime.now(timezone.utc) + timedelta(minutes=delta_minutes)).isoformat(timespec="seconds")


class FakeRaw:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))


class PlaceholderTests(unittest.TestCase):
    def test_postgres_translation(self):
        raw = FakeRaw()
        conn = Connection(raw, postgres=True)
        conn.execute("SELECT * FROM t WHERE a=? AND b LIKE '50%' AND c=?", (1, 2))
        conn.execute("INSERT INTO t(a, kick) VALUES(:a, '14:00Z') ON CONFLICT(a) DO UPDATE SET b=:b::text", {"a": 1, "b": 2})
        conn.execute("SELECT 1")
        self.assertEqual(raw.calls[0][0], "SELECT * FROM t WHERE a=%s AND b LIKE '50%%' AND c=%s")
        self.assertEqual(raw.calls[1][0],
                         "INSERT INTO t(a, kick) VALUES(%(a)s, '14:00Z') ON CONFLICT(a) DO UPDATE SET b=%(b)s::text")
        self.assertEqual(raw.calls[2], ("SELECT 1", None))


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for p in (patch.object(db, "DB_PATH", Path(self.tmp.name) / "t.db"), patch.object(db, "DATABASE_URL", None)):
            p.start()
            self.addCleanup(p.stop)
        db.init_db()

    def meta(self, key):
        with db.session() as conn:
            return get_meta(conn, key)

    def set(self, key, value):
        with db.session() as conn:
            set_meta(conn, key, value)

    def test_lock_is_exclusive_and_expires(self):
        with db.session() as conn:
            self.assertTrue(updater.acquire_lock(conn, 3))
        with db.session() as conn:
            self.assertFalse(updater.acquire_lock(conn, 3))
            set_meta(conn, "update_lock", iso(-1))  # süresi geçmiş kilit
        with db.session() as conn:
            self.assertTrue(updater.acquire_lock(conn, 3))
            updater.release_lock(conn)
        with db.session() as conn:
            self.assertTrue(updater.acquire_lock(conn, 3))

    def test_cooldown_left(self):
        self.assertEqual(updater.cooldown_left(None), 0)
        self.assertEqual(updater.cooldown_left(iso(-11)), 0)
        self.assertGreater(updater.cooldown_left(iso(-1)), 8 * 60)

    def test_quick_update_sets_shared_timestamp_then_cools_down(self):
        with patch.object(updater.espn, "sync_recent", return_value=(5, True)) as espn_sync, \
                patch.object(updater.iddaa, "sync_odds", return_value={}) as odds_sync:
            first = updater.run_quick_update()
            second = updater.run_quick_update()
        self.assertEqual(first["status"], "updated")
        self.assertIsNotNone(first["last_updated_at"])
        self.assertFalse(first["running"])
        self.assertEqual(second["status"], "cooldown")
        self.assertEqual(second["last_updated_at"], first["last_updated_at"])
        self.assertEqual(espn_sync.call_count, len(updater.LEAGUES))
        self.assertEqual(odds_sync.call_count, 1)  # ikinci çağrı kaynaklara gitmedi
        self.assertEqual(updater.status()["last_updated_at"], first["last_updated_at"])

    def test_quick_update_busy_when_locked(self):
        self.set("update_lock", iso(2))
        with patch.object(updater.espn, "sync_recent") as espn_sync:
            result = updater.run_quick_update()
        self.assertEqual(result["status"], "busy")
        self.assertTrue(result["running"])
        espn_sync.assert_not_called()

    def test_quick_update_error_does_not_stamp_or_keep_lock(self):
        with patch.object(updater.espn, "sync_recent", return_value=(0, False)), \
                patch.object(updater.iddaa, "sync_odds", side_effect=RuntimeError("down")):
            result = updater.run_quick_update()
        self.assertEqual(result["status"], "error")
        self.assertIsNone(self.meta("last_updated_at"))
        self.assertFalse(result["running"])
        self.assertEqual(result["cooldown_seconds"], 0)  # hata sonrası hemen tekrar denenebilir

    def test_iddaa_failure_keeps_recent_odds_but_wipes_stale(self):
        with db.session() as conn:
            conn.execute("INSERT INTO iddaa_events(id, league, competition_id, kickoff, home, away, updated_at) "
                         "VALUES('e1','eng.1',43,'2026-10-17T14:00Z','A','B','x')")
            conn.execute("INSERT INTO iddaa_odds(event_id, market, odd) VALUES('e1','1',1.5)")
            set_meta(conn, "iddaa_last_update", iso(-30))
        with patch.object(updater.iddaa, "sync_odds", side_effect=RuntimeError("down")), db.session() as conn:
            self.assertFalse(updater._sync_iddaa(conn))
        self.assertEqual(self.count("iddaa_odds"), 1)
        self.set("iddaa_last_update", iso(-60 * 7))
        with patch.object(updater.iddaa, "sync_odds", side_effect=RuntimeError("down")), db.session() as conn:
            self.assertFalse(updater._sync_iddaa(conn))
        self.assertEqual(self.count("iddaa_odds"), 0)

    def count(self, table):
        with db.session() as conn:
            return conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]

    def test_full_update_skips_when_locked_and_stamps_when_done(self):
        self.set("update_lock", iso(5))
        self.assertEqual(updater.run_update(with_news=False), "skipped")
        self.set("update_lock", "")
        with patch.object(updater.espn, "sync_league", return_value=3), \
                patch.object(updater.iddaa, "sync_odds", return_value={}):
            self.assertEqual(updater.run_update(with_news=False), "ok")
        self.assertIsNotNone(self.meta("last_updated_at"))
        self.assertEqual(self.meta("update_lock"), "")


if __name__ == "__main__":
    unittest.main()
