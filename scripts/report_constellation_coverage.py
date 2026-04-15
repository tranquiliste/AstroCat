from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
IGNORED_FILES = {
    "data_version.json",
    "version.json",
    "solar_system_catalog.json",
    "supporters.json",
}


def iter_catalog_entries(payload: object) -> Iterator[Tuple[str, dict]]:
    if not isinstance(payload, dict):
        return
    for entries in payload.values():
        if not isinstance(entries, dict):
            continue
        for object_id, entry in entries.items():
            if isinstance(entry, dict):
                yield str(object_id), entry


def count_constellations(path: Path) -> Tuple[int, int, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    total = 0
    filled = 0
    missing = 0
    for _object_id, entry in iter_catalog_entries(payload):
        total += 1
        if entry.get("constellation"):
            filled += 1
        else:
            missing += 1
    return total, filled, missing


def main() -> int:
    if not DATA_DIR.exists():
        print(f"Data directory not found: {DATA_DIR}")
        return 1

    print("Constellation coverage by file")
    print("-" * 72)
    print(f"{'File':32} {'Total':>8} {'Filled':>8} {'Missing':>8} {'Coverage':>11}")
    print("-" * 72)

    grand_total = 0
    grand_filled = 0
    grand_missing = 0

    for path in sorted(DATA_DIR.glob("*.json")):
        if path.name in IGNORED_FILES:
            continue
        total, filled, missing = count_constellations(path)
        coverage = (filled / total * 100.0) if total else 0.0
        grand_total += total
        grand_filled += filled
        grand_missing += missing
        print(f"{path.name:32} {total:8d} {filled:8d} {missing:8d} {coverage:10.1f}%")

    print("-" * 72)
    overall = (grand_filled / grand_total * 100.0) if grand_total else 0.0
    print(f"{'TOTAL':32} {grand_total:8d} {grand_filled:8d} {grand_missing:8d} {overall:10.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
