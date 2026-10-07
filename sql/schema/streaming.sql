CREATE SCHEMA IF NOT EXISTS streaming;
-- ONE ROW = ONE CANONICAL SOURCE EVENT; duplicates across replays do not add rows.
CREATE TABLE IF NOT EXISTS streaming.order_events (
    event_id uuid PRIMARY KEY,
    schema_version integer NOT NULL CHECK (schema_version = 1),
    event_type text NOT NULL,
    order_id text NOT NULL,
    customer_id text NOT NULL,
    occurred_at timestamp NOT NULL,
    payload jsonb NOT NULL,
    received_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS order_events_order_idx ON streaming.order_events (order_id, occurred_at);
-- No FK to a batch snapshot: independently arriving events must be retainable.
CREATE TABLE IF NOT EXISTS streaming.rejected_messages (
    topic text NOT NULL, partition_id integer NOT NULL, offset_id bigint NOT NULL,
    payload bytea, reason text NOT NULL,
    received_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (topic, partition_id, offset_id)
);
CREATE OR REPLACE VIEW streaming.event_counts AS
SELECT event_type, COUNT(*) AS event_count, COUNT(DISTINCT order_id) AS orders
FROM streaming.order_events GROUP BY event_type;
