-- İddia Oran Öneri: ortak Postgres şeması (app/db.py içindeki SQLite şemasının karşılığı).
-- Uygulama veritabanına doğrudan (postgres rolüyle, pooler üzerinden) bağlanır.

CREATE TABLE IF NOT EXISTS public.matches (
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
CREATE INDEX IF NOT EXISTS ix_matches_league_kickoff ON public.matches(league, kickoff);

CREATE TABLE IF NOT EXISTS public.news (
    id TEXT PRIMARY KEY,            -- link hash
    league TEXT NOT NULL,
    team TEXT NOT NULL,
    title TEXT NOT NULL,
    link TEXT,
    source TEXT,
    published TEXT,
    sentiment DOUBLE PRECISION NOT NULL DEFAULT 0,
    injury INTEGER NOT NULL DEFAULT 0,
    fetched_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_news_team ON public.news(league, team, published);

CREATE TABLE IF NOT EXISTS public.fetch_log (
    league TEXT NOT NULL,
    day TEXT NOT NULL,
    PRIMARY KEY (league, day)
);

CREATE TABLE IF NOT EXISTS public.iddaa_events (
    id TEXT PRIMARY KEY,
    league TEXT NOT NULL,
    competition_id INTEGER NOT NULL,
    kickoff TEXT NOT NULL,          -- ISO UTC
    home TEXT NOT NULL,
    away TEXT NOT NULL,
    match_id TEXT,                  -- eşleşen ESPN matches.id
    match_score DOUBLE PRECISION,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_iddaa_events_match ON public.iddaa_events(match_id);

CREATE TABLE IF NOT EXISTS public.iddaa_odds (
    event_id TEXT NOT NULL,
    market TEXT NOT NULL,
    odd DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (event_id, market)
);
CREATE INDEX IF NOT EXISTS ix_iddaa_odds_event ON public.iddaa_odds(event_id);

-- Anahtarlar: last_updated_at (son başarılı güncelleme), update_lock (kilidin bitiş zamanı),
-- update_last_error, iddaa_*, espn_done_<lig>, backtest*.
CREATE TABLE IF NOT EXISTS public.meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Tablolar Supabase'in herkese açık REST (anon anahtarı) arayüzünden erişilemesin:
-- RLS açık ve politika yok. Uygulama postgres rolüyle bağlandığı için etkilenmez.
ALTER TABLE public.matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.news ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fetch_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.iddaa_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.iddaa_odds ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.meta ENABLE ROW LEVEL SECURITY;
