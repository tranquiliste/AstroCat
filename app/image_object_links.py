from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from catalog import CatalogItem, load_catalog_items, load_config
from database import Database


def build_image_object_map(items: Iterable[CatalogItem]) -> Dict[str, List[Tuple[str, str]]]:
    image_map: Dict[str, set[Tuple[str, str]]] = {}
    for item in items:
        catalog_name = (item.catalog or "").strip()
        object_id = (item.object_id or "").strip()
        if not catalog_name or not object_id:
            continue
        for image_path in item.image_paths:
            image_id = image_path.name.strip()
            if not image_id:
                continue
            bucket = image_map.setdefault(image_id, set())
            bucket.add((catalog_name, object_id))

    normalized: Dict[str, List[Tuple[str, str]]] = {}
    for image_id in sorted(image_map.keys()):
        normalized[image_id] = sorted(image_map[image_id])
    return normalized


def rebuild_image_object_links_from_catalog(
    config_path: Path,
    db_path: Path,
    user_notes_path: Optional[Path] = None,
) -> Tuple[int, int]:
    config = load_config(config_path)
    items = load_catalog_items(config, user_notes_path=user_notes_path)
    image_map = build_image_object_map(items)
    database = Database(db_path)
    links_count = database.replace_all_image_object_links(image_map)
    return len(image_map), links_count
