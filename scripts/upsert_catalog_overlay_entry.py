#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Insert/update one catalog overlay translation entry with current source_hash."
    )
    parser.add_argument("--locale", required=True, help="Locale code, e.g. fr, es, de")
    parser.add_argument("--catalog", required=True, help="Catalog name, e.g. Barnard, NGC")
    parser.add_argument("--object-id", required=True, help="Object id as stored in metadata (e.g. B 33)")
    parser.add_argument(
        "--field",
        required=True,
        choices=["name", "description"],
        help="Translated field to update",
    )
    parser.add_argument("--text", required=True, help="Translated text")
    return parser.parse_args()


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return json.loads(path.read_text(encoding="latin-1"))


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]

    sys.path.insert(0, str(root / "app"))
    import catalog as catalog_module  # pylint: disable=import-error

    catalog_cfg = None
    for candidate in catalog_module.DEFAULT_CONFIG.get("catalogs", []):
        if str(candidate.get("name") or "") == args.catalog:
            catalog_cfg = candidate
            break
    if catalog_cfg is None:
        raise SystemExit(f"Unknown catalog: {args.catalog}")

    metadata_file = catalog_cfg.get("metadata_file")
    if not metadata_file:
        raise SystemExit(f"Catalog has no metadata file: {args.catalog}")
    metadata_path = root / str(metadata_file)
    if not metadata_path.exists():
        raise SystemExit(f"Missing metadata file: {metadata_path}")

    catalog_data = _load_json(metadata_path)
    if not isinstance(catalog_data, dict):
        raise SystemExit(f"Invalid metadata format: {metadata_path}")
    entries = catalog_module._select_catalog_entries(catalog_data, args.catalog)  # type: ignore[attr-defined]
    if args.object_id not in entries:
        raise SystemExit(f"Unknown object id '{args.object_id}' in catalog {args.catalog}")

    base_value = catalog_module._normalize_text(entries[args.object_id].get(args.field))  # type: ignore[attr-defined]
    source_hash = catalog_module._text_source_hash(base_value)  # type: ignore[attr-defined]

    locale = str(args.locale).strip().lower()
    overlay_dir = root / "data" / "i18n" / locale
    overlay_dir.mkdir(parents=True, exist_ok=True)
    overlay_path = overlay_dir / catalog_module._catalog_overlay_filename(  # type: ignore[attr-defined]
        args.catalog,
        str(metadata_file),
    )

    payload = {}
    if overlay_path.exists():
        loaded = _load_json(overlay_path)
        if isinstance(loaded, dict):
            payload = loaded

    entry = payload.setdefault(args.object_id, {})
    if not isinstance(entry, dict):
        entry = {}
        payload[args.object_id] = entry

    entry[args.field] = {
        "text": str(args.text).strip(),
        "source_hash": source_hash,
    }

    overlay_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Updated overlay: {overlay_path}")
    print(f"- {args.object_id}.{args.field}")
    print(f"- source_hash: {source_hash}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
