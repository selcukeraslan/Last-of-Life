"""DB'de kalıcı backtest kuyruğu; hesap GitHub Actions worker'ında çalışır."""
import json
import secrets
from datetime import datetime, timedelta, timezone
from .db import get_meta, init_db, session, set_meta

KEY = 'backtest_job'
LEASE_MINUTES = 45


def now():
    return datetime.now(timezone.utc)


def status():
    with session() as conn:
        raw = get_meta(conn, KEY)
    job = json.loads(raw) if raw else {'status': 'idle'}
    if job['status'] in ('queued', 'running') and now() > datetime.fromisoformat(job['expires_at']):
        job = {**job, 'status': 'expired', 'error': 'İşin süresi doldu; yeniden başlatabilirsiniz.'}
    return job


def request():
    for _ in range(3):
        with session() as conn:
            raw = get_meta(conn, KEY)
            old = json.loads(raw) if raw else {}
            if old.get('status') in ('queued', 'running') and now() < datetime.fromisoformat(old['expires_at']):
                return old
            job = {'id': secrets.token_hex(16), 'status': 'queued', 'requested_at': now().isoformat(),
                   'expires_at': (now() + timedelta(hours=6)).isoformat()}
            value = json.dumps(job)
            if raw is None:
                cur = conn.execute('INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO NOTHING', (KEY, value))
            else:
                cur = conn.execute('UPDATE meta SET value=? WHERE key=? AND value=?', (value, KEY, raw))
            if cur.rowcount == 1:
                return job
    return status()


def run_pending(build=None):
    from .model import engine
    build = build or (lambda: engine.run_backtests(persist=False))
    with session() as conn:
        raw = get_meta(conn, KEY)
        if not raw:
            return False
        job = json.loads(raw)
        if job['status'] != 'queued' or now() >= datetime.fromisoformat(job['expires_at']):
            return False
        running = json.dumps({**job, 'status': 'running', 'started_at': now().isoformat(),
                              'expires_at': (now() + timedelta(minutes=LEASE_MINUTES)).isoformat()})
        if conn.execute('UPDATE meta SET value=? WHERE key=? AND value=?', (running, KEY, raw)).rowcount != 1:
            return False
    try:
        results = build()
        with session() as conn:
            finished = {**json.loads(running), 'status': 'succeeded', 'finished_at': now().isoformat()}
            if conn.execute('UPDATE meta SET value=? WHERE key=? AND value=?', (json.dumps(finished), KEY, running)).rowcount != 1:
                return False  # eski worker yeni işin sonucunu ezemez
            set_meta(conn, 'backtest', json.dumps(results))
            set_meta(conn, 'backtest_at', now().isoformat())
        return True
    except Exception as exc:
        with session() as conn:
            failed = {**json.loads(running), 'status': 'failed', 'finished_at': now().isoformat(), 'error': type(exc).__name__}
            conn.execute('UPDATE meta SET value=? WHERE key=? AND value=?', (json.dumps(failed), KEY, running))
        raise


if __name__ == '__main__':
    init_db()
    print('backtest completed' if run_pending() else 'no pending backtest')
