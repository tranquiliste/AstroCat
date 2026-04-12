from __future__ import annotations

from pathlib import Path
import json
import locale
import os
from typing import Dict, List, Tuple


SUPPORTED_UI_LOCALES = {
    "en": "English",
    "fr": "Français",
}


def normalize_locale_code(value: object, fallback: str = "en") -> str:
    if value is None:
        return fallback
    text = str(value).strip().replace("_", "-").lower()
    if not text:
        return fallback
    if text == "system":
        return detect_system_locale(fallback=fallback)
    language = text.split("-", 1)[0]
    if language in SUPPORTED_UI_LOCALES:
        return language
    if len(language) >= 2:
        short = language[:2]
        if short in SUPPORTED_UI_LOCALES:
            return short
    return fallback


def detect_system_locale(fallback: str = "en") -> str:
    candidates = []

    if os.name == "nt":
        try:
            import ctypes

            # Most reliable on Windows: explicit locale name like "fr-FR".
            buffer = ctypes.create_unicode_buffer(85)
            if ctypes.windll.kernel32.GetUserDefaultLocaleName(buffer, 85):
                candidates.append(buffer.value)

            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            windows_locale = locale.windows_locale.get(lang_id)
            if windows_locale:
                candidates.append(windows_locale)
        except Exception:
            pass

    lang, _encoding = locale.getlocale()
    if lang:
        candidates.append(lang)

    for env_name in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        env_value = os.environ.get(env_name)
        if env_value:
            candidates.append(env_value)

    for candidate in candidates:
        normalized = normalize_locale_code(candidate, fallback="")
        if normalized in SUPPORTED_UI_LOCALES:
            return normalized
    return fallback


class TranslationManager:
    def __init__(self, locales_dir: Path) -> None:
        self.locales_dir = locales_dir
        self.fallback_locale = "en"
        self.current_locale = self.fallback_locale
        self._fallback_messages = self._load_messages(self.fallback_locale)
        self._messages = dict(self._fallback_messages)

    def set_locale(self, locale_setting: object) -> str:
        locale_code = normalize_locale_code(locale_setting, fallback=self.fallback_locale)
        if locale_code not in SUPPORTED_UI_LOCALES:
            locale_code = self.fallback_locale
        self.current_locale = locale_code
        self._messages = dict(self._fallback_messages)
        if locale_code != self.fallback_locale:
            self._messages.update(self._load_messages(locale_code))
        return locale_code

    def translate(self, key: str, **kwargs: object) -> str:
        template = self._messages.get(key) or self._fallback_messages.get(key) or key
        if kwargs:
            try:
                return template.format(**kwargs)
            except Exception:
                return template
        return template

    def language_choices(self) -> List[Tuple[str, str]]:
        system_locale = detect_system_locale(fallback=self.fallback_locale)
        system_language = SUPPORTED_UI_LOCALES.get(system_locale, system_locale.upper())
        return [
            ("system", self.translate("settings.language.system", language=system_language)),
            ("en", SUPPORTED_UI_LOCALES["en"]),
            ("fr", SUPPORTED_UI_LOCALES["fr"]),
        ]

    def language_name(self, locale_code: object) -> str:
        normalized = normalize_locale_code(locale_code, fallback=self.fallback_locale)
        return SUPPORTED_UI_LOCALES.get(normalized, normalized.upper())

    def _load_messages(self, locale_code: str) -> Dict[str, str]:
        path = self.locales_dir / f"{locale_code}.json"
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        return {str(key): str(value) for key, value in payload.items()}


_MANAGER = TranslationManager(Path(__file__).resolve().parent / "locales")


def set_ui_locale(locale_setting: object) -> str:
    return _MANAGER.set_locale(locale_setting)


def current_ui_locale() -> str:
    return _MANAGER.current_locale


def tr(key: str, **kwargs: object) -> str:
    return _MANAGER.translate(key, **kwargs)


def language_choices() -> List[Tuple[str, str]]:
    return _MANAGER.language_choices()


def language_name(locale_code: object) -> str:
    return _MANAGER.language_name(locale_code)


def format_best_months(value: str) -> str:
    if not value:
        return ""
    month_map = {
        "Jan": tr("month.jan"),
        "Feb": tr("month.feb"),
        "Mar": tr("month.mar"),
        "Apr": tr("month.apr"),
        "May": tr("month.may"),
        "Jun": tr("month.jun"),
        "Jul": tr("month.jul"),
        "Aug": tr("month.aug"),
        "Sep": tr("month.sep"),
        "Oct": tr("month.oct"),
        "Nov": tr("month.nov"),
        "Dec": tr("month.dec"),
    }
    months = [value[index:index + 3] for index in range(0, len(value), 3)]
    return " ".join(month_map.get(month, month) for month in months if month)