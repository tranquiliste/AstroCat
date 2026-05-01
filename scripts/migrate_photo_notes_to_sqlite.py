from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = PROJECT_ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from database import database_path_from_config_path  # noqa: E402
from photo_notes_migration import migrate_photo_notes_to_sqlite  # noqa: E402


def migrate(photo_notes_path: Path, db_path: Path, force: bool = False) -> Tuple[int, int, str]:
    return migrate_photo_notes_to_sqlite(photo_notes_path, db_path, force=force)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import photo_notes.json entries into SQLite (image_notes + object_thumbnails)."
    )
    parser.add_argument(
        "--photo-notes",
        type=Path,
        required=True,
        help="Path to photo_notes.json",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=None,
        help="Optional database path. Defaults to astrocat.db next to photo_notes.json",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force import even if target tables already contain data.",
    )
    args = parser.parse_args()

    photo_notes_path = args.photo_notes.resolve()
    if args.database is not None:
        db_path = args.database.resolve()
    else:
        db_path = database_path_from_config_path(photo_notes_path.with_name("config.json"))

    imported_notes, imported_thumbs, message = migrate(photo_notes_path, db_path, force=args.force)
    print(message)
    print(f"image_notes imported: {imported_notes}")
    print(f"object_thumbnails imported: {imported_thumbs}")
    print(f"database: {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
