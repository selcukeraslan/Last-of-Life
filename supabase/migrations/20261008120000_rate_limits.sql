-- /api/update için IP başına dakikalık sabit pencere sayacı. SQLite karşılığı: app/ops.py SCHEMA.
CREATE TABLE IF NOT EXISTS public.rate_limits (
    key TEXT NOT NULL,
    window BIGINT NOT NULL,
    hits INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (key, win)
);

ALTER TABLE public.rate_limits ENABLE ROW LEVEL SECURITY;
