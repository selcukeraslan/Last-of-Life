-- İddaa oranlarının ileriye dönük kaydı (harmanlı/harmansız backtest). SQLite karşılığı: app/odds_log.py SCHEMA.
-- iddaa_odds her senkronda silinip yeniden yazıldığı için geçmiş oran tutmaz; bu tablo ESPN maç kimliği başına
-- her pazarın maçtan önceki son oranını ve ilk görülen oranını saklar (maç başladıktan sonra güncellenmez).

CREATE TABLE IF NOT EXISTS public.odds_log (
    match_id TEXT NOT NULL,         -- ESPN matches.id
    market TEXT NOT NULL,
    odd DOUBLE PRECISION NOT NULL,  -- maçtan önce görülen son oran
    first_odd DOUBLE PRECISION NOT NULL,
    first_seen TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (match_id, market)
);

ALTER TABLE public.odds_log ENABLE ROW LEVEL SECURITY;
