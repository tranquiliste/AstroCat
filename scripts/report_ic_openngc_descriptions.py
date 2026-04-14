#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPENNGC_PATH = ROOT / "data" / "openngc" / "NGC.csv"
GENERIC_DESCRIPTION_PATTERNS = (
    r"nothing here",
    r"nominal position",
    r"does not exist",
    r"not certain",
    r"no other reasonable candidate",
    r"nothing obvious here",
    r"cannot be identified",
    r"wrong object",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List IC objects from OpenNGC that have a description in NGC.csv."
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit displayed rows (0 = all)",
    )
    parser.add_argument(
        "--include-generic",
        action="store_true",
        help="Include low-value descriptions such as 'Nothing here' or 'nominal position'.",
    )
    return parser.parse_args()


def is_generic_description(text: str) -> bool:
    folded = text.lower()
    return any(re.search(pattern, folded) for pattern in GENERIC_DESCRIPTION_PATTERNS)


def load_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with OPENNGC_PATH.open(encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row in reader:
            object_id = (row.get("Name") or "").strip().upper()
            if not object_id.startswith("IC"):
                continue
            openngc_notes = (row.get("OpenNGC notes") or "").strip()
            ned_notes = (row.get("NED notes") or "").strip()
            if not openngc_notes and not ned_notes:
                continue
            rows.append(
                {
                    "object_id": object_id,
                    "type": (row.get("Type") or "").strip(),
                    "constellation": (row.get("Const") or "").strip(),
                    "common_names": (row.get("Common names") or "").strip(),
                    "source": "OpenNGC" if openngc_notes else "NED",
                    "description": openngc_notes or ned_notes,
                    "is_generic": is_generic_description(openngc_notes or ned_notes),
                    "openngc_notes": openngc_notes,
                    "ned_notes": ned_notes,
                }
            )
    return rows


def main() -> int:
    args = parse_args()
    all_rows = load_rows()
    rows = all_rows if args.include_generic else [row for row in all_rows if not row["is_generic"]]
    if args.limit > 0:
        rows = rows[: args.limit]

    if args.format == "json":
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0

    generic_count = sum(1 for row in all_rows if row["is_generic"])
    informative_count = len(all_rows) - generic_count
    print(f"IC entries with OpenNGC/NED description: {len(all_rows)}")
    print(f"Informative descriptions: {informative_count}")
    print(f"Generic descriptions filtered out: {generic_count}")
    print(f"Displayed rows: {len(rows)}")
    for row in rows:
        print(
            f"{row['object_id']} | {row['source']} | {row['type']} | {row['constellation']} | "
            f"{row['common_names']} | {row['description']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())