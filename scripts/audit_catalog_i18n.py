#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List


ALLOWED_FIELDS = {"name", "description"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit catalog translation overlays (name/description + source_hash)."
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return exit code 1 if any issue is found.",
    )
    return parser.parse_args()


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return json.loads(path.read_text(encoding="latin-1"))


def _load_base_entries(catalog_module, metadata_path: Path, catalog_name: str) -> Dict[str, Dict]:
    if not metadata_path.exists():
        return {}
    data = _load_json(metadata_path)
    if not isinstance(data, dict):
        return {}
    entries = catalog_module._select_catalog_entries(data, catalog_name)  # type: ignore[attr-defined]
    if not isinstance(entries, dict):
        return {}
    return entries


def _norm(value: object) -> str:
    return str(value or "").strip()


def _field_base_text(catalog_module, base_meta: Dict, field_name: str) -> str:
    value = base_meta.get(field_name)
    normalized = catalog_module._normalize_text(value)  # type: ignore[attr-defined]
    return _norm(normalized)


def _audit_overlay_file(
    catalog_module,
    overlay_path: Path,
    base_entries: Dict[str, Dict],
) -> List[str]:
    issues: List[str] = []
    try:
        payload = _load_json(overlay_path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"Invalid JSON in {overlay_path}: {exc}"]

    if not isinstance(payload, dict):
        return [f"Overlay must be a JSON object: {overlay_path}"]

    for object_id, fields in payload.items():
        if not isinstance(object_id, str):
            issues.append(f"{overlay_path}: non-string object id key")
            continue
        if object_id not in base_entries:
            issues.append(f"{overlay_path}: unknown object id '{object_id}'")
            continue
        if not isinstance(fields, dict):
            issues.append(f"{overlay_path}: '{object_id}' must map to an object")
            continue

        for field_name in fields:
            if field_name not in ALLOWED_FIELDS:
                issues.append(
                    f"{overlay_path}: '{object_id}' has unexpected field '{field_name}'"
                )

        for field_name in ALLOWED_FIELDS:
            if field_name not in fields:
                continue
            field_payload = fields.get(field_name)
            if not isinstance(field_payload, dict):
                issues.append(
                    f"{overlay_path}: '{object_id}.{field_name}' must be an object"
                )
                continue
            text = field_payload.get("text")
            source_hash = field_payload.get("source_hash")
            if not isinstance(text, str):
                issues.append(
                    f"{overlay_path}: '{object_id}.{field_name}.text' must be a string"
                )
                continue
            if not isinstance(source_hash, str) or not source_hash.strip():
                issues.append(
                    f"{overlay_path}: '{object_id}.{field_name}.source_hash' missing or blank"
                )
                continue

            if not text.strip():
                continue

            expected_hash = catalog_module._text_source_hash(  # type: ignore[attr-defined]
                _field_base_text(catalog_module, base_entries[object_id], field_name)
            )
            if source_hash.strip() != expected_hash:
                issues.append(
                    f"{overlay_path}: stale source_hash for '{object_id}.{field_name}' (expected '{expected_hash}', got '{source_hash.strip()}')"
                )

    return issues


def main() -> int:
    _args = parse_args()
    root = Path(__file__).resolve().parents[1]

    sys.path.insert(0, str(root / "app"))
    import catalog as catalog_module  # pylint: disable=import-error

    data_dir = root / "data"
    i18n_dir = data_dir / "i18n"

    if not i18n_dir.exists():
        print("catalog i18n audit report")
        print(f"- overlays directory missing: {i18n_dir}")
        return 0

    locale_dirs = sorted(path for path in i18n_dir.iterdir() if path.is_dir())

    base_catalog_entries: Dict[str, Dict[str, Dict]] = {}
    metadata_files_by_catalog: Dict[str, str] = {}
    for catalog_cfg in catalog_module.DEFAULT_CONFIG.get("catalogs", []):
        catalog_name = str(catalog_cfg.get("name") or "")
        metadata_file = catalog_cfg.get("metadata_file")
        if not catalog_name or not metadata_file:
            continue
        metadata_path = root / str(metadata_file)
        base_catalog_entries[catalog_name] = _load_base_entries(
            catalog_module,
            metadata_path,
            catalog_name,
        )
        metadata_files_by_catalog[catalog_name] = str(metadata_file)

    issues: List[str] = []
    overlay_count = 0

    for locale_dir in locale_dirs:
        for catalog_name, entries in base_catalog_entries.items():
            metadata_file = metadata_files_by_catalog.get(catalog_name)
            overlay_name = catalog_module._catalog_overlay_filename(  # type: ignore[attr-defined]
                catalog_name,
                metadata_file,
            )
            overlay_path = locale_dir / overlay_name
            if not overlay_path.exists():
                continue
            overlay_count += 1
            issues.extend(_audit_overlay_file(catalog_module, overlay_path, entries))

    print("catalog i18n audit report")
    print(f"- locales scanned: {len(locale_dirs)}")
    print(f"- overlays scanned: {overlay_count}")
    print(f"- issues: {len(issues)}")
    for issue in issues:
        print(f"  - {issue}")

    if _args.strict and issues:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
