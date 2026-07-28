CREATE TABLE IF NOT EXISTS shopping_lists (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE REFERENCES events(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'Покупки',
    status TEXT NOT NULL DEFAULT 'active',
    source_text TEXT NOT NULL DEFAULT '',
    source_kind TEXT NOT NULL DEFAULT 'text',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_shopping_lists_status
    ON shopping_lists(status);

CREATE TABLE IF NOT EXISTS shopping_items (
    id TEXT PRIMARY KEY,
    shopping_list_id TEXT NOT NULL REFERENCES shopping_lists(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    quantity TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    position INTEGER NOT NULL,
    source_text TEXT NOT NULL DEFAULT '',
    source_kind TEXT NOT NULL DEFAULT 'text',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_shopping_items_list_position
    ON shopping_items(shopping_list_id, status, position);
