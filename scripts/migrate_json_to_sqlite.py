from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = PROJECT_ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from catalog import _merge_default_config  # noqa: E402
from database import Database, database_path_from_config_path  # noqa: E402


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate AstroCat config.json into SQLite storage.")
    parser.add_argument("config", type=Path, help="Path to the legacy config.json file")
    parser.add_argument(
        "--database",
        type=Path,
        default=None,
        help="Optional explicit SQLite database path (defaults to astrocat.db next to config.json)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing configuration data in the SQLite database",
    )
    args = parser.parse_args()

    config_path = args.config.resolve()
    db_path = args.database.resolve() if args.database else database_path_from_config_path(config_path)
    database = Database(db_path)

    payload = _load_json(config_path)
    merged = _merge_default_config(payload)

    if database.has_config_data() and not args.force:
        print(f"SQLite database already contains configuration data: {db_path}")
        print("Use --force to overwrite it.")
        return 0

    database.import_config(merged, overwrite=True)
    print(f"Configuration migrated to SQLite: {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())