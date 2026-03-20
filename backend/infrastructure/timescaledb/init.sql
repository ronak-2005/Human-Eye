CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

CREATE TABLE IF NOT EXISTS keystroke_events (
    id           UUID DEFAULT gen_random_uuid(),
    session_id   VARCHAR(255) NOT NULL,
    key          VARCHAR(50)  NOT NULL,
    keydown_time DOUBLE PRECISION NOT NULL,
    keyup_time   DOUBLE PRECISION NOT NULL,
    ts           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
SELECT create_hypertable('keystroke_events','ts', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS mouse_events (
    id         UUID DEFAULT gen_random_uuid(),
    session_id VARCHAR(255) NOT NULL,
    x          DOUBLE PRECISION,
    y          DOUBLE PRECISION,
    event_type VARCHAR(20),
    velocity   DOUBLE PRECISION,
    ts         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
SELECT create_hypertable('mouse_events','ts', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS scroll_events (
    id         UUID DEFAULT gen_random_uuid(),
    session_id VARCHAR(255) NOT NULL,
    scroll_y   DOUBLE PRECISION,
    direction  VARCHAR(10),
    velocity   DOUBLE PRECISION,
    ts         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
SELECT create_hypertable('scroll_events','ts', if_not_exists => TRUE);

SELECT add_retention_policy('keystroke_events', INTERVAL '90 days', if_not_exists => TRUE);
SELECT add_retention_policy('mouse_events',     INTERVAL '90 days', if_not_exists => TRUE);
SELECT add_retention_policy('scroll_events',    INTERVAL '90 days', if_not_exists => TRUE);
