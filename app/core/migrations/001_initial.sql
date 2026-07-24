CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    timezone TEXT NOT NULL,
    all_day INTEGER NOT NULL DEFAULT 0,
    start_at TEXT,
    event_date TEXT,
    event_time TEXT,
    recurrence_json TEXT NOT NULL DEFAULT '{}',
    source_text TEXT NOT NULL DEFAULT '',
    source_kind TEXT NOT NULL DEFAULT 'text',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_status
    ON events(status);

CREATE TABLE IF NOT EXISTS notification_rules (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    kind TEXT NOT NULL DEFAULT 'relative',
    minutes_before INTEGER NOT NULL DEFAULT 0,
    time_of_day TEXT,
    source TEXT NOT NULL DEFAULT 'default',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_notification_rules_event
    ON notification_rules(event_id, enabled);

CREATE TABLE IF NOT EXISTS event_occurrences (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    occurs_at TEXT NOT NULL,
    occurrence_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled',
    created_at TEXT NOT NULL,
    UNIQUE(event_id, occurs_at)
);

CREATE INDEX IF NOT EXISTS idx_event_occurrences_date
    ON event_occurrences(occurrence_date, status);

CREATE TABLE IF NOT EXISTS notification_jobs (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    occurrence_id TEXT NOT NULL REFERENCES event_occurrences(id) ON DELETE CASCADE,
    notification_rule_id TEXT NOT NULL REFERENCES notification_rules(id) ON DELETE CASCADE,
    notify_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    sent_at TEXT,
    telegram_message_id INTEGER,
    failure_reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(occurrence_id, notification_rule_id, notify_at)
);

CREATE INDEX IF NOT EXISTS idx_notification_jobs_due
    ON notification_jobs(status, notify_at);

CREATE TABLE IF NOT EXISTS parse_attempts (
    id TEXT PRIMARY KEY,
    source_kind TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    transcript TEXT NOT NULL DEFAULT '',
    agent_provider TEXT NOT NULL,
    agent_model TEXT NOT NULL DEFAULT '',
    prompt_version TEXT NOT NULL DEFAULT '',
    agent_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL,
    error TEXT NOT NULL DEFAULT '',
    created_event_ids_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

