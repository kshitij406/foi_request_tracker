-- One row per FOI request. due_date is calculated in Python at creation time.
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requester_name TEXT NOT NULL,
    requester_email TEXT NOT NULL,
    subject TEXT NOT NULL,
    received_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'RECEIVED' CHECK(status in('IN_PROGRESS', 'CLOSED', 'RESPONDED', 'WITHDRAWN', 'RECEIVED')),
    assigned_to TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- Append-only audit trail: one row per status change (from_status is NULL for the initial RECEIVED).
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL REFERENCES requests(id),
    from_status TEXT NULL,
    to_status TEXT NOT NULL,
    note TEXT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes back the status/overdue filters and the per-request history lookup.
CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
CREATE INDEX IF NOT EXISTS idx_requests_due_date ON requests(due_date);
CREATE INDEX IF NOT EXISTS idx_events_request_id ON events(request_id);
