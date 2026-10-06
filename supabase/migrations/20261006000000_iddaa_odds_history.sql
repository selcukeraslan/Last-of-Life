-- iddaa oran geçmişi (app/db.py içindeki SQLite şemasının karşılığı).
-- Her iddaa çekiminde oran değiştiyse zaman damgalı satır eklenir; aynı oran tekrar yazılmaz.
-- Bitmiş maçların geçmişi, son kickoff'tan 30 gün sonra uygulama tarafından silinir (app/odds_history.py).

CREATE TABLE IF NOT EXISTS public.iddaa_odds_history (
    event_id TEXT NOT NULL,
    market TEXT NOT NULL,
    odd DOUBLE PRECISION NOT NULL,
    captured_at TEXT NOT NULL,      -- ISO UTC
    kickoff TEXT NOT NULL,          -- ISO UTC
    PRIMARY KEY (event_id, market, captured_at)
);
CREATE INDEX IF NOT EXISTS ix_iddaa_odds_history_kickoff ON public.iddaa_odds_history(kickoff);

ALTER TABLE public.iddaa_odds_history ENABLE ROW LEVEL SECURITY;
