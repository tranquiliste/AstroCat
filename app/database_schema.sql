PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    description TEXT NOT NULL
);

INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES (1, 'Initial schema');

INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES (2, 'Add image capture blocks (location, integrations, imaging and guiding equipment)');

INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES (3, 'Add reusable imaging setups table');

CREATE TABLE IF NOT EXISTS app_settings (
    setting_key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS catalog_settings (
    catalog_name TEXT PRIMARY KEY,
    metadata_file TEXT,
    catalog_file TEXT,
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    sort_order INTEGER NOT NULL,
    extra_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS catalog_image_dirs (
    catalog_name TEXT NOT NULL,
    dir_path TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (catalog_name, dir_path),
    FOREIGN KEY (catalog_name) REFERENCES catalog_settings (catalog_name) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_catalog_image_dirs_catalog_sort
    ON catalog_image_dirs (catalog_name, sort_order);

-- Astrophotography notes: one note per image file (image_id is UNIQUE).
-- For object-level notes (no specific image), image_id uses sentinel '__object__::{catalog_name}::{object_id}'.
CREATE TABLE IF NOT EXISTS image_notes (
    note_id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id TEXT NOT NULL UNIQUE,
    title TEXT,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    legacy_source TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- One row per image note: free text capture location.
CREATE TABLE IF NOT EXISTS image_capture_details (
    note_id INTEGER PRIMARY KEY,
    capture_location TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (note_id) REFERENCES image_notes (note_id) ON DELETE CASCADE
);

-- Multiple integration entries per image (one row per filter/integration block).
CREATE TABLE IF NOT EXISTS image_filter_integrations (
    integration_id INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id INTEGER NOT NULL,
    filter_name TEXT NOT NULL DEFAULT 'none',
    filter_bandpass_nm REAL,
    filter_brand TEXT,
    filter_model TEXT,
    subframe_count INTEGER NOT NULL DEFAULT 1 CHECK (subframe_count >= 1),
    exposure_seconds REAL NOT NULL CHECK (exposure_seconds >= 0),
    captured_on TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (note_id) REFERENCES image_notes (note_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_image_filter_integrations_note
    ON image_filter_integrations (note_id);

CREATE INDEX IF NOT EXISTS idx_image_filter_integrations_note_date
    ON image_filter_integrations (note_id, captured_on);

-- Exactly one imaging setup per image note.
CREATE TABLE IF NOT EXISTS image_imaging_equipment (
    note_id INTEGER PRIMARY KEY,
    telescope_or_refractor TEXT,
    camera TEXT,
    mount TEXT,
    accessories TEXT,
    software TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (note_id) REFERENCES image_notes (note_id) ON DELETE CASCADE
);

-- Exactly one guiding setup per image note.
CREATE TABLE IF NOT EXISTS image_guiding_equipment (
    note_id INTEGER PRIMARY KEY,
    guide_telescope TEXT,
    guide_camera TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (note_id) REFERENCES image_notes (note_id) ON DELETE CASCADE
);

-- Reusable user imaging setups (global presets, independent from notes/images).
CREATE TABLE IF NOT EXISTS imaging_setups (
    setup_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    telescope_or_refractor TEXT,
    camera TEXT,
    mount TEXT,
    accessories TEXT,
    software TEXT,
    guide_telescope TEXT,
    guide_camera TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_imaging_setups_name
    ON imaging_setups (name);

CREATE TABLE IF NOT EXISTS note_metadata (
    note_id INTEGER NOT NULL,
    metadata_key TEXT NOT NULL,
    value_json TEXT NOT NULL,
    PRIMARY KEY (note_id, metadata_key),
    FOREIGN KEY (note_id) REFERENCES image_notes (note_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS note_tags (
    note_id INTEGER NOT NULL,
    tag TEXT NOT NULL COLLATE NOCASE,
    PRIMARY KEY (note_id, tag),
    FOREIGN KEY (note_id) REFERENCES image_notes (note_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_note_tags_tag
    ON note_tags (tag);

CREATE TABLE IF NOT EXISTS object_thumbnails (
    catalog_name TEXT NOT NULL,
    object_id TEXT NOT NULL,
    thumbnail_filename TEXT NOT NULL,
    PRIMARY KEY (catalog_name, object_id)
);

CREATE TABLE IF NOT EXISTS equipment (
    equipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_type TEXT NOT NULL,
    brand TEXT,
    model TEXT NOT NULL,
    serial_number TEXT,
    notes TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (equipment_type, brand, model, serial_number)
);

CREATE INDEX IF NOT EXISTS idx_equipment_type_model
    ON equipment (equipment_type, model);

CREATE TABLE IF NOT EXISTS note_equipment (
    note_id INTEGER NOT NULL,
    equipment_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (note_id, equipment_id, role),
    FOREIGN KEY (note_id) REFERENCES image_notes (note_id) ON DELETE CASCADE,
    FOREIGN KEY (equipment_id) REFERENCES equipment (equipment_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS imaging_sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id INTEGER NOT NULL,
    session_start TEXT NOT NULL,
    session_end TEXT,
    site_name TEXT,
    sky_quality TEXT,
    weather_notes TEXT,
    notes TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (note_id) REFERENCES image_notes (note_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_imaging_sessions_note_start
    ON imaging_sessions (note_id, session_start);

CREATE TABLE IF NOT EXISTS session_equipment (
    session_id INTEGER NOT NULL,
    equipment_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (session_id, equipment_id, role),
    FOREIGN KEY (session_id) REFERENCES imaging_sessions (session_id) ON DELETE CASCADE,
    FOREIGN KEY (equipment_id) REFERENCES equipment (equipment_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS capture_exposures (
    exposure_id INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id INTEGER NOT NULL,
    session_id INTEGER,
    filter_name TEXT,
    exposure_seconds REAL NOT NULL,
    subframe_count INTEGER NOT NULL DEFAULT 1,
    total_integration_seconds REAL,
    binning TEXT,
    gain REAL,
    offset REAL,
    sensor_temperature_c REAL,
    captured_on TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (note_id) REFERENCES image_notes (note_id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES imaging_sessions (session_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_capture_exposures_note
    ON capture_exposures (note_id);

CREATE INDEX IF NOT EXISTS idx_capture_exposures_session
    ON capture_exposures (session_id);