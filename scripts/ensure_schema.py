"""Yalnız idempotent ileri onarımı uygular; Supabase migration geçmişini değiştirmez."""
from pathlib import Path
import sys
import os
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.db import init_db, is_postgres, session


def ensure():
    if not is_postgres():
        if os.environ.get("REQUIRE_POSTGRES") == "1":
            raise RuntimeError("DATABASE_URL is required")
        init_db()
        return
    with session() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(73192401)')
        conn.executescript((Path(__file__).resolve().parent.parent / 'supabase/migrations/20261024000000_reconcile_and_predictions.sql').read_text())


if __name__ == '__main__':
    ensure()
