#!/usr/bin/env python3
"""
One-shot migration script to migrate user notes from the old format
to the new separated format.

Can migrate from:
- Old app bundle (AstroCat.app or AstroCatlogViewer.app)
- Existing user metadata files

Old format: notes and image_notes in *_metadata.json files.
New format: notes stay in *_metadata.json, image_notes in photo_notes.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def _new_metadata_dir_from_old(old_metadata_dir: Path) -> Path:
    """Derive the new AstroCat metadata directory from the old AstroCatalogueViewer location."""
    parts = old_metadata_dir.parts
    try:
        # Find the "AstroCatalogueViewer" directory in the path
        idx = parts.index("AstroCatalogueViewer")
        # Replace with "AstroCat" and add "AstroCat/metadata"
        base_parts = parts[:idx]
        new_parts = base_parts + ("AstroCat", "AstroCat", "metadata")
        return Path(*new_parts)
    except ValueError:
        # If "AstroCatalogueViewer" not found, fallback to default
        return _default_metadata_dir()


def _default_metadata_dir() -> Path:
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Preferences" / "AstroCat" / "AstroCat" / "metadata"
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "AstroCat" / "AstroCat" / "metadata"
        return home / "AppData" / "Roaming" / "AstroCat" / "AstroCat" / "metadata"
    return home / ".config" / "AstroCat" / "AstroCat" / "metadata"


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

    AstroCat stores photo_notes.json at the app config root, not inside the
    metadata subdirectory. If metadata_dir points to .../metadata, return the
    parent directory.
    """
    if metadata_dir.name == "metadata":
        return metadata_dir.parent / "photo_notes.json"
    return metadata_dir / "photo_notes.json"


def _load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, data: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


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
    metadata_files = list(metadata_dir.glob("*_metadata.json"))
    
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


def apply_migration(notes: Dict[Tuple[str, str], Dict[str, object]], metadata_dir: Path, log_file: object) -> tuple[int, int, int]:
    """Apply the extracted notes to the new format. Returns (migrated_notes, ignored_notes, migrated_images)."""
    notes_path = _user_notes_path(metadata_dir)
    existing_notes: Dict[str, str] = {}
    if notes_path.exists():
        try:
            existing_notes = _load_json(notes_path)
        except (OSError, json.JSONDecodeError):
            existing_notes = {}

    photo_notes: Dict[str, str] = {}
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
        metadata_path = metadata_dir / f"{catalog_name}_metadata.json"
        
        # Load or create metadata file
        if metadata_path.exists():
            try:
                data = _load_json(metadata_path)
            except (OSError, json.JSONDecodeError):
                data = {}
        else:
            data = {}
        
        catalog = data.setdefault(catalog_name, {})
        modified = False
        
        for object_id, entry_notes in objects.items():
            entry = catalog.setdefault(object_id, {})
            
            # Handle object notes
            if "notes" in entry_notes:
                if "notes" not in entry:  # Don't overwrite existing notes
                    entry["notes"] = entry_notes["notes"]
                    modified = True
                    migrated_object_notes += 1
                    log_entry = f"[MIGRATED] Object note: {catalog_name} {object_id}"
                    print(log_entry)
                    log_file.write(log_entry + "\n")
                else:
                    ignored_object_notes += 1
                    log_entry = f"[IGNORED] Object note already exists: {catalog_name} {object_id}"
                    print(log_entry)
                    log_file.write(log_entry + "\n")
            
            # Handle image notes - move to photo_notes.json
            if "image_notes" in entry_notes:
                image_notes = entry_notes["image_notes"]
                if isinstance(image_notes, dict):
                    for image_name, note in image_notes.items():
                        if isinstance(note, str) and note.strip():
                            image_key = image_name
                            if image_key in existing_notes or image_key in photo_notes:
                                ignored_image_notes += 1
                                log_entry = f"[IGNORED] Image note already exists: {image_key}"
                                print(log_entry)
                                log_file.write(log_entry + "\n")
                            else:
                                photo_notes[image_key] = note.strip()
                                migrated_image_notes += 1
                                log_entry = f"[MIGRATED] Image note: {image_key}"
                                print(log_entry)
                                log_file.write(log_entry + "\n")
                elif isinstance(image_notes, str) and image_notes.strip():
                    # Use object_id as key if it's a string
                    image_key = str(object_id)
                    if image_key in existing_notes or image_key in photo_notes:
                        ignored_image_notes += 1
                        log_entry = f"[IGNORED] Image note already exists: {image_key}"
                        print(log_entry)
                        log_file.write(log_entry + "\n")
                    else:
                        photo_notes[image_key] = image_notes.strip()
                        migrated_image_notes += 1
                        log_entry = f"[MIGRATED] Image note: {image_key}"
                        print(log_entry)
                        log_file.write(log_entry + "\n")

                # Remove image_notes from metadata
                if "image_notes" in entry:
                    del entry["image_notes"]
                    modified = True
        
        if modified:
            _save_json(metadata_path, data)
            print(f"  Updated {metadata_path.name}")

    # Save photo_notes
    if photo_notes:
        notes_path = _user_notes_path(metadata_dir)
        existing_notes.update(photo_notes)
        _save_json(notes_path, existing_notes)
        print(f"Migrated {migrated_image_notes} image notes to {notes_path}")
    
    return migrated_object_notes, ignored_object_notes, migrated_image_notes, ignored_image_notes


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate user notes from old AstroCatalogueViewer to new AstroCat format.",
    )
    parser.add_argument(
        "--old-app-dir",
        default=None,
        help="Path to old AstroCatalogueViewer config directory (optional, auto-detected if not provided).",
    )
    parser.add_argument(
        "--metadata-dir",
        default=None,
        help="User metadata directory (default: standard AstroCat directory).",
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
            log_file.write(f"New AstroCat metadata directory set to: {metadata_dir}\n")
            # Re-open log file in the correct location
            log_file.close()
            log_path, log_file = _open_log_file(metadata_dir)
            log_file.write("Legacy AstroCatalogueViewer locations checked:\n")
            for candidate in candidates:
                metadata_dir_candidate = candidate / "metadata"
                log_file.write(f"  - {candidate} (exists={candidate.exists()}, metadata_exists={metadata_dir_candidate.exists()})\n")
            log_file.write("\n")
            log_file.write(f"Legacy metadata directory selected: {old_dir}\n")
            log_file.write(f"New AstroCat metadata directory set to: {metadata_dir}\n")
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
        
        migrated_obj, ignored_obj, migrated_img, ignored_img = apply_migration(notes, metadata_dir, log_file)
        
        print("=" * 60)
        print("MIGRATION SUMMARY")
        print("=" * 60)
        print(f"Object notes migrated: {migrated_obj}")
        print(f"Object notes ignored (already exist): {ignored_obj}")
        print(f"Image notes migrated: {migrated_img}")
        print(f"Image notes ignored (already exist): {ignored_img}")
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
        log_file.write(f"Total notes migrated: {migrated_obj + migrated_img}\n")
        log_file.write("=" * 60 + "\n")
        
    finally:
        log_file.close()


if __name__ == "__main__":
    main()