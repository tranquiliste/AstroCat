from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Dict, Tuple

from database import Database


LEGACY_SOURCE = "photo_notes.json"


def _load_photo_notes(path: Path) -> Dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        return payload
    return {}


def _table_row_count(connection: sqlite3.Connection, table_name: str) -> int:
    row = connection.execute(f"SELECT COUNT(*) AS cnt FROM {table_name}").fetchone()
    if row is None:
        return 0
    return int(row["cnt"])


def _migrate_image_notes(connection: sqlite3.Connection, payload: Dict) -> int:
    count = 0
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        if key.startswith("__"):
            continue
        note_text = value.strip()
        image_id = Path(key).name.strip()
        if not image_id or not note_text:
            continue
        connection.execute(
            """
            INSERT INTO image_notes (
                image_id,
                title,
                description,
                status,
                legacy_source,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(image_id)
            DO UPDATE SET
                description = excluded.description,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                image_id,
                image_id,
                note_text,
                "imported",
                LEGACY_SOURCE,
            ),
        )
        count += 1
    return count


def _migrate_thumbnails(connection: sqlite3.Connection, payload: Dict) -> int:
    thumbnails = payload.get("__thumbnails__", {})
    if not isinstance(thumbnails, dict):
        return 0
    count = 0
    for key, value in thumbnails.items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        thumbnail_filename = value.strip()
        if not thumbnail_filename:
            continue
        parts = key.split(":", 1)
        if len(parts) != 2:
            continue
        catalog_name = parts[0].strip()
        object_id = parts[1].strip().upper()
        if not catalog_name or not object_id:
            continue
        connection.execute(
            """
            INSERT INTO object_thumbnails (catalog_name, object_id, thumbnail_filename)
            VALUES (?, ?, ?)
            ON CONFLICT(catalog_name, object_id)
            DO UPDATE SET thumbnail_filename = excluded.thumbnail_filename
            """,
            (catalog_name, object_id, thumbnail_filename),
        )
        count += 1
    return count


def migrate_photo_notes_to_sqlite(photo_notes_path: Path, db_path: Path, force: bool = False) -> Tuple[int, int, str]:
    database = Database(db_path)
    database.initialize()

    payload = _load_photo_notes(photo_notes_path)
    if not payload:
        return 0, 0, f"No photo notes to import at {photo_notes_path}."

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        image_notes_count = _table_row_count(connection, "image_notes")
        thumbnails_count = _table_row_count(connection, "object_thumbnails")

        if not force and (image_notes_count > 0 or thumbnails_count > 0):
            return 0, 0, (
                "Tables already contain data. "
                "Use --force to re-run the import and overwrite imported rows."
            )

        if force:
            connection.execute("DELETE FROM image_notes WHERE legacy_source = ?", (LEGACY_SOURCE,))
            connection.execute("DELETE FROM object_thumbnails")

        imported_notes = _migrate_image_notes(connection, payload)
        imported_thumbs = _migrate_thumbnails(connection, payload)
        connection.commit()
    finally:
        connection.close()

    return imported_notes, imported_thumbs, "Import completed."
