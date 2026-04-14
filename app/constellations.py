from __future__ import annotations

import difflib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, Optional

from i18n import current_ui_locale, normalize_locale_code


FALLBACK_LOCALE = "en"


def _get_constellations_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "app" / "locales" / "constellations"
    return Path(__file__).resolve().parent / "locales" / "constellations"


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
        normalized_key = key.strip()
        normalized_value = value.strip()
        if normalized_key and normalized_value:
            normalized[normalized_key] = normalized_value
    return normalized


def _load_constellation_names() -> Dict[str, Dict[str, str]]:
    directory = _get_constellations_dir()
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
    words = re.findall(r"[A-Za-z']+", without_marks)
    return " ".join(words).casefold()


CONSTELLATION_NAMES: Dict[str, Dict[str, str]] = _load_constellation_names()
AVAILABLE_CONSTELLATION_LOCALES = tuple(
    sorted({locale for translations in CONSTELLATION_NAMES.values() for locale in translations})
)

_CANONICAL_BY_FOLDED = {_fold_text(name): name for name in CONSTELLATION_NAMES}
for canonical_name, localized_names in CONSTELLATION_NAMES.items():
    for localized_name in localized_names.values():
        folded = _fold_text(localized_name)
        if folded:
            _CANONICAL_BY_FOLDED.setdefault(folded, canonical_name)

_DISPLAY_NAMES = [
    *CONSTELLATION_NAMES.keys(),
    *(value for names in CONSTELLATION_NAMES.values() for value in names.values()),
]
_DISPLAY_NAME_BY_FOLDED = {
    _fold_text(name): name
    for name in _DISPLAY_NAMES
    if _fold_text(name)
}
_NAME_PATTERN = "|".join(
    sorted((re.escape(name) for name in _DISPLAY_NAME_BY_FOLDED.values()), key=len, reverse=True)
)
_DESCRIPTION_PATTERNS = [
    re.compile(rf"\bconstellation of (?P<name>{_NAME_PATTERN})\b", re.IGNORECASE),
    re.compile(rf"\bconstellation\s+(?P<name>{_NAME_PATTERN})\b", re.IGNORECASE),
    re.compile(rf"\b(?:the\s+)?(?P<name>{_NAME_PATTERN})\s+constellation\b", re.IGNORECASE),
    re.compile(
        rf"\b(?:in|within|inside|from|near|toward|towards|appearing\s+in|located\s+in|lies\s+in|lie\s+in)\s+"
        rf"(?:the\s+)?(?:northern\s+|southern\s+|eastern\s+|western\s+)?(?:constellation\s+(?:of\s+)?)?"
        rf"(?P<name>{_NAME_PATTERN})\b",
        re.IGNORECASE,
    ),
]
_FUZZY_CONTEXT_PATTERN = re.compile(
    r"\bconstellation(?:\s+of)?\s+([A-Za-zÀ-ÖØ-öø-ÿ'’\-]+(?:\s+[A-Za-zÀ-ÖØ-öø-ÿ'’\-]+){0,2})",
    re.IGNORECASE,
)


def canonical_constellation_name(value: object) -> Optional[str]:
    if value is None:
        return None
    folded = _fold_text(value)
    if not folded:
        return None
    return _CANONICAL_BY_FOLDED.get(folded)


def _fuzzy_constellation_name(value: object) -> Optional[str]:
    folded = _fold_text(value)
    if not folded:
        return None
    closest = difflib.get_close_matches(folded, _CANONICAL_BY_FOLDED.keys(), n=1, cutoff=0.88)
    if not closest:
        return None
    return _CANONICAL_BY_FOLDED.get(closest[0])


def extract_constellation_from_description(description: object) -> Optional[str]:
    if description is None:
        return None
    text = " ".join(str(description).split())
    if not text:
        return None
    for pattern in _DESCRIPTION_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        name = canonical_constellation_name(match.group("name"))
        if name:
            return name
    for match in _FUZZY_CONTEXT_PATTERN.finditer(text):
        name = _fuzzy_constellation_name(match.group(1))
        if name:
            return name
    return None


def localized_constellation_name(latin_name: object, locale_code: Optional[object] = None) -> Optional[str]:
    canonical = canonical_constellation_name(latin_name)
    if not canonical:
        return None
    locale = normalize_locale_code(
        locale_code if locale_code is not None else current_ui_locale(),
        fallback=FALLBACK_LOCALE,
    )
    translations = CONSTELLATION_NAMES.get(canonical, {})
    return translations.get(locale) or translations.get(FALLBACK_LOCALE) or canonical


def format_constellation_display(latin_name: object, locale_code: Optional[object] = None) -> Optional[str]:
    canonical = canonical_constellation_name(latin_name)
    if not canonical:
        return None
    localized = localized_constellation_name(canonical, locale_code=locale_code)
    if not localized:
        return canonical
    return f"{canonical} ({localized})"
