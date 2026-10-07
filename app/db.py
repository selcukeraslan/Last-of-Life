"""Veritabanı katmanı: DATABASE_URL varsa Supabase Postgres, yoksa yerel SQLite (data/iddia.db).

İki arka uç aynı arayüzü sunar: `?` / `:isim` parametreleri, `row["kolon"]` erişimi, `execute()`.
Postgres şeması `supabase/migrations` altındadır; SQLite şeması aşağıdaki SCHEMA'dır.
"""
import re
import sqlite3
from collections.abc import Mapping
from contextlib import contextmanager

from . import config
from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (
    id TEXT PRIMARY KEY,
    league TEXT NOT NULL,
    kickoff TEXT NOT NULL,          -- ISO UTC
    home TEXT NOT NULL,
    away TEXT NOT NULL,
    home_id TEXT,
    away_id TEXT,
    home_goals INTEGER,
    away_goals INTEGER,
    completed INTEGER NOT NULL DEFAULT 0,
    status TEXT,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_matches_league_kickoff ON matches(league, kickoff);

CREATE TABLE IF NOT EXISTS news (
    id TEXT PRIMARY KEY,            -- link hash
    league TEXT NOT NULL,
    team TEXT NOT NULL,
    title TEXT NOT NULL,
    link TEXT,
    source TEXT,
    published TEXT,
    sentiment REAL NOT NULL DEFAULT 0,
    injury INTEGER NOT NULL DEFAULT 0,
    fetched_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_news_team ON news(league, team, published);

CREATE TABLE IF NOT EXISTS fetch_log (
    league TEXT NOT NULL,
    day TEXT NOT NULL,              -- YYYYMMDD, tamamlanmış gün bir daha çekilmez
    PRIMARY KEY (league, day)
);

CREATE TABLE IF NOT EXISTS iddaa_events (
    id TEXT PRIMARY KEY,
    league TEXT NOT NULL,
    competition_id INTEGER NOT NULL,
    kickoff TEXT NOT NULL,          -- ISO UTC
    home TEXT NOT NULL,
    away TEXT NOT NULL,
    match_id TEXT,                  -- eşleşen ESPN matches.id
    match_score REAL,
    league_name TEXT,
    country TEXT,
    is_small INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_iddaa_events_match ON iddaa_events(match_id);

CREATE TABLE IF NOT EXISTS iddaa_odds (
    event_id TEXT NOT NULL,
    market TEXT NOT NULL,
    odd REAL NOT NULL,
    PRIMARY KEY (event_id, market)
);
CREATE INDEX IF NOT EXISTS ix_iddaa_odds_event ON iddaa_odds(event_id);

CREATE TABLE IF NOT EXISTS iddaa_odds_history (
    event_id TEXT NOT NULL,
    market TEXT NOT NULL,
    odd REAL NOT NULL,
    captured_at TEXT NOT NULL,      -- ISO UTC; yalnız oran değişince satır eklenir
    kickoff TEXT NOT NULL,          -- ISO UTC; bitmiş maç temizliği için
    PRIMARY KEY (event_id, market, captured_at)
);
CREATE INDEX IF NOT EXISTS ix_iddaa_odds_history_kickoff ON iddaa_odds_history(kickoff);
CREATE TABLE IF NOT EXISTS saved_coupons (
    day TEXT NOT NULL,              -- YYYY-MM-DD (Türkiye saati)
    kind TEXT NOT NULL,             -- banko | surprise
    total_odds REAL NOT NULL,
    total_probability REAL NOT NULL,
    odds_source TEXT,
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | won | lost | void
    created_at TEXT NOT NULL,
    settled_at TEXT,
    PRIMARY KEY (day, kind)
);

CREATE TABLE IF NOT EXISTS saved_coupon_picks (
    day TEXT NOT NULL,
    kind TEXT NOT NULL,
    match_id TEXT NOT NULL,         -- matches.id
    league TEXT NOT NULL,
    league_name TEXT,
    kickoff TEXT NOT NULL,          -- ISO UTC
    home TEXT NOT NULL,
    away TEXT NOT NULL,
    market TEXT NOT NULL,
    odds REAL NOT NULL,
    odds_source TEXT,
    probability REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | won | lost | void
    home_goals INTEGER,
    away_goals INTEGER,
    PRIMARY KEY (day, kind, match_id)
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS telegram_posts (
    day TEXT NOT NULL,              -- YYYY-MM-DD (Türkiye saati)
    kind TEXT NOT NULL,             -- 'coupon' | 'result'
    status TEXT NOT NULL,           -- 'sending' (hak alındı) | 'sent'
    message_id TEXT,
    payload TEXT,                   -- coupon: gönderilen kuponların JSON özeti
    created_at TEXT NOT NULL,
    sent_at TEXT,
    PRIMARY KEY (day, kind)
);
"""

# Testler bu değeri None'a çekerek SQLite'a zorlar (gerçek veritabanına asla dokunmaz).
DATABASE_URL = config.DATABASE_URL

_NAMED = re.compile(r"(?<![:\w]):([A-Za-z_]\w*)")


def is_postgres() -> bool:
    return bool(DATABASE_URL)


class Connection:
    """sqlite3 ve psycopg bağlantılarının ortak ince sarmalayıcısı."""

    def __init__(self, raw, postgres: bool):
        self._raw = raw
        self.postgres = postgres

    def _translate(self, sql: str, params):
        if not self.postgres or params is None:
            return sql, params
        sql = sql.replace("%", "%%")
        if isinstance(params, Mapping):
            return _NAMED.sub(r"%(\1)s", sql), params
        return sql.replace("?", "%s"), params

    def execute(self, sql: str, params=None):
        sql, params = self._translate(sql, params)
        return self._raw.execute(sql) if params is None else self._raw.execute(sql, params)

    def executescript(self, sql: str):
        if self.postgres:
            self._raw.execute(sql)
        else:
            self._raw.executescript(sql)

    def commit(self):
        self._raw.commit()

    def rollback(self):
        self._raw.rollback()

    def close(self):
        self._raw.close()


def connect() -> Connection:
    if DATABASE_URL:
        import psycopg
        from psycopg.rows import dict_row

        # Transaction pooler hazırlanmış ifadeleri desteklemez -> prepare_threshold=None
        raw = psycopg.connect(DATABASE_URL, row_factory=dict_row, prepare_threshold=None, connect_timeout=15)
        return Connection(raw, True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    raw = sqlite3.connect(DB_PATH, timeout=30)
    raw.row_factory = sqlite3.Row
    raw.execute("PRAGMA journal_mode=WAL")
    return Connection(raw, False)


@contextmanager
def session():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """SQLite şemasını oluşturur. Postgres şeması supabase/migrations ile yönetilir."""
    if is_postgres():
        return
    from . import odds_log  # import döngüsünü önlemek için burada

    with session() as conn:
        conn.executescript(SCHEMA)
        # Var olan SQLite veritabanlarını sürüm değişmeden ileri uyumlu tut.
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(iddaa_events)").fetchall()}
        for name, declaration in (("league_name", "TEXT"), ("country", "TEXT"),
                                  ("is_small", "INTEGER NOT NULL DEFAULT 0")):
            if name not in columns:
                conn.execute(f"ALTER TABLE iddaa_events ADD COLUMN {name} {declaration}")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_iddaa_events_small_kickoff ON iddaa_events(is_small, kickoff)")
        conn.execute("UPDATE iddaa_events SET is_small=1 WHERE league LIKE 'small:%'")
        conn.executescript(odds_log.SCHEMA)


def get_meta(conn, key, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(conn, key, value):
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )
