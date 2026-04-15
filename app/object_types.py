from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, Optional

from i18n import current_ui_locale, normalize_locale_code


FALLBACK_LOCALE = "en"


def _get_object_types_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "app" / "locales" / "object_types"
    return Path(__file__).resolve().parent / "locales" / "object_types"


def _load_locale_payload(path: Path) -> Dict[str, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}

    normalized: Dict[str, str] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        canonical = key.strip()
        localized = value.strip()
        if canonical and localized:
            normalized[canonical] = localized
    return normalized


def _load_object_type_names() -> Dict[str, Dict[str, str]]:
    directory = _get_object_types_dir()
    english_payload = _load_locale_payload(directory / f"{FALLBACK_LOCALE}.json")
    names: Dict[str, Dict[str, str]] = {
        canonical: {FALLBACK_LOCALE: localized}
        for canonical, localized in english_payload.items()
    }
    if not names:
        return {}

    for path in sorted(directory.glob("*.json")):
        locale_code = path.stem.lower()
        if locale_code == FALLBACK_LOCALE:
            continue
        payload = _load_locale_payload(path)
        if not payload:
            continue
        for canonical in names:
            localized = payload.get(canonical)
            if localized:
                names[canonical][locale_code] = localized
    return names


def _fold_text(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    without_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    words = re.findall(r"[A-Za-z0-9+\-/']+", without_marks)
    return " ".join(words).casefold()


OBJECT_TYPE_NAMES: Dict[str, Dict[str, str]] = _load_object_type_names()

_HIDDEN_OBJECT_TYPE_FOLDED = {
    _fold_text("Duplicate Entry"),
    _fold_text("Nonexistent Object"),
    _fold_text("Nonexistant Object"),
}

_CANONICAL_BY_FOLDED = {_fold_text(name): name for name in OBJECT_TYPE_NAMES}
for canonical_name, localized_names in OBJECT_TYPE_NAMES.items():
    for localized_name in localized_names.values():
        folded = _fold_text(localized_name)
        if folded:
            _CANONICAL_BY_FOLDED.setdefault(folded, canonical_name)


def canonical_object_type(value: object) -> Optional[str]:
    if value is None:
        return None
    folded = _fold_text(value)
    if not folded:
        return None
    if folded in _HIDDEN_OBJECT_TYPE_FOLDED:
        return None
    return _CANONICAL_BY_FOLDED.get(folded)


def is_hidden_object_type(value: object) -> bool:
    folded = _fold_text(value)
    return bool(folded) and folded in _HIDDEN_OBJECT_TYPE_FOLDED


def localized_object_type(value: object, locale_code: Optional[object] = None) -> Optional[str]:
    if is_hidden_object_type(value):
        return None
    canonical = canonical_object_type(value)
    if not canonical:
        return None
    locale = normalize_locale_code(
        locale_code if locale_code is not None else current_ui_locale(),
        fallback=FALLBACK_LOCALE,
    )
    translations = OBJECT_TYPE_NAMES.get(canonical, {})
    return translations.get(locale) or translations.get(FALLBACK_LOCALE) or canonical
