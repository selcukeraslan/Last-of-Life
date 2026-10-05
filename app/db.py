import sqlite3
from contextlib import contextmanager

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

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def session():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with session() as conn:
        conn.executescript(SCHEMA)


def get_meta(conn, key, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(conn, key, value):
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )
