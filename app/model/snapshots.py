"""Yayımlanan tahminin değişmez, maç öncesi kaydı ve ileriye dönük ölçümü."""
import hashlib
import json
from datetime import datetime, timezone
from functools import lru_cache
from ..config import BASE_DIR, MODEL
from ..db import get_meta, set_meta

SCHEMA = '''
CREATE TABLE IF NOT EXISTS prediction_snapshots (
    match_id TEXT PRIMARY KEY,
    league TEXT NOT NULL,
    kickoff TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    model_version TEXT NOT NULL,
    data_version TEXT,
    parameters TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_prediction_snapshots_league ON prediction_snapshots(league, captured_at);
'''


def now():
    return datetime.now(timezone.utc)


@lru_cache(maxsize=1)
def code_version():
    digest = hashlib.sha256()
    for name in ('config.py', 'news_intel.py', 'model/engine.py', 'model/ratings.py', 'model/predict.py',
                 'model/european.py', 'model/blend.py', 'model/extra_markets.py'):
        digest.update((BASE_DIR / 'app' / name).read_bytes())
    return digest.hexdigest()[:16]


def record(conn, predictions):
    at = now()
    parameters = json.dumps(MODEL, sort_keys=True)
    version = hashlib.sha256((code_version() + parameters).encode()).hexdigest()[:16]
    data_version = '|'.join(get_meta(conn, k, '') or '' for k in ('last_updated_at', 'iddaa_last_update', 'update_data_version'))
    rows = []
    for p in predictions:
        if p.get('small_league') or not p.get('markets') or datetime.fromisoformat(p['kickoff'].replace('Z', '+00:00')) <= at:
            continue
        markets = p['markets']
        payload = {'model': {k: v.get('model_p', v.get('p')) for k, v in markets.items()},
                   'blend': {k: v.get('p') for k, v in markets.items()},
                   'market': {k: v.get('market_p') for k, v in markets.items()},
                   'odds': p.get('iddaa_odds', {}), 'news': p.get('factors', {}).get('news'),
                   'blend_settings': p.get('blend'), 'extra_markets': p.get('extra_markets', {})}
        rows.append((str(p['id']), p['league'], p['kickoff'], at.isoformat(), version, data_version, parameters, json.dumps(payload)))
    conn.executemany('INSERT INTO prediction_snapshots(match_id,league,kickoff,captured_at,model_version,data_version,parameters,payload) '
                     'VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(match_id) DO NOTHING', rows)
    return len(rows)


def record_safely(conn, predictions):
    conn.execute('SAVEPOINT prediction_capture')
    try:
        record(conn, predictions)
        conn.execute('RELEASE SAVEPOINT prediction_capture')
        set_meta(conn, 'prediction_capture_error', '')
    except Exception as exc:
        conn.execute('ROLLBACK TO SAVEPOINT prediction_capture')
        conn.execute('RELEASE SAVEPOINT prediction_capture')
        set_meta(conn, 'prediction_capture_error', type(exc).__name__)


def report(conn):
    from .report import metrics, calibration
    from .blend import GROUPS
    from .settlement import outcome
    rows = conn.execute('SELECT s.*,m.home_goals,m.away_goals,m.kickoff AS actual_kickoff '
                        'FROM prediction_snapshots s JOIN matches m ON m.id=s.match_id WHERE m.completed=1').fetchall()
    samples = {k: [] for k in ('model', 'blend', 'market')}
    market_scores = {}
    versions = set()
    for r in rows:
        captured = datetime.fromisoformat(r['captured_at'].replace('Z', '+00:00'))
        if captured >= datetime.fromisoformat(r['actual_kickoff'].replace('Z', '+00:00')):
            continue
        hg, ag = r['home_goals'], r['away_goals']
        if hg is None or ag is None:
            continue
        payload = json.loads(r['payload'])
        versions.add(r['model_version'])
        actual = 0 if hg > ag else 1 if hg == ag else 2
        # Aynı maç örnekleminde üç varyantın karşılaştırması.
        if all(payload[variant].get(k) is not None for variant in samples for k in ('1', 'X', '2')):
            for variant in samples:
                probs = [payload[variant][k] for k in ('1', 'X', '2')]
                samples[variant].append({'day': r['kickoff'][:10], 'probs': probs, 'actual': actual})
        for market, probability in payload['blend'].items():
            won = outcome(market, hg, ag)
            if probability is None or won is None:
                continue
            score = market_scores.setdefault(market, {'n': 0, 'brier_sum': 0.0})
            score['n'] += 1
            score['brier_sum'] += (probability - int(won)) ** 2
    return {'scope': 'first_published_prematch', 'versions': sorted(versions),
            'variants': {v: {'metrics': metrics(s), 'calibration': calibration(s)} for v, s in samples.items()},
            'markets': {k: {'n': v['n'], 'brier': round(v['brier_sum'] / v['n'], 4)} for k, v in market_scores.items()},
            'stored': conn.execute('SELECT COUNT(*) n FROM prediction_snapshots').fetchone()['n']}
