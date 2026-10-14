-- news_intel: haber sınıfı ve tetikleyen kalıp (SQLite karşılığı: app/db.py init_db).
ALTER TABLE public.news ADD COLUMN IF NOT EXISTS category TEXT;
ALTER TABLE public.news ADD COLUMN IF NOT EXISTS reason TEXT;
