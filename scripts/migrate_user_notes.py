#!/usr/bin/env python3
"""
One-shot migration script to migrate user notes from the old format
to the new separated format.

Can migrate from:
- Old app bundle (Selune.app or SelunelogViewer.app)
- Existing user metadata files

Old format: notes and image_notes in *_metadata.json files.
New format: notes stay in *_catalog.json, image_notes in photo_notes.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = PROJECT_ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from database import Database, database_path_from_config_path  # noqa: E402


def _new_metadata_dir_from_old(old_metadata_dir: Path) -> Path:
    """Derive the new Selune metadata directory from the old AstroCatalogueViewer location."""
    parts = old_metadata_dir.parts
    try:
        # Find the "AstroCatalogueViewer" directory in the path
        idx = parts.index("AstroCatalogueViewer")
        # Replace with "Selune" and add "Selune/metadata"
        base_parts = parts[:idx]
        new_parts = base_parts + ("Selune", "Selune", "metadata")
        return Path(*new_parts)
    except ValueError:
        # If "AstroCatalogueViewer" not found, fallback to default
        return _default_metadata_dir()


def _default_metadata_dir() -> Path:
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Preferences" / "Selune" / "Selune" / "metadata"
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "Selune" / "Selune" / "metadata"
        return home / "AppData" / "Roaming" / "Selune" / "Selune" / "metadata"
    return home / ".config" / "Selune" / "Selune" / "metadata"


def _old_app_candidate_paths() -> List[Path]:
    """Return possible legacy AstroCatalogueViewer metadata paths."""
    home = Path.home()
    candidates: List[Path] = []
    if sys.platform == "darwin":
        support_base = home / "Library" / "Application Support"
        preferences_base = home / "Library" / "Preferences"
        candidates.extend([
            support_base / "AstroCatalogueViewer",
            support_base / "AstroCatalogueViewer" / "Astro Catalogue Viewer",
            preferences_base / "AstroCatalogueViewer",
            preferences_base / "AstroCatalogueViewer" / "Astro Catalogue Viewer",
        ])
    elif sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        local_appdata = os.environ.get("LOCALAPPDATA")
        if appdata:
            roaming_base = Path(appdata)
        else:
            roaming_base = home / "AppData" / "Roaming"
        if local_appdata:
            local_base = Path(local_appdata)
        else:
            local_base = home / "AppData" / "Local"
        candidates.extend([
            roaming_base / "AstroCatalogueViewer",
            roaming_base / "AstroCatalogueViewer" / "Astro Catalogue Viewer",
            local_base / "AstroCatalogueViewer",
            local_base / "AstroCatalogueViewer" / "Astro Catalogue Viewer",
        ])
    else:
        config_base = home / ".config"
        local_share_base = home / ".local" / "share"
        candidates.extend([
            config_base / "AstroCatalogueViewer",
            config_base / "AstroCatalogueViewer" / "Astro Catalogue Viewer",
            local_share_base / "AstroCatalogueViewer",
            local_share_base / "AstroCatalogueViewer" / "Astro Catalogue Viewer",
        ])
    return candidates


def _old_app_metadata_dir(candidates: Optional[List[Path]] = None) -> Optional[Path]:
    """Find the metadata directory from the old AstroCatalogueViewer app."""
    if candidates is None:
        candidates = _old_app_candidate_paths()
    for candidate in candidates:
        metadata_dir = candidate / "metadata"
        print(f"Checking old-app candidate: {candidate}")
        print(f"  candidate exists: {candidate.exists()}")
        print(f"  metadata dir: {metadata_dir}")
        print(f"  metadata dir exists: {metadata_dir.exists()}")
        if metadata_dir.exists():
            return metadata_dir
        if candidate.exists() and any(candidate.glob("*_metadata.json")):
            print(f"  Found metadata files directly under {candidate}")
            return candidate
    return None


def _user_notes_path(metadata_dir: Path) -> Path:
    """Path to the photo_notes.json file.

    Selune stores photo_notes.json at the app config root, not inside the
    metadata subdirectory. If metadata_dir points to .../metadata, return the
    parent directory.
    """
    if metadata_dir.name == "metadata":
        return metadata_dir.parent / "photo_notes.json"
    return metadata_dir / "photo_notes.json"


def _sqlite_db_path(metadata_dir: Path, explicit_db_path: Optional[Path]) -> Path:
    if explicit_db_path is not None:
        return explicit_db_path
    if metadata_dir.name == "metadata":
        config_dir = metadata_dir.parent
    else:
        config_dir = metadata_dir
    return database_path_from_config_path(config_dir / "config.json")


def _old_config_path(old_dir: Path) -> Path:
    if old_dir.name == "metadata":
        return old_dir.parent / "config.json"
    return old_dir / "config.json"


def _load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, data: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def _load_old_config_for_migration(old_dir: Path) -> Dict:
    config_path = _old_config_path(old_dir)
    if not config_path.exists():
        return {}
    try:
        payload = _load_json(config_path)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _migrate_config_to_sqlite(db_path: Path, old_config: Dict) -> bool:
    if not old_config:
        return False
    database = Database(db_path)
    database.initialize()
    database.import_config(old_config, overwrite=True)
    # ui_state lives in app_settings but is managed outside save_config.
    if "ui_state" in old_config:
        database.set_setting("ui_state", old_config.get("ui_state"))
    return True


def _open_log_file(metadata_dir: Path) -> tuple[Path, object]:
    """Open the migration log file and return path and file handle."""
    log_path = metadata_dir / "migration_notes.log"
    log_file = log_path.open("w", encoding="utf-8")
    return log_path, log_file


def _extract_notes(payload: Dict) -> Dict[Tuple[str, str], Dict[str, object]]:
    notes: Dict[Tuple[str, str], Dict[str, object]] = {}
    for catalog_name, catalog in payload.items():
        if not isinstance(catalog, dict):
            continue
        for object_id, entry in catalog.items():
            if not isinstance(entry, dict):
                continue
            entry_notes = {}
            if "notes" in entry:
                entry_notes["notes"] = entry["notes"]
            if "image_notes" in entry:
                entry_notes["image_notes"] = entry["image_notes"]
            if entry_notes:
                notes[(str(catalog_name), str(object_id))] = entry_notes
    return notes


def _bundle_metadata_dir(app_bundle: Path) -> Path:
    return app_bundle / "Contents" / "Resources" / "data"


def migrate_from_app_bundle(app_bundle: Path) -> Dict[Tuple[str, str], Dict[str, object]]:
    """Extract all notes from old AstroCatalogueViewer metadata directory."""
    print(f"Extracting notes from old app metadata: {app_bundle}")
    
    if not app_bundle.exists():
        print(f"Error: Old app metadata directory not found: {app_bundle}", file=sys.stderr)
        sys.exit(1)

    all_notes: Dict[Tuple[str, str], Dict[str, object]] = {}
    metadata_files = sorted(app_bundle.glob("*_metadata.json"))
    print(f"  Found {len(metadata_files)} metadata files in {app_bundle}")
    for metadata_path in metadata_files:
        print(f"    - {metadata_path}")
    
    if not metadata_files:
        print(f"Error: No metadata files found in: {app_bundle}", file=sys.stderr)
        print(f"The old AstroCatalogueViewer metadata directory does not appear to contain any *_metadata.json files.", file=sys.stderr)
        sys.exit(1)
    
    for metadata_path in metadata_files:
        try:
            source_payload = _load_json(metadata_path)
            notes = _extract_notes(source_payload)
            if notes:
                all_notes.update(notes)
                print(f"  Extracted {len(notes)} note entries from {metadata_path.name}")
        except (OSError, json.JSONDecodeError) as e:
            print(f"  Warning: Error reading {metadata_path}: {e}", file=sys.stderr)
    
    if not all_notes:
        print(f"Error: No notes found in any metadata files at {app_bundle}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Total notes extracted: {len(all_notes)}")
    return all_notes


def migrate_from_user_metadata(metadata_dir: Path) -> Dict[Tuple[str, str], Dict[str, object]]:
    """Extract notes from existing user metadata files."""
    print(f"Extracting notes from user metadata: {metadata_dir}")
    
    all_notes: Dict[Tuple[str, str], Dict[str, object]] = {}
    # Legacy AstroCatalogueViewer source files are *_metadata.json.
    metadata_files = list(metadata_dir.glob("*_metadata.json"))
    if not metadata_files:
        # Compatibility fallback for already-migrated Selune metadata.
        metadata_files = list(metadata_dir.glob("*_catalog.json"))
    
    for metadata_path in metadata_files:
        try:
            data = _load_json(metadata_path)
            notes = _extract_notes(data)
            all_notes.update(notes)
            print(f"  Extracted {len(notes)} note entries from {metadata_path.name}")
        except (OSError, json.JSONDecodeError) as e:
            print(f"  Error reading {metadata_path}: {e}")
    
    print(f"Total notes extracted: {len(all_notes)}")
    return all_notes


def apply_migration(
    notes: Dict[Tuple[str, str], Dict[str, object]],
    metadata_dir: Path,
    log_file: object,
    db_path: Path,
) -> tuple[int, int, int, int]:
    """Apply extracted notes into SQLite runtime tables."""
    database = Database(db_path)
    database.initialize()
    migrated_object_notes = 0
    ignored_object_notes = 0
    migrated_image_notes = 0
    ignored_image_notes = 0

    # Group notes by catalog
    catalog_notes: Dict[str, Dict[str, Dict[str, object]]] = {}
    for (catalog_name, object_id), entry_notes in notes.items():
        if catalog_name not in catalog_notes:
            catalog_notes[catalog_name] = {}
        catalog_notes[catalog_name][object_id] = entry_notes

    # Process each catalog
    for catalog_name, objects in catalog_notes.items():
        for object_id, entry_notes in objects.items():
            # Handle object notes in SQLite sentinel rows.
            if "notes" in entry_notes:
                object_image_id = f"__object__::{catalog_name}::{object_id}"
                existing = database.get_note_by_image_id(object_image_id)
                existing_text = ""
                if existing is not None:
                    existing_text = str(existing.get("description") or "").strip()
                notes_value = str(entry_notes["notes"] or "").strip()
                if notes_value and not existing_text:
                    database.upsert_object_note(
                        catalog_name,
                        object_id,
                        notes_value,
                        legacy_source="AstroCatalogueViewer",
                    )
                    migrated_object_notes += 1
                    log_entry = f"[MIGRATED] Object note: {catalog_name} {object_id}"
                    print(log_entry)
                    log_file.write(log_entry + "\n")
                else:
                    ignored_object_notes += 1
                    log_entry = f"[IGNORED] Object note already exists: {catalog_name} {object_id}"
                    print(log_entry)
                    log_file.write(log_entry + "\n")
            
            # Handle image notes directly in SQLite image_notes.
            if "image_notes" in entry_notes:
                image_notes = entry_notes["image_notes"]
                if isinstance(image_notes, dict):
                    for image_name, note in image_notes.items():
                        if isinstance(note, str) and note.strip():
                            image_key = str(image_name).strip()
                            existing = database.get_note_by_image_id(image_key)
                            existing_text = ""
                            if existing is not None:
                                existing_text = str(existing.get("description") or "").strip()
                            if existing_text:
                                ignored_image_notes += 1
                                log_entry = f"[IGNORED] Image note already exists: {image_key}"
                                print(log_entry)
                                log_file.write(log_entry + "\n")
                            else:
                                database.upsert_image_note(
                                    image_id=image_key,
                                    description=note.strip(),
                                    legacy_source="AstroCatalogueViewer",
                                )
                                migrated_image_notes += 1
                                log_entry = f"[MIGRATED] Image note: {image_key}"
                                print(log_entry)
                                log_file.write(log_entry + "\n")
                elif isinstance(image_notes, str) and image_notes.strip():
                    # Use object_id as key if it's a string
                    image_key = str(object_id)
                    existing = database.get_note_by_image_id(image_key)
                    existing_text = ""
                    if existing is not None:
                        existing_text = str(existing.get("description") or "").strip()
                    if existing_text:
                        ignored_image_notes += 1
                        log_entry = f"[IGNORED] Image note already exists: {image_key}"
                        print(log_entry)
                        log_file.write(log_entry + "\n")
                    else:
                        database.upsert_image_note(
                            image_id=image_key,
                            description=image_notes.strip(),
                            legacy_source="AstroCatalogueViewer",
                        )
                        migrated_image_notes += 1
                        log_entry = f"[MIGRATED] Image note: {image_key}"
                        print(log_entry)
                        log_file.write(log_entry + "\n")
    
    return migrated_object_notes, ignored_object_notes, migrated_image_notes, ignored_image_notes


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate user notes from old AstroCatalogueViewer to new Selune format.",
    )
    parser.add_argument(
        "--old-app-dir",
        default=None,
        help="Path to old AstroCatalogueViewer config directory (optional, auto-detected if not provided).",
    )
    parser.add_argument(
        "--metadata-dir",
        default=None,
        help="User metadata directory (default: standard Selune directory).",
    )
    parser.add_argument(
        "--database",
        default=None,
        help="Path to target Selune SQLite database (default: selune.db next to metadata root).",
    )
    args = parser.parse_args()

    metadata_dir = Path(args.metadata_dir) if args.metadata_dir else _default_metadata_dir()
    metadata_dir.mkdir(parents=True, exist_ok=True)

    # Open log file (after determining metadata_dir)
    log_path, log_file = _open_log_file(metadata_dir)
    
    try:
        candidates = _old_app_candidate_paths()
        log_file.write("Legacy AstroCatalogueViewer locations checked:\n")
        for candidate in candidates:
            metadata_dir_candidate = candidate / "metadata"
            log_file.write(f"  - {candidate} (exists={candidate.exists()}, metadata_exists={metadata_dir_candidate.exists()})\n")
        log_file.write("\n")

        # Find old app directory
        if args.old_app_dir:
            old_dir = Path(args.old_app_dir).expanduser()
            if not old_dir.exists():
                print("Error: Could not find old AstroCatalogueViewer directory at:", old_dir, file=sys.stderr)
                log_file.write(f"Specified old app directory not found: {old_dir}\n")
                sys.exit(1)
        else:
            old_dir = _old_app_metadata_dir(candidates)
            if not old_dir:
                print(
                    "Error: Could not find old AstroCatalogueViewer metadata directory.\n"
                    "The old app was either not installed or has never been run.\n"
                    "Expected locations: \n"
                    "  - macOS: ~/Library/Application Support/AstroCatalogueViewer/metadata or ~/Library/Application Support/AstroCatalogueViewer/Astro Catalogue Viewer/metadata\n"
                    "  - macOS: ~/Library/Preferences/AstroCatalogueViewer/metadata or ~/Library/Preferences/AstroCatalogueViewer/Astro Catalogue Viewer/metadata\n"
                    "  - Windows: %APPDATA%\\AstroCatalogueViewer\\metadata or %APPDATA%\\AstroCatalogueViewer\\Astro Catalogue Viewer\\metadata\n"
                    "  - Windows: %LOCALAPPDATA%\\AstroCatalogueViewer\\metadata or %LOCALAPPDATA%\\AstroCatalogueViewer\\Astro Catalogue Viewer\\metadata\n"
                    "  - Linux: ~/.config/AstroCatalogueViewer/metadata or ~/.config/AstroCatalogueViewer/Astro Catalogue Viewer/metadata\n"
                    "  - Linux: ~/.local/share/AstroCatalogueViewer/metadata or ~/.local/share/AstroCatalogueViewer/Astro Catalogue Viewer/metadata",
                    file=sys.stderr
                )
                log_file.write("No legacy AstroCatalogueViewer metadata directory found.\n")
                sys.exit(1)

        # Determine new metadata directory based on old location
        if not args.metadata_dir:
            metadata_dir = _new_metadata_dir_from_old(old_dir)
            metadata_dir.mkdir(parents=True, exist_ok=True)
            log_file.write(f"New Selune metadata directory set to: {metadata_dir}\n")
            # Re-open log file in the correct location
            log_file.close()
            log_path, log_file = _open_log_file(metadata_dir)
            log_file.write("Legacy AstroCatalogueViewer locations checked:\n")
            for candidate in candidates:
                metadata_dir_candidate = candidate / "metadata"
                log_file.write(f"  - {candidate} (exists={candidate.exists()}, metadata_exists={metadata_dir_candidate.exists()})\n")
            log_file.write("\n")
            log_file.write(f"Legacy metadata directory selected: {old_dir}\n")
            log_file.write(f"New Selune metadata directory set to: {metadata_dir}\n")

        explicit_db_path = Path(args.database).expanduser() if args.database else None
        db_path = _sqlite_db_path(metadata_dir, explicit_db_path)
        old_config = _load_old_config_for_migration(old_dir)
        config_imported = _migrate_config_to_sqlite(db_path, old_config)
        if config_imported:
            print(f"Config migrated to SQLite: {db_path}")
            log_file.write(f"[MIGRATED] Config to SQLite: {db_path}\n")
        else:
            print("No legacy config.json found to migrate.")
            log_file.write("[INFO] No legacy config.json found to migrate.\n")

        try:
            notes = migrate_from_app_bundle(old_dir)
        except SystemExit as e:
            sys.exit(e.code if isinstance(e.code, int) else 1)

        if not notes:
            print("No notes found to migrate in the old AstroCatalogueViewer installation.", file=sys.stderr)
            sys.exit(1)

        print("=" * 60)
        print("STARTING MIGRATION")
        print("=" * 60)
        
        migrated_obj, ignored_obj, migrated_img, ignored_img = apply_migration(
            notes,
            metadata_dir,
            log_file,
            db_path,
        )
        
        print("=" * 60)
        print("MIGRATION SUMMARY")
        print("=" * 60)
        print(f"Object notes migrated: {migrated_obj}")
        print(f"Object notes ignored (already exist): {ignored_obj}")
        print(f"Image notes migrated: {migrated_img}")
        print(f"Image notes ignored (already exist): {ignored_img}")
        print(f"SQLite database: {db_path}")
        print(f"Legacy config migrated: {'yes' if config_imported else 'no'}")
        print(f"Total notes migrated: {migrated_obj + migrated_img}")
        print(f"Migration log saved to: {log_path}")
        print("=" * 60)
        
        log_file.write("\n" + "=" * 60 + "\n")
        log_file.write("MIGRATION SUMMARY\n")
        log_file.write("=" * 60 + "\n")
        log_file.write(f"Object notes migrated: {migrated_obj}\n")
        log_file.write(f"Object notes ignored (already exist): {ignored_obj}\n")
        log_file.write(f"Image notes migrated: {migrated_img}\n")
        log_file.write(f"Image notes ignored (already exist): {ignored_img}\n")
        log_file.write(f"SQLite database: {db_path}\n")
        log_file.write(f"Legacy config migrated: {'yes' if config_imported else 'no'}\n")
        log_file.write(f"Total notes migrated: {migrated_obj + migrated_img}\n")
        log_file.write("=" * 60 + "\n")
        
    finally:
        log_file.close()


if __name__ == "__main__":
    main()