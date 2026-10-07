import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db, main, ops


class OpsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [patch.object(db, "DATABASE_URL", None),
                        patch.object(db, "DB_PATH", Path(self.tmp.name) / "t.db")]
        for p in self.patches:
            p.start()
        db.init_db()
        ops._cache.clear()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_rate_limit_blocks_after_limit(self):
        results = [ops.rate_limited("k", 3) for _ in range(5)]
        self.assertEqual(results, [False, False, False, True, True])
        self.assertFalse(ops.rate_limited("other", 3))

    def test_cache_reuses_until_version_changes(self):
        calls = []
        build = lambda: calls.append(1) or len(calls)
        self.assertEqual(ops.cached(("a",), build), 1)
        self.assertEqual(ops.cached(("a",), build), 1)
        with db.session() as conn:
            db.set_meta(conn, "last_updated_at", "2026-01-01T00:00:00+00:00")
        self.assertEqual(ops.cached(("a",), build), 2)

    def test_health_reports_stale_data(self):
        self.assertFalse(ops.health()["ok"])
        with db.session() as conn:
            now = ops.datetime.now(ops.timezone.utc).isoformat()
            db.set_meta(conn, "last_updated_at", now)
            db.set_meta(conn, "iddaa_last_update", now)
        self.assertTrue(ops.health()["ok"])

    def test_health_endpoint_status_and_cdn_header(self):
        client = TestClient(main.app)
        self.assertEqual(client.get("/api/health").status_code, 503)
        self.assertIn("s-maxage", client.get("/api/leagues").headers["cache-control"])
