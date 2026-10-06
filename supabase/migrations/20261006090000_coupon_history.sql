-- Kupon geçmişi: günün Banko / Sürpriz kuponu ilk üretildiği haliyle dondurulur (gün + tür başına bir kez),
-- maç sonuçları gelince seçimler ve kupon 'won' / 'lost' / 'void' olarak işaretlenir (app/model/coupon_history.py).
-- app/db.py içindeki SQLite şemasının karşılığıdır.

CREATE TABLE IF NOT EXISTS public.saved_coupons (
    day TEXT NOT NULL,              -- YYYY-MM-DD (Türkiye saati)
    kind TEXT NOT NULL,             -- banko | surprise
    total_odds DOUBLE PRECISION NOT NULL,
    total_probability DOUBLE PRECISION NOT NULL,
    odds_source TEXT,
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | won | lost | void
    created_at TEXT NOT NULL,
    settled_at TEXT,
    PRIMARY KEY (day, kind)
);

CREATE TABLE IF NOT EXISTS public.saved_coupon_picks (
    day TEXT NOT NULL,
    kind TEXT NOT NULL,
    match_id TEXT NOT NULL,         -- matches.id
    league TEXT NOT NULL,
    league_name TEXT,
    kickoff TEXT NOT NULL,          -- ISO UTC
    home TEXT NOT NULL,
    away TEXT NOT NULL,
    market TEXT NOT NULL,
    odds DOUBLE PRECISION NOT NULL,
    odds_source TEXT,
    probability DOUBLE PRECISION NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | won | lost | void
    home_goals INTEGER,
    away_goals INTEGER,
    PRIMARY KEY (day, kind, match_id),
    FOREIGN KEY (day, kind) REFERENCES public.saved_coupons(day, kind) ON DELETE CASCADE
);

-- Tablolar Supabase'in herkese açık REST arayüzünden erişilemesin (init_schema ile aynı yaklaşım).
ALTER TABLE public.saved_coupons ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saved_coupon_picks ENABLE ROW LEVEL SECURITY;
