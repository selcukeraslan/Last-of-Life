-- Kimlik doğrulama: kullanıcılar, oturumlar, şifre sıfırlama. SQLite karşılığı: app/db.py SCHEMA.
-- Zaman damgaları 'YYYY-MM-DDTHH:MM:SSZ' biçiminde TEXT (sözlük sırası = zaman sırası); uygulama iki arka uçta aynı kodu çalıştırır.
-- Düz metin şifre ve token saklanmaz: password_hash argon2id, token_hash çerez/bağlantı token'ının SHA-256 özetidir.
CREATE TABLE IF NOT EXISTS public.users (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email TEXT NOT NULL UNIQUE CHECK (email = lower(email)),
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS public.sessions (
    token_hash TEXT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_sessions_user ON public.sessions(user_id);

CREATE TABLE IF NOT EXISTS public.password_resets (
    token_hash TEXT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_password_resets_user ON public.password_resets(user_id);

-- Uygulama postgres rolüyle bağlanır (RLS'i atlar); anon/authenticated API rolleri bu tablolara erişemez.
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.password_resets ENABLE ROW LEVEL SECURITY;
