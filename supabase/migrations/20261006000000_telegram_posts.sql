-- Telegram kanalına gönderilen günlük kupon / sonuç mesajlarının kaydı (app/telegram_bot.py).
-- (day, kind) birincil anahtarı aynı gün aynı türden ikinci gönderimi engeller.
CREATE TABLE IF NOT EXISTS public.telegram_posts (
    day TEXT NOT NULL,              -- YYYY-MM-DD (Türkiye saati)
    kind TEXT NOT NULL,             -- 'coupon' | 'result'
    status TEXT NOT NULL,           -- 'sending' (hak alındı) | 'sent'
    message_id TEXT,                -- Telegram mesaj kimliği (sonuç, kuponu yanıt olarak yazar)
    payload TEXT,                   -- coupon: gönderilen kuponların JSON özeti
    created_at TEXT NOT NULL,
    sent_at TEXT,
    PRIMARY KEY (day, kind)
);

-- Supabase'in herkese açık REST arayüzünden erişilemesin (RLS açık, politika yok).
ALTER TABLE public.telegram_posts ENABLE ROW LEVEL SECURITY;
