-- Oyuncu gol pazarı için ESPN maç özetlerinden oyuncu bazlı maç istatistikleri.
-- SQLite karşılığı: app/scrapers/espn_players.py SCHEMA.

CREATE TABLE IF NOT EXISTS public.player_match_stats (
    match_id TEXT NOT NULL,         -- ESPN matches.id
    player_id TEXT NOT NULL,        -- ESPN athlete id
    team_id TEXT NOT NULL,          -- ESPN team id (matches.home_id / away_id)
    name TEXT NOT NULL,
    position TEXT,                  -- ESPN kısaltması (CF, AM-L, CD-R, G ...)
    starter INTEGER NOT NULL DEFAULT 0,
    minutes REAL NOT NULL DEFAULT 0,
    goals INTEGER NOT NULL DEFAULT 0,       -- penaltılar dahil, kendi kalesine goller hariç
    shots INTEGER NOT NULL DEFAULT 0,
    shots_on_target INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (match_id, player_id)
);
CREATE INDEX IF NOT EXISTS ix_player_stats_team ON public.player_match_stats(team_id, match_id);

-- Özeti çekilmiş maçlar (oyuncusuz dönen özet tekrar denenmesin diye)
CREATE TABLE IF NOT EXISTS public.player_fetch_log (
    match_id TEXT PRIMARY KEY,
    fetched_at TEXT NOT NULL,
    players INTEGER NOT NULL DEFAULT 0
);

ALTER TABLE public.player_match_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.player_fetch_log ENABLE ROW LEVEL SECURITY;
