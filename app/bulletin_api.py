"""Günlük bülten: model eşleşmesi olmayan gerçek iddaa maçları da kaybolmaz."""
import json
from datetime import date, datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException
from .config import LEAGUES
from .db import session, get_meta
from .model import engine
from .scrapers.iddaa import load_constraints
from . import ops
from .model.coupons import TZ
from .model.small_leagues import bulletin_event

router = APIRouter()
LEAGUE_ORDER = ('tur.1', 'eng.1', 'esp.1', 'ger.1', 'ita.1', 'fra.1', 'tur.2',
                'ned.1', 'por.1', 'uefa.champions', 'uefa.europa')


def build_bulletin(day: date, category: str, league: str | None = None):
    start = datetime.combine(day, datetime.min.time(), TZ).astimezone(timezone.utc)
    end = start + timedelta(days=1)
    with session() as conn:
        rows = conn.execute('SELECT e.*,o.market,o.odd FROM iddaa_events e '
                            'LEFT JOIN iddaa_odds o ON o.event_id=e.id '
                            'WHERE e.kickoff>=? AND e.kickoff<? ORDER BY e.kickoff,e.id',
                            (start.isoformat(), end.isoformat())).fetchall()
        constraints = load_constraints(conn)
        updated = get_meta(conn, 'iddaa_last_update')
        coverage = json.loads(get_meta(conn, 'iddaa_stats') or 'null')
        days = sorted({datetime.fromisoformat(r['kickoff'].replace('Z','+00:00')).astimezone(TZ).date().isoformat()
                       for r in conn.execute('SELECT kickoff FROM iddaa_events')})
    events = {}
    for row in rows:
        if bool(row['is_small']) != (category == 'other') or (league and row['league'] != league):
            continue
        event = events.setdefault(row['id'], {**dict(row), 'iddaa_odds': {}})
        if row['market'] and row['odd']:
            event['iddaa_odds'][row['market']] = row['odd']
    modeled, limited = [], []
    for event in events.values():
        base = {k: event[k] for k in ('league','kickoff','home','away','country','competition_id')}
        base['country'] = LEAGUES.get(event['league'], {}).get('country', event['country'])
        base.update({'league_name': LEAGUES.get(event['league'], {}).get('name', event['league_name']),
                     'iddaa_event_id': event['id'], 'iddaa_updated_at': event['updated_at'],
                     'iddaa_min_matches': constraints.get(event['id'], {})})
        # Kimliği doğrulanmış fikstür varsa model kurulabilir; eksik eşleşme bültenden maçı silmez.
        model = engine.get_model(event['league']) if event['match_id'] and event['league'] in LEAGUES else None
        fixture = next((m for m in model.upcoming if str(m['id']) == str(event['match_id'])), None) if model else None
        if fixture:
            prediction = model.predict(fixture['home'], fixture['away'], datetime.fromisoformat(event['kickoff'].replace('Z','+00:00')))
            modeled.append({**base, **prediction, 'id': str(event['match_id'])})
        else:
            limited.append(bulletin_event({**base, 'id': 'iddaa:'+event['id'], 'small_league': True,
                                          'bulletin_only': True, 'iddaa_odds': event['iddaa_odds']}))
    from .main import _attach_iddaa_odds
    matches = _attach_iddaa_odds(modeled) + limited
    groups = {}
    for item in matches:
        group = groups.setdefault(item['league'], {'league':item['league'], 'name':item['league_name'],
                                                   'country':item.get('country',''), 'matches':[]})
        group['matches'].append(item)
    rank = {key:i for i,key in enumerate(LEAGUE_ORDER)}
    ordered = sorted(groups.values(), key=lambda g:(rank.get(g['league'],999),g['country'],g['name']))
    for group in ordered:
        group['matches'].sort(key=lambda m: (-(m.get('confidence') or 0), m['kickoff'], m['id']))
    return {'day':day.isoformat(), 'category':category, 'groups':ordered, 'total':len(matches),
            'modeled':len(modeled), 'limited':len(limited), 'coverage':coverage, 'updated_at':updated, 'available_days':days}


@router.get('/api/bulletin')
def bulletin(day: date | None = None, category: str = 'main', league: str | None = None):
    if category not in ('main','other'):
        raise HTTPException(400, 'Bilinmeyen bülten türü')
    if league and (category != 'main' or league not in LEAGUES):
        raise HTTPException(400, 'Bilinmeyen lig')
    target = day or datetime.now(TZ).date()
    return ops.cached(('bulletin', target, category, league), lambda: build_bulletin(target, category, league))
