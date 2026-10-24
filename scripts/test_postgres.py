"""Yalnız yerel, geçici CI PostgreSQL veritabanında migration ve SQL uyumluluk testi."""
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import psycopg
from psycopg.rows import dict_row
from app.db import Connection
from app.updater import acquire_lock, release_lock, renew_lock, LostLease
from app.model import snapshots

url = os.environ['TEST_DATABASE_URL']
parsed = urlparse(url)
assert parsed.hostname in ('127.0.0.1', 'localhost') and parsed.path == '/lol_ci', 'Only disposable CI DB allowed'
files = sorted((Path(__file__).resolve().parent.parent / 'supabase/migrations').glob('*.sql'))
assert len({p.name.split('_', 1)[0] for p in files}) == len(files)
with psycopg.connect(url, row_factory=dict_row, prepare_threshold=None) as raw:
    conn = Connection(raw, True)
    for path in files:
        conn.executescript(path.read_text())
    repair = files[-1].read_text()
    conn.executescript(repair)
    # Legacy duplicate-version case: recorded migration did not install auth/news.
    conn.execute('DROP TABLE public.sessions,public.password_resets,public.users CASCADE')
    conn.execute('ALTER TABLE public.news DROP COLUMN category, DROP COLUMN reason')
    conn.executescript(repair)
    conn.executescript(repair)
    assert conn.execute("SELECT to_regclass('public.users') AS name").fetchone()['name'] == 'users'
    first = acquire_lock(conn, 3)
    assert first and acquire_lock(conn, 3) is None
    assert not release_lock(conn, 'other-owner')
    renew_lock(conn, first, 3)
    assert release_lock(conn, first)
    assert acquire_lock(conn, 3)
    snapshots.record_safely(conn, [])
    assert conn.execute('SELECT COUNT(*) n FROM prediction_snapshots').fetchone()['n'] == 0
print('PostgreSQL migrations, idempotent repair and lease SQL passed')
