from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from typing import Dict, Iterable, Iterator, List, Optional


def database_path_from_config_path(config_path: Path) -> Path:
    return config_path.with_name("astrocat.db")


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.schema_path = Path(__file__).with_name("database_schema.sql")
        self._initialized = False

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        self.initialize()
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        if self._initialized and self.db_path.exists():
            return
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        schema = self.schema_path.read_text(encoding="utf-8")
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(schema)
            connection.execute("PRAGMA user_version = 1")
            connection.commit()
        finally:
            connection.close()
        self._initialized = True

    def has_config_data(self) -> bool:
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT EXISTS(
                    SELECT 1 FROM app_settings
                    UNION ALL
                    SELECT 1 FROM catalog_settings
                ) AS has_data
                """
            ).fetchone()
        return bool(row and row["has_data"])

    def load_config(self) -> Dict:
        self.initialize()
        with self.connection() as connection:
            settings_rows = connection.execute(
                "SELECT setting_key, value_json FROM app_settings ORDER BY setting_key"
            ).fetchall()
            catalog_rows = connection.execute(
                """
                SELECT catalog_name, metadata_file, catalog_file, enabled, sort_order, extra_json
                FROM catalog_settings
                ORDER BY sort_order, catalog_name
                """
            ).fetchall()
            image_dir_rows = connection.execute(
                """
                SELECT catalog_name, dir_path, sort_order
                FROM catalog_image_dirs
                ORDER BY catalog_name, sort_order, dir_path
                """
            ).fetchall()

        if not settings_rows and not catalog_rows:
            return {}

        config: Dict = {}
        for row in settings_rows:
            config[row["setting_key"]] = self._loads_json(row["value_json"])

        catalogs_by_name: Dict[str, Dict] = {}
        for row in catalog_rows:
            extra = self._loads_json(row["extra_json"], default={})
            catalog_entry = dict(extra) if isinstance(extra, dict) else {}
            catalog_entry["name"] = row["catalog_name"]
            catalog_entry["metadata_file"] = row["metadata_file"]
            if row["catalog_file"]:
                catalog_entry["catalog_file"] = row["catalog_file"]
            catalog_entry["enabled"] = bool(row["enabled"])
            catalog_entry["image_dirs"] = []
            catalogs_by_name[row["catalog_name"]] = catalog_entry

        for row in image_dir_rows:
            catalog = catalogs_by_name.get(row["catalog_name"])
            if catalog is not None:
                catalog.setdefault("image_dirs", []).append(row["dir_path"])

        if catalogs_by_name:
            config["catalogs"] = list(catalogs_by_name.values())
        return config

    def save_config(self, config: Dict) -> None:
        settings_payload = {key: value for key, value in config.items() if key != "catalogs"}
        catalogs = list(config.get("catalogs", []))

        with self.connection() as connection:
            connection.execute("DELETE FROM app_settings")
            connection.execute("DELETE FROM catalog_image_dirs")
            connection.execute("DELETE FROM catalog_settings")

            for key, value in sorted(settings_payload.items()):
                connection.execute(
                    """
                    INSERT INTO app_settings (setting_key, value_json, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    (key, self._dumps_json(value), self._utc_now()),
                )

            for sort_order, catalog in enumerate(catalogs):
                if not isinstance(catalog, dict):
                    continue
                name = str(catalog.get("name") or "").strip()
                if not name:
                    continue
                extra = {
                    key: value
                    for key, value in catalog.items()
                    if key not in {"name", "metadata_file", "catalog_file", "enabled", "image_dirs"}
                }
                connection.execute(
                    """
                    INSERT INTO catalog_settings (
                        catalog_name,
                        metadata_file,
                        catalog_file,
                        enabled,
                        sort_order,
                        extra_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        catalog.get("metadata_file"),
                        catalog.get("catalog_file"),
                        1 if catalog.get("enabled", True) else 0,
                        sort_order,
                        self._dumps_json(extra),
                    ),
                )
                for dir_order, dir_path in enumerate(catalog.get("image_dirs", [])):
                    if not dir_path:
                        continue
                    connection.execute(
                        """
                        INSERT INTO catalog_image_dirs (catalog_name, dir_path, sort_order)
                        VALUES (?, ?, ?)
                        """,
                        (name, str(dir_path), dir_order),
                    )

    def import_config(self, config: Dict, overwrite: bool = True) -> None:
        if not overwrite and self.has_config_data():
            return
        self.save_config(config)

    def get_setting(self, key: str, default=None):
        with self.connection() as connection:
            row = connection.execute(
                "SELECT value_json FROM app_settings WHERE setting_key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return default
        return self._loads_json(row["value_json"], default=default)

    def set_setting(self, key: str, value) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO app_settings (setting_key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(setting_key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (key, self._dumps_json(value), self._utc_now()),
            )

    def delete_setting(self, key: str) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM app_settings WHERE setting_key = ?", (key,))

    def create_note(
        self,
        catalog_name: str,
        object_id: str,
        description: str = "",
        title: Optional[str] = None,
        status: str = "draft",
        legacy_source: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> int:
        with self.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO astro_notes (
                    catalog_name,
                    object_id,
                    title,
                    description,
                    status,
                    legacy_source,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    catalog_name,
                    object_id,
                    title,
                    description,
                    status,
                    legacy_source,
                    self._utc_now(),
                    self._utc_now(),
                ),
            )
            note_id = int(cursor.lastrowid)
            if metadata:
                self._replace_note_metadata(connection, note_id, metadata)
        return note_id

    def update_note(
        self,
        note_id: int,
        description: Optional[str] = None,
        title: Optional[str] = None,
        status: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        updates: List[str] = []
        values: List[object] = []
        if title is not None:
            updates.append("title = ?")
            values.append(title)
        if description is not None:
            updates.append("description = ?")
            values.append(description)
        if status is not None:
            updates.append("status = ?")
            values.append(status)
        updates.append("updated_at = ?")
        values.append(self._utc_now())
        values.append(note_id)
        with self.connection() as connection:
            connection.execute(
                f"UPDATE astro_notes SET {', '.join(updates)} WHERE note_id = ?",
                values,
            )
            if metadata is not None:
                self._replace_note_metadata(connection, note_id, metadata)

    def get_note(self, note_id: int) -> Optional[Dict]:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM astro_notes WHERE note_id = ?",
                (note_id,),
            ).fetchone()
            if row is None:
                return None
            metadata_rows = connection.execute(
                "SELECT metadata_key, value_json FROM note_metadata WHERE note_id = ? ORDER BY metadata_key",
                (note_id,),
            ).fetchall()
        note = dict(row)
        note["metadata"] = {
            item["metadata_key"]: self._loads_json(item["value_json"])
            for item in metadata_rows
        }
        return note

    def list_notes(self, catalog_name: Optional[str] = None, object_id: Optional[str] = None) -> List[Dict]:
        clauses: List[str] = []
        values: List[object] = []
        if catalog_name:
            clauses.append("catalog_name = ?")
            values.append(catalog_name)
        if object_id:
            clauses.append("object_id = ?")
            values.append(object_id)
        query = "SELECT * FROM astro_notes"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY updated_at DESC, note_id DESC"
        with self.connection() as connection:
            rows = connection.execute(query, values).fetchall()
        return [dict(row) for row in rows]

    def upsert_equipment(
        self,
        equipment_type: str,
        model: str,
        brand: Optional[str] = None,
        serial_number: Optional[str] = None,
        notes: str = "",
        metadata: Optional[Dict] = None,
    ) -> int:
        metadata_json = self._dumps_json(metadata or {})
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO equipment (
                    equipment_type,
                    brand,
                    model,
                    serial_number,
                    notes,
                    metadata_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(equipment_type, brand, model, serial_number) DO UPDATE SET
                    notes = excluded.notes,
                    metadata_json = excluded.metadata_json
                """,
                (
                    equipment_type,
                    brand,
                    model,
                    serial_number,
                    notes,
                    metadata_json,
                    self._utc_now(),
                ),
            )
            row = connection.execute(
                """
                SELECT equipment_id
                FROM equipment
                WHERE equipment_type = ?
                  AND ifnull(brand, '') = ifnull(?, '')
                  AND model = ?
                  AND ifnull(serial_number, '') = ifnull(?, '')
                """,
                (equipment_type, brand, model, serial_number),
            ).fetchone()
        if row is None:
            raise RuntimeError("Unable to resolve equipment row after upsert.")
        return int(row["equipment_id"])

    def list_equipment(self, equipment_type: Optional[str] = None) -> List[Dict]:
        query = "SELECT * FROM equipment"
        values: List[object] = []
        if equipment_type:
            query += " WHERE equipment_type = ?"
            values.append(equipment_type)
        query += " ORDER BY equipment_type, brand, model"
        with self.connection() as connection:
            rows = connection.execute(query, values).fetchall()
        return [dict(row) for row in rows]

    def add_note_equipment(self, note_id: int, equipment_id: int, role: str, details: Optional[Dict] = None) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO note_equipment (note_id, equipment_id, role, details_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(note_id, equipment_id, role) DO UPDATE SET
                    details_json = excluded.details_json
                """,
                (note_id, equipment_id, role, self._dumps_json(details or {})),
            )

    def add_session(
        self,
        note_id: int,
        session_start: str,
        session_end: Optional[str] = None,
        site_name: Optional[str] = None,
        sky_quality: Optional[str] = None,
        weather_notes: Optional[str] = None,
        notes: str = "",
        metadata: Optional[Dict] = None,
    ) -> int:
        with self.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO imaging_sessions (
                    note_id,
                    session_start,
                    session_end,
                    site_name,
                    sky_quality,
                    weather_notes,
                    notes,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    note_id,
                    session_start,
                    session_end,
                    site_name,
                    sky_quality,
                    weather_notes,
                    notes,
                    self._dumps_json(metadata or {}),
                ),
            )
        return int(cursor.lastrowid)

    def add_capture_exposure(
        self,
        note_id: int,
        exposure_seconds: float,
        subframe_count: int = 1,
        filter_name: Optional[str] = None,
        session_id: Optional[int] = None,
        total_integration_seconds: Optional[float] = None,
        binning: Optional[str] = None,
        gain: Optional[float] = None,
        offset: Optional[float] = None,
        sensor_temperature_c: Optional[float] = None,
        captured_on: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> int:
        total_value = total_integration_seconds
        if total_value is None:
            total_value = float(exposure_seconds) * int(subframe_count)
        with self.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO capture_exposures (
                    note_id,
                    session_id,
                    filter_name,
                    exposure_seconds,
                    subframe_count,
                    total_integration_seconds,
                    binning,
                    gain,
                    offset,
                    sensor_temperature_c,
                    captured_on,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    note_id,
                    session_id,
                    filter_name,
                    exposure_seconds,
                    subframe_count,
                    total_value,
                    binning,
                    gain,
                    offset,
                    sensor_temperature_c,
                    captured_on,
                    self._dumps_json(metadata or {}),
                ),
            )
        return int(cursor.lastrowid)

    def _replace_note_metadata(self, connection: sqlite3.Connection, note_id: int, metadata: Dict) -> None:
        connection.execute("DELETE FROM note_metadata WHERE note_id = ?", (note_id,))
        for key, value in sorted(metadata.items()):
            connection.execute(
                "INSERT INTO note_metadata (note_id, metadata_key, value_json) VALUES (?, ?, ?)",
                (note_id, key, self._dumps_json(value)),
            )

    @staticmethod
    def _dumps_json(value) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _loads_json(payload: Optional[str], default=None):
        if payload is None:
            return default
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return default

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")