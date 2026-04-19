from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import hashlib
import math
import os
import sys
from typing import Dict, Iterable, List, Optional, Set
from urllib.parse import quote
import re

from constellations import canonical_constellation_name, extract_constellation_from_description
from i18n import normalize_locale_code

PROJECT_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))



DEFAULT_CONFIG = {
    "catalogs": [
        {
            "name": "Messier",
            "metadata_file": "data/object_catalog.json",
            "image_dirs": [],
        },
        {
            "name": "NGC",
            "metadata_file": "data/ngc_catalog.json",
            "image_dirs": [],
        },
        {
            "name": "IC",
            "metadata_file": "data/ic_catalog.json",
            "image_dirs": [],
        },
        {
            "name": "Solar system",
            "metadata_file": "data/solar_system_catalog.json",
            "image_dirs": [],
        },
        {
            "name": "Sh2",
            "metadata_file": "data/sh2_catalog.json",
            "image_dirs": [],
        },
        {
            "name": "LDN",
            "metadata_file": "data/ldn_catalog.json",
            "image_dirs": [],
        },
        {
            "name": "Barnard",
            "metadata_file": "data/barnard_catalog.json",
            "image_dirs": [],
        },
        {
            "name": "VdB",
            "metadata_file": "data/vdb_catalog.json",
            "image_dirs": [],
        },
        {
            "name": "LBN",
            "metadata_file": "data/lbn_catalog.json",
            "image_dirs": [],
        },
        {
            "name": "PNG",
            "metadata_file": "data/png_catalog.json",
            "image_dirs": [],
        },
    ],
    "image_extensions": [".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"],
    "thumb_size": 240,
    "observer": {"latitude": 0.0, "longitude": 0.0, "elevation_m": 0.0},
    "show_welcome": True,
    "master_image_dir": "",
    "archive_image_dir": "",
    "use_wiki_thumbnails": False,
    "auto_check_updates": True,
    "ui_locale": "system",
}


MESSIER_TO_NGC = {
    "M1": ["NGC1952"],
    "M2": ["NGC7089"],
    "M3": ["NGC5272"],
    "M4": ["NGC6121"],
    "M5": ["NGC5904"],
    "M6": ["NGC6405"],
    "M7": ["NGC6475"],
    "M8": ["NGC6523"],
    "M9": ["NGC6333"],
    "M10": ["NGC6254"],
    "M11": ["NGC6705"],
    "M12": ["NGC6218"],
    "M13": ["NGC6205"],
    "M14": ["NGC6402"],
    "M15": ["NGC7078"],
    "M16": ["NGC6611"],
    "M17": ["NGC6618"],
    "M18": ["NGC6613"],
    "M19": ["NGC6273"],
    "M20": ["NGC6514"],
    "M21": ["NGC6531"],
    "M22": ["NGC6656"],
    "M23": ["NGC6494"],
    "M24": ["NGC6603"],
    "M25": ["IC4725"],
    "M26": ["NGC6694"],
    "M27": ["NGC6853"],
    "M28": ["NGC6626"],
    "M29": ["NGC6913"],
    "M30": ["NGC7099"],
    "M31": ["NGC224"],
    "M32": ["NGC221"],
    "M33": ["NGC598"],
    "M34": ["NGC1039"],
    "M35": ["NGC2168"],
    "M36": ["NGC1960"],
    "M37": ["NGC2099"],
    "M38": ["NGC1912"],
    "M39": ["NGC7092"],
    "M41": ["NGC2287"],
    "M42": ["NGC1976"],
    "M43": ["NGC1982"],
    "M44": ["NGC2632"],
    "M46": ["NGC2437"],
    "M47": ["NGC2422"],
    "M48": ["NGC2548"],
    "M49": ["NGC4472"],
    "M50": ["NGC2323"],
    "M51": ["NGC5194"],
    "M52": ["NGC7654"],
    "M53": ["NGC5024"],
    "M54": ["NGC6715"],
    "M55": ["NGC6809"],
    "M56": ["NGC6779"],
    "M57": ["NGC6720"],
    "M58": ["NGC4579"],
    "M59": ["NGC4621"],
    "M60": ["NGC4649"],
    "M61": ["NGC4303"],
    "M62": ["NGC6266"],
    "M63": ["NGC5055"],
    "M64": ["NGC4826"],
    "M65": ["NGC3623"],
    "M66": ["NGC3627"],
    "M67": ["NGC2682"],
    "M68": ["NGC4590"],
    "M69": ["NGC6637"],
    "M70": ["NGC6681"],
    "M71": ["NGC6838"],
    "M72": ["NGC6981"],
    "M73": ["NGC6994"],
    "M74": ["NGC628"],
    "M75": ["NGC6864"],
    "M76": ["NGC650"],
    "M77": ["NGC1068"],
    "M78": ["NGC2068"],
    "M79": ["NGC1904"],
    "M80": ["NGC6093"],
    "M81": ["NGC3031"],
    "M82": ["NGC3034"],
    "M83": ["NGC5236"],
    "M84": ["NGC4374"],
    "M85": ["NGC4382"],
    "M86": ["NGC4406"],
    "M87": ["NGC4486"],
    "M88": ["NGC4501"],
    "M89": ["NGC4552"],
    "M90": ["NGC4569"],
    "M91": ["NGC4548"],
    "M92": ["NGC6341"],
    "M93": ["NGC2447"],
    "M94": ["NGC4736"],
    "M95": ["NGC3351"],
    "M96": ["NGC3368"],
    "M97": ["NGC3587"],
    "M98": ["NGC4192"],
    "M99": ["NGC4254"],
    "M100": ["NGC4321"],
    "M101": ["NGC5457"],
    "M102": ["NGC5866"],
    "M103": ["NGC581"],
    "M104": ["NGC4594"],
    "M105": ["NGC3379"],
    "M106": ["NGC4258"],
    "M107": ["NGC6171"],
    "M108": ["NGC3556"],
    "M109": ["NGC3992"],
    "M110": ["NGC205"],
}


NGC_TO_MESSIER = {
    "NGC205": ["M110"],
    "NGC221": ["M32"],
    "NGC224": ["M31"],
    "NGC581": ["M103"],
    "NGC598": ["M33"],
    "NGC628": ["M74"],
    "NGC650": ["M76"],
    "NGC1039": ["M34"],
    "NGC1068": ["M77"],
    "NGC1904": ["M79"],
    "NGC1912": ["M38"],
    "NGC1952": ["M1"],
    "NGC1960": ["M36"],
    "NGC1976": ["M42"],
    "NGC1982": ["M43"],
    "NGC2068": ["M78"],
    "NGC2099": ["M37"],
    "NGC2168": ["M35"],
    "NGC2287": ["M41"],
    "NGC2323": ["M50"],
    "NGC2422": ["M47"],
    "NGC2437": ["M46"],
    "NGC2447": ["M93"],
    "NGC2548": ["M48"],
    "NGC2632": ["M44"],
    "NGC2682": ["M67"],
    "NGC3031": ["M81"],
    "NGC3034": ["M82"],
    "NGC3351": ["M95"],
    "NGC3368": ["M96"],
    "NGC3379": ["M105"],
    "NGC3556": ["M108"],
    "NGC3587": ["M97"],
    "NGC3623": ["M65"],
    "NGC3627": ["M66"],
    "NGC3992": ["M109"],
    "NGC4192": ["M98"],
    "NGC4254": ["M99"],
    "NGC4258": ["M106"],
    "NGC4303": ["M61"],
    "NGC4321": ["M100"],
    "NGC4374": ["M84"],
    "NGC4382": ["M85"],
    "NGC4406": ["M86"],
    "NGC4472": ["M49"],
    "NGC4486": ["M87"],
    "NGC4501": ["M88"],
    "NGC4548": ["M91"],
    "NGC4552": ["M89"],
    "NGC4569": ["M90"],
    "NGC4579": ["M58"],
    "NGC4590": ["M68"],
    "NGC4594": ["M104"],
    "NGC4621": ["M59"],
    "NGC4649": ["M60"],
    "NGC4736": ["M94"],
    "NGC4826": ["M64"],
    "NGC5024": ["M53"],
    "NGC5055": ["M63"],
    "NGC5194": ["M51"],
    "NGC5236": ["M83"],
    "NGC5272": ["M3"],
    "NGC5457": ["M101"],
    "NGC5866": ["M102"],
    "NGC5904": ["M5"],
    "NGC6093": ["M80"],
    "NGC6121": ["M4"],
    "NGC6171": ["M107"],
    "NGC6205": ["M13"],
    "NGC6218": ["M12"],
    "NGC6254": ["M10"],
    "NGC6266": ["M62"],
    "NGC6273": ["M19"],
    "NGC6333": ["M9"],
    "NGC6341": ["M92"],
    "NGC6402": ["M14"],
    "NGC6405": ["M6"],
    "NGC6475": ["M7"],
    "NGC6494": ["M23"],
    "NGC6514": ["M20"],
    "NGC6523": ["M8"],
    "NGC6531": ["M21"],
    "NGC6603": ["M24"],
    "NGC6611": ["M16"],
    "NGC6613": ["M18"],
    "NGC6618": ["M17"],
    "NGC6626": ["M28"],
    "NGC6637": ["M69"],
    "NGC6656": ["M22"],
    "NGC6681": ["M70"],
    "NGC6694": ["M26"],
    "NGC6705": ["M11"],
    "NGC6715": ["M54"],
    "NGC6720": ["M57"],
    "NGC6779": ["M56"],
    "NGC6809": ["M55"],
    "NGC6838": ["M71"],
    "NGC6853": ["M27"],
    "NGC6864": ["M75"],
    "NGC6913": ["M29"],
    "NGC6981": ["M72"],
    "NGC6994": ["M73"],
    "NGC7078": ["M15"],
    "NGC7089": ["M2"],
    "NGC7092": ["M39"],
    "NGC7099": ["M30"],
    "NGC7654": ["M52"],
    "IC4725": ["M25"],
}


@dataclass(frozen=True)
class CatalogItem:
    object_id: str
    catalog: str
    name: str
    object_type: str
    distance_ly: Optional[float]
    discoverer: Optional[str]
    discovery_year: Optional[int]
    best_months: Optional[str]
    constellation: Optional[str]
    description: Optional[str]
    notes: Optional[str]
    image_notes: Dict[str, str]
    external_link: Optional[str]
    wiki_thumbnail: Optional[str]
    ra_hours: Optional[float]
    dec_deg: Optional[float]
    image_paths: List[Path]
    thumbnail_path: Optional[Path]

    @property
    def display_name(self) -> str:
        id_clean = self.object_id.replace(" ", "").lower()
        name_clean = self.name.replace(" ", "").lower()
        # if the name is essentially the same as the ID, don't include it in the display name to reduce clutter.
        if self.name and name_clean != id_clean:
            return f"{self.object_id} - {self.name}"

        return self.object_id
    
    @property
    def unique_key(self) -> str:
        return f"{self.catalog}:{self.object_id}"


def _resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _is_bundled_catalog_path(path: Path) -> bool:
    try:
        return path.resolve().is_relative_to((PROJECT_ROOT / "data").resolve())
    except Exception:
        return False


def load_config(config_path: Path) -> Dict:
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        return _merge_default_config(loaded)
    return _merge_default_config({})


def _collect_catalog_image_dirs(config: Dict) -> Dict[str, List[Path]]:
    catalog_dirs: Dict[str, List[Path]] = {}
    for catalog_cfg in config.get("catalogs", []):
        name = catalog_cfg.get("name") or ""
        paths = [_resolve_path(path) for path in catalog_cfg.get("image_dirs", []) if path]
        catalog_dirs[name] = paths
    return catalog_dirs


def _unique_paths(paths: Iterable[Path]) -> List[Path]:
    unique: List[Path] = []
    seen: Set[str] = set()
    for path in paths:
        key = os.path.normcase(os.path.abspath(str(path)))
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def resolve_metadata_path(config: Dict, catalog_name: str) -> Optional[Path]:
    default_map = {c.get("name"): c for c in DEFAULT_CONFIG.get("catalogs", [])}
    default_catalog = default_map.get(catalog_name)
    if isinstance(default_catalog, dict):
        metadata_value = default_catalog.get("metadata_file")
        if metadata_value:
            return _resolve_path(metadata_value)
    for catalog_cfg in config.get("catalogs", []):
        if catalog_cfg.get("name") == catalog_name:
            metadata_value = catalog_cfg.get("metadata_file")
            if not metadata_value:
                return None
            return _resolve_path(metadata_value)
    return None


def save_config(config_path: Path, config: Dict) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)


def _build_image_index(image_dirs: Iterable[Path], extensions: Iterable[str]) -> Dict[str, List[Path]]:
    exts = {ext.lower() for ext in extensions}
    index: Dict[str, List[Path]] = {}
    seen: Dict[str, set] = {}
    for image_dir in image_dirs:
        if not image_dir.exists():
            continue
        for root, _, files in os.walk(image_dir):
            for filename in files:
                suffix = Path(filename).suffix.lower()
                if suffix not in exts:
                    continue
                stem = Path(filename).stem.upper()
                matches = _expand_catalog_aliases(_extract_object_ids(stem))
                if not matches:
                    continue
                image_path = Path(root) / filename
                resolved = str(image_path.resolve())
                for object_id in matches:
                    seen.setdefault(object_id, set())
                    if resolved in seen[object_id]:
                        continue
                    seen[object_id].add(resolved)
                    index.setdefault(object_id, []).append(image_path)
    for object_id, paths in index.items():
        index[object_id] = sorted(paths, key=lambda p: p.name.lower())
    return index


def _expand_catalog_aliases(object_ids: Iterable[str]) -> List[str]:
    expanded: List[str] = []
    seen: Set[str] = set()
    for object_id in object_ids:
        if not object_id:
            continue
        normalized = object_id.upper()
        if normalized not in seen:
            seen.add(normalized)
            expanded.append(normalized)
        for alias in MESSIER_TO_NGC.get(normalized, []):
            if alias not in seen:
                seen.add(alias)
                expanded.append(alias)
        for alias in NGC_TO_MESSIER.get(normalized, []):
            if alias not in seen:
                seen.add(alias)
                expanded.append(alias)
    return expanded


def _load_catalog_metadata(metadata_path: Path) -> Dict[str, Dict]:
    try:
        with metadata_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except UnicodeDecodeError:
        with metadata_path.open("r", encoding="latin-1") as handle:
            return json.load(handle)


def _load_json(path: Path) -> object:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except UnicodeDecodeError:
        with path.open("r", encoding="latin-1") as handle:
            return json.load(handle)


def _catalog_overlay_filename(catalog_name: str, metadata_file: Optional[str] = None) -> str:
    # Keep overlay filenames aligned with source metadata filenames whenever possible.
    if metadata_file:
        source_name = Path(str(metadata_file)).name.strip()
        if source_name.lower().endswith(".json"):
            return source_name
    normalized = re.sub(r"[^a-z0-9]+", "_", (catalog_name or "").strip().lower())
    normalized = normalized.strip("_") or "catalog"
    return f"{normalized}.json"


def _text_source_hash(value: Optional[str]) -> str:
    normalized = (value or "").strip()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _load_catalog_translation_overlay(
    catalog_name: str,
    locale_code: str,
    metadata_file: Optional[str] = None,
) -> Dict[str, Dict[str, Dict[str, str]]]:
    if not locale_code or locale_code == "en":
        return {}
    overlay_filenames: List[str] = [
        _catalog_overlay_filename(
            catalog_name,
            metadata_file,
        )
    ]
    if metadata_file:
        source_name = Path(str(metadata_file)).name.strip()
        if source_name.lower().endswith("_metadata.json"):
            fallback_name = source_name[: -len("_metadata.json")] + "_catalog.json"
            if fallback_name and fallback_name not in overlay_filenames:
                overlay_filenames.append(fallback_name)

    payload: object = {}
    for overlay_name in overlay_filenames:
        overlay_path = PROJECT_ROOT / "data" / "i18n" / locale_code / overlay_name
        if not overlay_path.exists():
            continue
        try:
            payload = _load_json(overlay_path)
            break
        except (OSError, json.JSONDecodeError):
            continue
    if not isinstance(payload, dict):
        return {}

    normalized: Dict[str, Dict[str, Dict[str, str]]] = {}
    for object_id, fields in payload.items():
        if not isinstance(object_id, str) or not isinstance(fields, dict):
            continue
        entry: Dict[str, Dict[str, str]] = {}
        for field_name in ("name", "description"):
            field_payload = fields.get(field_name)
            if not isinstance(field_payload, dict):
                continue
            text = field_payload.get("text")
            source_hash = field_payload.get("source_hash")
            if not isinstance(text, str) or not isinstance(source_hash, str):
                continue
            entry[field_name] = {
                "text": text.strip(),
                "source_hash": source_hash.strip(),
            }
        if entry:
            normalized[object_id] = entry
    return normalized


def _apply_overlay_text(base_text: Optional[str], field_overlay: Optional[Dict[str, str]]) -> Optional[str]:
    if not field_overlay:
        return base_text
    translated = (field_overlay.get("text") or "").strip()
    source_hash = (field_overlay.get("source_hash") or "").strip()
    if not translated or not source_hash:
        return base_text
    if source_hash != _text_source_hash(base_text):
        return base_text
    return translated


def _load_user_image_notes(notes_path: Optional[Path]) -> Dict[str, str]:
    if notes_path is None or not notes_path.exists():
        return {}
    try:
        data = _load_json(notes_path)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    notes: Dict[str, str] = {}
    for key, value in data.items():
        if isinstance(key, str) and isinstance(value, str):
            normalized = value.strip()
            if normalized:
                notes[key] = normalized
    return notes


def _load_user_object_notes(notes_path: Optional[Path]) -> Dict[str, str]:
    if notes_path is None or not notes_path.exists():
        return {}
    try:
        data = _load_json(notes_path)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    payload = data.get("__object_notes__", {})
    if not isinstance(payload, dict):
        return {}
    notes: Dict[str, str] = {}
    for key, value in payload.items():
        if isinstance(key, str) and isinstance(value, str):
            normalized = value.strip()
            if normalized:
                notes[key] = normalized
    return notes


def _load_user_thumbnails(notes_path: Optional[Path]) -> Dict[str, str]:
    if notes_path is None or not notes_path.exists():
        return {}
    try:
        data = _load_json(notes_path)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    payload = data.get("__thumbnails__", {})
    if not isinstance(payload, dict):
        return {}
    thumbnails: Dict[str, str] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        normalized = value.strip()
        if normalized:
            thumbnails[key] = normalized
    return thumbnails


def _save_user_image_note(notes_path: Path, image_name: str, notes: str) -> None:
    data = _load_user_image_notes(notes_path) if notes_path.exists() else {}
    if notes.strip():
        data[image_name] = notes.strip()
    else:
        data.pop(image_name, None)
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    with notes_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def _save_user_object_note(notes_path: Path, catalog_name: str, object_id: str, notes: str) -> None:
    data = _load_json(notes_path) if notes_path.exists() else {}
    if not isinstance(data, dict):
        data = {}
    object_notes = data.get("__object_notes__")
    if not isinstance(object_notes, dict):
        object_notes = {}
    key = f"{catalog_name}:{object_id}"
    if notes.strip():
        object_notes[key] = notes.strip()
    else:
        object_notes.pop(key, None)
    if object_notes:
        data["__object_notes__"] = object_notes
    else:
        data.pop("__object_notes__", None)
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    with notes_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def _save_user_thumbnail(notes_path: Path, catalog_name: str, object_id: str, thumbnail_name: str) -> None:
    data = _load_json(notes_path) if notes_path.exists() else {}
    if not isinstance(data, dict):
        data = {}
    thumbnails = data.get("__thumbnails__")
    if not isinstance(thumbnails, dict):
        thumbnails = {}
    key = f"{catalog_name}:{object_id}"
    normalized = (thumbnail_name or "").strip()
    if normalized:
        thumbnails[key] = normalized
    else:
        thumbnails.pop(key, None)
    if thumbnails:
        data["__thumbnails__"] = thumbnails
    else:
        data.pop("__thumbnails__", None)
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    with notes_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def _cleanup_metadata_image_note(metadata_path: Path, catalog_name: str, object_id: str, image_name: str) -> None:
    if _is_bundled_catalog_path(metadata_path):
        return
    if not metadata_path.exists():
        return
    data = _load_catalog_metadata(metadata_path)
    catalog = data.get(catalog_name)
    if not isinstance(catalog, dict):
        return
    entry = catalog.get(object_id)
    if not isinstance(entry, dict):
        return
    image_notes = entry.get("image_notes")
    if not isinstance(image_notes, dict):
        return
    if image_name not in image_notes:
        return
    image_notes.pop(image_name, None)
    if not image_notes:
        entry.pop("image_notes", None)
    if not entry:
        catalog.pop(object_id, None)
    if not catalog:
        data.pop(catalog_name, None)
    with metadata_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def load_catalog_items(config: Dict, user_notes_path: Optional[Path] = None) -> List[CatalogItem]:
    items: List[CatalogItem] = []
    user_image_notes = _load_user_image_notes(user_notes_path)
    user_object_notes = _load_user_object_notes(user_notes_path)
    user_thumbnails = _load_user_thumbnails(user_notes_path)
    ui_locale = normalize_locale_code(config.get("ui_locale", "system"), fallback="en")
    extensions = config.get("image_extensions", DEFAULT_CONFIG["image_extensions"])
    observer = config.get("observer", {})
    latitude = observer.get("latitude")
    longitude = observer.get("longitude") or 0.0
    master_dir = config.get("master_image_dir") or ""
    master_path = _resolve_path(master_dir) if master_dir else None
    catalog_dirs = _collect_catalog_image_dirs(config)

    for catalog_cfg in config.get("catalogs", []):
        catalog_name = catalog_cfg.get("name", "Unknown")
        catalog_prefix = _catalog_prefix(catalog_name)
        metadata_file = catalog_cfg.get("metadata_file", "")
        metadata_path = _resolve_path(metadata_file)
        image_dirs = list(catalog_dirs.get(catalog_name, []))
        if catalog_name == "Messier":
            image_dirs += catalog_dirs.get("NGC", [])
        elif catalog_name == "NGC":
            image_dirs += catalog_dirs.get("Messier", [])
        if master_path:
            image_dirs.append(master_path)
        image_dirs = _unique_paths(image_dirs)
        image_index = _build_image_index(image_dirs, extensions)
        translation_overlay = _load_catalog_translation_overlay(
            catalog_name,
            ui_locale,
            metadata_file=metadata_file,
        )

        if not metadata_path.exists():
            continue

        catalog_entries: Dict[str, Dict] = {}
        if metadata_path.exists():
            catalog_data = _load_catalog_metadata(metadata_path)
            catalog_entries = _select_catalog_entries(catalog_data, catalog_name)
        for object_id, meta in catalog_entries.items():
            image_paths = image_index.get(object_id.upper(), [])
            note_key = f"{catalog_name}:{object_id}"
            thumbnail_value = user_thumbnails.get(note_key) or _normalize_text(meta.get("thumbnail"))
            thumbnail_path = _select_thumbnail(image_paths, thumbnail_value)
            ra_hours = _parse_ra(meta.get("ra_hours") or meta.get("ra"))
            dec_deg = _parse_dec(meta.get("dec_deg") or meta.get("dec"))
            best_months = _adjust_best_months(meta.get("best_months"), latitude)
            if not best_months and ra_hours is not None and dec_deg is not None and latitude is not None:
                best_months = _compute_best_months(ra_hours, dec_deg, latitude, longitude)
            notes = _normalize_text(meta.get("notes"))
            if note_key in user_object_notes:
                notes = user_object_notes[note_key]
            image_notes = _normalize_image_notes(meta.get("image_notes"))
            base_name = _normalize_text(meta.get("name", "")) or ""
            base_description = _normalize_text(meta.get("description"))
            entry_overlay = translation_overlay.get(object_id, {})
            localized_name = _apply_overlay_text(base_name, entry_overlay.get("name")) or ""
            localized_description = _apply_overlay_text(base_description, entry_overlay.get("description"))
            for image_path in image_paths:
                note_text = user_image_notes.get(image_path.name)
                if note_text:
                    image_notes[image_path.name] = note_text
            items.append(
                CatalogItem(
                    object_id=object_id,
                    catalog=catalog_name,
                    name=localized_name,
                    object_type=_normalize_text(meta.get("type", "")),
                    distance_ly=meta.get("distance_ly"),
                    discoverer=_normalize_text(meta.get("discoverer")),
                    discovery_year=meta.get("discovery_year"),
                    best_months=best_months,
                    constellation=canonical_constellation_name(meta.get("constellation"))
                    or extract_constellation_from_description(base_description),
                    description=localized_description,
                    notes=notes,
                    image_notes=image_notes,
                    external_link=_normalize_text(
                        meta.get("external_link")
                    ) or _default_external_link(object_id, base_name),
                    wiki_thumbnail=_normalize_text(meta.get("wiki_thumbnail")),
                    ra_hours=ra_hours,
                    dec_deg=dec_deg,
                    image_paths=image_paths,
                    thumbnail_path=thumbnail_path,
                )
            )

        # Add image-only entries that are not in metadata.
        for object_id, image_paths in image_index.items():
            if not catalog_prefix:
                continue
            if not _matches_catalog_object_id(catalog_name, object_id):
                continue
            if object_id in catalog_entries:
                continue
            thumbnail_path = _select_thumbnail(image_paths, user_thumbnails.get(f"{catalog_name}:{object_id}"))
            image_notes: Dict[str, str] = {}
            for image_path in image_paths:
                note_text = user_image_notes.get(image_path.name)
                if note_text:
                    image_notes[image_path.name] = note_text
            items.append(
                CatalogItem(
                    object_id=object_id,
                    catalog=catalog_name,
                    name="",
                    object_type="",
                    distance_ly=None,
                    discoverer=None,
                    discovery_year=None,
                    best_months=None,
                    constellation=None,
                    description=None,
                    notes=user_object_notes.get(f"{catalog_name}:{object_id}"),
                    image_notes=image_notes,
                    external_link=_default_external_link(object_id, None),
                    wiki_thumbnail=None,
                    ra_hours=None,
                    dec_deg=None,
                    image_paths=image_paths,
                    thumbnail_path=thumbnail_path,
                )
            )

    return items


def _select_thumbnail(image_paths: List[Path], thumbnail_value: Optional[str]) -> Optional[Path]:
    if not image_paths:
        return None
    if not thumbnail_value:
        return image_paths[0]
    normalized = thumbnail_value.strip()
    for path in image_paths:
        if path.name == normalized:
            return path
    for path in image_paths:
        if path.stem == normalized:
            return path
    return image_paths[0]


def _select_catalog_entries(catalog_data: Dict[str, Dict], catalog_name: str) -> Dict[str, Dict]:
    if not isinstance(catalog_data, dict):
        return {}
    entries = catalog_data.get(catalog_name)
    if isinstance(entries, dict):
        return entries
    lower_name = (catalog_name or "").lower()
    for key, value in catalog_data.items():
        if isinstance(key, str) and key.lower() == lower_name and isinstance(value, dict):
            return value
    if len(catalog_data) == 1:
        only_value = next(iter(catalog_data.values()))
        if isinstance(only_value, dict):
            return only_value
    return {}


def collect_object_types(items: Iterable[CatalogItem]) -> List[str]:
    # Ordre d'affichage préférentiel pour les types connus
    _TYPE_ORDER = [
        "Galaxy",
        "Galaxy Cluster",
        "Globular Cluster",
        "Open Cluster",
        "Emission Nebula",
        "Reflection Nebula",
        "Dark Nebula",
        "Planetary Nebula",
        "Supernova Remnant",
        "HII Region",
        "Star",
        "Double Star",
        "Asterism",
    ]
    all_types = {item.object_type for item in items if item.object_type}
    ordered = [t for t in _TYPE_ORDER if t in all_types]
    remaining = sorted(all_types - set(ordered))
    return ordered + remaining


def save_note(
    metadata_path: Path,
    catalog_name: str,
    object_id: str,
    notes: str,
    user_notes_path: Optional[Path] = None,
) -> None:
    if user_notes_path is not None and user_notes_path != metadata_path:
        _save_user_object_note(user_notes_path, catalog_name, object_id, notes)
        return
    if _is_bundled_catalog_path(metadata_path):
        return
    if not metadata_path.exists():
        return
    data = _load_catalog_metadata(metadata_path)
    catalog = data.setdefault(catalog_name, {})
    entry = catalog.setdefault(object_id, {})
    if notes.strip():
        entry["notes"] = notes
    else:
        entry.pop("notes", None)
    with metadata_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def save_image_note(
    metadata_path: Path,
    catalog_name: str,
    object_id: str,
    image_name: str,
    notes: str,
    user_notes_path: Optional[Path] = None,
) -> None:
    if user_notes_path is not None and user_notes_path != metadata_path:
        _save_user_image_note(user_notes_path, image_name, notes)
        _cleanup_metadata_image_note(metadata_path, catalog_name, object_id, image_name)
        return
    if _is_bundled_catalog_path(metadata_path):
        return
    if not metadata_path.exists():
        return
    data = _load_catalog_metadata(metadata_path)
    catalog = data.setdefault(catalog_name, {})
    entry = catalog.setdefault(object_id, {})
    image_notes = entry.setdefault("image_notes", {})
    if not isinstance(image_notes, dict):
        image_notes = {}
        entry["image_notes"] = image_notes
    if notes.strip():
        image_notes[image_name] = notes
    else:
        image_notes.pop(image_name, None)
    with metadata_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def save_thumbnail(
    metadata_path: Path,
    catalog_name: str,
    object_id: str,
    thumbnail_name: str,
    user_notes_path: Optional[Path] = None,
) -> None:
    if user_notes_path is not None and user_notes_path != metadata_path:
        _save_user_thumbnail(user_notes_path, catalog_name, object_id, thumbnail_name)
        return
    if _is_bundled_catalog_path(metadata_path):
        return
    if not metadata_path.exists():
        return
    data = _load_catalog_metadata(metadata_path)
    catalog = data.setdefault(catalog_name, {})
    entry = catalog.setdefault(object_id, {})
    entry["thumbnail"] = thumbnail_name
    with metadata_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def _merge_default_config(loaded: Dict) -> Dict:
    merged = DEFAULT_CONFIG.copy()
    merged.update(loaded)
    merged.setdefault("observer", DEFAULT_CONFIG["observer"])
    merged.setdefault("image_extensions", DEFAULT_CONFIG["image_extensions"])
    merged.setdefault("thumb_size", DEFAULT_CONFIG["thumb_size"])

    existing_catalogs = {
        c.get("name"): c for c in loaded.get("catalogs", []) if isinstance(c, dict)
    }
    catalogs = []
    # Tous les catalogues définis dans DEFAULT_CONFIG sont toujours inclus
    for default_catalog in DEFAULT_CONFIG["catalogs"]:
        name = default_catalog.get("name")
        if name in existing_catalogs:
            updated = default_catalog.copy()
            updated.update(existing_catalogs[name])
            catalogs.append(updated)
        else:
            catalogs.append(default_catalog.copy())
    # Inclure les catalogues personnalisés absents des defaults
    default_names = {c.get("name") for c in catalogs}
    for name, catalog in existing_catalogs.items():
        if name not in default_names:
            catalogs.append(catalog)
    merged["catalogs"] = catalogs
    _normalize_catalog_paths(merged)
    return merged


def _normalize_catalog_paths(config: Dict) -> None:
    default_map = {c.get("name"): c for c in DEFAULT_CONFIG.get("catalogs", [])}
    for catalog in config.get("catalogs", []):
        name = catalog.get("name")
        default_catalog = default_map.get(name, {})
        default_metadata_file = default_catalog.get("metadata_file")
        if default_metadata_file:
            catalog["metadata_file"] = default_metadata_file
        image_dirs = [path for path in catalog.get("image_dirs", []) if path]
        existing = [path for path in image_dirs if _resolve_path(path).exists()]
        if existing:
            catalog["image_dirs"] = existing
        else:
            default_dirs = default_catalog.get("image_dirs", [])
            if default_dirs:
                catalog["image_dirs"] = list(default_dirs)
            elif image_dirs:
                catalog["image_dirs"] = image_dirs
    master_dir = config.get("master_image_dir") or ""
    if master_dir and not _resolve_path(master_dir).exists():
        config["master_image_dir"] = ""


SOLAR_OBJECTS = [
    "Sun",
    "Moon",
    "Mercury",
    "Venus",
    "Earth",
    "Mars",
    "Phobos",
    "Deimos",
    "Jupiter",
    "Io",
    "Europa",
    "Ganymede",
    "Callisto",
    "Saturn",
    "Titan",
    "Enceladus",
    "Rhea",
    "Iapetus",
    "Dione",
    "Tethys",
    "Mimas",
    "Uranus",
    "Miranda",
    "Ariel",
    "Umbriel",
    "Titania",
    "Oberon",
    "Neptune",
    "Triton",
    "Nereid",
    "Proteus",
    "Pluto",
    "Charon",
    "Ceres",
    "Vesta",
    "Pallas",
    "Hygiea",
    "Haumea",
    "Makemake",
    "Eris",
    "Sedna",
    "Orcus",
    "Quaoar",
    "Gonggong",
    "Chiron",
    "Chariklo",
    "Halley",
    "Encke",
    "Tempel 1",
    "Borrelly",
    "67P Churyumov-Gerasimenko",
    "Hartley 2",
    "Swift-Tuttle",
    "Hale-Bopp",
]

SOLAR_ALIAS_EXTRAS = {
    "Sun": ["solar"],
    "Moon": ["luna", "lunar"],
    "Halley": ["halleycomet", "halley's"],
    "67P Churyumov-Gerasimenko": ["67p", "churyumov", "gerasimenko", "churyumov-gerasimenko"],
    "Tempel 1": ["tempel1", "tempel-1", "9p", "9p-tempel", "9p-tempel-1"],
    "Borrelly": ["19p", "19p-borrelly"],
    "Hartley 2": ["hartley2", "hartley-2", "103p", "103p-hartley", "103p-hartley-2"],
    "Swift-Tuttle": ["swifttuttle", "swift_tuttle", "109p", "109p-swift", "109p-swift-tuttle"],
    "Hale-Bopp": ["halebopp", "hale bopp"],
}

def _solar_aliases(name: str) -> List[str]:
    base = name.lower()
    variants = {
        base,
        base.replace(" ", ""),
        base.replace(" ", "-"),
        base.replace(" ", "_"),
        base.replace("'", ""),
    }
    variants |= {v.replace("-", "") for v in variants}
    variants |= {v.replace("_", "") for v in variants}
    extras = SOLAR_ALIAS_EXTRAS.get(name, [])
    return sorted(set(variants) | set(extras))

def _alias_matches(stem: str, alias: str) -> bool:
    if not alias:
        return False
    if re.fullmatch(r"[a-z]+(?: [a-z]+)*", alias):
        pattern = rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])"
        return re.search(pattern, stem) is not None
    if len(alias) <= 2:
        pattern = rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])"
        return re.search(pattern, stem) is not None
    return alias in stem


def _extract_object_ids(stem: str) -> List[str]:
    ids: List[str] = []
    lower_stem = stem.lower()

    # ── Système solaire ──────────────────────────────────────────────────────
    for object_id in SOLAR_OBJECTS:
        if any(_alias_matches(lower_stem, alias) for alias in _solar_aliases(object_id)):
            ids.append(object_id.upper())

    # ── Messier / NGC / IC / Caldwell ────────────────────────────────────────
    pattern = re.compile(r"(NGC|IC|M|(?<!I)(?<!NG)C)[\s_-]*0*(\d{1,5})(?!\d)")
    for match in pattern.finditer(stem):
        prefix, number = match.groups()
        ids.append(f"{prefix}{int(number)}")

    # ── Sharpless (Sh2) ──────────────────────────────────────────────────────
    # Reconnaît : Sh2-155, Sh2155, Sh2_155, SH2-155, sh2155, ...
    sh2_pattern = re.compile(r"(?<![A-Z0-9])SH2[\s_-]*0*(\d{1,3}[a-z]?)(?![A-Z0-9])",
                             re.IGNORECASE)
    for m in sh2_pattern.finditer(stem):
        ids.append(f"Sh2-{m.group(1)}")

    # ── LDN (Lynds Dark Nebulae) ─────────────────────────────────────────────
    # Reconnaît : LDN1630, LDN_1630, LDN 1630, ldn183, ...
    ldn_pattern = re.compile(r"(?<![A-Z0-9])LDN[\s_-]*0*(\d{1,4})(?!\d)",
                             re.IGNORECASE)
    for m in ldn_pattern.finditer(stem):
        ids.append(f"LDN {int(m.group(1))}")

    # ── Barnard (B) ──────────────────────────────────────────────────────────
    # Reconnaît : B33, B_33, B-33, B 33, b150, ...
    # Préfixe seul ("B") trop court → on exige au moins 2 chiffres ou
    # un séparateur explicite pour éviter les faux positifs.
    barnard_pattern = re.compile(
        r"(?<![A-Z0-9])"
        r"B"
        r"(?:[\s_-]+0*(\d{1,3})|0*(\d{2,3}))"  # séparateur OU 2-3 chiffres directs
        r"(?![A-Z0-9])",
        re.IGNORECASE,
    )
    for m in barnard_pattern.finditer(stem):
        num = m.group(1) or m.group(2)
        ids.append(f"B {int(num)}")

    # ── VdB (van den Bergh) ──────────────────────────────────────────────────
    # Reconnaît : VdB139, VDB139, VDB_139, vdb 139, ...
    vdb_pattern = re.compile(r"(?<![A-Z0-9])VDB[\s_-]*0*(\d{1,3})(?!\d)",
                             re.IGNORECASE)
    for m in vdb_pattern.finditer(stem):
        ids.append(f"VdB {int(m.group(1))}")

    # ── LBN (Lynds Bright Nebulae) ───────────────────────────────────────────
    # Reconnaît : LBN667, LBN_667, LBN 667, lbn667a, ...
    lbn_pattern = re.compile(r"(?<![A-Z0-9])LBN[\s_-]*0*(\d{1,4}[a-z]?)(?![A-Z0-9])",
                             re.IGNORECASE)
    for m in lbn_pattern.finditer(stem):
        ids.append(f"LBN {m.group(1)}")

    # ── PNG (Strasbourg-ESO PN catalogue) ────────────────────────────────────
    # IDs très complexes (ex. PNG 59.0-13.9) — on tente une correspondance
    # souple sur le motif PNG suivi de chiffres/points/signes.
    # Reconnaît : PNG59.0-13.9, PNG_59.0+13.9, PNG590-139, ...
    png_pattern = re.compile(
        r"(?<![A-Z0-9])PNG[\s_-]*([\d]+\.?\d*[+\-][\d]+\.?\d*)(?![A-Z0-9])",
        re.IGNORECASE,
    )
    for m in png_pattern.finditer(stem):
        ids.append(f"PNG {m.group(1)}")

    return list(dict.fromkeys(ids))


def _normalize_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return value.replace("M\u008echain", "M\u00e9chain")


def _normalize_image_notes(value: Optional[Dict]) -> Dict[str, str]:
    if not isinstance(value, dict):
        return {}
    normalized: Dict[str, str] = {}
    for key, note in value.items():
        if not isinstance(key, str):
            continue
        if not isinstance(note, str):
            continue
        normalized[key] = _normalize_text(note) or ""
    return normalized


def _default_external_link(object_id: str, name: Optional[str]) -> str:
    match = re.match(r"^M\\s*0*(\\d+)$", object_id, re.IGNORECASE)
    if match:
        messier_num = int(match.group(1))
        return f"https://en.wikipedia.org/wiki/Messier_{messier_num}"
    target = name or object_id
    slug = quote(target.replace(" ", "_"))
    return f"https://en.wikipedia.org/wiki/{slug}"


def _catalog_prefix(catalog_name: str) -> str:
    name = (catalog_name or "").strip().lower()
    if name == "messier":
        return "M"
    if name == "ngc":
        return "NGC"
    if name == "ic":
        return "IC"
    if name == "caldwell":
        return "C"
    if name == "sh2":
        return "Sh2"
    if name == "ldn":
        return "LDN"
    if name == "barnard":
        return "B"
    if name == "vdb":
        return "VdB"
    if name == "lbn":
        return "LBN"
    if name == "png":
        return "PNG"
    return ""


def _matches_catalog_object_id(catalog_name: str, object_id: str) -> bool:
    name = (catalog_name or "").strip().lower()
    value = (object_id or "").strip()
    if name == "messier":
        return re.match(r"^M\d+$", value, re.IGNORECASE) is not None
    if name == "caldwell":
        return re.match(r"^C\d+$", value, re.IGNORECASE) is not None
    if name == "ngc":
        return re.match(r"^NGC\d+$", value, re.IGNORECASE) is not None
    if name == "ic":
        return re.match(r"^IC\d+$", value, re.IGNORECASE) is not None
    if name == "sh2":
        return re.match(r"^Sh2-\d+[a-z]?$", value, re.IGNORECASE) is not None
    if name == "ldn":
        return re.match(r"^LDN\s+\d+$", value, re.IGNORECASE) is not None
    if name == "barnard":
        return re.match(r"^B\s+\d+$", value, re.IGNORECASE) is not None
    if name == "vdb":
        return re.match(r"^VdB\s+\d+$", value, re.IGNORECASE) is not None
    if name == "lbn":
        return re.match(r"^LBN\s+\d+[a-z]?$", value, re.IGNORECASE) is not None
    if name == "png":
        return re.match(r"^PNG\s+[\d.+\-]+$", value, re.IGNORECASE) is not None
    return True


def _adjust_best_months(best_months: Optional[str], latitude: Optional[float]) -> Optional[str]:
    if not best_months:
        return best_months
    if latitude is None or latitude >= 0:
        return best_months
    month_map = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                 "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    months = []
    for idx in range(0, len(best_months), 3):
        chunk = best_months[idx: idx + 3]
        if chunk in month_map:
            months.append(chunk)
    if not months:
        return best_months
    shifted = []
    for month in months:
        new_index = (month_map.index(month) + 6) % 12
        shifted.append(month_map[new_index])
    return "".join(shifted)


def _parse_ra(value: Optional[str]) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    parts = re.split(r"[:\s]+", text)
    try:
        hours = float(parts[0])
        minutes = float(parts[1]) if len(parts) > 1 else 0.0
        seconds = float(parts[2]) if len(parts) > 2 else 0.0
        return hours + minutes / 60.0 + seconds / 3600.0
    except ValueError:
        return None


def _parse_dec(value: Optional[str]) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    sign = -1.0 if text.startswith("-") else 1.0
    text = text.lstrip("+-")
    parts = re.split(r"[:\s]+", text)
    try:
        deg = float(parts[0])
        minutes = float(parts[1]) if len(parts) > 1 else 0.0
        seconds = float(parts[2]) if len(parts) > 2 else 0.0
        return sign * (deg + minutes / 60.0 + seconds / 3600.0)
    except ValueError:
        return None


def _compute_best_months(ra_hours: float, dec_deg: float, lat_deg: float, lon_deg: float) -> str:
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    best = []
    for month in range(1, 13):
        date = datetime(2025, month, 15, 0, 0, tzinfo=timezone.utc)
        lst = _local_sidereal_time(date, lon_deg)
        ha = (lst - ra_hours) * 15.0
        ha = (ha + 180.0) % 360.0 - 180.0
        alt = _altitude_deg(lat_deg, dec_deg, ha)
        if alt >= 25.0:
            best.append(month_names[month - 1])
    return "".join(best)


def _local_sidereal_time(date: datetime, longitude_deg: float) -> float:
    jd = _julian_date(date)
    t = (jd - 2451545.0) / 36525.0
    gmst = 280.46061837 + 360.98564736629 * (jd - 2451545.0) + 0.000387933 * t * t - t * t * t / 38710000.0
    gmst = gmst % 360.0
    lst = (gmst + longitude_deg) % 360.0
    return lst / 15.0


def _julian_date(date: datetime) -> float:
    year = date.year
    month = date.month
    day = date.day + (date.hour + date.minute / 60.0) / 24.0
    if month <= 2:
        year -= 1
        month += 12
    a = math.floor(year / 100)
    b = 2 - a + math.floor(a / 4)
    jd = math.floor(365.25 * (year + 4716)) + math.floor(30.6001 * (month + 1)) + day + b - 1524.5
    return jd


def _altitude_deg(lat_deg: float, dec_deg: float, ha_deg: float) -> float:
    lat_rad = math.radians(lat_deg)
    dec_rad = math.radians(dec_deg)
    ha_rad = math.radians(ha_deg)
    sin_alt = math.sin(lat_rad) * math.sin(dec_rad) + math.cos(lat_rad) * math.cos(dec_rad) * math.cos(ha_rad)
    return math.degrees(math.asin(sin_alt))

