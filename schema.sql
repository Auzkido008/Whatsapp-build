-- LagosGo Supabase schema
-- Run this once in your Supabase SQL editor

-- Users table
CREATE TABLE IF NOT EXISTS users (
    phone        TEXT PRIMARY KEY,
    name         TEXT NOT NULL DEFAULT '',
    is_premium   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Routes table
CREATE TABLE IF NOT EXISTS routes (
    id             SERIAL PRIMARY KEY,
    phone          TEXT NOT NULL REFERENCES users(phone) ON DELETE CASCADE,
    label          TEXT NOT NULL DEFAULT 'Home→Work',
    origin         TEXT NOT NULL,
    destination    TEXT NOT NULL,
    arrive_by      TEXT NOT NULL,          -- 'HH:MM' 24h Lagos time
    alert_enabled  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(phone, label)
);

-- Index for morning alert cron (all alert-enabled routes)
CREATE INDEX IF NOT EXISTS idx_routes_alert ON routes(alert_enabled) WHERE alert_enabled = TRUE;

-- Row-Level Security (optional but recommended)
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE routes ENABLE ROW LEVEL SECURITY;

-- Service role policy (your backend uses the service key, not anon key, for full access)
CREATE POLICY "service_all_users"  ON users  FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "service_all_routes" ON routes FOR ALL USING (TRUE) WITH CHECK (TRUE);
