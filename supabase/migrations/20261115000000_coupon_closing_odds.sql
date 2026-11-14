-- Kupon geçmişi: her seçim için maçtan önce görülen son iddaa oranı (closing line value).
-- app/model/coupon_history.record_closing() settle sırasında doldurur; SQLite şeması app/db.py'de.
ALTER TABLE public.saved_coupon_picks ADD COLUMN IF NOT EXISTS closing_odds DOUBLE PRECISION;
COMMENT ON COLUMN public.saved_coupon_picks.closing_odds IS 'Maçtan önce görülen son iddaa oranı; CLV = odds / closing_odds - 1';
