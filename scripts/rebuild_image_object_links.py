from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = PROJECT_ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from database import database_path_from_config_path  # noqa: E402
from image_object_links import rebuild_image_object_links_from_catalog  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild image to object associations in SQLite (image_objects)."
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to runtime config path (selune.db path used by load_config).",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=None,
        help="Optional database path. Defaults to selune.db next to --config.",
    )
    parser.add_argument(
        "--notes",
        type=Path,
        default=None,
        help="Optional user notes path used while loading catalog items.",
    )
    args = parser.parse_args()

    config_path = args.config.resolve()
    if args.database is not None:
        db_path = args.database.resolve()
    else:
        db_path = database_path_from_config_path(config_path)

    notes_path = args.notes.resolve() if args.notes is not None else None

    image_count, link_count = rebuild_image_object_links_from_catalog(
        config_path=config_path,
        db_path=db_path,
        user_notes_path=notes_path,
    )

    print(f"image_objects rebuilt: {link_count} links across {image_count} images")
    print(f"database: {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
