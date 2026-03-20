-- HumanEye TimescaleDB initialization
-- Creates hypertables for behavioral signal streams

CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Keystroke events
CREATE TABLE IF NOT EXISTS keystroke_events (
    id          UUID DEFAULT uuid_generate_v4(),
    session_id  UUID NOT NULL,
    key_code    VARCHAR(32) NOT NULL,
    keydown_ts  TIMESTAMPTZ NOT NULL,
    keyup_ts    TIMESTAMPTZ NOT NULL,
    dwell_ms    FLOAT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
SELECT create_hypertable('keystroke_events', 'keydown_ts', if_not_exists => TRUE);
CREATE INDEX ON keystroke_events (session_id, keydown_ts DESC);

-- Mouse events
CREATE TABLE IF NOT EXISTS mouse_events (
    id          UUID DEFAULT uuid_generate_v4(),
    session_id  UUID NOT NULL,
    event_type  VARCHAR(16) NOT NULL,
    x           FLOAT NOT NULL,
    y           FLOAT NOT NULL,
    velocity    FLOAT,
    ts          TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
SELECT create_hypertable('mouse_events', 'ts', if_not_exists => TRUE);
CREATE INDEX ON mouse_events (session_id, ts DESC);

-- Scroll events
CREATE TABLE IF NOT EXISTS scroll_events (
    id          UUID DEFAULT uuid_generate_v4(),
    session_id  UUID NOT NULL,
    delta_y     FLOAT NOT NULL,
    velocity    FLOAT,
    ts          TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
SELECT create_hypertable('scroll_events', 'ts', if_not_exists => TRUE);
CREATE INDEX ON scroll_events (session_id, ts DESC);

-- Retention policy: drop raw signals older than 90 days
SELECT add_retention_policy('keystroke_events', INTERVAL '90 days');
SELECT add_retention_policy('mouse_events', INTERVAL '90 days');
SELECT add_retention_policy('scroll_events', INTERVAL '90 days');
