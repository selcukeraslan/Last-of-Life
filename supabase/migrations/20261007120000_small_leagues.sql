-- Preserve iddaa bulletin competition labels for the separate small leagues view.
ALTER TABLE public.iddaa_events ADD COLUMN IF NOT EXISTS league_name TEXT;
ALTER TABLE public.iddaa_events ADD COLUMN IF NOT EXISTS country TEXT;
ALTER TABLE public.iddaa_events ADD COLUMN IF NOT EXISTS is_small INTEGER NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS ix_iddaa_events_small_kickoff
    ON public.iddaa_events(is_small, kickoff);

ALTER TABLE public.iddaa_events ENABLE ROW LEVEL SECURITY;
