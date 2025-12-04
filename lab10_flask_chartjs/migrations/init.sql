-- migrations/init.sql

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS temperature_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    temperature REAL NOT NULL,
    humidity REAL,
    device_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS motion_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    motion INTEGER NOT NULL,     -- 0/1
    image_path TEXT,             -- local path to captured image
    uploaded INTEGER DEFAULT 0   -- 0=not uploaded/synced, 1=uploaded
);

CREATE TABLE IF NOT EXISTS actuator_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_name TEXT NOT NULL UNIQUE,
    state INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sync_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_synced_temperature_id INTEGER DEFAULT 0,
    last_synced_motion_id INTEGER DEFAULT 0,
    last_sync_ts TEXT
);

INSERT OR IGNORE INTO sync_meta (id) VALUES (1);

COMMIT;
