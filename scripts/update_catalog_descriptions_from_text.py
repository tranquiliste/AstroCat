#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Met a jour description.text dans un catalog JSON a partir d'un fichier texte "
            "au format 'CLE: description'."
        )
    )
    parser.add_argument(
        "input_file",
        help="Fichier texte source (une ligne = CLE: description)",
    )
    parser.add_argument(
        "catalog_file",
        help="Fichier JSON cible (ex: data/i18n/fr/ngc_catalog.json)",
    )
    parser.add_argument(
        "--log-file",
        dest="log_file",
        default=None,
        help="Chemin du fichier de log pour les cles introuvables (optionnel)",
    )
    return parser.parse_args()


def load_json(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Le JSON doit etre un objet: {path}")
    return data


def looks_like_entry(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    # Some catalogs contain partial i18n entries (only name or only description).
    return "name" in value or "description" in value


def score_entry_container(value: object) -> Tuple[int, int]:
    """Return (matching_entries, total_items) for a candidate object map."""
    if not isinstance(value, dict) or not value:
        return (0, 0)
    total = len(value)
    matching = sum(1 for item in value.values() if looks_like_entry(item))
    return (matching, total)


def resolve_entries(root: Dict) -> Dict:
    root_matching, root_total = score_entry_container(root)
    if root_total > 0 and root_matching >= 1:
        return root

    candidates: List[Tuple[str, Dict]] = []
    for key, value in root.items():
        matching, total = score_entry_container(value)
        if total > 0 and matching >= 1:
            candidates.append((key, value))

    if len(candidates) == 1:
        return candidates[0][1]

    if not candidates:
        raise ValueError(
            "Impossible de trouver le mapping des objets dans le JSON cible. "
            "Le format attendu est soit {ID: {...}}, soit {SECTION: {ID: {...}}}."
        )

    names = ", ".join(name for name, _ in candidates)
    raise ValueError(
        "Plusieurs sections candidates detectees dans le JSON cible "
        f"({names}). Le script ne peut pas choisir automatiquement."
    )


def parse_input_line(raw_line: str, line_no: int) -> Tuple[str, str]:
    line = raw_line.strip()
    if not line or line.startswith("#"):
        return "", ""

    if ":" not in line:
        raise ValueError(f"Ligne {line_no}: separateur ':' manquant")

    key, text = line.split(":", 1)
    key = key.strip()
    text = text.strip()

    if not key:
        raise ValueError(f"Ligne {line_no}: cle vide")

    return key, text


def update_descriptions(input_file: Path, catalog_file: Path, log_file: Path) -> None:
    root = load_json(catalog_file)
    entries = resolve_entries(root)

    modified = 0
    unchanged = 0
    not_found: List[str] = []
    malformed: List[str] = []

    with input_file.open("r", encoding="utf-8") as f:
        for idx, raw_line in enumerate(f, start=1):
            try:
                key, text = parse_input_line(raw_line, idx)
            except ValueError as exc:
                malformed.append(str(exc))
                continue

            if not key:
                continue

            entry = entries.get(key)
            if not isinstance(entry, dict):
                not_found.append(key)
                continue

            desc = entry.get("description")
            if isinstance(desc, dict):
                previous = str(desc.get("text", ""))
                if previous == text:
                    unchanged += 1
                else:
                    desc["text"] = text
                    modified += 1
            else:
                entry["description"] = {"text": text}
                modified += 1

    with catalog_file.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(root, f, ensure_ascii=False, indent=2)
        f.write("\n")

    with log_file.open("w", encoding="utf-8", newline="\n") as f:
        if not_found:
            f.write("Cles introuvables:\n")
            for key in not_found:
                f.write(f"{key}\n")
        else:
            f.write("Aucune cle introuvable.\n")

        if malformed:
            f.write("\nLignes ignorees (format invalide):\n")
            for line in malformed:
                f.write(f"{line}\n")

    print(f"Fichier mis a jour: {catalog_file}")
    print(f"Log: {log_file}")
    print(f"nb modifiees: {modified}")
    print(f"nb non trouvees: {len(not_found)}")
    if unchanged:
        print(f"nb inchangees: {unchanged}")
    if malformed:
        print(f"nb lignes invalides ignorees: {len(malformed)}")


def main() -> int:
    args = parse_args()

    input_file = Path(args.input_file).expanduser().resolve()
    catalog_file = Path(args.catalog_file).expanduser().resolve()

    if not input_file.exists():
        raise SystemExit(f"Fichier d'entree introuvable: {input_file}")
    if not catalog_file.exists():
        raise SystemExit(f"Fichier catalog introuvable: {catalog_file}")

    if args.log_file:
        log_file = Path(args.log_file).expanduser().resolve()
    else:
        log_file = catalog_file.with_name(f"{catalog_file.stem}_not_found.log")

    update_descriptions(input_file, catalog_file, log_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())