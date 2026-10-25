"""Son 30 günün kaynak bülten metadatası; güncel bülten değişse de tarihler silinmez."""
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from .db import get_meta, set_meta

PREFIX = 'bulletin_archive:'
TZ = ZoneInfo('Europe/Istanbul')


def load_day(conn, day):
    return json.loads(get_meta(conn, PREFIX+str(day)) or '{}')


def record(conn, events):
    grouped = {}
    for event in events:
        day = datetime.fromisoformat(event['kickoff'].replace('Z','+00:00')).astimezone(TZ).date().isoformat()
        grouped.setdefault(day, {})[str(event['id'])] = event
    for day, events in grouped.items():
        previous = load_day(conn, day)
        previous.update(events)
        set_meta(conn, PREFIX+day, json.dumps(previous, ensure_ascii=False))
    cutoff = (datetime.now(TZ).date()-timedelta(days=30)).isoformat()
    conn.execute('DELETE FROM meta WHERE key LIKE ? AND key<?', (PREFIX+'%', PREFIX+cutoff))


def preserve_current(conn):
    """Silmeden önce mevcut aktif kayıtları kaynak kimliği ve oranlarıyla koru."""
    rows = conn.execute('SELECT e.*,o.market,o.odd FROM iddaa_events e LEFT JOIN iddaa_odds o ON o.event_id=e.id').fetchall()
    events = {}
    for row in rows:
        event = events.setdefault(row['id'], {**dict(row), 'odds':{}})
        if row['market'] and row['odd']:
            event['odds'][row['market']] = row['odd']
    record(conn, list(events.values()))


def available_days(conn):
    return [row['key'][len(PREFIX):] for row in conn.execute('SELECT key FROM meta WHERE key LIKE ?', (PREFIX+'%',))]


def find_event(conn, event_id):
    # Normal durumda oran geçmişi hangi günlük arşiv kaydının okunacağını söyler.
    rows = conn.execute('SELECT DISTINCT kickoff FROM iddaa_odds_history WHERE event_id=?', (event_id,)).fetchall()
    for row in rows:
        day=datetime.fromisoformat(row['kickoff'].replace('Z','+00:00')).astimezone(TZ).date()
        event=load_day(conn,day).get(event_id)
        if event:return event
    for row in conn.execute('SELECT value FROM meta WHERE key LIKE ? ORDER BY key DESC', (PREFIX+'%',)):
        event=json.loads(row['value']).get(event_id)
        if event:return event
    return None
