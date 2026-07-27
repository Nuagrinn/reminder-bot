CREATE TABLE IF NOT EXISTS event_contexts (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    value TEXT NOT NULL,
    normalized_value TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'parser',
    position INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_event_contexts_event
    ON event_contexts(event_id, position);
