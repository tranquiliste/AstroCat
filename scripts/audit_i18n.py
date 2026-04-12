#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


TR_CALL_RE = re.compile(r'tr\(\s*"([^"]+)"')
TRANSLATE_CALL_RE = re.compile(r'translate\(\s*"([^"]+)"')

# Heuristic pattern to catch likely hardcoded UI labels in app/main.py.
# It intentionally allows symbols like "◀" or "?" and ignores tr("...").
HARDCODED_UI_RE = re.compile(
    r'\b(?:setWindowTitle|setText|setPlaceholderText|QLabel|QPushButton|QCheckBox|QGroupBox|QAction)\s*\(\s*"([^"]*[A-Za-z][^"]*)"'
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit i18n keys and likely hardcoded UI strings."
    )
    parser.add_argument(
        "--app-dir",
        type=Path,
        default=Path("app"),
        help="Application directory containing Python files and locales (default: app)",
    )
    parser.add_argument(
        "--main-file",
        type=Path,
        default=Path("app") / "main.py",
        help="Main UI file checked for hardcoded candidates (default: app/main.py)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return exit code 1 if any issue is found.",
    )
    return parser.parse_args()


def load_locale_keys(path: Path) -> set[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"Missing locale file: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}")

    if not isinstance(payload, dict):
        raise SystemExit(f"Locale file must contain a JSON object: {path}")
    return {str(key) for key in payload.keys()}


def find_used_tr_keys(py_files: list[Path]) -> set[str]:
    keys: set[str] = set()
    for path in py_files:
        text = path.read_text(encoding="utf-8", errors="replace")
        keys.update(TR_CALL_RE.findall(text))
        keys.update(TRANSLATE_CALL_RE.findall(text))
    return keys


def find_hardcoded_candidates(main_file: Path) -> list[tuple[int, str]]:
    if not main_file.exists():
        return []

    results: list[tuple[int, str]] = []
    for line_number, raw_line in enumerate(
        main_file.read_text(encoding="utf-8", errors="replace").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line or "tr(\"" in line:
            continue
        if ".join(" in line:
            continue
        if '"AstroCat"' in line:
            continue
        if HARDCODED_UI_RE.search(line):
            results.append((line_number, line))
    return results


def print_section(title: str, rows: list[str]) -> None:
    print(title)
    if not rows:
        print("  (none)")
        return
    for row in rows:
        print(f"  - {row}")


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    app_dir = (root / args.app_dir).resolve()
    main_file = (root / args.main_file).resolve()

    py_files = sorted(app_dir.glob("*.py"))
    if not py_files:
        raise SystemExit(f"No Python files found in {app_dir}")

    locales_dir = app_dir / "locales"
    locale_files = sorted(locales_dir.glob("*.json"))
    if not locale_files:
        raise SystemExit(f"No locale files found in {locales_dir}")

    locale_keys: dict[str, set[str]] = {}
    for locale_file in locale_files:
        locale_keys[locale_file.name] = load_locale_keys(locale_file)

    used_keys = find_used_tr_keys(py_files)

    missing_by_locale: dict[str, list[str]] = {}
    unused_by_locale: dict[str, list[str]] = {}
    for locale_name, keys in locale_keys.items():
        missing_by_locale[locale_name] = sorted(key for key in used_keys if key not in keys)
        unused_by_locale[locale_name] = sorted(key for key in keys if key not in used_keys)

    hardcoded = find_hardcoded_candidates(main_file)

    print("i18n audit report")
    print(f"- app dir: {app_dir}")
    print(f"- python files scanned: {len(py_files)}")
    print(f"- used translation keys: {len(used_keys)}")
    print(f"- locale files scanned: {len(locale_files)}")
    for locale_name, keys in locale_keys.items():
        print(f"- {locale_name} keys: {len(keys)}")

    for locale_name in locale_keys:
        print_section(f"\nMissing in {locale_name}", missing_by_locale[locale_name])
    for locale_name in locale_keys:
        print_section(f"\nUnused in {locale_name}", unused_by_locale[locale_name])

    hardcoded_rows = [f"L{line}: {text}" for line, text in hardcoded]
    print_section("\nLikely hardcoded UI strings in main.py", hardcoded_rows)

    issue_count = sum(len(v) for v in missing_by_locale.values())
    issue_count += sum(len(v) for v in unused_by_locale.values())
    issue_count += len(hardcoded)
    if args.strict and issue_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
