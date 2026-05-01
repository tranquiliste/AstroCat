from __future__ import annotations

# ============================================================================
# INTÉGRATION DES NOUVEAUX CATALOGUES — À AJOUTER DANS catalog.py
# ============================================================================
# Dans catalog.py, dans le dictionnaire DEFAULT_CONFIG["catalogs"], ajouter
# les 6 entrées suivantes après les catalogues existants (Messier, NGC…) :
#
#     {
#         "name": "Sh2",
#         "catalog_file": "data/sh2_catalog.json",
#         "metadata_file": "data/sh2_catalog.json",
#         "image_dirs": [],
#         "enabled": True,
#     },
#     {
#         "name": "LDN",
#         "catalog_file": "data/ldn_catalog.json",
#         "metadata_file": "data/ldn_catalog.json",
#         "image_dirs": [],
#         "enabled": True,
#     },
#     {
#         "name": "Barnard",
#         "catalog_file": "data/barnard_catalog.json",
#         "metadata_file": "data/barnard_catalog.json",
#         "image_dirs": [],
#         "enabled": True,
#     },
#     {
#         "name": "VdB",
#         "catalog_file": "data/vdb_catalog.json",
#         "metadata_file": "data/vdb_catalog.json",
#         "image_dirs": [],
#         "enabled": True,
#     },
#     {
#         "name": "LBN",
#         "catalog_file": "data/lbn_catalog.json",
#         "metadata_file": "data/lbn_catalog.json",
#         "image_dirs": [],
#         "enabled": True,
#     },
#     {
#         "name": "PNG",
#         "catalog_file": "data/png_catalog.json",
#         "metadata_file": "data/png_catalog.json",
#         "image_dirs": [],
#         "enabled": True,
#     },
#
# Les fichiers JSON (sh2_catalog.json, ldn_catalog.json, barnard_catalog.json,
# vdb_catalog.json, lbn_catalog.json, png_catalog.json) doivent être placés
# dans le dossier  data/  à la racine du projet.
#
# Les fichiers *_catalog.json seront créés automatiquement au premier
# lancement si la fonction de création de métadonnées est implémentée,
# sinon les créer manuellement avec un JSON vide : {}
# ============================================================================

import sys
import hashlib
import re
import subprocess
import shutil
import io
import runpy
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple
import http.server
import json
import threading
from urllib.parse import urlparse, unquote
import datetime
import array
from dataclasses import replace

from PySide6 import QtCore, QtGui, QtWidgets
from shiboken6 import isValid

from database import Database, database_path_from_config_path
from catalog import DEFAULT_CONFIG, CatalogItem, collect_object_types, load_config, load_catalog_items, resolve_metadata_path, save_config, save_note, save_thumbnail, save_image_note
from constellations import format_constellation_display
from object_types import is_hidden_object_type, localized_object_type
from catalog import PROJECT_ROOT
from i18n import format_best_months, language_choices, set_ui_locale, tr
from image_cache import ThumbnailCache
from photo_notes_migration import migrate_photo_notes_to_sqlite

# Keep numpy import type-only to satisfy static analysis without adding startup cost.
if TYPE_CHECKING:
    import numpy as np


APP_NAME = "AstroCat"
ORG_NAME = "AstroCat"
UPDATE_REPO = "tranquiliste/AstroCat"
SUPPORTERS_URL = f"https://raw.githubusercontent.com/{UPDATE_REPO}/main/data/supporters.json"
APP_VERSION_FILE = "data/version.json"
DATA_VERSION_FILE = "data/data_version.json"
DATA_VERSION_URL = f"https://raw.githubusercontent.com/{UPDATE_REPO}/main/data/data_version.json"


def _extract_version(payload: object) -> Optional[str]:
    if isinstance(payload, dict):
        for key in ("version", "app_version", "tag"):
            value = payload.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None
    if isinstance(payload, str):
        text = payload.strip()
        return text or None
    return None


def _load_version_from_file(path: Path) -> Optional[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return _extract_version(payload)


def _load_bundled_app_version() -> str:
    return _load_version_from_file(PROJECT_ROOT / APP_VERSION_FILE) or "Unknown"


def _load_bundled_data_version() -> str:
    return _load_version_from_file(PROJECT_ROOT / DATA_VERSION_FILE) or "Unknown"


APP_VERSION = _load_bundled_app_version()
DEFAULT_DATA_VERSION = _load_bundled_data_version()
SHUTDOWN_EVENT = threading.Event()



def _build_focus_toggle_icon(direction: str, color: str = "#d9a441") -> QtGui.QIcon:
    pixmap = QtGui.QPixmap(20, 20)
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)

    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

    pen = QtGui.QPen(QtGui.QColor(color), 2.2,
                     QtCore.Qt.PenStyle.SolidLine,
                     QtCore.Qt.PenCapStyle.RoundCap,
                     QtCore.Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    cx, cy = 11, 11
    gap = 2  # espace vide autour du centre
    if direction == "expand":
       # ↗
        shaft_start = (12, 9)
        shaft_end   = (19,2)
        painter.drawLine(*shaft_start, *shaft_end)
        # pointe vers l'extérieur (haut‑droite)
        painter.drawLine(shaft_end[0], shaft_end[1],
                         shaft_end[0], shaft_end[1] + 4)
        painter.drawLine(shaft_end[0], shaft_end[1],
                         shaft_end[0] - 4, shaft_end[1])

        # ↙ : part du centre vers le coin bas‑gauche
        shaft_start = (9,12)
        shaft_end   = (2, 19)
        painter.drawLine(*shaft_start, *shaft_end)
        # pointe vers l'extérieur (bas‑gauche)
        painter.drawLine(shaft_end[0], shaft_end[1],
                         shaft_end[0], shaft_end[1] - 4)
        painter.drawLine(shaft_end[0], shaft_end[1],
                         shaft_end[0] + 4, shaft_end[1])
    else:
      # ↖
        shaft_start = (19,2)
        shaft_end   = (12, 9)
        painter.drawLine(*shaft_start, *shaft_end)
        # flèche
        painter.drawLine(shaft_end[0], shaft_end[1],
                         shaft_end[0], shaft_end[1] - 4)
        painter.drawLine(shaft_end[0], shaft_end[1],
                         shaft_end[0] + 4, shaft_end[1])
 
        shaft_start = (2, 19)
        shaft_end   = (9,12)
        painter.drawLine(*shaft_start, *shaft_end)
        painter.drawLine(shaft_end[0], shaft_end[1],
                         shaft_end[0], shaft_end[1] + 4)
        painter.drawLine(shaft_end[0], shaft_end[1],
                         shaft_end[0] - 4, shaft_end[1])
    painter.end()
    return QtGui.QIcon(pixmap)



class ThumbnailSignals(QtCore.QObject):
    loaded = QtCore.Signal(str, QtGui.QImage)


class CatalogLoadSignals(QtCore.QObject):
    loaded = QtCore.Signal(list)


class MapFetchSignals(QtCore.QObject):
    loaded = QtCore.Signal(bytes)
    failed = QtCore.Signal()


class RemoteThumbnailSignals(QtCore.QObject):
    loaded = QtCore.Signal(str, QtGui.QImage)
    failed = QtCore.Signal(str)


class ImageLoadSignals(QtCore.QObject):
    loaded = QtCore.Signal(int, str, QtGui.QImage)
    failed = QtCore.Signal(int, str, str)


class UpdateSignals(QtCore.QObject):
    available = QtCore.Signal(str, str)
    up_to_date = QtCore.Signal(str)
    failed = QtCore.Signal(str)
    finished = QtCore.Signal()


class SupportersSignals(QtCore.QObject):
    loaded = QtCore.Signal(list)
    failed = QtCore.Signal(str)


class DataVersionSignals(QtCore.QObject):
    loaded = QtCore.Signal(str)
    failed = QtCore.Signal(str)


class DuplicateScanSignals(QtCore.QObject):
    finished = QtCore.Signal(str, str)


class DuplicateScanTask(QtCore.QRunnable):
    def __init__(
        self,
        config_path: Path,
        extensions: List[str],
        report_path: Path,
    ) -> None:
        super().__init__()
        self.config_path = config_path
        self.extensions = extensions
        self.report_path = report_path
        self.signals = DuplicateScanSignals()

    def run(self) -> None:
        if SHUTDOWN_EVENT.is_set():
            return
        error = ""
        try:
            sort_command = [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "sort_master_images.py"),
                "--config",
                str(self.config_path),
                "--extensions",
                ",".join(self.extensions),
            ]
            scan_command = [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "find_duplicate_images_by_catalog.py"),
                "--config",
                str(self.config_path),
                "--extensions",
                ",".join(self.extensions),
                "--output",
                str(self.report_path),
            ]
            result = subprocess.run(sort_command, check=False, capture_output=True, text=True)
            if result.returncode != 0:
                error = result.stderr.strip() or result.stdout.strip()
            if not error:
                result = subprocess.run(scan_command, check=False, capture_output=True, text=True)
                if result.returncode != 0:
                    error = result.stderr.strip() or result.stdout.strip()
        except Exception as exc:
            error = str(exc)
        if SHUTDOWN_EVENT.is_set() or not isValid(self.signals):
            return
        try:
            self.signals.finished.emit(str(self.report_path), error)
        except RuntimeError:
            return


class ThumbnailTask(QtCore.QRunnable):
    def __init__(self, item_key: str, image_path: Path, cache: ThumbnailCache) -> None:
        super().__init__()
        self.item_key = item_key
        self.image_path = image_path
        self.cache = cache
        self.signals = ThumbnailSignals()

    def run(self) -> None:
        if SHUTDOWN_EVENT.is_set():
            return
        image = self.cache.create_thumbnail(self.image_path)
        if image is None:
            return
        if not isValid(self.signals):
            return
        try:
            self.signals.loaded.emit(self.item_key, image)
        except RuntimeError:
            return


class WikiThumbnailTask(QtCore.QRunnable):
    def __init__(
        self,
        item_key: str,
        page_title: str,
        cache_path: Path,
        thumb_size: int,
        image_url: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.item_key = item_key
        self.page_title = page_title
        self.cache_path = cache_path
        self.thumb_size = thumb_size
        self.image_url = image_url
        self.signals = RemoteThumbnailSignals()

    def run(self) -> None:
        import urllib.parse

        if SHUTDOWN_EVENT.is_set():
            return
        if self.cache_path.exists():
            image = QtGui.QImage(str(self.cache_path))
            if not image.isNull():
                self._emit_loaded(image)
                return
            try:
                self.cache_path.unlink()
            except OSError:
                pass
        try:
            if self.image_url:
                data = self._fetch_bytes(self.image_url)
            else:
                title = urllib.parse.quote(self.page_title.replace(" ", "_"))
                summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
                summary_payload = self._fetch_bytes(summary_url)
                if SHUTDOWN_EVENT.is_set():
                    return
                payload = json.loads(summary_payload.decode("utf-8"))
                thumb = payload.get("thumbnail", {}).get("source") or payload.get("originalimage", {}).get("source")
                if not thumb:
                    self._emit_failed()
                    return
                if CatalogModel._is_bad_wiki_thumbnail(thumb):
                    self._emit_failed()
                    return
                data = self._fetch_bytes(thumb)
            if SHUTDOWN_EVENT.is_set():
                return
            image = QtGui.QImage.fromData(data)
            if image.isNull():
                self._emit_failed()
                return
            image = image.convertToFormat(QtGui.QImage.Format.Format_ARGB32)
            if self.page_title.strip().lower() == "saturn":
                image = self._center_square_crop(image)
            image = self._scale_to_square(image)
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(str(self.cache_path), "PNG")
            self._emit_loaded(image)
        except Exception:
            self._emit_failed()

    def _emit_loaded(self, image: QtGui.QImage) -> None:
        if SHUTDOWN_EVENT.is_set():
            return
        if not isValid(self.signals):
            return
        try:
            self.signals.loaded.emit(self.item_key, image)
        except RuntimeError:
            return

    def _emit_failed(self) -> None:
        if SHUTDOWN_EVENT.is_set():
            return
        if not isValid(self.signals):
            return
        try:
            self.signals.failed.emit(self.item_key)
        except RuntimeError:
            return

    def _scale_to_square(self, image: QtGui.QImage) -> QtGui.QImage:
        scaled = image.scaled(
            self.thumb_size,
            self.thumb_size,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        canvas = QtGui.QImage(
            self.thumb_size,
            self.thumb_size,
            QtGui.QImage.Format.Format_ARGB32,
        )
        canvas.fill(QtGui.QColor("#1c1c1c"))
        painter = QtGui.QPainter(canvas)
        x = (self.thumb_size - scaled.width()) // 2
        y = (self.thumb_size - scaled.height()) // 2
        painter.drawImage(x, y, scaled)
        painter.end()
        return canvas

    @staticmethod
    def _center_square_crop(image: QtGui.QImage) -> QtGui.QImage:
        width = image.width()
        height = image.height()
        side = min(width, height)
        x = (width - side) // 2
        y = (height - side) // 2
        return image.copy(x, y, side, side)

    @staticmethod
    def _fetch_bytes(url: str) -> bytes:
        if SHUTDOWN_EVENT.is_set():
            return b""
        creationflags = 0
        if sys.platform.startswith("win"):
            creationflags = subprocess.CREATE_NO_WINDOW
        result = subprocess.run(
            [
                "curl",
                "-sL",
                "--max-time",
                "8",
                "--retry",
                "3",
                "--retry-delay",
                "1",
                "-H",
                "User-Agent: AstroCat/1.0",
                url,
            ],
            check=True,
            capture_output=True,
            creationflags=creationflags,
        )
        return result.stdout


class ImageLoadTask(QtCore.QRunnable):
    def __init__(self, request_id: int, image_path: Path) -> None:
        super().__init__()
        self.request_id = request_id
        self.image_path = image_path
        self.signals = ImageLoadSignals()

    def run(self) -> None:
        if SHUTDOWN_EVENT.is_set():
            return
        image, error = _load_display_image(self.image_path)
        if image is None or image.isNull():
            if not isValid(self.signals):
                return
            try:
                self.signals.failed.emit(self.request_id, str(self.image_path), error or "Unable to load image.")
            except RuntimeError:
                return
            return
        if not isValid(self.signals):
            return
        try:
            self.signals.loaded.emit(self.request_id, str(self.image_path), image)
        except RuntimeError:
            return


class CatalogLoadTask(QtCore.QRunnable):
    def __init__(self, config: Dict, user_notes_path: Optional[Path] = None) -> None:
        super().__init__()
        self.config = config
        self.user_notes_path = user_notes_path
        self.signals = CatalogLoadSignals()

    def run(self) -> None:
        items = load_catalog_items(self.config, self.user_notes_path)
        self.signals.loaded.emit(items)


class MapTileFetchTask(QtCore.QRunnable):
    def __init__(
        self,
        latitude: float,
        longitude: float,
        zoom: int,
        size: QtCore.QSize,
        tile_servers: List[str],
    ) -> None:
        super().__init__()
        self.latitude = latitude
        self.longitude = longitude
        self.zoom = zoom
        self.size = size
        self.tile_servers = tile_servers
        self.signals = MapFetchSignals()

    def run(self) -> None:
        import math
        import urllib.request

        tile_size = 256
        width = self.size.width()
        height = self.size.height()

        lat = max(-85.0511, min(85.0511, self.latitude))
        world = tile_size * (2**self.zoom)
        x = (self.longitude + 180.0) / 360.0 * world
        rad = math.radians(lat)
        y = (1.0 - math.log(math.tan(rad) + 1.0 / math.cos(rad)) / math.pi) / 2.0 * world

        x0 = x - width / 2
        y0 = y - height / 2
        x_start = int(math.floor(x0 / tile_size))
        x_end = int(math.floor((x0 + width - 1) / tile_size))
        y_start = int(math.floor(y0 / tile_size))
        y_end = int(math.floor((y0 + height - 1) / tile_size))

        image = QtGui.QImage(width, height, QtGui.QImage.Format.Format_ARGB32)
        image.fill(QtGui.QColor("#141414"))
        painter = QtGui.QPainter(image)

        tiles_fetched = 0
        max_tile = 2**self.zoom
        for ty in range(y_start, y_end + 1):
            if ty < 0 or ty >= max_tile:
                continue
            for tx in range(x_start, x_end + 1):
                tx_wrapped = tx % max_tile
                tile_data = None
                for base in self.tile_servers:
                    url = base.format(z=self.zoom, x=tx_wrapped, y=ty)
                    try:
                        request = urllib.request.Request(
                            url,
                            headers={"User-Agent": "AstroCat/1.0"},
                        )
                        with urllib.request.urlopen(request, timeout=6) as response:
                            tile_data = response.read()
                        if tile_data:
                            break
                    except Exception:
                        continue
                if not tile_data:
                    continue
                tile_img = QtGui.QImage.fromData(tile_data)
                if tile_img.isNull():
                    continue
                target_x = int(tx * tile_size - x0)
                target_y = int(ty * tile_size - y0)
                painter.drawImage(target_x, target_y, tile_img)
                tiles_fetched += 1

        painter.end()

        if tiles_fetched == 0:
            self.signals.failed.emit()
            return

        buffer = QtCore.QBuffer()
        buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        data = bytes(buffer.data())
        self.signals.loaded.emit(data)


class CatalogModel(QtCore.QAbstractListModel):
    wiki_thumbnail_loaded = QtCore.Signal(str, QtGui.QPixmap)
    _wiki_thumbnail_blocklist = {
        "Caldwell": {"C64"},
        "NGC": {"NGC146", "NGC771", "NGC1502"},
        # PNG : entrées dupliquées ou sans page Wikipedia dédiée
        "PNG": {
            "PNG64.7-73.5",   # doublon NGC 246
            "PNG118.8-74.7",  # doublon NGC 246
            "PNG234.9+2.4",   # doublon NGC 2438
            "PNG292.5+4.4",   # doublon NGC 3918
            "PNG342.5+27.5",  # doublon NGC 6026
            "PNG348.0+31.4",  # extension NGC 6210, pas de page propre
            "PNG85.4-0.1",    # Sh2-120, page HII pas PN
            "PNG97.0-2.0",    # Sh2-124, page HII pas PN
            "PNG114.0-4.6",   # NGC 7538, page HII pas PN
            "PNG107.6+2.3",   # IC 1396, page EN pas PN
        },
        # LDN : nébuleuses sombres sans image Wikipedia utilisable
        "LDN": {
            "LDN1",
            "LDN43",
            "LDN694",
            "LDN1333",
        },
        # Barnard : objets sans image Wikipedia distincte
        "Barnard": {
            "B144", "B145", "B163", "B169", "B170",
            "B171", "B174", "B175", "B312",
        },
    }
    _wiki_thumbnail_refresh = {
        "Solar system": {"CHARIKLO", "SWIFT-TUTTLE"},
    }

    def __init__(self, items: List[CatalogItem], cache: ThumbnailCache, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self._items = items
        self._cache = cache
        self._loading = set()
        self._pixmaps: Dict[str, QtGui.QPixmap] = {}
        self._remote_pixmaps: Dict[str, QtGui.QPixmap] = {}
        self._remote_loading = set()
        self._remote_failed = set()
        self._wiki_refresh_done = set()
        self._wiki_enabled = False
        self._row_lookup = {item.unique_key: row for row, item in enumerate(items)}
        self._thread_pool = QtCore.QThreadPool.globalInstance()
        self._wiki_pool = QtCore.QThreadPool(self)
        self._wiki_pool.setMaxThreadCount(4)
        self._placeholder = self._create_placeholder()

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._items)

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        item = self._items[index.row()]
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            return item.display_name
        if role == QtCore.Qt.ItemDataRole.ToolTipRole:
            raw_object_type = (item.object_type or "").strip()
            object_type_display = localized_object_type(raw_object_type)
            if object_type_display is None and raw_object_type and not is_hidden_object_type(raw_object_type):
                object_type_display = raw_object_type
            if object_type_display:
                return f"{item.catalog} | {object_type_display}"
            return item.catalog
        if role == QtCore.Qt.ItemDataRole.DecorationRole:
            if item.thumbnail_path is None:
                remote = self._remote_pixmaps.get(item.unique_key)
                if remote:
                    return remote
                if self._wiki_enabled:
                    self._queue_wiki_thumbnail(item)
                return self._placeholder
            cached = self._cache.get_thumbnail(item.thumbnail_path)
            if cached:
                return cached
            pixmap = self._pixmaps.get(item.unique_key)
            if pixmap:
                return pixmap
            self._queue_thumbnail(item)
            return self._placeholder
        if role == QtCore.Qt.ItemDataRole.UserRole:
            return item
        return None

    def _queue_thumbnail(self, item: CatalogItem) -> None:
        if item.thumbnail_path is None:
            return
        if item.unique_key in self._loading:
            return
        self._loading.add(item.unique_key)
        task = ThumbnailTask(item.unique_key, item.thumbnail_path, self._cache)
        task.signals.loaded.connect(self._on_thumbnail_loaded)
        self._thread_pool.start(task)

    def _queue_wiki_thumbnail(self, item: CatalogItem) -> None:
        if item.unique_key in self._remote_loading or item.unique_key in self._remote_failed:
            return
        if self._should_skip_wiki_thumbnail(item):
            self._remote_failed.add(item.unique_key)
            return
        title = self._wiki_title_for_item(item)
        image_url = item.wiki_thumbnail
        if image_url and self._is_bad_wiki_thumbnail(image_url):
            image_url = None
        if not title and not image_url:
            self._remote_failed.add(item.unique_key)
            return
        cache_key = title or item.object_id.replace(" ", "_")
        cache_path = self._wiki_cache_path(cache_key)
        self._maybe_refresh_wiki_thumbnail(item, cache_path)
        if cache_path.exists():
            image = QtGui.QImage(str(cache_path))
            if not image.isNull():
                pixmap = QtGui.QPixmap.fromImage(image)
                self._remote_pixmaps[item.unique_key] = pixmap
                row = self._row_lookup.get(item.unique_key)
                if row is not None:
                    index = self.index(row)
                    self.dataChanged.emit(index, index, [QtCore.Qt.ItemDataRole.DecorationRole])
                return
            try:
                cache_path.unlink()
            except OSError:
                pass
        self._remote_loading.add(item.unique_key)
        task = WikiThumbnailTask(item.unique_key, cache_key, cache_path, self._cache.thumb_size, image_url=image_url)
        task.signals.loaded.connect(self._on_wiki_thumbnail_loaded)
        task.signals.failed.connect(self._on_wiki_thumbnail_failed)
        self._wiki_pool.start(task)

    @staticmethod
    def _is_bad_wiki_thumbnail(url: str) -> bool:
        if not url:
            return False
        parsed = urlparse(url)
        name = Path(parsed.path).name.lower()
        bad_tokens = ("map", "chart", "finder", "locator", "diagram", "orbit", "orbital", "trajectory")
        return any(token in name for token in bad_tokens)

    def _should_skip_wiki_thumbnail(self, item: CatalogItem) -> bool:
        blocklist = self._wiki_thumbnail_blocklist.get(item.catalog)
        if not blocklist:
            return False
        normalized = item.object_id.replace(" ", "").upper()
        return normalized in blocklist

    def _maybe_refresh_wiki_thumbnail(self, item: CatalogItem, cache_path: Path) -> None:
        refresh_list = self._wiki_thumbnail_refresh.get(item.catalog)
        if not refresh_list:
            return
        normalized = item.object_id.replace(" ", "").upper()
        if normalized not in refresh_list:
            return
        if item.unique_key in self._wiki_refresh_done:
            return
        self._wiki_refresh_done.add(item.unique_key)
        if cache_path.exists():
            try:
                cache_path.unlink()
            except OSError:
                pass

    def _on_wiki_thumbnail_loaded(self, item_key: str, image: QtGui.QImage) -> None:
        pixmap = QtGui.QPixmap.fromImage(image)
        if pixmap.isNull():
            self._remote_failed.add(item_key)
            self._remote_loading.discard(item_key)
            return
        self._remote_pixmaps[item_key] = pixmap
        self.wiki_thumbnail_loaded.emit(item_key, pixmap)
        self._remote_loading.discard(item_key)
        row = self._row_lookup.get(item_key)
        if row is None:
            return
        index = self.index(row)
        self.dataChanged.emit(index, index, [QtCore.Qt.ItemDataRole.DecorationRole])

    def _on_wiki_thumbnail_failed(self, item_key: str) -> None:
        self._remote_loading.discard(item_key)
        self._remote_failed.add(item_key)

    def _wiki_title_for_item(self, item: CatalogItem) -> Optional[str]:
        link = item.external_link or ""
        if "wikipedia.org" not in link:
            return None
        parsed = urlparse(link)
        if not parsed.path.startswith("/wiki/"):
            return None
        title = parsed.path[len("/wiki/"):]
        if not title:
            return None
        return unquote(title)

    def _wiki_cache_path(self, title: str) -> Path:
        payload = f"{title}:{self._cache.thumb_size}"
        key = hashlib.sha1(payload.encode("utf-8")).hexdigest()
        return self._cache.cache_dir / f"wiki_{key}.png"

    def _on_thumbnail_loaded(self, item_key: str, image: QtGui.QImage) -> None:
        row = self._row_lookup.get(item_key)
        if row is None:
            return
        item = self._items[row]
        if item.thumbnail_path is None:
            return
        pixmap = self._cache.store_thumbnail_image(item.thumbnail_path, image)
        self._pixmaps[item_key] = pixmap
        self._loading.discard(item_key)
        index = self.index(row)
        self.dataChanged.emit(index, index, [QtCore.Qt.ItemDataRole.DecorationRole])

    def set_items(self, items: List[CatalogItem]) -> None:
        self.beginResetModel()
        self._items = items
        self._pixmaps.clear()
        self._remote_pixmaps.clear()
        self._remote_loading.clear()
        self._remote_failed.clear()
        self._loading.clear()
        self._wiki_refresh_done.clear()
        self._row_lookup = {item.unique_key: row for row, item in enumerate(items)}
        self.endResetModel()

    def update_cache(self, cache: ThumbnailCache) -> None:
        self._cache = cache
        self._pixmaps.clear()
        self._remote_pixmaps.clear()
        self._remote_loading.clear()
        self._remote_failed.clear()

    def set_wiki_thumbnails_enabled(self, enabled: bool) -> None:
        self._wiki_enabled = enabled
        if not enabled:
            self._remote_pixmaps.clear()
            self._remote_loading.clear()
            self._remote_failed.clear()
        self._loading.clear()
        if self._items:
            self.dataChanged.emit(self.index(0), self.index(len(self._items) - 1))

    def index_for_key(self, item_key: str) -> Optional[QtCore.QModelIndex]:
        row = self._row_lookup.get(item_key)
        if row is None:
            return None
        return self.index(row)

    def get_wiki_pixmap(self, item_key: str) -> Optional[QtGui.QPixmap]:
        return self._remote_pixmaps.get(item_key)

    def update_item_notes(self, item_key: str, notes: str) -> None:
        row = self._row_lookup.get(item_key)
        if row is None:
            return
        item = self._items[row]
        updated = replace(item, notes=notes)
        self._items[row] = updated
        index = self.index(row)
        self.dataChanged.emit(index, index, [QtCore.Qt.ItemDataRole.DisplayRole])

    def update_item_image_note(self, item_key: str, image_name: str, notes: str) -> None:
        # A single image file can be associated with multiple catalog objects.
        # Keep all corresponding in-memory entries in sync after saving a note.
        changed_rows: List[int] = []
        for row, item in enumerate(self._items):
            if not any(path.name == image_name for path in item.image_paths):
                continue
            image_notes = dict(item.image_notes)
            if notes.strip():
                image_notes[image_name] = notes
            else:
                image_notes.pop(image_name, None)
            self._items[row] = replace(item, image_notes=image_notes)
            changed_rows.append(row)

        # Fallback: if no image path match was found, keep legacy behavior.
        if not changed_rows:
            row = self._row_lookup.get(item_key)
            if row is None:
                return
            item = self._items[row]
            image_notes = dict(item.image_notes)
            if notes.strip():
                image_notes[image_name] = notes
            else:
                image_notes.pop(image_name, None)
            self._items[row] = replace(item, image_notes=image_notes)
            changed_rows.append(row)

        for row in changed_rows:
            index = self.index(row)
            self.dataChanged.emit(index, index, [QtCore.Qt.ItemDataRole.DisplayRole])

    def update_item_thumbnail(self, item_key: str, thumbnail_name: str) -> None:
        row = self._row_lookup.get(item_key)
        if row is None:
            return
        item = self._items[row]
        thumbnail_path = next(
            (path for path in item.image_paths if path.name == thumbnail_name or path.stem == thumbnail_name),
            item.thumbnail_path,
        )
        updated = replace(item, thumbnail_path=thumbnail_path)
        self._items[row] = updated
        self._pixmaps.pop(item_key, None)
        index = self.index(row)
        self.dataChanged.emit(index, index, [QtCore.Qt.ItemDataRole.DecorationRole])

    def _create_placeholder(self) -> QtGui.QPixmap:
        size = self._cache.thumb_size
        pixmap = QtGui.QPixmap(size, size)
        pixmap.fill(QtGui.QColor("#1c1c1c"))
        painter = QtGui.QPainter(pixmap)
        painter.setPen(QtGui.QColor("#2d2d2d"))
        painter.drawRect(0, 0, size - 1, size - 1)
        painter.end()
        return pixmap


class CatalogItemDelegate(QtWidgets.QStyledItemDelegate):
    def paint(self, painter: QtGui.QPainter, option: QtWidgets.QStyleOptionViewItem, index: QtCore.QModelIndex) -> None:
        painter.save()
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        rect = option.rect.adjusted(4, 4, -4, -4)
        icon = index.data(QtCore.Qt.ItemDataRole.DecorationRole)
        text = index.data(QtCore.Qt.ItemDataRole.DisplayRole) or ""
        metrics = option.fontMetrics
        text_height = metrics.height() + 12
        card_rect = rect
        image_rect = QtCore.QRect(
            card_rect.left() + 1,
            card_rect.top() + 1,
            card_rect.width() - 2,
            card_rect.height() - text_height - 12,
        )
        text_rect = QtCore.QRect(card_rect.left() + 8, card_rect.bottom() - text_height - 8, card_rect.width() - 16, text_height)

        base_color = QtGui.QColor("#121a2b")
        border_color = QtGui.QColor("#24304a")
        accent_color = QtGui.QColor("#d4a85f")
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(base_color)
        painter.drawRoundedRect(QtCore.QRectF(card_rect), 12, 12)

        if isinstance(icon, QtGui.QPixmap) and not icon.isNull():
            image = icon.toImage()
            painter.drawImage(image_rect, image, image.rect())
        else:
            painter.fillRect(image_rect, QtGui.QColor("#182235"))
            pen = QtGui.QPen(border_color)
            painter.setPen(pen)
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QtCore.QRectF(image_rect.adjusted(0, 0, -1, -1)), 11, 11)
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.setPen(QtGui.QPen(border_color, 1))
        painter.drawRoundedRect(QtCore.QRectF(card_rect.adjusted(0, 0, -1, -1)), 12, 12)
        if option.state & QtWidgets.QStyle.StateFlag.State_Selected:
            painter.setPen(QtGui.QPen(accent_color, 2))
            painter.drawRoundedRect(QtCore.QRectF(card_rect.adjusted(1, 1, -1, -1)), 12, 12)
        elif option.state & QtWidgets.QStyle.StateFlag.State_MouseOver:
            painter.setPen(QtGui.QPen(QtGui.QColor("#4a628f"), 1))
            painter.drawRoundedRect(QtCore.QRectF(card_rect.adjusted(1, 1, -1, -1)), 12, 12)

        badge_size = 18
        margin = 4
        item: CatalogItem = index.data(QtCore.Qt.ItemDataRole.UserRole)
        if item:
            if len(item.image_paths) > 0:
                count_rect = QtCore.QRect(
                    image_rect.left() + margin,
                    image_rect.top() + margin,
                    badge_size + 10,
                    badge_size + 2,
                )
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.setBrush(QtGui.QColor(7, 14, 25, 190))
                painter.drawRoundedRect(QtCore.QRectF(count_rect), 9, 9)
                painter.setPen(QtGui.QColor("#edf1f7"))
                painter.drawText(
                    count_rect,
                    QtCore.Qt.AlignmentFlag.AlignCenter,
                    str(len(item.image_paths)),
                )
            if item.notes or any(note for note in item.image_notes.values()):
                info_rect = QtCore.QRect(
                    image_rect.right() - badge_size - margin,
                    image_rect.top() + margin,
                    badge_size,
                    badge_size,
                )
                painter.setBrush(QtGui.QColor(7, 14, 25, 190))
                painter.setPen(QtGui.QColor("#edf1f7"))
                painter.drawEllipse(info_rect)
                painter.drawText(
                    info_rect,
                    QtCore.Qt.AlignmentFlag.AlignCenter,
                    "i",
                )

        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QColor(8, 12, 20, 198))
        painter.drawRoundedRect(QtCore.QRectF(text_rect), 10, 10)
        painter.setPen(QtGui.QColor("#edf1f7"))
        elided = metrics.elidedText(text, QtCore.Qt.TextElideMode.ElideRight, text_rect.width() - 12)
        painter.drawText(text_rect.adjusted(6, 0, -6, 0), QtCore.Qt.AlignmentFlag.AlignCenter, elided)

        painter.restore()

    def sizeHint(self, option: QtWidgets.QStyleOptionViewItem, index: QtCore.QModelIndex) -> QtCore.QSize:
        size = index.data(QtCore.Qt.ItemDataRole.SizeHintRole)
        if isinstance(size, QtCore.QSize):
            return size
        return super().sizeHint(option, index)


class CatalogFilterProxy(QtCore.QSortFilterProxyModel):
    def __init__(self, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self.search_text = ""
        self.type_filter = ""
        self.catalog_filter = ""
        self.status_filter = ""
        self.setFilterCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)

    def set_search_text(self, text: str) -> None:
        self.search_text = text.strip()
        self.invalidate()

    def set_type_filter(self, value: str) -> None:
        self.type_filter = value
        self.invalidate()

    def set_catalog_filter(self, value: str) -> None:
        self.catalog_filter = value
        self.invalidate()

    def set_status_filter(self, value: str) -> None:
        self.status_filter = value
        self.invalidate()

    @staticmethod
    def _normalize_object_search(value: str) -> str:
        return "".join(value.casefold().split())

    @staticmethod
    def _normalize_name_search(value: str) -> str:
        return value.casefold()

    def filterAcceptsRow(self, source_row: int, source_parent: QtCore.QModelIndex) -> bool:
        model = self.sourceModel()
        index = model.index(source_row, 0, source_parent)
        item: CatalogItem = model.data(index, QtCore.Qt.ItemDataRole.UserRole)
        if item is None:
            return False
        if self.catalog_filter and not self.search_text:
            if item.catalog != self.catalog_filter:
                return False
        if self.type_filter and item.object_type != self.type_filter:
            return False
        if self.status_filter:
            if self.status_filter == "Captured" and not item.image_paths:
                return False
            if self.status_filter == "Missing" and item.image_paths:
                return False
            if self.status_filter == "Suggested" and not self._is_suggested(item):
                return False
        if self.search_text:
            search = self._normalize_name_search(self.search_text)
            normalized_search = self._normalize_object_search(self.search_text)
            object_id = self._normalize_object_search(item.object_id)
            name = self._normalize_name_search(item.name)
            compact_name = self._normalize_object_search(item.name)
            if (
                normalized_search not in object_id
                and search not in name
                and normalized_search not in compact_name
            ):
                return False
        return True

    def _is_suggested(self, item: CatalogItem) -> bool:
        if item.image_paths:
            return False
        if not item.best_months:
            return False
        month = datetime.datetime.now().strftime("%b")
        for idx in range(0, len(item.best_months), 3):
            if item.best_months[idx: idx + 3] == month:
                return True
        return False


class ImageView(QtWidgets.QGraphicsView):
    fullscreen_requested = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform)
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.ScrollHandDrag)
        self.setViewportUpdateMode(QtWidgets.QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setScene(QtWidgets.QGraphicsScene(self))
        self._pixmap_item: Optional[QtWidgets.QGraphicsPixmapItem] = None
        self._zoom = 0
        self._pixmap: Optional[QtGui.QPixmap] = None

    def set_pixmap(self, pixmap: Optional[QtGui.QPixmap]) -> None:
        self.scene().clear()
        self._zoom = 0
        self._pixmap = pixmap if pixmap and not pixmap.isNull() else None
        if self._pixmap:
            self._pixmap_item = self.scene().addPixmap(self._pixmap)
            self.setSceneRect(pixmap.rect())
            self.fit_to_window()
        else:
            self._pixmap_item = None

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._pixmap_item and self._pixmap and self._zoom == 0:
            self.fit_to_window()

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        if self._pixmap_item is None:
            return
        angle = event.angleDelta().y()
        if angle > 0:
            factor = 1.15
            self._zoom += 1
        else:
            factor = 0.87
            self._zoom -= 1
        if self._zoom < -5:
            self._zoom = -5
            return
        if self._zoom > 120:
            self._zoom = 120
            return
        self.scale(factor, factor)

    def fit_to_window(self) -> None:
        if self._pixmap_item is None:
            return
        self.resetTransform()
        self.fitInView(self.sceneRect(), QtCore.Qt.AspectRatioMode.KeepAspectRatio)

    def zoom_actual(self) -> None:
        if self._pixmap_item is None:
            return
        self.resetTransform()
        self.centerOn(self._pixmap_item)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._pixmap_item is None:
            return
        self.fullscreen_requested.emit()
        event.accept()


def _tone_map_high_bit_image(image: QtGui.QImage) -> QtGui.QImage:
    fmt = image.format()
    if fmt == QtGui.QImage.Format.Format_Grayscale16:
        return _tone_map_grayscale16(image)
    if fmt in (
        QtGui.QImage.Format.Format_RGBX64,
        QtGui.QImage.Format.Format_RGBA64,
        QtGui.QImage.Format.Format_RGBA64_Premultiplied,
    ):
        return _tone_map_rgba64(image)
    if image.depth() > 32:
        converted = image.convertToFormat(QtGui.QImage.Format.Format_RGBA64)
        return _tone_map_rgba64(converted)
    return image


def _tone_map_grayscale16(image: QtGui.QImage) -> QtGui.QImage:
    width = image.width()
    height = image.height()
    buf = image.bits()
    if hasattr(buf, "setsize"):
        buf.setsize(image.sizeInBytes())
    data = array.array("H")
    data.frombytes(buf.tobytes())
    if not data:
        return image.convertToFormat(QtGui.QImage.Format.Format_Grayscale8)
    step = max(1, len(data) // 100000)
    sample = data[::step]
    min_val = min(sample)
    max_val = max(sample)
    if max_val == min_val:
        max_val = min_val + 1
    scale = 255.0 / (max_val - min_val)
    out = bytearray(len(data))
    for i, value in enumerate(data):
        mapped = int((value - min_val) * scale)
        if mapped < 0:
            mapped = 0
        elif mapped > 255:
            mapped = 255
        out[i] = mapped
    out_image = QtGui.QImage(out, width, height, width, QtGui.QImage.Format.Format_Grayscale8)
    return out_image.copy()


def _tone_map_rgba64(image: QtGui.QImage) -> QtGui.QImage:
    width = image.width()
    height = image.height()
    buf = image.bits()
    if hasattr(buf, "setsize"):
        buf.setsize(image.sizeInBytes())
    data = array.array("H")
    data.frombytes(buf.tobytes())
    if not data:
        return image.convertToFormat(QtGui.QImage.Format.Format_RGB888)
    step = max(1, (len(data) // 4) // 100000)
    if step < 1:
        step = 1
    min_val = 65535
    max_val = 0
    for i in range(0, len(data), 4 * step):
        r = data[i]
        g = data[i + 1]
        b = data[i + 2]
        if r < min_val:
            min_val = r
        if g < min_val:
            min_val = g
        if b < min_val:
            min_val = b
        if r > max_val:
            max_val = r
        if g > max_val:
            max_val = g
        if b > max_val:
            max_val = b
    if max_val == min_val:
        max_val = min_val + 1
    scale = 255.0 / (max_val - min_val)
    out = bytearray(width * height * 3)
    out_i = 0
    for i in range(0, len(data), 4):
        r = int((data[i] - min_val) * scale)
        g = int((data[i + 1] - min_val) * scale)
        b = int((data[i + 2] - min_val) * scale)
        if r < 0:
            r = 0
        elif r > 255:
            r = 255
        if g < 0:
            g = 0
        elif g > 255:
            g = 255
        if b < 0:
            b = 0
        elif b > 255:
            b = 255
        out[out_i] = r
        out[out_i + 1] = g
        out[out_i + 2] = b
        out_i += 3
    out_image = QtGui.QImage(out, width, height, width * 3, QtGui.QImage.Format.Format_RGB888)
    return out_image.copy()


def _load_tiff_with_tifffile(path: Path) -> Tuple[Optional[QtGui.QImage], Optional[str]]:
    try:
        import numpy as np
        import tifffile
    except Exception:
        return None, "TIFF support not available (missing tifffile)."

    try:
        with tifffile.TiffFile(str(path)) as tif:
            series = tif.series[0] if tif.series else None
            if series is not None:
                data = series.asarray()
                axes = getattr(series, "axes", None)
            elif tif.pages:
                page = tif.pages[0]
                data = page.asarray()
                axes = getattr(page, "axes", None)
            else:
                data = None
                axes = None
    except Exception:
        return None, "Unable to decode TIFF. Install imagecodecs for compressed TIFFs."

    if data is None:
        return None, "Unable to decode TIFF."
    data = np.asarray(data)
    if data.dtype.kind == "c":
        data = np.abs(data)
    data = _normalize_tiff_array(data, axes)
    if data is None:
        return None, "Unsupported TIFF layout."
    if data.ndim == 2:
        return _tone_map_numpy_to_qimage(data, "L"), None
    if data.ndim == 3 and data.shape[2] in (3, 4):
        mode = "RGB" if data.shape[2] == 3 else "RGBA"
        return _tone_map_numpy_to_qimage(data, mode), None
    return None, "Unsupported TIFF layout."


def _normalize_tiff_array(data, axes: Optional[str] = None) -> Optional["np.ndarray"]:
    import numpy as np

    if data is None:
        return None
    array_data = np.asarray(data)
    if array_data.size == 0:
        return None
    if axes and len(axes) == array_data.ndim:
        axes = axes.upper()
        sample_axes = [idx for idx, axis in enumerate(axes) if axis in ("S", "C")]
        if sample_axes:
            channel_axis = sample_axes[0]
            array_data = np.moveaxis(array_data, channel_axis, -1)
            axes = axes.replace(axes[channel_axis], "")
        # Drop non-image axes (e.g., Z/T) by taking the first frame.
        while array_data.ndim > 3:
            array_data = array_data[0]
        if array_data.ndim == 3 and array_data.shape[2] > 4:
            array_data = array_data[:, :, :3]
        if array_data.ndim == 2:
            return array_data
        if array_data.ndim == 3 and array_data.shape[2] in (1, 2):
            return array_data[:, :, 0]
        return array_data

    array_data = np.squeeze(array_data)
    if array_data.ndim == 2:
        return array_data

    channel_axis = _detect_channel_axis(array_data)
    if channel_axis is not None:
        array_data = np.moveaxis(array_data, channel_axis, -1)
        while array_data.ndim > 3:
            array_data = array_data[0]
        if array_data.ndim == 3:
            channels = array_data.shape[2]
            if channels == 1:
                return array_data[:, :, 0]
            if channels == 2:
                return array_data[:, :, 0]
            if channels > 4:
                array_data = array_data[:, :, :3]
        return array_data

    while array_data.ndim > 2:
        array_data = array_data[0]
    return array_data


def _detect_channel_axis(array_data) -> Optional[int]:
    if array_data.ndim < 3:
        return None
    shape = array_data.shape
    candidates = []
    for axis, size in enumerate(shape):
        if size in (3, 4):
            candidates.append(axis)
    if not candidates:
        for axis, size in enumerate(shape):
            if size in (1, 2):
                candidates.append(axis)
    if not candidates and array_data.ndim == 3:
        for axis, size in enumerate(shape):
            if size <= 8:
                other_dims = [shape[i] for i in range(array_data.ndim) if i != axis]
                if all(dim > 16 for dim in other_dims):
                    candidates.append(axis)
    if not candidates:
        return None
    if candidates[-1] == array_data.ndim - 1:
        return candidates[-1]
    if candidates[0] == 0:
        return candidates[0]
    return candidates[0]


def _tone_map_numpy_to_qimage(data, mode: str) -> Optional[QtGui.QImage]:
    import numpy as np

    if data.size == 0:
        return None
    array_data = np.asarray(data)
    array_data = np.nan_to_num(array_data, nan=0.0, posinf=0.0, neginf=0.0)
    if array_data.dtype.kind in ("f", "i", "u"):
        low = np.percentile(array_data, 1.0)
        high = np.percentile(array_data, 99.0)
        if high <= low:
            high = low + 1.0
        scaled = (array_data - low) * (255.0 / (high - low))
        scaled = np.clip(scaled, 0, 255).astype(np.uint8)
    else:
        scaled = array_data.astype(np.uint8)

    if mode == "L":
        height, width = scaled.shape
        stride = width
        image = QtGui.QImage(scaled.tobytes(), width, height, stride, QtGui.QImage.Format.Format_Grayscale8)
        return image.copy()
    if mode == "RGB":
        height, width, _ = scaled.shape
        stride = width * 3
        image = QtGui.QImage(scaled.tobytes(), width, height, stride, QtGui.QImage.Format.Format_RGB888)
        return image.copy()
    if mode == "RGBA":
        height, width, _ = scaled.shape
        stride = width * 4
        image = QtGui.QImage(scaled.tobytes(), width, height, stride, QtGui.QImage.Format.Format_RGBA8888)
        return image.copy()
    return None


def _load_display_image(path: Path) -> Tuple[Optional[QtGui.QImage], Optional[str]]:
    reader = QtGui.QImageReader(str(path))
    if reader.canRead():
        reader.setAutoTransform(True)
        image = reader.read()
        if not image.isNull():
            if image.depth() > 32 or image.format() in (
                QtGui.QImage.Format.Format_Grayscale16,
                QtGui.QImage.Format.Format_RGBX64,
                QtGui.QImage.Format.Format_RGBA64,
                QtGui.QImage.Format.Format_RGBA64_Premultiplied,
            ):
                image = _tone_map_high_bit_image(image)
            return image, None
    error = reader.errorString() if reader.error() != QtGui.QImageReader.ImageReaderError.UnknownError else None
    tif_image, tif_error = _load_tiff_with_tifffile(path)
    if tif_image is not None:
        return tif_image, None
    if tif_error:
        error = tif_error
    pil_image, pil_error = _load_tiff_with_pillow(path)
    if pil_image is not None:
        return pil_image, None
    if pil_error:
        error = pil_error
    fallback = QtGui.QImage(str(path))
    if not fallback.isNull():
        return fallback, None
    return None, error or "Unable to load image."


def _load_tiff_with_pillow(path: Path) -> Tuple[Optional[QtGui.QImage], Optional[str]]:
    try:
        import warnings
        from PIL import Image
    except Exception:
        return None, None
    try:
        Image.MAX_IMAGE_PIXELS = None
        warnings.simplefilter("ignore", Image.DecompressionBombWarning)
        with Image.open(str(path)) as img:
            img = img.convert("RGB")
            width, height = img.size
            data = img.tobytes()
            image = QtGui.QImage(data, width, height, width * 3, QtGui.QImage.Format.Format_RGB888)
            return image.copy(), None
    except Exception:
        return None, "Pillow could not decode this TIFF."


class LightboxDialog(QtWidgets.QDialog):
    def __init__(self, pixmap: QtGui.QPixmap, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("detail.image_preview"))
        self.setWindowFlag(QtCore.Qt.WindowType.FramelessWindowHint, True)
        self.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)

        self.image_view = ImageView()
        self.image_view.set_pixmap(pixmap)

        close_button = QtWidgets.QPushButton(tr("detail.exit"))
        close_button.clicked.connect(self.close)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.addWidget(self.image_view, stretch=1)

        button_row = QtWidgets.QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

        self.setStyleSheet(
            "QDialog { background: #0b0b0b; } QPushButton { background: #2c2c2c; border: 1px solid #3b3b3b; padding: 8px 16px; }"
        )

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() in (QtCore.Qt.Key.Key_Escape, QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            self.close()
            event.accept()
            return
        super().keyPressEvent(event)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        screen = None
        if self.parentWidget():
            screen = self.parentWidget().screen()
        if screen is None:
            screen = QtGui.QGuiApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())
        super().showEvent(event)


class ImagingInfoDialog(QtWidgets.QDialog):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, setups: Optional[List[Dict[str, str]]] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("imaging.dialog_title"))
        self.resize(920, 680)
        self._setups: List[Dict[str, str]] = []
        if isinstance(setups, list):
            self._setups = [dict(item) for item in setups if isinstance(item, dict)]

        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(10)

        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        root_layout.addWidget(self.scroll_area, stretch=1)

        content = QtWidgets.QWidget()
        self.scroll_area.setWidget(content)

        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        location_group = QtWidgets.QGroupBox(tr("imaging.capture_location"))
        location_layout = QtWidgets.QFormLayout(location_group)
        self.capture_location_edit = QtWidgets.QLineEdit()
        location_layout.addRow(tr("imaging.location_label"), self.capture_location_edit)
        layout.addWidget(location_group)

        integrations_group = QtWidgets.QGroupBox(tr("imaging.integration_data"))
        integrations_layout = QtWidgets.QVBoxLayout(integrations_group)
        self.integrations_table = QtWidgets.QTableWidget(0, 7)
        self.integrations_table.setHorizontalHeaderLabels(
            [
                tr("imaging.col_filter"),
                tr("imaging.col_bandpass"),
                tr("imaging.col_brand"),
                tr("imaging.col_model"),
                tr("imaging.col_frames"),
                tr("imaging.col_exposure"),
                tr("imaging.col_capture_date"),
            ]
        )
        self.integrations_table.verticalHeader().setVisible(False)
        self.integrations_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.integrations_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.integrations_table.horizontalHeader().setStretchLastSection(True)
        self.integrations_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.integrations_table.verticalHeader().setDefaultSectionSize(30)
        self.integrations_table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._update_integrations_table_height()
        integrations_layout.addWidget(self.integrations_table)

        integration_buttons = QtWidgets.QHBoxLayout()
        self.integration_add_button = QtWidgets.QPushButton(tr("imaging.add_filter_row"))
        self.integration_remove_button = QtWidgets.QPushButton(tr("imaging.remove_filter_row"))
        self.integration_add_button.clicked.connect(lambda: self._add_integration_row())
        self.integration_remove_button.clicked.connect(self._remove_selected_integration_row)
        integration_buttons.addWidget(self.integration_add_button)
        integration_buttons.addWidget(self.integration_remove_button)
        integration_buttons.addStretch(1)
        integrations_layout.addLayout(integration_buttons)
        layout.addWidget(integrations_group, stretch=1)

        imaging_group = QtWidgets.QGroupBox(tr("imaging.imaging_equipment"))
        imaging_layout = QtWidgets.QFormLayout(imaging_group)
        self.setup_selector = QtWidgets.QComboBox()
        self.setup_selector.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.setup_apply_button = QtWidgets.QPushButton(tr("imaging.setup_apply"))
        self.setup_save_button = QtWidgets.QPushButton(tr("imaging.setup_save"))
        self.setup_delete_button = QtWidgets.QPushButton(tr("imaging.setup_delete"))
        self.setup_apply_button.clicked.connect(self._apply_selected_setup)
        self.setup_save_button.clicked.connect(self._save_setup_from_current_values)
        self.setup_delete_button.clicked.connect(self._delete_selected_setup)

        setup_row = QtWidgets.QHBoxLayout()
        setup_row.addWidget(self.setup_selector, stretch=1)
        setup_row.addWidget(self.setup_apply_button)
        setup_row.addWidget(self.setup_save_button)
        setup_row.addWidget(self.setup_delete_button)
        setup_row_widget = QtWidgets.QWidget()
        setup_row_widget.setLayout(setup_row)
        imaging_layout.addRow(tr("imaging.setup_label"), setup_row_widget)

        self.imaging_telescope_edit = QtWidgets.QLineEdit()
        self.imaging_camera_edit = QtWidgets.QLineEdit()
        self.imaging_mount_edit = QtWidgets.QLineEdit()
        self.imaging_accessories_edit = QtWidgets.QLineEdit()
        self.imaging_software_edit = QtWidgets.QLineEdit()
        imaging_layout.addRow(tr("imaging.telescope"), self.imaging_telescope_edit)
        imaging_layout.addRow(tr("imaging.camera"), self.imaging_camera_edit)
        imaging_layout.addRow(tr("imaging.mount"), self.imaging_mount_edit)
        imaging_layout.addRow(tr("imaging.accessories"), self.imaging_accessories_edit)
        imaging_layout.addRow(tr("imaging.software"), self.imaging_software_edit)
        layout.addWidget(imaging_group)

        guiding_group = QtWidgets.QGroupBox(tr("imaging.guiding_equipment"))
        guiding_layout = QtWidgets.QFormLayout(guiding_group)
        self.guiding_telescope_edit = QtWidgets.QLineEdit()
        self.guiding_camera_edit = QtWidgets.QLineEdit()
        guiding_layout.addRow(tr("imaging.guide_telescope"), self.guiding_telescope_edit)
        guiding_layout.addRow(tr("imaging.guide_camera"), self.guiding_camera_edit)
        layout.addWidget(guiding_group)

        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        root_layout.addWidget(self.button_box)

        self._refresh_setup_selector()
        self._apply_dynamic_dialog_size()

    def _apply_dynamic_dialog_size(self) -> None:
        screen = self.screen()
        if screen is None and self.parentWidget() is not None:
            screen = self.parentWidget().screen()
        if screen is None:
            screen = QtGui.QGuiApplication.primaryScreen()

        if screen is None:
            return

        available = screen.availableGeometry()
        max_width = max(700, int(available.width() * 0.95))
        max_height = max(520, int(available.height() * 0.95))

        preferred = self.sizeHint()
        preferred_width = max(920, preferred.width())
        preferred_height = max(680, preferred.height())

        self.setMaximumSize(max_width, max_height)
        self.resize(min(preferred_width, max_width), min(preferred_height, max_height))

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        self._apply_dynamic_dialog_size()
        super().showEvent(event)

    def _make_date_edit(self, date_str: str) -> QtWidgets.QDateEdit:
        edit = QtWidgets.QDateEdit()
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("yyyy-MM-dd")
        edit.setMinimumDate(QtCore.QDate(1900, 1, 1))
        edit.setSpecialValueText("—")  # displayed when date == minimumDate (1900-01-01)
        parsed = QtCore.QDate.fromString(date_str, "yyyy-MM-dd") if date_str else QtCore.QDate()
        edit.setDate(parsed if parsed.isValid() else QtCore.QDate.currentDate())
        return edit

    def _add_integration_row(self, row_data: Optional[Dict] = None) -> None:
        row = self.integrations_table.rowCount()
        if row_data is None and row > 0:
            row_data = self._get_row_data(row - 1)
        self.integrations_table.insertRow(row)
        defaults = row_data or {}

        def line(text: str) -> QtWidgets.QLineEdit:
            w = QtWidgets.QLineEdit(text)
            w.setFrame(True)
            return w

        bpv = defaults.get("filter_bandpass_nm")
        frames_spin = QtWidgets.QSpinBox()
        frames_spin.setMinimum(0)
        frames_spin.setMaximum(99999)
        frames_spin.setValue(int(defaults.get("subframe_count") or 1))

        self.integrations_table.setCellWidget(row, 0, line(str(defaults.get("filter_name") or "")))
        self.integrations_table.setCellWidget(row, 1, line("" if bpv is None else str(bpv)))
        self.integrations_table.setCellWidget(row, 2, line(str(defaults.get("filter_brand") or "")))
        self.integrations_table.setCellWidget(row, 3, line(str(defaults.get("filter_model") or "")))
        self.integrations_table.setCellWidget(row, 4, frames_spin)
        self.integrations_table.setCellWidget(row, 5, line(str(defaults.get("exposure_seconds") or "0")))
        self.integrations_table.setCellWidget(row, 6, self._make_date_edit(str(defaults.get("captured_on") or "")))
        self._update_integrations_table_height()

    def _get_row_data(self, row: int) -> Dict:
        def wtext(col: int) -> str:
            w = self.integrations_table.cellWidget(row, col)
            return w.text().strip() if isinstance(w, QtWidgets.QLineEdit) else ""

        frames_w = self.integrations_table.cellWidget(row, 4)
        frames = frames_w.value() if isinstance(frames_w, QtWidgets.QSpinBox) else 1

        date_w = self.integrations_table.cellWidget(row, 6)
        if isinstance(date_w, QtWidgets.QDateEdit):
            d = date_w.date()
            date_str = d.toString("yyyy-MM-dd") if d != date_w.minimumDate() else None
        else:
            date_str = None

        return {
            "filter_name": wtext(0) or None,
            "filter_bandpass_nm": self._parse_float(wtext(1)),
            "filter_brand": wtext(2) or None,
            "filter_model": wtext(3) or None,
            "subframe_count": frames,
            "exposure_seconds": self._parse_float(wtext(5), default=0.0),
            "captured_on": date_str,
        }

    def _remove_selected_integration_row(self) -> None:
        row = self.integrations_table.currentRow()
        if row >= 0:
            self.integrations_table.removeRow(row)
            self._update_integrations_table_height()

    def set_payload(self, payload: Dict) -> None:
        self.capture_location_edit.setText(str(payload.get("capture_location") or ""))
        self.integrations_table.setRowCount(0)
        for integration in self._sorted_integrations(payload.get("integrations", [])):
            if isinstance(integration, dict):
                self._add_integration_row(integration)
        self._update_integrations_table_height()

        imaging = payload.get("imaging_equipment") or {}
        self.imaging_telescope_edit.setText(str(imaging.get("telescope_or_refractor") or ""))
        self.imaging_camera_edit.setText(str(imaging.get("camera") or ""))
        self.imaging_mount_edit.setText(str(imaging.get("mount") or ""))
        self.imaging_accessories_edit.setText(str(imaging.get("accessories") or ""))
        self.imaging_software_edit.setText(str(imaging.get("software") or ""))

        guiding = payload.get("guiding_equipment") or {}
        self.guiding_telescope_edit.setText(str(guiding.get("guide_telescope") or ""))
        self.guiding_camera_edit.setText(str(guiding.get("guide_camera") or ""))

    def setups_payload(self) -> List[Dict[str, str]]:
        payload: List[Dict[str, str]] = []
        for setup in self._setups:
            name = str(setup.get("name") or "").strip()
            if not name:
                continue
            payload.append(
                {
                    "name": name,
                    "telescope_or_refractor": str(setup.get("telescope_or_refractor") or "").strip(),
                    "camera": str(setup.get("camera") or "").strip(),
                    "mount": str(setup.get("mount") or "").strip(),
                    "accessories": str(setup.get("accessories") or "").strip(),
                    "software": str(setup.get("software") or "").strip(),
                    "guide_telescope": str(setup.get("guide_telescope") or "").strip(),
                    "guide_camera": str(setup.get("guide_camera") or "").strip(),
                }
            )
        return payload

    def _refresh_setup_selector(self) -> None:
        previous_name = self.setup_selector.currentData()
        self.setup_selector.blockSignals(True)
        self.setup_selector.clear()
        self.setup_selector.addItem(tr("imaging.setup_none"), None)
        for setup in sorted(self._setups, key=lambda item: str(item.get("name") or "").lower()):
            name = str(setup.get("name") or "").strip()
            if name:
                self.setup_selector.addItem(name, name)
        self.setup_selector.blockSignals(False)

        if previous_name:
            index = self.setup_selector.findData(previous_name)
            if index >= 0:
                self.setup_selector.setCurrentIndex(index)

    def _collect_current_setup_values(self) -> Dict[str, str]:
        return {
            "telescope_or_refractor": self.imaging_telescope_edit.text().strip(),
            "camera": self.imaging_camera_edit.text().strip(),
            "mount": self.imaging_mount_edit.text().strip(),
            "accessories": self.imaging_accessories_edit.text().strip(),
            "software": self.imaging_software_edit.text().strip(),
            "guide_telescope": self.guiding_telescope_edit.text().strip(),
            "guide_camera": self.guiding_camera_edit.text().strip(),
        }

    def _apply_setup_values(self, setup: Dict[str, str]) -> None:
        self.imaging_telescope_edit.setText(str(setup.get("telescope_or_refractor") or ""))
        self.imaging_camera_edit.setText(str(setup.get("camera") or ""))
        self.imaging_mount_edit.setText(str(setup.get("mount") or ""))
        self.imaging_accessories_edit.setText(str(setup.get("accessories") or ""))
        self.imaging_software_edit.setText(str(setup.get("software") or ""))
        self.guiding_telescope_edit.setText(str(setup.get("guide_telescope") or ""))
        self.guiding_camera_edit.setText(str(setup.get("guide_camera") or ""))

    def _apply_selected_setup(self) -> None:
        selected_name = self.setup_selector.currentData()
        if not selected_name:
            return
        setup = next((item for item in self._setups if str(item.get("name") or "").strip() == selected_name), None)
        if setup is None:
            return
        self._apply_setup_values(setup)

    def _save_setup_from_current_values(self) -> None:
        name, ok = QtWidgets.QInputDialog.getText(
            self,
            tr("imaging.setup_name_title"),
            tr("imaging.setup_name_prompt"),
            QtWidgets.QLineEdit.EchoMode.Normal,
            str(self.setup_selector.currentData() or ""),
        )
        if not ok:
            return
        setup_name = (name or "").strip()
        if not setup_name:
            return

        values = self._collect_current_setup_values()
        existing_index = -1
        for index, setup in enumerate(self._setups):
            if str(setup.get("name") or "").strip().lower() == setup_name.lower():
                existing_index = index
                break

        setup_payload = {"name": setup_name, **values}
        if existing_index >= 0:
            self._setups[existing_index] = setup_payload
        else:
            self._setups.append(setup_payload)

        self._refresh_setup_selector()
        index = self.setup_selector.findData(setup_name)
        if index >= 0:
            self.setup_selector.setCurrentIndex(index)

    def _delete_selected_setup(self) -> None:
        selected_name = self.setup_selector.currentData()
        if not selected_name:
            return

        answer = QtWidgets.QMessageBox.question(
            self,
            tr("imaging.setup_delete_title"),
            tr("imaging.setup_delete_confirm", name=selected_name),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        self._setups = [
            setup
            for setup in self._setups
            if str(setup.get("name") or "").strip() != selected_name
        ]
        self._refresh_setup_selector()

    @staticmethod
    def _canonical_filter_name(name: str) -> Optional[str]:
        raw = (name or "").strip().upper()
        if not raw:
            return None

        normalized = "".join(ch for ch in raw if ("A" <= ch <= "Z") or ("0" <= ch <= "9"))
        if normalized in {"L", "LUM", "LUMINANCE"}:
            return "L"
        if normalized in {"R", "RED"}:
            return "R"
        if normalized in {"G", "GREEN"}:
            return "G"
        if normalized in {"B", "BLUE"}:
            return "B"
        if normalized in {"S", "SII", "S2"}:
            return "S"
        if normalized in {"H", "HA", "HALPHA","Hα"}:
            return "H"
        if normalized in {"O", "OIII", "O3"}:
            return "O"
        return None

    @classmethod
    def _sorted_integrations(cls, integrations: object) -> List[Dict]:
        if not isinstance(integrations, list):
            return []

        order = {"L": 0, "R": 1, "G": 2, "B": 3, "S": 4, "H": 5, "O": 6}
        indexed_rows: List[tuple[int, Dict]] = []
        for index, row in enumerate(integrations):
            if isinstance(row, dict):
                indexed_rows.append((index, row))

        indexed_rows.sort(
            key=lambda pair: (
                order.get(cls._canonical_filter_name(str(pair[1].get("filter_name") or "")), 999),
                pair[0],
            )
        )
        return [row for _, row in indexed_rows]

    def _update_integrations_table_height(self) -> None:
        row_count = self.integrations_table.rowCount()
        visible_rows = max(1, min(5, row_count))
        row_height = max(24, self.integrations_table.verticalHeader().defaultSectionSize())
        header_height = self.integrations_table.horizontalHeader().sizeHint().height()
        table_height = header_height + (visible_rows * row_height) + (2 * self.integrations_table.frameWidth()) + 8
        self.integrations_table.setMinimumHeight(table_height)
        self.integrations_table.setMaximumHeight(table_height)

    def payload(self) -> Dict:
        integrations: List[Dict] = []
        for row in range(self.integrations_table.rowCount()):
            data = self._get_row_data(row)
            filter_name = data["filter_name"] or ""
            bandpass_value = data["filter_bandpass_nm"]
            filter_brand = data["filter_brand"] or ""
            filter_model = data["filter_model"] or ""
            subframe_count = data["subframe_count"] or 0
            exposure_seconds = data["exposure_seconds"] or 0.0
            captured_on = data["captured_on"] or ""
            if not any([filter_name, bandpass_value is not None, filter_brand, filter_model, captured_on, subframe_count > 0, exposure_seconds > 0]):
                continue
            integrations.append(
                {
                    "filter_name": filter_name or "none",
                    "filter_bandpass_nm": bandpass_value,
                    "filter_brand": filter_brand or None,
                    "filter_model": filter_model or None,
                    "subframe_count": max(1, subframe_count),
                    "exposure_seconds": max(0.0, exposure_seconds),
                    "captured_on": captured_on or None,
                }
            )

        return {
            "capture_location": self.capture_location_edit.text().strip(),
            "integrations": integrations,
            "imaging_equipment": {
                "telescope_or_refractor": self.imaging_telescope_edit.text().strip() or None,
                "camera": self.imaging_camera_edit.text().strip() or None,
                "mount": self.imaging_mount_edit.text().strip() or None,
                "accessories": self.imaging_accessories_edit.text().strip() or None,
                "software": self.imaging_software_edit.text().strip() or None,
            },
            "guiding_equipment": {
                "guide_telescope": self.guiding_telescope_edit.text().strip() or None,
                "guide_camera": self.guiding_camera_edit.text().strip() or None,
            },
        }

    def _parse_float(self, value: str, default: Optional[float] = None) -> Optional[float]:
        if not value:
            return default
        try:
            return float(value.replace(",", "."))
        except ValueError:
            return default

    def _cell_text(self, row: int, col: int) -> str:
        item = self.integrations_table.item(row, col)
        return (item.text() if item else "").strip()

    def _cell_float(self, row: int, col: int, default: Optional[float] = None) -> Optional[float]:
        return self._parse_float(self._cell_text(row, col), default)

    def _cell_int(self, row: int, col: int, default: int = 0) -> int:
        value = self._cell_text(row, col)
        if not value:
            return default
        try:
            return int(float(value.replace(",", ".")))
        except ValueError:
            return default


class DetailPanel(QtWidgets.QWidget):
    thumbnail_selected = QtCore.Signal(str, str, str)
    archive_requested = QtCore.Signal(str)
    image_changed = QtCore.Signal(str)
    focus_mode_toggled = QtCore.Signal(bool)
    navigation_requested = QtCore.Signal(int)
    imaging_info_requested = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__()
        self.image_view = ImageView()
        self.title = QtWidgets.QLabel(tr("detail.select_object"))
        self.title.setObjectName("detailTitle")
        self.metadata = QtWidgets.QLabel("")
        self.metadata.setObjectName("detailMetadata")
        self.metadata.setWordWrap(True)
        self.metadata.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed)
        self.metadata.setContentsMargins(0, 0, 0, 0)
        self.image_info = QtWidgets.QLabel("")
        self.image_info.setObjectName("imageInfo")
        self.image_info.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed)
        self.image_info.setContentsMargins(0, 0, 0, 0)
        self.description = QtWidgets.QTextEdit()
        self.description.setReadOnly(True)
        self.description.setObjectName("descriptionBox")
        self.notes = QtWidgets.QTextEdit()
        self.notes.setObjectName("notesBox")
        self.notes.setPlaceholderText(tr("detail.notes_placeholder"))
        self.notes.setMinimumHeight(80)
        self.notes.setMaximumHeight(140)
        self._detail_text_min_size = 9.0
        self._detail_text_max_size = 24.0
        self._detail_text_size = self.description.font().pointSizeF()
        if self._detail_text_size <= 0:
            self._detail_text_size = QtWidgets.QApplication.font().pointSizeF()
        if self._detail_text_size <= 0:
            self._detail_text_size = 10.0
        self.external_link = QtWidgets.QLabel("")
        self.external_link.setOpenExternalLinks(True)
        self.external_link.setObjectName("externalLink")
        self.external_link.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed)
        self.external_link.setContentsMargins(0, 0, 0, 0)
        self.fit_button = QtWidgets.QPushButton(tr("detail.fit_to_window"))
        self.fit_button.clicked.connect(self.image_view.fit_to_window)
        self.image_view.fullscreen_requested.connect(self._toggle_focus_mode)
        self.image_view.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.image_view.customContextMenuRequested.connect(self._show_image_context_menu)
        self.prev_button = QtWidgets.QPushButton("◀")
        self.next_button = QtWidgets.QPushButton("▶")
        self.thumb_button = QtWidgets.QPushButton(tr("detail.set_as_thumbnail"))
        self.archive_button = QtWidgets.QPushButton(tr("detail.archive_image"))
        self.imaging_info_button = QtWidgets.QPushButton(tr("detail.imaging_info"))
        self.prev_button.clicked.connect(lambda: self.navigation_requested.emit(-1))
        self.next_button.clicked.connect(lambda: self.navigation_requested.emit(1))
        self.thumb_button.clicked.connect(self._set_thumbnail)
        self.archive_button.clicked.connect(self._request_archive)
        self.imaging_info_button.clicked.connect(self._request_imaging_info)
        self._current_item: Optional[CatalogItem] = None
        self._notes_block = False
        self._image_index = 0
        self._wiki_pixmap: Optional[QtGui.QPixmap] = None
        self._lightbox: Optional[LightboxDialog] = None
        self._image_load_id = 0
        self._image_thread_pool = QtCore.QThreadPool.globalInstance()
        self._image_cache: Dict[str, QtGui.QPixmap] = {}
        self._focus_mode = False
        self._saved_detail_sizes: Optional[List[int]] = None

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        self.text_smaller_button = QtWidgets.QPushButton(tr("detail.text_button_smaller"))
        self.text_larger_button = QtWidgets.QPushButton(tr("detail.text_button_larger"))
        self.text_smaller_button.setToolTip(tr("detail.text_smaller"))
        self.text_larger_button.setToolTip(tr("detail.text_larger"))
        self.text_smaller_button.clicked.connect(lambda: self._change_detail_text_size(-1.0))
        self.text_larger_button.clicked.connect(lambda: self._change_detail_text_size(1.0))
        self.focus_toggle_button = QtWidgets.QToolButton()
        self.focus_toggle_button.setObjectName("focusToggleButton")
        self.focus_toggle_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.focus_toggle_button.setFixedSize(30, 30)
        self.focus_toggle_button.setIconSize(QtCore.QSize(20, 20))
        self.focus_toggle_button.setIcon(_build_focus_toggle_icon("expand"))
        self.focus_toggle_button.setToolTip(tr("detail.focus_mode_enter"))
        self.focus_toggle_button.setAutoRaise(False)
        self.focus_toggle_button.clicked.connect(self._toggle_focus_mode)

        image_container = QtWidgets.QWidget()
        image_container.setObjectName("detailImageContainer")
        image_layout = QtWidgets.QVBoxLayout(image_container)
        image_layout.setContentsMargins(12, 12, 12, 12)
        image_layout.setSpacing(10)
        image_header = QtWidgets.QWidget()
        image_header.setObjectName("detailImageHeader")
        image_header_layout = QtWidgets.QHBoxLayout(image_header)
        image_header_layout.setContentsMargins(2, 0, 2, 0)
        image_header_layout.setSpacing(10)
        image_header_layout.addWidget(self.title)
        image_header_layout.addSpacing(10)
        image_header_layout.addWidget(self.fit_button)
        image_header_layout.addWidget(self.text_smaller_button)
        image_header_layout.addWidget(self.text_larger_button)
        image_header_layout.addStretch(1)
        image_header_layout.addWidget(self.prev_button)
        image_header_layout.addWidget(self.next_button)
        image_header_layout.addWidget(self.focus_toggle_button)
        image_layout.addWidget(image_header)
        image_layout.addWidget(self.image_view, stretch=1)

        left_widget = QtWidgets.QWidget()
        left_widget.setObjectName("detailMetaPanel")
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setContentsMargins(18, 18, 18, 18)
        left_layout.setSpacing(12)
        nav_row = QtWidgets.QHBoxLayout()
        nav_row.setSpacing(8)
        nav_row.addWidget(self.thumb_button)
        nav_row.addWidget(self.archive_button)
        nav_row.addWidget(self.imaging_info_button)
        nav_row.addStretch(1)
        left_layout.addLayout(nav_row)
        left_layout.addWidget(self.metadata)
        left_layout.addWidget(self.image_info)
        self.imaging_summary = QtWidgets.QLabel("")
        self.imaging_summary.setObjectName("imagingSummary")
        self.imaging_summary.setWordWrap(True)
        self.imaging_summary.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed)
        self.imaging_summary.hide()
        left_layout.addWidget(self.imaging_summary)
        left_layout.addWidget(self.external_link)

        right_widget = QtWidgets.QWidget()
        right_widget.setObjectName("detailTextPanel")
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        right_layout.setContentsMargins(18, 18, 18, 18)
        right_layout.setSpacing(12)
        right_layout.addWidget(self.description, stretch=2)
        right_layout.addWidget(self.notes, stretch=1)
        self._change_detail_text_size(0.0)

        columns_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        columns_splitter.addWidget(left_widget)
        columns_splitter.addWidget(right_widget)
        columns_splitter.setStretchFactor(0, 1)
        columns_splitter.setStretchFactor(1, 3)
        columns_splitter.setChildrenCollapsible(False)
        columns_splitter.setHandleWidth(6)
        columns_splitter.setSizes([320, 960])
        self._columns_splitter = columns_splitter
        main_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        main_splitter.addWidget(image_container)
        main_splitter.addWidget(columns_splitter)
        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 0)
        main_splitter.setChildrenCollapsible(False)
        main_splitter.setHandleWidth(6)
        main_splitter.setSizes([520, 200])
        self.splitter = main_splitter
        self._left_widget = left_widget
        self._main_splitter = main_splitter
        self._initial_detail_sized = False

        layout.addWidget(main_splitter, stretch=1)

    def set_focus_mode(self, enabled: bool) -> None:
        if self._focus_mode == enabled:
            return
        self._focus_mode = enabled
        if enabled:
            current_sizes = self._main_splitter.sizes()
            if len(current_sizes) >= 2 and current_sizes[0] > 0 and current_sizes[1] > 0:
                self._saved_detail_sizes = current_sizes
            self._columns_splitter.hide()
            self._main_splitter.setHandleWidth(0)
            self._main_splitter.setSizes([1, 0])
            self.focus_toggle_button.setIcon(_build_focus_toggle_icon("reduce"))
            self.focus_toggle_button.setToolTip(tr("detail.focus_mode_exit"))
            return
        self._columns_splitter.show()
        self._main_splitter.setHandleWidth(6)
        self._main_splitter.setSizes(self._saved_detail_sizes or [520, 200])
        self.focus_toggle_button.setIcon(_build_focus_toggle_icon("expand"))
        self.focus_toggle_button.setToolTip(tr("detail.focus_mode_enter"))

    def _toggle_focus_mode(self) -> None:
        self.focus_mode_toggled.emit(not self._focus_mode)

    def update_item(self, item: Optional[CatalogItem]) -> None:
        self._current_item = item
        self._notes_block = True
        self._wiki_pixmap = None
        self._image_load_id += 1
        if item is None:
            self.title.setText(tr("detail.select_object"))
            self.metadata.setText("")
            self.description.setPlainText("")
            self.notes.setPlainText("")
            self.image_info.setText("")
            self.image_view.set_pixmap(None)
            self.prev_button.setEnabled(False)
            self.next_button.setEnabled(False)
            self.thumb_button.setEnabled(False)
            self.archive_button.setEnabled(False)
            self.imaging_info_button.setEnabled(False)
            self.imaging_summary.clear()
            self.imaging_summary.hide()
            self._notes_block = False
            return
        self.title.setText(item.display_name)
        raw_object_type = (item.object_type or "").strip()
        object_type_display = localized_object_type(raw_object_type)
        if object_type_display is None and raw_object_type and not is_hidden_object_type(raw_object_type):
            object_type_display = raw_object_type
        metadata_lines = [
            tr("detail.metadata.catalog", value=item.catalog),
        ]
        if object_type_display:
            metadata_lines.append(tr("detail.metadata.type", value=object_type_display))
        if item.distance_ly:
            metadata_lines.append(tr("detail.metadata.distance", value=f"{item.distance_ly:,.0f}"))
        if item.discoverer:
            if item.discovery_year:
                metadata_lines.append(
                    tr("detail.metadata.discoverer_year", value=item.discoverer, year=item.discovery_year)
                )
            else:
                metadata_lines.append(tr("detail.metadata.discoverer", value=item.discoverer))
        if item.best_months:
            metadata_lines.append(tr("detail.metadata.best_visibility", value=self._format_months(item.best_months)))
        constellation_display = format_constellation_display(item.constellation)
        if constellation_display:
            metadata_lines.append(tr("detail.metadata.constellation", value=constellation_display))
        self.metadata.setText("\n".join(metadata_lines))
        self.description.setPlainText(item.description or "")
        if item.external_link:
            self.external_link.setText(f'<a href="{item.external_link}">{tr("detail.more_info")}</a>')
            self.external_link.show()
        else:
            self.external_link.hide()
        self._image_index = 0
        if item.thumbnail_path and item.image_paths:
            try:
                self._image_index = item.image_paths.index(item.thumbnail_path)
            except ValueError:
                self._image_index = 0
        self._update_image_view()
        self._apply_notes_for_current_image()
        self._notes_block = False

    @staticmethod
    def _format_months(value: str) -> str:
        return format_best_months(value)

    def connect_notes_changed(self, callback) -> None:
        self.notes.textChanged.connect(callback)

    def set_imaging_summary(self, summary: str) -> None:
        text = (summary or "").strip()
        self.imaging_summary.setText(text)
        self.imaging_summary.setVisible(bool(text))

    def current_notes(self) -> str:
        return self.notes.toPlainText()

    def current_image_name(self) -> Optional[str]:
        if not self._current_item or not self._current_item.image_paths:
            return None
        paths = self._current_item.image_paths
        if not paths:
            return None
        index = max(0, min(self._image_index, len(paths) - 1))
        return paths[index].name

    def current_image_path(self) -> Optional[Path]:
        if not self._current_item or not self._current_item.image_paths:
            return None
        index = max(0, min(self._image_index, len(self._current_item.image_paths) - 1))
        return self._current_item.image_paths[index]

    def current_item(self) -> Optional[CatalogItem]:
        return self._current_item

    def notes_blocked(self) -> bool:
        return self._notes_block

    def _update_image_view(self) -> None:
        if not self._current_item or not self._current_item.image_paths:
            if self._wiki_pixmap and not self._wiki_pixmap.isNull():
                self.image_view.set_pixmap(self._wiki_pixmap)
                size_info = f"{self._wiki_pixmap.width()}x{self._wiki_pixmap.height()}"
                self.image_info.setText(tr("detail.image.wikipedia_preview", size=size_info))
            else:
                self.image_view.set_pixmap(None)
                self.image_info.setText(tr("detail.image.none"))
            self.prev_button.setEnabled(True)
            self.next_button.setEnabled(True)
            self.thumb_button.setEnabled(False)
            self.archive_button.setEnabled(False)
            self.imaging_info_button.setEnabled(False)
            return
        paths = self._current_item.image_paths
        self._image_index = max(0, min(self._image_index, len(paths) - 1))
        path = paths[self._image_index]
        cache_key = str(path)
        cached = self._image_cache.get(cache_key)
        if cached and not cached.isNull():
            self.image_view.set_pixmap(cached)
            size_info = f"{cached.width()}x{cached.height()}"
            self.image_info.setText(
                tr(
                    "detail.image.info",
                    index=self._image_index + 1,
                    total=len(paths),
                    name=path.name,
                    size_suffix=tr("detail.image.size_suffix", size=size_info) if size_info else "",
                )
            )
            self.prev_button.setEnabled(True)
            self.next_button.setEnabled(True)
            self.thumb_button.setEnabled(True)
            self.archive_button.setEnabled(True)
            self.imaging_info_button.setEnabled(True)
            return
        self.image_view.set_pixmap(None)
        self.image_info.setText(tr("detail.image.loading", name=path.name))
        self.prev_button.setEnabled(True)
        self.next_button.setEnabled(True)
        self.thumb_button.setEnabled(True)
        self.archive_button.setEnabled(True)
        self.imaging_info_button.setEnabled(True)
        self._start_image_load(path)

    def _start_image_load(self, path: Path) -> None:
        self._image_load_id += 1
        request_id = self._image_load_id
        task = ImageLoadTask(request_id, path)
        task.signals.loaded.connect(self._on_image_loaded)
        task.signals.failed.connect(self._on_image_failed)
        self._image_thread_pool.start(task)

    def _on_image_loaded(self, request_id: int, path_value: str, image: QtGui.QImage) -> None:
        if request_id != self._image_load_id:
            return
        if not self._current_item or not self._current_item.image_paths:
            return
        current_path = self._current_item.image_paths[self._image_index]
        if str(current_path) != path_value:
            return
        pixmap = QtGui.QPixmap.fromImage(image)
        if pixmap.isNull():
            self._on_image_failed(request_id, path_value)
            return
        cache_key = str(current_path)
        self._image_cache[cache_key] = pixmap
        self.image_view.set_pixmap(pixmap)
        size_info = f"{pixmap.width()}x{pixmap.height()}"
        self.image_info.setText(
            tr(
                "detail.image.info",
                index=self._image_index + 1,
                total=len(self._current_item.image_paths),
                name=current_path.name,
                size_suffix=tr("detail.image.size_suffix", size=size_info) if size_info else "",
            )
        )
        self.thumb_button.setEnabled(True)
        self.archive_button.setEnabled(True)
        self.imaging_info_button.setEnabled(True)

    def _on_image_failed(self, request_id: int, path_value: str, message: str) -> None:
        if request_id != self._image_load_id:
            return
        self.image_view.set_pixmap(None)
        self.image_info.setText(message or tr("detail.image.load_failed"))
        self.thumb_button.setEnabled(False)
        self.archive_button.setEnabled(False)
        self.imaging_info_button.setEnabled(False)

    def _request_imaging_info(self) -> None:
        self.imaging_info_requested.emit()

    def _apply_initial_sizes(self) -> None:
        if self._initial_detail_sized:
            return
        if self._focus_mode:
            return
        if not hasattr(self, "_left_widget") or not hasattr(self, "_main_splitter"):
            return
        total_height = max(self._main_splitter.size().height(), self.height())
        if total_height <= 0:
            QtCore.QTimer.singleShot(50, self._apply_initial_sizes)
            return
        detail_height = 200
        image_height = max(240, total_height - detail_height)
        self._main_splitter.setSizes([image_height, detail_height])
        self._initial_detail_sized = True

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        QtCore.QTimer.singleShot(0, self._apply_initial_sizes)

    def navigate_images(self, direction: int) -> bool:
        if direction == 0:
            return False
        return self._step_image(1 if direction > 0 else -1, wrap=False)

    def _step_image(self, delta: int, wrap: bool) -> bool:
        if not self._current_item or not self._current_item.image_paths:
            return False
        paths = self._current_item.image_paths
        new_index = self._image_index + delta
        if wrap:
            new_index %= len(paths)
        elif new_index < 0 or new_index >= len(paths):
            return False
        self._image_index = new_index
        self._update_image_view()
        self._apply_notes_for_current_image()
        current_name = self.current_image_name() or ""
        self.image_changed.emit(current_name)
        return True

    def _set_thumbnail(self) -> None:
        if not self._current_item or not self._current_item.image_paths:
            return
        path = self._current_item.image_paths[self._image_index]
        self.thumbnail_selected.emit(self._current_item.catalog, self._current_item.object_id, path.name)

    def set_wiki_pixmap(self, pixmap: Optional[QtGui.QPixmap]) -> None:
        self._wiki_pixmap = pixmap if pixmap and not pixmap.isNull() else None
        self._update_image_view()

    def _request_archive(self) -> None:
        if not self._current_item or not self._current_item.image_paths:
            return
        path = self._current_item.image_paths[self._image_index]
        self.archive_requested.emit(str(path))

    def _change_detail_text_size(self, delta: float) -> None:
        self._detail_text_size = max(
            self._detail_text_min_size,
            min(self._detail_text_max_size, self._detail_text_size + delta),
        )
        for widget in (
            self.title,
            self.metadata,
            self.image_info,
            self.imaging_summary,
            self.external_link,
            self.description,
            self.notes,
        ):
            font = widget.font()
            font.setPointSizeF(self._detail_text_size)
            widget.setFont(font)
        self.text_smaller_button.setEnabled(self._detail_text_size > self._detail_text_min_size)
        self.text_larger_button.setEnabled(self._detail_text_size < self._detail_text_max_size)

    def _show_image_context_menu(self, position: QtCore.QPoint) -> None:
        path = self.current_image_path()
        menu = QtWidgets.QMenu(self)
        if path is None:
            empty = QtGui.QAction(tr("detail.menu.no_image"), menu)
            empty.setEnabled(False)
            menu.addAction(empty)
            menu.exec(self.image_view.mapToGlobal(position))
            return
        path_action = QtGui.QAction(str(path), menu)
        path_action.setEnabled(False)
        menu.addAction(path_action)
        menu.addSeparator()
        open_action = QtGui.QAction(tr("detail.menu.open_folder"), menu)
        open_action.triggered.connect(lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path.parent))))
        menu.addAction(open_action)
        copy_action = QtGui.QAction(tr("detail.menu.copy_path"), menu)
        copy_action.triggered.connect(lambda: QtWidgets.QApplication.clipboard().setText(str(path)))
        menu.addAction(copy_action)
        menu.exec(self.image_view.mapToGlobal(position))

    def set_current_image_by_name(self, image_name: str) -> None:
        if not self._current_item or not self._current_item.image_paths:
            return
        for index, path in enumerate(self._current_item.image_paths):
            if path.name == image_name:
                if index != self._image_index:
                    self._image_index = index
                    self._update_image_view()
                    self._apply_notes_for_current_image()
                return

    def update_current_item_notes(self, image_name: Optional[str], notes: Optional[str], object_notes: Optional[str] = None) -> None:
        if not self._current_item:
            return
        image_notes = dict(self._current_item.image_notes)
        if image_name:
            if notes and notes.strip():
                image_notes[image_name] = notes
            else:
                image_notes.pop(image_name, None)
        updated_notes = self._current_item.notes if object_notes is None else object_notes
        self._current_item = replace(
            self._current_item,
            notes=updated_notes,
            image_notes=image_notes,
        )

    def _apply_notes_for_current_image(self) -> None:
        self._notes_block = True
        note_text = ""
        if self._current_item:
            image_name = self.current_image_name()
            if image_name:
                if self._current_item.image_notes:
                    note_text = self._current_item.image_notes.get(image_name, "")
                else:
                    note_text = self._current_item.notes or ""
            else:
                note_text = self._current_item.notes or ""
        self.notes.setPlainText(note_text)
        self._notes_block = False



class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, config_path: Path) -> None:
        super().__init__()

        self.config_path = config_path
        self.config = load_config(self.config_path)
        set_ui_locale(self.config.get("ui_locale", "system"))
        self.setWindowTitle(APP_NAME)
        self._data_version = self._load_local_data_version()
        self._ensure_user_metadata_files()
        self.user_notes_path = self._user_notes_path()
        self.db_path = database_path_from_config_path(self.config_path)
        self.database = Database(self.db_path)
        if not self.config.get("cleanup_invalid_image_only_entries_done", False):
            self._cleanup_invalid_image_only_entries()
            self.config["cleanup_invalid_image_only_entries_done"] = True
            save_config(self.config_path, self.config)
        if not self.config_path.exists():
            save_config(self.config_path, self.config)
        self._saved_state = self.config.get("ui_state", {})
        if not self._saved_state:
            self._saved_state = {
                "filters": {"catalog": "Messier"},
                "search": "",
            }
        self._saved_state_applied = False

        cache_dir = self._cache_dir()
        thumb_size = self.config.get("thumb_size", 240)
        self.thumbnail_cache = ThumbnailCache(cache_dir, thumb_size)

        self.items: List[CatalogItem] = []
        self.model = CatalogModel(self.items, self.thumbnail_cache, self)
        self.proxy = CatalogFilterProxy(self)
        self.proxy.setSourceModel(self.model)
        self._auto_fit_enabled = True
        self._suppress_auto_fit = True
        self._thread_pool = QtCore.QThreadPool.globalInstance()
        self._catalog_pool = QtCore.QThreadPool(self)
        self._catalog_pool.setMaxThreadCount(1)
        self._loading = False
        self._pending_reload = False
        self._pending_config: Optional[Dict] = None
        self._preview_active = False
        self._auto_fit_timer = QtCore.QTimer(self)
        self._auto_fit_timer.setSingleShot(True)
        self._auto_fit_timer.setInterval(150)
        self._auto_fit_timer.timeout.connect(self._auto_fit_thumbnails)
        self._zoom_timer = QtCore.QTimer(self)
        self._zoom_timer.setSingleShot(True)
        self._zoom_timer.setInterval(120)
        self._zoom_timer.timeout.connect(self._apply_zoom)
        self._pending_zoom = self.thumbnail_cache.thumb_size
        self._notes_timer = QtCore.QTimer(self)
        self._notes_timer.setSingleShot(True)
        self._notes_timer.setInterval(600)
        self._notes_timer.timeout.connect(self._flush_notes)
        self._pending_notes: Dict[str, Tuple[str, str, Optional[str], str]] = {}
        self._pending_selection_key: Optional[str] = None
        self._pending_image_name: Optional[str] = None
        self._about_dialog: Optional[AboutDialog] = None
        self._update_status = tr("about.not_checked")
        self._latest_version: Optional[str] = None
        self._update_url: Optional[str] = None
        self._remote_data_version: Optional[str] = None
        self._data_update_status = tr("about.checking_data_updates")
        self._update_tasks: List[UpdateCheckTask] = []
        self._data_version_task: Optional[DataVersionFetchTask] = None
        self._closing = False
        self._compact_toolbar = False
        self._syncing_compact = False
        self._toolbar_full_width = 0

        self._build_ui()
        self._start_data_version_fetch()
        self._apply_dark_theme()
        self._apply_saved_window_state()
        self._update_toolbar_compact_mode()
        self._update_filters()
        self._start_catalog_load()
        if self.config.get("auto_check_updates", True):
            QtCore.QTimer.singleShot(250, self._check_updates_silent)

    def _cache_dir(self) -> Path:
        location = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.CacheLocation)
        return Path(location)

    def _load_local_data_version(self) -> str:
        # Data version shown in About must always reflect the local bundled data.
        # Clean up legacy override keys from older behavior.
        updated = False
        if "data_version_override" in self.config:
            self.config.pop("data_version_override", None)
            updated = True
        if "app_version_override" in self.config:
            self.config.pop("app_version_override", None)
            updated = True
        if updated:
            save_config(self.config_path, self.config)
        return DEFAULT_DATA_VERSION

    def _ensure_user_metadata_files(self) -> None:
        updated = False
        default_map = {c.get("name"): c for c in DEFAULT_CONFIG.get("catalogs", [])}
        for catalog in self.config.get("catalogs", []):
            name = catalog.get("name")
            default_catalog = default_map.get(name, {}) if isinstance(name, str) else {}
            default_metadata = default_catalog.get("metadata_file")
            if default_metadata and catalog.get("metadata_file") != default_metadata:
                catalog["metadata_file"] = default_metadata
                updated = True

        notes_file = self._user_notes_path()
        if notes_file is not None:
            notes_file.parent.mkdir(parents=True, exist_ok=True)
            if not notes_file.exists():
                try:
                    with notes_file.open("w", encoding="utf-8") as handle:
                        json.dump({}, handle, indent=2, ensure_ascii=False)
                    updated = True
                except OSError:
                    pass
        if updated:
            save_config(self.config_path, self.config)

    def _user_notes_path(self) -> Optional[Path]:
        location = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.AppConfigLocation)
        if not location:
            return None
        return Path(location) / "photo_notes.json"

    def _bundled_metadata_path(self, catalog_name: str) -> Optional[Path]:
        name = (catalog_name or "").strip().lower()
        for catalog in DEFAULT_CONFIG.get("catalogs", []):
            if (catalog.get("name") or "").strip().lower() == name:
                meta_value = catalog.get("metadata_file")
                if not meta_value:
                    return None
                return (PROJECT_ROOT / meta_value).resolve()
        return None

    def _merge_metadata_updates(self, source_path: Path, target_path: Path, catalog_name: str) -> bool:
        try:
            source_data = json.loads(source_path.read_text(encoding="utf-8"))
            target_data = json.loads(target_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        source_entries = source_data.get(catalog_name, {})
        target_entries = target_data.get(catalog_name, {})
        if not isinstance(source_entries, dict) or not isinstance(target_entries, dict):
            return False
        updated = False
        fields = {
            "name",
            "type",
            "distance_ly",
            "discoverer",
            "discovery_year",
            "best_months",
            "constellation",
            "description",
            "external_link",
            "ra_hours",
            "dec_deg",
            "wiki_thumbnail",
        }
        force_fields = {"description", "external_link", "wiki_thumbnail"}
        for object_id, source_meta in source_entries.items():
            if not isinstance(source_meta, dict):
                continue
            target_meta = target_entries.get(object_id)
            if not isinstance(target_meta, dict):
                target_entries[object_id] = dict(source_meta)
                updated = True
                continue
            for field in fields:
                if field in source_meta and field in force_fields:
                    value = source_meta.get(field)
                    if target_meta.get(field) != value:
                        target_meta[field] = value
                        updated = True
                    continue
                value = source_meta.get(field)
                if value is None or value == "":
                    continue
                if target_meta.get(field) != value:
                    target_meta[field] = value
                    updated = True
        for object_id in list(target_entries.keys()):
            if object_id not in source_entries:
                continue
        if updated:
            target_data[catalog_name] = target_entries
            try:
                target_path.write_text(json.dumps(target_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            except OSError:
                return False
        return updated

    def _cleanup_invalid_image_only_entries(self) -> None:
        # Legacy cleanup targeted mutable user metadata mirrors. Catalog files are now authoritative.
        # Keep the method callable from older UI paths but do not mutate bundled catalog sources.
        return

    def clear_thumbnail_cache(self) -> bool:
        try:
            self.thumbnail_cache.clear()
            self.model.update_cache(self.thumbnail_cache)
            self._refresh_catalog()
            return True
        except Exception:
            return False

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(0)

        self.toolbar_container = QtWidgets.QWidget()
        toolbar = QtWidgets.QHBoxLayout(self.toolbar_container)
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(10)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText(tr("main.search.placeholder"))
        self.search.setClearButtonEnabled(False)
        clear_icon = self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_LineEditClearButton)
        self.search_clear_action = self.search.addAction(
            clear_icon,
            QtWidgets.QLineEdit.ActionPosition.TrailingPosition,
        )
        self.search_clear_action.triggered.connect(self._clear_search)
        self.search_clear_action.setVisible(False)
        self.search.textChanged.connect(self._on_search_changed)
        self.search.setMinimumWidth(280)
        self.search.setMaximumWidth(700)
        self.search.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self._search_min_width = self.search.minimumWidth()
        self._search_max_width = self.search.maximumWidth()
        self.catalog_title = QtWidgets.QLabel("")
        self.catalog_title.setObjectName("catalogTitle")
        self.catalog_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        self.catalog_title.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.catalog_count = QtWidgets.QLabel("")
        self.catalog_count.setObjectName("catalogSummary")
        self.catalog_count.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        self.catalog_count.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.catalog_summary_container = QtWidgets.QWidget()
        summary_layout = QtWidgets.QVBoxLayout(self.catalog_summary_container)
        summary_layout.setContentsMargins(8, 0, 8, 0)
        summary_layout.setSpacing(0)
        summary_layout.addWidget(self.catalog_title)
        summary_layout.addWidget(self.catalog_count)

        self.controls_container = QtWidgets.QWidget()
        controls_layout = QtWidgets.QHBoxLayout(self.controls_container)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(10)

        self.catalog_filter = QtWidgets.QComboBox()
        self.catalog_filter.currentTextChanged.connect(self._on_catalog_changed)
        self.catalog_filter.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.catalog_filter.setMinimumContentsLength(12)

        self.type_filter = QtWidgets.QComboBox()
        self.type_filter.currentTextChanged.connect(self._on_type_changed)
        self.type_filter.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.type_filter.setMinimumContentsLength(18)

        self.status_filter = QtWidgets.QComboBox()
        self.status_filter.currentTextChanged.connect(self._on_status_changed)
        self.status_filter.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.status_filter.setMinimumContentsLength(12)

        self.zoom_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(80, 360)
        self.zoom_slider.setValue(self.thumbnail_cache.thumb_size)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)

        self.wiki_thumbs = QtWidgets.QCheckBox(tr("main.wiki_thumbnails"))
        self.wiki_thumbs.setChecked(bool(self.config.get("use_wiki_thumbnails", False)))
        self.wiki_thumbs.toggled.connect(self._on_wiki_thumbs_toggled)
        self.refresh_button = QtWidgets.QPushButton(tr("main.refresh"))
        self.refresh_button.clicked.connect(self._refresh_catalog)
        self.settings_button = QtWidgets.QPushButton(tr("main.settings"))
        self.settings_button.clicked.connect(self._open_settings)
        self.about_button = QtWidgets.QPushButton(tr("main.about"))
        self.about_button.clicked.connect(self._open_about)

        self.compact_filters_container = QtWidgets.QWidget()
        compact_filters_layout = QtWidgets.QHBoxLayout(self.compact_filters_container)
        compact_filters_layout.setContentsMargins(0, 0, 0, 0)
        compact_filters_layout.setSpacing(8)

        self.compact_toolbar_catalog_button = QtWidgets.QToolButton()
        self.compact_toolbar_catalog_button.setText(tr("main.catalog"))
        self.compact_toolbar_catalog_button.setToolTip(tr("main.catalog"))
        self.compact_toolbar_catalog_button.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.compact_toolbar_catalog_button.setProperty("compactPill", True)
        self.compact_toolbar_catalog_menu = QtWidgets.QMenu(self)
        self.compact_toolbar_catalog_button.setMenu(self.compact_toolbar_catalog_menu)

        self.compact_toolbar_type_button = QtWidgets.QToolButton()
        self.compact_toolbar_type_button.setText(tr("main.object_type"))
        self.compact_toolbar_type_button.setToolTip(tr("main.object_type"))
        self.compact_toolbar_type_button.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.compact_toolbar_type_button.setProperty("compactPill", True)
        self.compact_toolbar_type_menu = QtWidgets.QMenu(self)
        self.compact_toolbar_type_button.setMenu(self.compact_toolbar_type_menu)

        self.compact_toolbar_status_button = QtWidgets.QToolButton()
        self.compact_toolbar_status_button.setText(tr("main.status"))
        self.compact_toolbar_status_button.setToolTip(tr("main.status"))
        self.compact_toolbar_status_button.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.compact_toolbar_status_button.setProperty("compactPill", True)
        self.compact_toolbar_status_menu = QtWidgets.QMenu(self)
        self.compact_toolbar_status_button.setMenu(self.compact_toolbar_status_menu)

        pill_label = tr("main.object_type")
        pill_width = QtGui.QFontMetrics(self.compact_toolbar_type_button.font()).horizontalAdvance(
            pill_label
        ) + 32
        for button in (
            self.compact_toolbar_catalog_button,
            self.compact_toolbar_type_button,
            self.compact_toolbar_status_button,
        ):
            button.setFixedWidth(pill_width)
            button.setFixedHeight(32)

        compact_filters_layout.addWidget(self.compact_toolbar_catalog_button)
        compact_filters_layout.addWidget(self.compact_toolbar_type_button)
        compact_filters_layout.addWidget(self.compact_toolbar_status_button)
        self.compact_filters_container.setVisible(False)

        self.toolbar_right_container = QtWidgets.QWidget()
        right_layout = QtWidgets.QHBoxLayout(self.toolbar_right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        toolbar.addWidget(self.search)
        toolbar.addStretch(1)
        toolbar.addWidget(self.catalog_summary_container)
        toolbar.addStretch(1)
        self.catalog_label = QtWidgets.QLabel(tr("main.catalog"))
        self.type_label = QtWidgets.QLabel(tr("main.object_type"))
        self.status_filter_label = QtWidgets.QLabel(tr("main.status"))
        controls_layout.addWidget(self.catalog_label)
        controls_layout.addWidget(self.catalog_filter)
        controls_layout.addSpacing(6)
        controls_layout.addWidget(self.type_label)
        controls_layout.addWidget(self.type_filter)
        controls_layout.addSpacing(6)
        controls_layout.addWidget(self.status_filter_label)
        controls_layout.addWidget(self.status_filter)
        controls_layout.addWidget(self.settings_button)
        controls_layout.addWidget(self.about_button)
        right_layout.addWidget(self.controls_container)
        right_layout.addWidget(self.compact_filters_container)
        toolbar.addWidget(self.toolbar_right_container)

        self.grid_controls_container = QtWidgets.QWidget()
        grid_controls_layout = QtWidgets.QHBoxLayout(self.grid_controls_container)
        grid_controls_layout.setContentsMargins(0, 0, 0, 0)
        grid_controls_layout.setSpacing(10)
        self.zoom_label = QtWidgets.QLabel(tr("main.zoom"))
        grid_controls_layout.addWidget(self.zoom_label)
        grid_controls_layout.addWidget(self.zoom_slider)
        grid_controls_layout.addWidget(self.wiki_thumbs)
        grid_controls_layout.addWidget(self.refresh_button)
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.hide()

        layout.addWidget(self.toolbar_container)
        layout.addSpacing(2)
        layout.addWidget(self.grid_controls_container)
        layout.addSpacing(2)
        layout.addWidget(self.status_label)
        layout.addSpacing(2)

        self.grid = QtWidgets.QListView()
        self.grid.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
        self.grid.setResizeMode(QtWidgets.QListView.ResizeMode.Adjust)
        self.grid.setUniformItemSizes(True)
        self.grid.setSpacing(10)
        self.grid.setMouseTracking(True)
        self.grid.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self._update_grid_metrics(self.thumbnail_cache.thumb_size)
        self.grid.setItemDelegate(CatalogItemDelegate(self.grid))
        self.grid.setStyleSheet("QListView::item { margin: 2px; padding: 0px; border: none; }")
        self.grid.setModel(self.proxy)
        self.grid.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.grid.viewport().installEventFilter(self)

        self.detail = DetailPanel()
        self.detail.connect_notes_changed(self._on_notes_changed)
        self.detail.thumbnail_selected.connect(self._on_thumbnail_selected)
        self.detail.image_changed.connect(self._on_image_changed)
        self.detail.archive_requested.connect(self._on_archive_requested)
        self.detail.focus_mode_toggled.connect(self._on_detail_focus_mode_toggled)
        self.detail.navigation_requested.connect(self._navigate_images_and_filtered_items)
        self.detail.imaging_info_requested.connect(self._open_imaging_info_editor)
        self.model.wiki_thumbnail_loaded.connect(self._on_wiki_thumbnail_loaded)

        splitter = QtWidgets.QSplitter()
        splitter.addWidget(self.grid)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)
        splitter.setSizes([420, 980])
        splitter.splitterMoved.connect(self._schedule_auto_fit)
        self.splitter = splitter
        self._saved_main_sizes: Optional[List[int]] = None

        layout.addWidget(splitter, stretch=1)

        footer = QtWidgets.QHBoxLayout()
        footer.addStretch(1)
        layout.addLayout(footer)
        self.setCentralWidget(central)
        self._toolbar_full_width = self.toolbar_container.sizeHint().width()
        self._sync_grid_controls_width()

    def _on_detail_focus_mode_toggled(self, enabled: bool) -> None:
        if self.splitter is None:
            return
        self.detail.set_focus_mode(enabled)
        if enabled:
            current_sizes = self.splitter.sizes()
            if len(current_sizes) >= 2 and current_sizes[0] > 0 and current_sizes[1] > 0:
                self._saved_main_sizes = current_sizes
            self.grid.hide()
            self.grid_controls_container.hide()
            self.status_label.hide()
            self.splitter.setHandleWidth(0)
            self.splitter.setSizes([0, 1])
            return
        self.grid.show()
        self.grid_controls_container.show()
        self.status_label.setVisible(bool(self.status_label.text().strip()))
        self.splitter.setHandleWidth(6)
        self.splitter.setSizes(self._saved_main_sizes or [720, 480])
        self._sync_grid_controls_width()
        self._schedule_auto_fit()

    def _apply_dark_theme(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                background: #0b1220;
                color: #edf1f7;
                font-family: 'Segoe UI', 'Aptos', 'Helvetica Neue', Arial;
                selection-background-color: #d4a85f;
                selection-color: #08111d;
            }
            QLineEdit, QComboBox, QTextEdit {
                background: #121a2b;
                border: 1px solid #23314a;
                border-radius: 10px;
                padding: 8px 10px;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border-color: #d4a85f;
            }
            QToolButton[compactPill="true"] {
                background: #152038;
                border: 1px solid #2a3854;
                border-radius: 16px;
                padding: 5px 22px 5px 12px;
            }
            QToolButton[compactPill="true"]:hover { background: #1c2943; border-color: #45618a; }
            QToolButton[compactPill="true"]::menu-indicator { image: none; }
            QToolButton#focusToggleButton { background: #152038; border: 1px solid #3d5376; border-radius: 0px; padding: 0; }
            QToolButton#focusToggleButton:hover { background: #1f2e4a; border-color: #d4a85f; }
            QToolButton#focusToggleButton:pressed { background: #253657; }
            QListView {
                background: #08111d;
                border: 1px solid #1e2a42;
                border-radius: 14px;
                padding: 8px;
            }
            QSplitter::handle { background: #142038; }
            QSplitter::handle:horizontal { width: 6px; }
            QSplitter::handle:vertical { height: 6px; }
            QLabel#detailTitle {
                font-family: 'Georgia', 'Palatino Linotype', serif;
                font-size: 24px;
                font-weight: 700;
                letter-spacing: 0.5px;
                color: #f6f1e8;
            }
            QLabel#detailMetadata {
                color: #d7deea;
                background: transparent;
                padding: 4px 0;
            }
            QLabel#imageInfo { color: #8e9eb8; padding-top: 2px; }
            QLabel#catalogTitle { font-size: 18px; font-weight: 600; color: #d4a85f; }
            QLabel#welcomeTitle { font-size: 20px; font-weight: 600; }
            QLabel#aboutTitle { font-size: 22px; font-weight: 600; }
            QLabel#aboutVersion { color: #9aa6ba; }
            QLabel#aboutSectionTitle { font-size: 16px; font-weight: 600; }
            QLabel#aboutUpdateStatus a { color: #d4a85f; text-decoration: none; }
            QTextBrowser#welcomeBody { background: #11182a; border: 1px solid #1f2d46; border-radius: 12px; }
            QLabel#statusLabel { color: #d4a85f; padding: 6px 0; }
            QLabel#coordLabel { color: #9aa6ba; padding: 4px 0; }
            QLabel#supportLink { color: #9aa6ba; }
            QLabel#supportLink a { color: #d4a85f; text-decoration: none; }
            QLabel#externalLink { padding-top: 4px; }
            QLabel#externalLink a { color: #7db4ff; text-decoration: none; }
            QWidget#detailImageContainer {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #11192b, stop:1 #0d1524);
                border: 1px solid #1e2a42;
                border-radius: 18px;
            }
            QWidget#detailImageHeader {
                background: transparent;
                border: none;
            }
            QWidget#detailMetaPanel, QWidget#detailTextPanel {
                background: #11182a;
                border: 1px solid #1f2d46;
                border-radius: 16px;
            }
            QTextEdit#descriptionBox {
                background: #0e1625;
                border: 1px solid #22314c;
                border-radius: 12px;
                padding: 12px;
            }
            QTextEdit#notesBox {
                background: #111d25;
                border: 1px solid #27414d;
                border-radius: 12px;
                padding: 12px;
            }
            QMenu { background: #11192b; border: 1px solid #23314a; }
            QMenu::item { padding: 6px 14px; }
            QMenu::item:selected { background: #1f2b45; color: #ffffff; }
            QPushButton {
                background: #16223a;
                border: 1px solid #2a3854;
                border-radius: 10px;
                padding: 7px 14px;
            }
            QPushButton:hover { background: #1c2943; border-color: #45618a; }
            QPushButton:pressed { background: #223150; }
            QSlider::groove:horizontal { height: 6px; background: #1e2a42; border-radius: 3px; }
            QSlider::handle:horizontal { width: 14px; background: #d4a85f; margin: -4px 0; border-radius: 7px; }
            QScrollBar:vertical {
                background: #09111d;
                width: 12px;
                margin: 6px 2px 6px 2px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #23314a;
                min-height: 28px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover { background: #355179; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            """
        )

    def _sync_compact_combo_items(self, source: QtWidgets.QComboBox, target: QtWidgets.QComboBox) -> None:
        target.blockSignals(True)
        target.clear()
        for index in range(source.count()):
            target.addItem(source.itemText(index))
        target.setCurrentText(source.currentText())
        target.blockSignals(False)

    def _sync_compact_toolbar_menu(
        self,
        source: QtWidgets.QComboBox,
        menu: QtWidgets.QMenu,
        current_value: str,
        handler: Callable[[str], None],
    ) -> None:
        menu.clear()
        for index in range(source.count()):
            text = source.itemText(index)
            value = source.itemData(index)
            action = QtGui.QAction(text, menu)
            action.setCheckable(True)
            action.setChecked(value == current_value)
            action.triggered.connect(lambda _checked=False, selected=value: handler(selected))
            menu.addAction(action)

    def _sync_compact_filters(self) -> None:
        if self._syncing_compact:
            return
        if hasattr(self, "compact_catalog_filter"):
            self._sync_compact_combo_items(self.catalog_filter, self.compact_catalog_filter)
            self._sync_compact_combo_items(self.type_filter, self.compact_type_filter)
            self._sync_compact_combo_items(self.status_filter, self.compact_status_filter)
        if hasattr(self, "compact_toolbar_catalog_button"):
            self._sync_compact_toolbar_menu(
                self.catalog_filter,
                self.compact_toolbar_catalog_menu,
                self.catalog_filter.currentText(),
                self._on_compact_toolbar_catalog_changed,
            )
            self._sync_compact_toolbar_menu(
                self.type_filter,
                self.compact_toolbar_type_menu,
                self.type_filter.currentText(),
                self._on_compact_toolbar_type_changed,
            )
            self._sync_compact_toolbar_menu(
                self.status_filter,
                self.compact_toolbar_status_menu,
                self.status_filter.currentText(),
                self._on_compact_toolbar_status_changed,
            )
        self._sync_compact_state()
        self._sync_compact_toolbar_spacing()

    def _sync_compact_state(self) -> None:
        if not hasattr(self, "compact_zoom_slider"):
            return
        self.compact_zoom_slider.blockSignals(True)
        self.compact_zoom_slider.setValue(self.zoom_slider.value())
        self.compact_zoom_slider.blockSignals(False)
        self.compact_wiki_thumbs.blockSignals(True)
        self.compact_wiki_thumbs.setChecked(self.wiki_thumbs.isChecked())
        self.compact_wiki_thumbs.blockSignals(False)

    def _set_toolbar_compact(self, compact: bool) -> None:
        if compact == self._compact_toolbar:
            return
        self._compact_toolbar = compact
        self.controls_container.setVisible(not compact)
        if hasattr(self, "compact_filters_container"):
            self.compact_filters_container.setVisible(compact)
        if compact:
            self._sync_compact_filters()

    def _sync_compact_toolbar_spacing(self) -> None:
        if not hasattr(self, "toolbar_right_container"):
            return
        if self._compact_toolbar:
            search_width = self.search.width() or self.search.sizeHint().width()
            right_width = self.toolbar_right_container.sizeHint().width()
            target_width = min(search_width, right_width) if right_width else search_width
            if target_width:
                self.search.setMinimumWidth(target_width)
                self.search.setMaximumWidth(target_width)
                self.toolbar_right_container.setFixedWidth(target_width)
        else:
            self.search.setMinimumWidth(self._search_min_width)
            self.search.setMaximumWidth(self._search_max_width)
            self.toolbar_right_container.setMinimumWidth(0)
            self.toolbar_right_container.setMaximumWidth(16777215)

    def _update_toolbar_compact_mode(self) -> None:
        if not self._toolbar_full_width:
            self._toolbar_full_width = self.toolbar_container.sizeHint().width()
        if self.toolbar_container.width() == 0:
            return
        should_compact = self.toolbar_container.width() < self._toolbar_full_width
        self._set_toolbar_compact(should_compact)
        self._sync_compact_toolbar_spacing()

    def _apply_saved_window_state(self) -> None:
        state = self._saved_state or {}
        size = state.get("window_size")
        if isinstance(size, list) and len(size) == 2:
            self.resize(int(size[0]), int(size[1]))
        else:
            self.resize(1400, 900)
        splitter_sizes = state.get("splitter_sizes")
        if isinstance(splitter_sizes, list) and splitter_sizes:
            self.splitter.setSizes(self._normalized_main_splitter_sizes(splitter_sizes))

    @staticmethod
    def _normalized_main_splitter_sizes(sizes: List[int]) -> List[int]:
        if not sizes:
            return [420, 980]
        if len(sizes) == 1:
            left = max(320, int(sizes[0]))
            return [left, 980]
        left = max(320, int(sizes[0]))
        right = max(520, int(sizes[1]))
        return [left, right]

    def _set_status_message(self, text: str) -> None:
        self.status_label.setText(text)
        self.status_label.setVisible(bool(text.strip()))

    def _update_filters(self) -> None:
        catalogs = {item.catalog for item in self.items}
        configured = {c.get("name") for c in self.config.get("catalogs", []) if c.get("name")}
        catalogs = sorted(catalogs | configured)
        current_catalog = self._combo_value(self.catalog_filter) if self.catalog_filter.count() else ""
        self.catalog_filter.blockSignals(True)
        self.catalog_filter.clear()
        self._add_combo_item(self.catalog_filter, tr("catalog.all"), "")
        for name in catalogs:
            self._add_combo_item(self.catalog_filter, self._catalog_display_name(name), name)
        self._set_combo_value(self.catalog_filter, current_catalog, fallback="")
        self.catalog_filter.blockSignals(False)
        self.catalog_filter.view().setMinimumWidth(160)

        self._update_type_filter(current_catalog)

        current_status = self._combo_value(self.status_filter) if self.status_filter.count() else ""
        self.status_filter.blockSignals(True)
        self.status_filter.clear()
        self._add_combo_item(self.status_filter, tr("catalog.all"), "")
        self._add_combo_item(self.status_filter, tr("status.captured"), "Captured")
        self._add_combo_item(self.status_filter, tr("status.missing"), "Missing")
        self._add_combo_item(self.status_filter, tr("status.suggested"), "Suggested")
        self._set_combo_value(self.status_filter, current_status, fallback="")
        self.status_filter.blockSignals(False)
        self.status_filter.view().setMinimumWidth(160)
        self._update_catalog_summary()
        self._sync_compact_filters()

    def _refresh_catalog(self) -> None:
        self.config = load_config(self.config_path)
        if self._zoom_timer.isActive():
            self._zoom_timer.stop()
        self._start_catalog_load()

    def _on_selection_changed(self) -> None:
        self._flush_notes()
        indexes = self.grid.selectionModel().selectedIndexes()
        if not indexes:
            self.detail.update_item(None)
            self.detail.set_imaging_summary("")
            return
        source_index = self.proxy.mapToSource(indexes[0])
        item = self.model.data(source_index, QtCore.Qt.ItemDataRole.UserRole)
        self.detail.update_item(item)
        if item and not item.image_paths:
            pixmap = self.model.get_wiki_pixmap(item.unique_key)
            if pixmap:
                self.detail.set_wiki_pixmap(pixmap)
        self._refresh_current_image_imaging_summary()
        if item:
            self._notes_timer.start()

    def _on_image_changed(self, _image_name: str) -> None:
        self._flush_notes()
        self._refresh_current_image_imaging_summary()

    def _open_imaging_info_editor(self) -> None:
        item = self.detail.current_item()
        image_name = self.detail.current_image_name()
        if item is None or not image_name:
            QtWidgets.QMessageBox.information(
                self,
                tr("imaging.no_image_title"),
                tr("imaging.no_image_message"),
            )
            return
        try:
            note_id = self.database.ensure_image_note(
                image_name,
                title=image_name,
                status="active",
                legacy_source="app",
            )
            payload = self._load_imaging_payload(note_id)
            dialog = ImagingInfoDialog(self, setups=self._load_imaging_setups())
            dialog.set_payload(payload)
            dialog_result = dialog.exec()
            self._save_imaging_setups(dialog.setups_payload())
            if dialog_result != int(QtWidgets.QDialog.DialogCode.Accepted):
                return
            self._save_imaging_payload(note_id, dialog.payload())
            self._refresh_current_image_imaging_summary()
            self._set_status_message(tr("imaging.saved_status", name=image_name))
        except Exception as exc:
            QtWidgets.QMessageBox.warning(
                self,
                tr("imaging.error_title"),
                tr("imaging.error_message", error=exc),
            )

    def _load_imaging_setups(self) -> List[Dict[str, str]]:
        rows = self.database.list_imaging_setups()
        if rows:
            result: List[Dict[str, str]] = []
            for item in rows:
                name = str(item.get("name") or "").strip()
                if not name:
                    continue
                result.append(
                    {
                        "name": name,
                        "telescope_or_refractor": str(item.get("telescope_or_refractor") or "").strip(),
                        "camera": str(item.get("camera") or "").strip(),
                        "mount": str(item.get("mount") or "").strip(),
                        "accessories": str(item.get("accessories") or "").strip(),
                        "software": str(item.get("software") or "").strip(),
                        "guide_telescope": str(item.get("guide_telescope") or "").strip(),
                        "guide_camera": str(item.get("guide_camera") or "").strip(),
                    }
                )
            return result

        # Backward compatibility: migrate old settings storage if present.
        legacy_payload = self.database.get_setting("imaging_setups", default=[])
        if isinstance(legacy_payload, list) and legacy_payload:
            self._save_imaging_setups(legacy_payload)
            self.database.delete_setting("imaging_setups")
            return self._load_imaging_setups()

        return []

    def _save_imaging_setups(self, setups: List[Dict[str, str]]) -> None:
        normalized: List[Dict[str, str]] = []
        seen: set[str] = set()
        for setup in setups:
            if not isinstance(setup, dict):
                continue
            name = str(setup.get("name") or "").strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(
                {
                    "name": name,
                    "telescope_or_refractor": str(setup.get("telescope_or_refractor") or "").strip(),
                    "camera": str(setup.get("camera") or "").strip(),
                    "mount": str(setup.get("mount") or "").strip(),
                    "accessories": str(setup.get("accessories") or "").strip(),
                    "software": str(setup.get("software") or "").strip(),
                    "guide_telescope": str(setup.get("guide_telescope") or "").strip(),
                    "guide_camera": str(setup.get("guide_camera") or "").strip(),
                }
            )

        self.database.replace_imaging_setups(normalized)

    def _load_imaging_payload(self, note_id: int) -> Dict:
        return {
            "capture_location": self.database.get_capture_location(note_id),
            "integrations": self.database.list_filter_integrations(note_id),
            "imaging_equipment": self.database.get_imaging_equipment(note_id) or {},
            "guiding_equipment": self.database.get_guiding_equipment(note_id) or {},
        }

    def _save_imaging_payload(self, note_id: int, payload: Dict) -> None:
        self.database.upsert_capture_location(note_id, str(payload.get("capture_location") or ""))
        self.database.replace_filter_integrations(note_id, payload.get("integrations", []))

        imaging = payload.get("imaging_equipment") or {}
        self.database.upsert_imaging_equipment(
            note_id,
            telescope_or_refractor=imaging.get("telescope_or_refractor"),
            camera=imaging.get("camera"),
            mount=imaging.get("mount"),
            accessories=imaging.get("accessories"),
            software=imaging.get("software"),
        )

        guiding = payload.get("guiding_equipment") or {}
        self.database.upsert_guiding_equipment(
            note_id,
            guide_telescope=guiding.get("guide_telescope"),
            guide_camera=guiding.get("guide_camera"),
        )

    def _refresh_current_image_imaging_summary(self) -> None:
        image_name = self.detail.current_image_name()
        if not image_name:
            self.detail.set_imaging_summary("")
            return
        note = self.database.get_note_by_image_id(image_name)
        if not note:
            self.detail.set_imaging_summary("")
            return

        note_id = int(note["note_id"])
        location = self.database.get_capture_location(note_id)
        integrations = self.database.list_filter_integrations(note_id)
        imaging = self.database.get_imaging_equipment(note_id) or {}
        guiding = self.database.get_guiding_equipment(note_id) or {}

        total_seconds = 0.0
        raw_filters: List[str] = []
        for row in integrations:
            exposure = float(row.get("exposure_seconds") or 0.0)
            frames = int(row.get("subframe_count") or 0)
            total_seconds += max(0.0, exposure) * max(0, frames)
            name = str(row.get("filter_name") or "").strip()
            if name:
                raw_filters.append(name)

        filters_display = self._ordered_filter_summary(raw_filters)

        lines: List[str] = []
        if location:
            lines.append(tr("imaging.summary_location", value=location))
        if integrations:
            lines.append(
                tr(
                    "imaging.summary_integrations",
                    duration=self._format_duration_short(total_seconds),
                    filters=filters_display or tr("imaging.summary_filters_none"),
                )
            )
        else:
            lines.append(tr("imaging.summary_integrations_none"))

        imaging_parts = [
            str(imaging.get("telescope_or_refractor") or "").strip(),
            str(imaging.get("camera") or "").strip(),
            str(imaging.get("mount") or "").strip(),
        ]
        imaging_text = " | ".join(part for part in imaging_parts if part)
        if imaging_text:
            lines.append(tr("imaging.summary_imaging", value=imaging_text))

        guiding_parts = [
            str(guiding.get("guide_telescope") or "").strip(),
            str(guiding.get("guide_camera") or "").strip(),
        ]
        guiding_text = " | ".join(part for part in guiding_parts if part)
        if guiding_text:
            lines.append(tr("imaging.summary_guiding", value=guiding_text))

        self.detail.set_imaging_summary("\n".join(lines))

    @staticmethod
    def _format_duration_short(total_seconds: float) -> str:
        seconds = int(max(0.0, total_seconds))
        hours, rem = divmod(seconds, 3600)
        minutes, _ = divmod(rem, 60)
        if hours > 0:
            return f"{hours}h{minutes:02d}"
        return f"{minutes}m"

    @staticmethod
    def _canonical_filter_name(name: str) -> Optional[str]:
        raw = (name or "").strip().upper()
        if not raw:
            return None

        # Keep only ASCII letters/digits for robust matching (e.g. H-alpha, Hα).
        normalized = "".join(ch for ch in raw if ("A" <= ch <= "Z") or ("0" <= ch <= "9"))

        if normalized in {"L", "LUM", "LUMINANCE"}:
            return "L"
        if normalized in {"R", "RED"}:
            return "R"
        if normalized in {"G", "GREEN"}:
            return "G"
        if normalized in {"B", "BLUE"}:
            return "B"
        if normalized in {"S", "SII", "S2"}:
            return "S"
        if normalized in {"H", "HA", "HALPHA"}:
            return "H"
        if normalized in {"O", "OIII", "O3"}:
            return "O"
        return None

    @classmethod
    def _ordered_filter_summary(cls, names: List[str]) -> str:
        ordered_groups = ["L", "R", "G", "B", "S", "H", "O"]
        present: set[str] = set()
        extras: List[str] = []

        for name in names:
            cleaned = str(name or "").strip()
            if not cleaned:
                continue
            canonical = cls._canonical_filter_name(cleaned)
            if canonical:
                present.add(canonical)
                continue
            if cleaned not in extras:
                extras.append(cleaned)

        result = [group for group in ordered_groups if group in present]
        result.extend(extras)
        return ", ".join(result)

    def _on_catalog_changed(self, _value: str) -> None:
        value = self._combo_value(self.catalog_filter)
        self.proxy.set_catalog_filter(value)
        self._update_type_filter(value)
        self._update_catalog_summary()
        self._schedule_auto_fit()
        if not self._syncing_compact:
            self._sync_compact_filters()

    def _on_type_changed(self, _value: str) -> None:
        value = self._combo_value(self.type_filter)
        self.proxy.set_type_filter(value)
        self._schedule_auto_fit()
        if not self._syncing_compact:
            self._sync_compact_filters()

    def _on_status_changed(self, _value: str) -> None:
        value = self._combo_value(self.status_filter)
        self.proxy.set_status_filter(value)
        self._schedule_auto_fit()
        if not self._syncing_compact:
            self._sync_compact_filters()

    def _on_search_changed(self, text: str) -> None:
        self._update_search_clear_action(text)
        self.proxy.set_search_text(text)
        self._schedule_auto_fit()

    def _clear_search(self) -> None:
        self.search.clear()

    def _update_search_clear_action(self, text: str) -> None:
        if not hasattr(self, "search_clear_action"):
            return
        self.search_clear_action.setVisible(bool((text or "").strip()))

    def _on_compact_catalog_changed(self, value: str) -> None:
        if self._syncing_compact:
            return
        self._syncing_compact = True
        try:
            self.catalog_filter.setCurrentText(value)
        finally:
            self._syncing_compact = False

    def _on_compact_toolbar_catalog_changed(self, value: str) -> None:
        if self._syncing_compact:
            return
        self._syncing_compact = True
        try:
            self.catalog_filter.setCurrentText(value)
        finally:
            self._syncing_compact = False

    def _on_compact_type_changed(self, value: str) -> None:
        if self._syncing_compact:
            return
        self._syncing_compact = True
        try:
            self.type_filter.setCurrentText(value)
        finally:
            self._syncing_compact = False

    def _on_compact_toolbar_type_changed(self, value: str) -> None:
        if self._syncing_compact:
            return
        self._syncing_compact = True
        try:
            self.type_filter.setCurrentText(value)
        finally:
            self._syncing_compact = False

    def _on_compact_status_changed(self, value: str) -> None:
        if self._syncing_compact:
            return
        self._syncing_compact = True
        try:
            self.status_filter.setCurrentText(value)
        finally:
            self._syncing_compact = False

    def _on_compact_toolbar_status_changed(self, value: str) -> None:
        if self._syncing_compact:
            return
        self._syncing_compact = True
        try:
            self.status_filter.setCurrentText(value)
        finally:
            self._syncing_compact = False

    def _on_compact_zoom_changed(self, value: int) -> None:
        if self._syncing_compact:
            return
        self._syncing_compact = True
        try:
            self.zoom_slider.setValue(value)
        finally:
            self._syncing_compact = False

    def _on_compact_wiki_toggled(self, enabled: bool) -> None:
        if self._syncing_compact:
            return
        self._syncing_compact = True
        try:
            self.wiki_thumbs.setChecked(enabled)
        finally:
            self._syncing_compact = False

    def _update_catalog_summary(self) -> None:
        current = self._combo_value(self.catalog_filter)
        if not current:
            filtered = self.items
            title = tr("catalog.all_catalogues")
        else:
            filtered = [item for item in self.items if item.catalog == current]
            title = self._catalog_title_text(current)
        total = len(filtered)
        captured = sum(1 for item in filtered if item.image_paths)
        self.catalog_title.setText(title)
        self.catalog_count.setText(tr("main.captured_count", captured=captured, total=total))

    @staticmethod
    def _combo_value(combo: QtWidgets.QComboBox) -> str:
        data = combo.currentData()
        if isinstance(data, str):
            return data
        return combo.currentText()

    @staticmethod
    def _add_combo_item(combo: QtWidgets.QComboBox, text: str, value: str) -> None:
        combo.addItem(text, value)

    @staticmethod
    def _set_combo_value(combo: QtWidgets.QComboBox, value: str, fallback: str = "") -> None:
        index = combo.findData(value)
        if index < 0:
            index = combo.findData(fallback)
        if index < 0 and combo.count():
            index = 0
        if index >= 0:
            combo.setCurrentIndex(index)

    @staticmethod
    def _catalog_display_name(name: str) -> str:
        base = tr("catalog.solar_system") if name == "Solar system" else name
        if name in {"IC"}:
            return tr("catalog.in_progress", catalog=base)
        return base

    @staticmethod
    def _catalog_title_text(title: str) -> str:
        if title in {"IC"}:
            return tr("catalog.in_progress", catalog=title)
        base = tr("catalog.solar_system") if title == "Solar system" else title
        return tr("catalog.summary_title", catalog=base)

    @staticmethod
    def _catalog_internal_name(display_name: str) -> str:
        return display_name.replace(" (In progress)", "")

    def _update_type_filter(self, catalog_value: str) -> None:
        current_type = self._combo_value(self.type_filter) if self.type_filter.count() else ""
        if catalog_value:
            filtered = [item for item in self.items if item.catalog == catalog_value]
            types = collect_object_types(filtered)
        else:
            types = collect_object_types(self.items)
        self.type_filter.blockSignals(True)
        self.type_filter.clear()
        self._add_combo_item(self.type_filter, tr("catalog.all"), "")
        for object_type in types:
            if is_hidden_object_type(object_type):
                continue
            self._add_combo_item(
                self.type_filter,
                localized_object_type(object_type) or object_type,
                object_type,
            )
        self._set_combo_value(self.type_filter, current_type, fallback="")
        self.type_filter.blockSignals(False)
        self.type_filter.view().setMinimumWidth(220)
        self._sync_compact_filters()

    def _on_zoom_changed(self, value: int) -> None:
        self._auto_fit_enabled = False
        self._pending_zoom = value
        self._zoom_timer.start()
        if not self._syncing_compact:
            self._sync_compact_state()

    def _apply_zoom(self) -> None:
        value = self._pending_zoom
        self._update_grid_metrics(value)
        self.config["thumb_size"] = value
        save_config(self.config_path, self.config)
        self.thumbnail_cache = ThumbnailCache(self._cache_dir(), value)
        self.model.update_cache(self.thumbnail_cache)
        self._schedule_view_refresh()

    def _schedule_auto_fit(self) -> None:
        if self._suppress_auto_fit:
            self._schedule_view_refresh()
            return
        if self._auto_fit_enabled:
            self._auto_fit_timer.start()
        else:
            self._schedule_view_refresh()

    def _auto_fit_thumbnails(self) -> None:
        if not self._auto_fit_enabled:
            return
        item_count = self.proxy.rowCount()
        if item_count <= 0:
            return
        width = self.grid.viewport().width()
        height = self.grid.viewport().height()
        if width <= 0 or height <= 0:
            return
        spacing = self.grid.spacing()
        grid_extra = 2
        min_size = 60
        max_size = max(min(width, height), min_size)
        best = min_size
        best_gap = width

        max_columns = min(item_count, max(1, width // min_size))
        for columns in range(1, max_columns + 1):
            rows = (item_count + columns - 1) // columns
            grid_size_w = (width + spacing) // columns - spacing
            grid_size_h = (height + spacing) // rows - spacing
            grid_size = min(grid_size_w, grid_size_h)
            size = grid_size - grid_extra
            if size < min_size:
                continue
            if size > max_size:
                size = max_size
            grid_size = size + grid_extra
            used_width = max(0, columns * (grid_size + spacing) - spacing)
            gap = max(0, width - used_width)
            if gap < best_gap or (gap == best_gap and size > best):
                best = size
                best_gap = gap
        self.grid.setIconSize(QtCore.QSize(best, best))
        self._update_grid_metrics(best)
        self.zoom_slider.blockSignals(True)
        self.zoom_slider.setValue(best)
        self.zoom_slider.blockSignals(False)
        self.config["thumb_size"] = best
        save_config(self.config_path, self.config)
        self.thumbnail_cache = ThumbnailCache(self._cache_dir(), best)
        self.model.update_cache(self.thumbnail_cache)
        self._schedule_view_refresh()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_toolbar_compact_mode()
        self._sync_grid_controls_width()
        self._schedule_auto_fit()

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        self._update_toolbar_compact_mode()
        self._sync_grid_controls_width()
        QtCore.QTimer.singleShot(0, self._sync_grid_controls_width)
        if self._suppress_auto_fit:
            QtCore.QTimer.singleShot(250, self._disable_startup_auto_fit)

    def _disable_startup_auto_fit(self) -> None:
        self._suppress_auto_fit = False

    def _sync_grid_controls_width(self) -> None:
        if not hasattr(self, "grid_controls_container"):
            return
        if not hasattr(self, "search"):
            return
        target_width = self.search.width()
        if not target_width:
            target_width = self.search.sizeHint().width()
        if target_width:
            self.grid_controls_container.setFixedWidth(target_width)

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if obj is self.grid.viewport() and event.type() == QtCore.QEvent.Type.Resize:
            self._schedule_auto_fit()
        return super().eventFilter(obj, event)

    def _navigate_images_and_filtered_items(self, direction: int) -> bool:
        if direction == 0 or self.proxy.rowCount() == 0:
            return False
        if self.detail.navigate_images(direction):
            return True

        current_index = self.grid.currentIndex()
        if not current_index.isValid():
            selected = self.grid.selectionModel().selectedIndexes()
            current_index = selected[0] if selected else QtCore.QModelIndex()
        if not current_index.isValid():
            return False

        next_row = current_index.row() + direction
        if next_row < 0 or next_row >= self.proxy.rowCount():
            return False

        next_index = self.proxy.index(next_row, 0)
        if not next_index.isValid():
            return False

        self.grid.setCurrentIndex(next_index)
        self.grid.selectionModel().select(
            next_index,
            QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )

        source_index = self.proxy.mapToSource(next_index)
        next_item = self.model.data(source_index, QtCore.Qt.ItemDataRole.UserRole)
        if next_item and next_item.image_paths:
            edge_name = next_item.image_paths[0].name if direction > 0 else next_item.image_paths[-1].name
            QtCore.QTimer.singleShot(0, lambda: self.detail.set_current_image_by_name(edge_name))
        return True

    def _schedule_view_refresh(self) -> None:
        if self._loading:
            return
        QtCore.QTimer.singleShot(0, self._refresh_view)

    def _refresh_view(self) -> None:
        if self._loading:
            return
        self.grid.doItemsLayout()
        self.grid.viewport().update()

    def _open_settings(self) -> None:
        base_config = self.config
        dialog = SettingsDialog(self.config, self)
        dialog.previewChanged.connect(self._preview_settings_changed)
        result = dialog.exec()
        if result != QtWidgets.QDialog.DialogCode.Accepted:
            if self._preview_active:
                self._preview_active = False
                self._start_catalog_load(base_config)
            return
        previous_ui_locale = str(self.config.get("ui_locale") or "system")
        self.config = dialog.updated_config
        self.user_notes_path = self._user_notes_path()
        save_config(self.config_path, self.config)
        self.thumbnail_cache = ThumbnailCache(self._cache_dir(), self.config.get("thumb_size", 240))
        self._auto_fit_enabled = True
        self._start_catalog_load()
        self._preview_active = False
        if str(self.config.get("ui_locale") or "system") != previous_ui_locale:
            QtWidgets.QMessageBox.information(
                self,
                tr("settings.locale_restart_needed_title"),
                tr("settings.locale_restart_needed_message"),
            )

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self._closing = True
        SHUTDOWN_EVENT.set()
        self._thread_pool.clear()
        self._thread_pool.waitForDone(1500)
        self._persist_ui_state()
        super().closeEvent(event)

    def _start_catalog_load(self, config_override: Optional[Dict] = None) -> None:
        config = config_override or self.config
        if self._loading:
            self._pending_reload = True
            self._pending_config = config
            return
        if self._zoom_timer.isActive():
            self._zoom_timer.stop()
        self._loading = True
        self._loading_config = config
        self._set_ui_enabled(False)
        self._set_status_message(tr("main.loading_catalog"))
        task = CatalogLoadTask(config, self.user_notes_path)
        task.signals.loaded.connect(self._on_catalog_loaded)
        self._catalog_pool.start(task)

    def _on_catalog_loaded(self, items: List[CatalogItem]) -> None:
        self.items = items
        self.model.set_items(self.items)
        wiki_enabled = bool(self._loading_config.get("use_wiki_thumbnails", False))
        self.model.set_wiki_thumbnails_enabled(wiki_enabled)
        self._update_filters()
        if not self._saved_state_applied:
            self._apply_saved_filters()
            self._saved_state_applied = True
        self._schedule_view_refresh()
        self._set_status_message("")
        self._loading = False
        self._set_ui_enabled(True)
        if self._pending_selection_key:
            QtCore.QTimer.singleShot(150, self._restore_pending_selection)
        else:
            QtCore.QTimer.singleShot(150, self._select_first_item)
        if self._pending_reload:
            pending = self._pending_config
            self._pending_reload = False
            self._pending_config = None
            self._start_catalog_load(pending)

    def _select_first_item(self) -> None:
        if self.grid.selectionModel().hasSelection():
            return
        if self.proxy.rowCount() == 0:
            return
        index = self.proxy.index(0, 0)
        if not index.isValid():
            return
        self.grid.setCurrentIndex(index)
        self.grid.selectionModel().select(
            index, QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect
        )

    def _restore_pending_selection(self) -> None:
        key = self._pending_selection_key
        image_name = self._pending_image_name
        self._pending_selection_key = None
        self._pending_image_name = None
        if not key:
            self._select_first_item()
            return
        source_index = self.model.index_for_key(key)
        if source_index is None or not source_index.isValid():
            self._select_first_item()
            return
        proxy_index = self.proxy.mapFromSource(source_index)
        if not proxy_index.isValid():
            self._select_first_item()
            return
        self.grid.setCurrentIndex(proxy_index)
        self.grid.selectionModel().select(
            proxy_index, QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect
        )
        if image_name:
            QtCore.QTimer.singleShot(0, lambda: self.detail.set_current_image_by_name(image_name))

    def _update_grid_metrics(self, size: int) -> None:
        self.grid.setIconSize(QtCore.QSize(size, size))
        self.grid.setGridSize(QtCore.QSize(size + 18, size + 28))

    def _set_ui_enabled(self, enabled: bool) -> None:
        self.search.setEnabled(enabled)
        self.catalog_filter.setEnabled(enabled)
        self.type_filter.setEnabled(enabled)
        self.status_filter.setEnabled(enabled)
        self.zoom_slider.setEnabled(enabled)
        self.grid.setEnabled(enabled)
        self.wiki_thumbs.setEnabled(enabled)
        self.refresh_button.setEnabled(enabled)
        self.settings_button.setEnabled(enabled)
        self.about_button.setEnabled(enabled)
        if hasattr(self, "compact_catalog_filter"):
            self.compact_catalog_filter.setEnabled(enabled)
            self.compact_type_filter.setEnabled(enabled)
            self.compact_status_filter.setEnabled(enabled)
            self.compact_zoom_slider.setEnabled(enabled)
            self.compact_wiki_thumbs.setEnabled(enabled)
            self.compact_refresh_button.setEnabled(enabled)
            self.compact_settings_button.setEnabled(enabled)
            self.compact_about_button.setEnabled(enabled)
        if hasattr(self, "compact_toolbar_catalog_button"):
            self.compact_toolbar_catalog_button.setEnabled(enabled)
            self.compact_toolbar_type_button.setEnabled(enabled)
            self.compact_toolbar_status_button.setEnabled(enabled)

    def _preview_settings_changed(self, config: Dict) -> None:
        self._preview_active = True
        self._start_catalog_load(config)

    def _on_notes_changed(self) -> None:
        if self.detail.notes_blocked():
            return
        item = self.detail.current_item()
        if item is None:
            return
        image_name = self.detail.current_image_name()
        note_key = f"{item.unique_key}::{image_name or ''}"
        self._pending_notes[note_key] = (item.catalog, item.object_id, image_name, self.detail.current_notes())
        self._notes_timer.start()

    def _on_thumbnail_selected(self, catalog: str, object_id: str, thumbnail_name: str) -> None:
        metadata_path = resolve_metadata_path(self.config, catalog)
        if metadata_path is None:
            return
        save_thumbnail(
            metadata_path,
            catalog,
            object_id,
            thumbnail_name,
            user_notes_path=self.user_notes_path,
        )
        item = self.detail.current_item()
        if item:
            self.model.update_item_thumbnail(item.unique_key, thumbnail_name)

    def _on_wiki_thumbs_toggled(self, enabled: bool) -> None:
        self.config["use_wiki_thumbnails"] = bool(enabled)
        save_config(self.config_path, self.config)
        self.model.set_wiki_thumbnails_enabled(bool(enabled))
        current = self.detail.current_item()
        if current and not current.image_paths and not enabled:
            self.detail.update_item(current)
        self._schedule_view_refresh()
        if not self._syncing_compact:
            self._sync_compact_state()

    def _open_about(self) -> None:
        if self._about_dialog and self._about_dialog.isVisible():
            self._about_dialog.raise_()
            self._about_dialog.activateWindow()
            return
        dialog = AboutDialog(self.config, APP_VERSION, self._data_version, self)
        dialog.check_updates_requested.connect(self._check_updates_user)
        dialog.auto_check_toggled.connect(self._set_auto_check_updates)
        dialog.set_update_status(self._update_status, self._latest_version, self._update_url)
        dialog.set_data_update_status(self._data_update_status)
        dialog.set_remote_data_version(self._remote_data_version, self._data_version)
        self._about_dialog = dialog
        dialog.finished.connect(lambda _result: self._clear_about_dialog())
        dialog.show()

    def _clear_about_dialog(self) -> None:
        self._about_dialog = None

    def _set_auto_check_updates(self, enabled: bool) -> None:
        self.config["auto_check_updates"] = bool(enabled)
        save_config(self.config_path, self.config)

    def _start_data_version_fetch(self) -> None:
        if self._data_version_task is not None:
            return
        task = DataVersionFetchTask(DATA_VERSION_URL)
        task.signals.loaded.connect(self._apply_remote_data_version)
        task.signals.failed.connect(self._data_version_fetch_failed)
        self._data_version_task = task
        self._thread_pool.start(task)

    def _apply_remote_data_version(self, version: str) -> None:
        self._data_version_task = None
        if not version:
            self._data_update_status = tr("updates.data_unavailable")
            if self._about_dialog:
                self._about_dialog.set_data_update_status(self._data_update_status)
                self._about_dialog.set_remote_data_version(None, self._data_version)
            return
        self._remote_data_version = version
        if version != self._data_version:
            self._data_update_status = tr("updates.data_available", remote=version, installed=self._data_version)
        else:
            self._data_update_status = tr("updates.data_uptodate")
        if self._about_dialog:
            self._about_dialog.set_data_update_status(self._data_update_status)
            self._about_dialog.set_remote_data_version(version, self._data_version)

    def _data_version_fetch_failed(self, _message: str) -> None:
        self._data_version_task = None
        self._data_update_status = tr("updates.data_check_failed")
        if self._about_dialog:
            self._about_dialog.set_data_update_status(self._data_update_status)
            self._about_dialog.set_remote_data_version(None, self._data_version)

    def _check_updates_silent(self) -> None:
        self._start_update_check(silent=True)

    def _check_updates_user(self) -> None:
        self._start_update_check(silent=False)

    def _start_update_check(self, silent: bool) -> None:
        task = UpdateCheckTask(APP_VERSION)
        self._update_tasks.append(task)
        task.signals.available.connect(lambda tag, url: self._on_update_available(tag, url, silent))
        task.signals.up_to_date.connect(lambda tag: self._on_update_uptodate(tag, silent))
        task.signals.failed.connect(lambda message: self._on_update_failed(message, silent))
        task.signals.finished.connect(lambda: self._discard_update_task(task))
        self._thread_pool.start(task)

    def _discard_update_task(self, task: UpdateCheckTask) -> None:
        if task in self._update_tasks:
            self._update_tasks.remove(task)

    def _on_update_available(self, tag: str, url: str, silent: bool) -> None:
        if self._closing:
            return
        self._update_status = tr("updates.status_available", tag=tag)
        self._latest_version = tag
        self._update_url = url
        if self._about_dialog:
            self._about_dialog.set_update_status(self._update_status, self._latest_version, self._update_url)
        elif not silent:
            QtWidgets.QMessageBox.information(
                self,
                tr("updates.available_title"),
                tr("updates.available_message", tag=tag),
            )

    def _on_update_uptodate(self, tag: str, silent: bool) -> None:
        if self._closing:
            return
        self._update_status = tr("updates.status_uptodate", tag=tag)
        self._latest_version = tag
        self._update_url = None
        if self._about_dialog:
            self._about_dialog.set_update_status(self._update_status, self._latest_version, self._update_url)
        elif not silent:
            QtWidgets.QMessageBox.information(
                self,
                tr("updates.uptodate_title"),
                tr("updates.uptodate_message", tag=tag),
            )

    def _on_update_failed(self, message: str, silent: bool) -> None:
        if self._closing:
            return
        self._update_status = message
        self._latest_version = None
        self._update_url = None
        if self._about_dialog:
            self._about_dialog.set_update_status(self._update_status, self._latest_version, self._update_url)
        elif not silent:
            QtWidgets.QMessageBox.warning(self, tr("updates.check_failed_title"), message)

    def _on_wiki_thumbnail_loaded(self, item_key: str, pixmap: QtGui.QPixmap) -> None:
        current = self.detail.current_item()
        if not current or current.unique_key != item_key:
            return
        if current.image_paths:
            return
        self.detail.set_wiki_pixmap(pixmap)

    @staticmethod
    def _next_image_name(item: CatalogItem, current_name: Optional[str]) -> Optional[str]:
        if not current_name or not item.image_paths:
            return None
        names = [path.name for path in item.image_paths]
        if current_name not in names:
            return None
        if len(names) == 1:
            return None
        index = names.index(current_name)
        if index + 1 < len(names):
            return names[index + 1]
        if index > 0:
            return names[index - 1]
        return None

    def _on_archive_requested(self, path_value: str) -> None:
        self._flush_notes()
        archive_dir = (self.config.get("archive_image_dir") or "").strip()
        if not archive_dir:
            choice = QtWidgets.QMessageBox.question(
                self,
                tr("archive.folder_not_set"),
                tr("archive.folder_not_set_message"),
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.Cancel,
            )
            if choice == QtWidgets.QMessageBox.StandardButton.Yes:
                self._open_settings()
            return

        path = Path(path_value)
        if not path.exists():
            QtWidgets.QMessageBox.warning(
                self,
                tr("archive.image_not_found"),
                tr("archive.image_not_found_message"),
            )
            return

        archive_root = Path(archive_dir).expanduser()
        if not archive_root.is_absolute():
            archive_root = (PROJECT_ROOT / archive_root).resolve()
        else:
            archive_root = archive_root.resolve()
        source_dir = path.parent.resolve()
        if archive_root == source_dir:
            QtWidgets.QMessageBox.warning(
                self,
                tr("archive.folder_invalid"),
                tr("archive.folder_invalid_message"),
            )
            return
        archive_inside_scanned = []
        master_dir = (self.config.get("master_image_dir") or "").strip()
        if master_dir:
            master_path = Path(master_dir).expanduser()
            if not master_path.is_absolute():
                master_path = (PROJECT_ROOT / master_path).resolve()
            else:
                master_path = master_path.resolve()
            if archive_root == master_path or archive_root.is_relative_to(master_path):
                archive_inside_scanned.append(str(master_path))
        for catalog in self.config.get("catalogs", []):
            for image_dir in catalog.get("image_dirs", []):
                if not image_dir:
                    continue
                image_path = Path(image_dir).expanduser()
                if not image_path.is_absolute():
                    image_path = (PROJECT_ROOT / image_path).resolve()
                else:
                    image_path = image_path.resolve()
                if archive_root == image_path or archive_root.is_relative_to(image_path):
                    archive_inside_scanned.append(str(image_path))
        if archive_inside_scanned:
            choice = QtWidgets.QMessageBox.question(
                self,
                tr("archive.folder_inside_library"),
                tr("archive.folder_inside_library_message"),
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.Cancel,
            )
            if choice != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        archive_root.mkdir(parents=True, exist_ok=True)

        stat = path.stat()
        size = self._format_bytes(stat.st_size)
        modified = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        target = self._next_available_path(archive_root / path.name)

        confirm = QtWidgets.QMessageBox.question(
            self,
            tr("archive.confirm_title"),
            tr(
                "archive.confirm_message",
                file_name=path.name,
                size=size,
                modified=modified,
                source=path,
                target=target,
            ),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.Cancel,
        )
        if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        try:
            shutil.move(str(path), str(target))
        except Exception as exc:
            QtWidgets.QMessageBox.critical(
                self,
                tr("archive.failed_title"),
                tr("archive.failed_message", error=exc),
            )
            return
        if path.exists():
            QtWidgets.QMessageBox.warning(
                self,
                tr("archive.incomplete_title"),
                tr("archive.incomplete_message"),
            )

        self._set_status_message(tr("main.archived", name=path.name))
        current_item = self.detail.current_item()
        if current_item:
            current_image = self.detail.current_image_name()
            self._pending_selection_key = current_item.unique_key
            self._pending_image_name = self._next_image_name(current_item, current_image)
        self._start_catalog_load()

    def _flush_notes(self) -> None:
        if not self._pending_notes:
            return
        pending = list(self._pending_notes.values())
        self._pending_notes.clear()
        current = self.detail.current_item()
        for catalog, object_id, image_name, notes in pending:
            metadata_path = resolve_metadata_path(self.config, catalog)
            if metadata_path is None:
                continue
            item_key = f"{catalog}:{object_id}"
            if image_name:
                save_image_note(metadata_path, catalog, object_id, image_name, notes, user_notes_path=self.user_notes_path)
                self.model.update_item_image_note(item_key, image_name, notes)
                if current and current.unique_key == item_key:
                    self.detail.update_current_item_notes(image_name, notes)
            else:
                save_note(metadata_path, catalog, object_id, notes, user_notes_path=self.user_notes_path)
                self.model.update_item_notes(item_key, notes)
                if current and current.unique_key == item_key:
                    self.detail.update_current_item_notes(None, None, notes)

    def _apply_saved_filters(self) -> None:
        state = self._saved_state or {}
        filters = state.get("filters", {})
        search = state.get("search", "")

        catalog = filters.get("catalog", "")
        if not catalog:
            catalog = "Messier"
        type_filter = filters.get("type", "")
        status_filter = filters.get("status", "")

        self.search.blockSignals(True)
        self.search.setText(search or "")
        self.search.blockSignals(False)
        self._on_search_changed(self.search.text())

        self.catalog_filter.blockSignals(True)
        self._set_combo_value(self.catalog_filter, catalog, fallback="")
        self.catalog_filter.blockSignals(False)
        self._on_catalog_changed("")

        self.type_filter.blockSignals(True)
        self._set_combo_value(self.type_filter, type_filter, fallback="")
        self.type_filter.blockSignals(False)
        self._on_type_changed("")

        self.status_filter.blockSignals(True)
        self._set_combo_value(self.status_filter, status_filter, fallback="")
        self.status_filter.blockSignals(False)
        self._on_status_changed("")

    def _capture_ui_state(self) -> None:
        self.config["ui_state"] = {
            "window_size": [self.width(), self.height()],
            "splitter_sizes": self.splitter.sizes() if self.splitter else [],
            "filters": {
                "catalog": self._combo_value(self.catalog_filter) if self.catalog_filter else "",
                "type": self._combo_value(self.type_filter) if self.type_filter else "",
                "status": self._combo_value(self.status_filter) if self.status_filter else "",
            },
            "search": self.search.text() if self.search else "",
        }

    def _persist_ui_state(self) -> None:
        if self._zoom_timer.isActive():
            self._zoom_timer.stop()
            self._apply_zoom()
        self._capture_ui_state()
        if hasattr(self, "grid"):
            size = self.grid.iconSize().width()
        else:
            size = self.zoom_slider.value()
        if size:
            self.config["thumb_size"] = size
        save_config(self.config_path, self.config)

    @staticmethod
    def _format_bytes(value: int) -> str:
        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(value)
        for unit in units:
            if size < 1024 or unit == units[-1]:
                return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
            size /= 1024.0

    @staticmethod
    def _next_available_path(path: Path) -> Path:
        if not path.exists():
            return path
        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        counter = 1
        while True:
            candidate = parent / f"{stem}-{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1


class SettingsDialog(QtWidgets.QDialog):
    previewChanged = QtCore.Signal(dict)

    def __init__(self, config: Dict, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("settings.title"))
        self.setMinimumWidth(520)
        self._config = config
        self.updated_config: Dict = {}
        self._map_server: Optional[_MapHttpServer] = None
        self._map_url: Optional[str] = None
        self._map_open_timer: Optional[QtCore.QTimer] = None
        self._scan_thread_pool = QtCore.QThreadPool.globalInstance()
        self._scan_task: Optional[DuplicateScanTask] = None
        self._report_path: Optional[Path] = None

        self.ui_language = QtWidgets.QComboBox()
        for value, label in language_choices():
            self.ui_language.addItem(label, value)
        current_ui_locale = str(config.get("ui_locale") or "system")
        ui_index = self.ui_language.findData(current_ui_locale)
        self.ui_language.setCurrentIndex(ui_index if ui_index >= 0 else 0)
        self.ui_language.currentIndexChanged.connect(self._emit_preview)

        observer = config.get("observer", {})
        self.latitude = QtWidgets.QDoubleSpinBox()
        self.latitude.setRange(-90.0, 90.0)
        self.latitude.setDecimals(5)
        self.latitude.setValue(observer.get("latitude", 0.0))

        self.longitude = QtWidgets.QDoubleSpinBox()
        self.longitude.setRange(-180.0, 180.0)
        self.longitude.setDecimals(5)
        self.longitude.setValue(observer.get("longitude", 0.0))

        self.elevation = QtWidgets.QDoubleSpinBox()
        self.elevation.setRange(-500.0, 9000.0)
        self.elevation.setDecimals(1)
        self.elevation.setSuffix(" m")
        self.elevation.setValue(observer.get("elevation_m", 0.0))

        form = QtWidgets.QFormLayout()
        form.addRow(tr("settings.language.ui"), self.ui_language)
        form.addRow(tr("settings.latitude"), self.latitude)
        form.addRow(tr("settings.longitude"), self.longitude)
        form.addRow(tr("settings.elevation"), self.elevation)

        map_button = QtWidgets.QPushButton(tr("settings.pick_on_map"))
        map_button.clicked.connect(self._open_map_picker)
        form.addRow("", map_button)

        self.master_folder = QtWidgets.QLineEdit()
        self.master_folder.setText(config.get("master_image_dir", ""))
        browse_master = QtWidgets.QPushButton(tr("settings.browse"))
        browse_master.clicked.connect(self._browse_master_folder)
        master_row = QtWidgets.QHBoxLayout()
        master_row.addWidget(self.master_folder)
        master_row.addWidget(browse_master)
        form.addRow(tr("settings.master_folder"), master_row)
        master_note = QtWidgets.QLabel(
            tr("settings.master_note")
        )
        master_note.setWordWrap(True)
        master_note.setStyleSheet("color: #bcbcbc;")
        form.addRow("", master_note)

        self.archive_folder = QtWidgets.QLineEdit()
        self.archive_folder.setText(config.get("archive_image_dir", ""))
        browse_archive = QtWidgets.QPushButton(tr("settings.browse"))
        browse_archive.clicked.connect(self._browse_archive_folder)
        archive_row = QtWidgets.QHBoxLayout()
        archive_row.addWidget(self.archive_folder)
        archive_row.addWidget(browse_archive)
        form.addRow(tr("settings.archive_folder"), archive_row)

        # Notes are stored in the settings directory
        open_settings_folder = QtWidgets.QPushButton()
        open_settings_folder.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DirOpenIcon))
        open_settings_folder.setToolTip(tr("settings.open_settings_folder"))
        open_settings_folder.clicked.connect(self._open_settings_folder)
        form.addRow(tr("settings.settings_folder"), open_settings_folder)

        clear_cache = QtWidgets.QPushButton(tr("settings.clear_thumbnail_cache"))
        clear_cache.clicked.connect(self._clear_thumbnail_cache)
        form.addRow(tr("settings.thumbnail_cache"), clear_cache)

        scan_row = QtWidgets.QHBoxLayout()
        self.scan_button = QtWidgets.QPushButton(tr("settings.scan"))
        self.scan_button.clicked.connect(self._scan_duplicate_images)
        scan_row.addWidget(self.scan_button)
        self.report_label = QtWidgets.QLabel("")
        self.report_label.setOpenExternalLinks(False)
        self.report_label.linkActivated.connect(self._open_duplicate_report)
        self.report_label.hide()
        scan_row.addWidget(self.report_label, stretch=1)
        form.addRow(tr("settings.duplicate_scan"), scan_row)

        self.cleanup_button = QtWidgets.QPushButton(tr("settings.clean_invalid_entries"))
        self.cleanup_button.clicked.connect(self._run_cleanup_now)
        form.addRow(tr("settings.cleanup"), self.cleanup_button)

        # Migration section
        migrate_row = QtWidgets.QHBoxLayout()
        migrate_button = QtWidgets.QPushButton(tr("settings.migrate_notes"))
        migrate_button.clicked.connect(self._migrate_notes_from_old_app)
        migrate_row.addWidget(migrate_button)
        
        help_button = QtWidgets.QPushButton("?")
        help_button.setMaximumWidth(30)
        help_button.setToolTip(tr("settings.migrate_help"))
        migrate_row.addWidget(help_button)
        form.addRow(tr("settings.migration"), migrate_row)

        self.catalog_fields: Dict[str, QtWidgets.QLineEdit] = {}
        catalogs = config.get("catalogs", [])
        catalog_group = QtWidgets.QGroupBox("")
        catalog_layout = QtWidgets.QFormLayout(catalog_group)
        for catalog in catalogs:
            name = catalog.get("name", "Unknown")
            field = QtWidgets.QLineEdit()
            image_dirs = catalog.get("image_dirs", [])
            field.setText(image_dirs[0] if image_dirs else "")
            browse = QtWidgets.QPushButton(tr("settings.browse"))
            browse.clicked.connect(lambda _checked=False, n=name: self._browse_catalog_folder(n))
            row = QtWidgets.QHBoxLayout()
            row.addWidget(field)
            row.addWidget(browse)
            catalog_layout.addRow(name, row)
            self.catalog_fields[name] = field

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(catalog_group)
        layout.addWidget(buttons)

    def accept(self) -> None:
        updated = dict(self._config)
        updated["ui_locale"] = str(self.ui_language.currentData() or "system")
        updated["observer"] = {
            "latitude": self.latitude.value(),
            "longitude": self.longitude.value(),
            "elevation_m": self.elevation.value(),
        }
        updated["master_image_dir"] = self.master_folder.text().strip()
        updated["archive_image_dir"] = self.archive_folder.text().strip()
        # Notes folder is hardcoded to settings directory, remove any old config
        updated.pop("notes_folder", None)

        catalogs = []
        for catalog in updated.get("catalogs", []):
            name = catalog.get("name", "Unknown")
            field = self.catalog_fields.get(name)
            if field:
                paths = [part.strip() for part in field.text().split(",") if part.strip()]
                catalog["image_dirs"] = paths
            catalogs.append(catalog)
        updated["catalogs"] = catalogs

        self.updated_config = updated
        super().accept()

    def _browse_catalog_folder(self, name: str) -> None:
        field = self.catalog_fields.get(name)
        if field is None:
            return
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            tr("settings.select_catalog_image_folder", catalog=name),
        )
        if not directory:
            return
        field.setText(directory)
        self._emit_preview()

    def _browse_master_folder(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, tr("settings.select_master_image_folder"))
        if not directory:
            return
        self.master_folder.setText(directory)
        self._emit_preview()

    def _browse_archive_folder(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, tr("settings.select_archive_image_folder"))
        if not directory:
            return
        self.archive_folder.setText(directory)
        self._emit_preview()

    def _open_settings_folder(self) -> None:
        location = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.AppConfigLocation)
        if location:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(location))

    def _clear_thumbnail_cache(self) -> None:
        parent = self.parent()
        if parent is None or not hasattr(parent, "clear_thumbnail_cache"):
            QtWidgets.QMessageBox.warning(self, tr("settings.thumbnail_cache"), tr("settings.thumbnail_cache_clear_failed"))
            return
        if parent.clear_thumbnail_cache():
            QtWidgets.QMessageBox.information(self, tr("settings.thumbnail_cache"), tr("settings.thumbnail_cache_cleared"))
            return
        QtWidgets.QMessageBox.warning(self, tr("settings.thumbnail_cache"), tr("settings.thumbnail_cache_clear_failed"))

    def _scan_duplicate_images(self) -> None:
        config = self._build_preview_config()
        config_dir = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.AppConfigLocation)
        output_dir = Path(config_dir) if config_dir else PROJECT_ROOT
        output_dir.mkdir(parents=True, exist_ok=True)
        config_path = output_dir / "duplicate_scan_config.json"
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        report_path = output_dir / "duplicate_image_report.txt"
        extensions = config.get(
            "image_extensions",
            [".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"],
        )
        self.scan_button.setEnabled(False)
        self.scan_button.setText(tr("settings.scanning"))
        self.report_label.hide()
        self.report_label.setText("")
        task = DuplicateScanTask(config_path, extensions, report_path)
        task.signals.finished.connect(self._on_duplicate_scan_finished)
        self._scan_task = task
        self._scan_thread_pool.start(task)

    def _on_duplicate_scan_finished(self, report_path: str, error: str) -> None:
        self.scan_button.setEnabled(True)
        self.scan_button.setText(tr("settings.scan"))
        if error:
            QtWidgets.QMessageBox.warning(
                self,
                tr("settings.duplicate_scan"),
                tr("settings.duplicate_scan_failed", error=error),
            )
            return
        self._report_path = Path(report_path)
        self.report_label.setText(f'<a href="{report_path}">{tr("settings.duplicate_report_available")}</a>')
        self.report_label.show()
        groups = self._load_duplicate_groups(self._report_path)
        if not groups:
            QtWidgets.QMessageBox.information(
                self,
                tr("settings.duplicate_scan"),
                tr("settings.duplicate_scan_none"),
            )
            return
        choice = QtWidgets.QMessageBox.question(
            self,
            tr("settings.duplicate_scan"),
            tr("settings.duplicate_scan_found", count=len(groups)),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )
        if choice != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self._move_duplicate_groups(groups)

    def _open_duplicate_report(self, link: str) -> None:
        if link:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(link))

    def _load_duplicate_groups(self, report_path: Path) -> List[Dict[str, object]]:
        json_path = report_path.with_suffix(".json")
        if not json_path.exists():
            return []
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        groups = payload.get("groups", [])
        return groups if isinstance(groups, list) else []

    def _move_duplicate_groups(self, groups: List[Dict[str, object]]) -> None:
        archive_dir = self.archive_folder.text().strip()
        if not archive_dir:
            object_name = self._describe_duplicate_object(groups)
            QtWidgets.QMessageBox.information(
                self,
                tr("settings.archive_folder_required"),
                tr("settings.archive_folder_required_message", object_name=object_name),
            )
            self._browse_archive_folder()
            archive_dir = self.archive_folder.text().strip()
            if not archive_dir:
                return
        archive_root = Path(archive_dir).expanduser()
        if not archive_root.is_absolute():
            archive_root = (PROJECT_ROOT / archive_root).resolve()
        archive_root.mkdir(parents=True, exist_ok=True)
        moved = 0
        for group in groups:
            files = group.get("files", [])
            if not isinstance(files, list) or len(files) <= 1:
                continue
            file_paths = [Path(item.get("path", "")) for item in files if isinstance(item, dict)]
            file_paths = [path for path in file_paths if path.exists()]
            if len(file_paths) <= 1:
                continue
            file_paths = sorted(file_paths, key=lambda p: p.name.lower())
            for path in file_paths[1:]:
                target = self._next_available_path(archive_root / path.name)
                try:
                    shutil.move(str(path), str(target))
                    moved += 1
                except OSError:
                    continue
        QtWidgets.QMessageBox.information(
            self,
            tr("settings.duplicate_scan"),
            tr("settings.duplicate_files_moved", count=moved),
        )

    def _run_cleanup_now(self) -> None:
        parent = self.parent()
        if parent is None or not hasattr(parent, "_cleanup_invalid_image_only_entries"):
            QtWidgets.QMessageBox.warning(self, tr("settings.cleanup"), tr("settings.cleanup_failed"))
            return
        parent._cleanup_invalid_image_only_entries()
        parent.config["cleanup_invalid_image_only_entries_done"] = True
        save_config(parent.config_path, parent.config)
        QtWidgets.QMessageBox.information(self, tr("settings.cleanup"), tr("settings.cleanup_complete"))

    def _migrate_notes_from_old_app(self) -> None:
        choice = QtWidgets.QMessageBox.question(
            self,
            tr("settings.migration"),
            tr("settings.migrate_notes_confirm"),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )
        if choice != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        
        # Run the migration script
        try:
            migrate_script = PROJECT_ROOT / "scripts" / "migrate_user_notes.py"
            if not migrate_script.exists():
                QtWidgets.QMessageBox.warning(
                    self,
                    tr("settings.migration_error"),
                    tr("settings.migration_script_missing", path=migrate_script),
                )
                return

            # Run the migration script in-process so it works in frozen builds.
            # It keeps compatibility with source runs and allows capturing output.
            out_buffer = io.StringIO()
            err_buffer = io.StringIO()
            return_code = 0
            original_argv = list(sys.argv)
            try:
                sys.argv = [str(migrate_script)]
                with redirect_stdout(out_buffer), redirect_stderr(err_buffer):
                    try:
                        runpy.run_path(str(migrate_script), run_name="__main__")
                    except SystemExit as exc:
                        code = exc.code
                        if code is None:
                            return_code = 0
                        elif isinstance(code, int):
                            return_code = code
                        else:
                            return_code = 1
            finally:
                sys.argv = original_argv

            stdout_text = out_buffer.getvalue().strip()
            stderr_text = err_buffer.getvalue().strip()

            if return_code != 0:
                # Build error message from stderr
                error_msg = stderr_text if stderr_text else "Unknown error"
                
                # Provide user-friendly error messages
                if "Could not find old AstroCatalogueViewer" in error_msg:
                    QtWidgets.QMessageBox.warning(
                        self,
                        tr("settings.migration_no_previous_title"),
                        tr("settings.migration_no_previous_message"),
                    )
                elif "No notes found" in error_msg:
                    QtWidgets.QMessageBox.information(
                        self,
                        tr("settings.migration_no_notes_title"),
                        tr("settings.migration_no_notes_message"),
                    )
                else:
                    QtWidgets.QMessageBox.warning(
                        self,
                        tr("settings.migration_error"),
                        tr("settings.migration_failed", error=error_msg),
                    )
                return
            
            # Show success message with detailed summary
            success_msg = stdout_text if stdout_text else "Migration completed successfully!"
            self._show_migration_summary(success_msg)
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                tr("settings.migration_error"),
                tr("settings.migration_unexpected", error=str(e)),
            )

    def _show_migration_summary(self, output: str) -> None:
        """Show migration summary in a dialog with copy functionality."""
        # Parse the output to extract migration statistics
        lines = output.split('\n')
        summary_lines = []
        log_lines = []
        
        in_summary = False
        in_log = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if "MIGRATION SUMMARY" in line:
                in_summary = True
                in_log = False
                summary_lines.append(line)
            elif "Migration log saved to:" in line:
                in_log = True
                in_summary = False
                log_lines.append(line)
            elif in_summary:
                summary_lines.append(line)
            elif in_log or "STARTING MIGRATION" in line or any(keyword in line for keyword in ["MIGRATED", "IGNORED", "Extracted", "Total notes extracted"]):
                log_lines.append(line)
            elif any(keyword in line for keyword in ["Object notes migrated:", "Image notes migrated:", "Total notes migrated:"]):
                summary_lines.append(line)
        
        # Create the dialog
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(tr("settings.migration_complete"))
        dialog.setModal(True)
        dialog.resize(600, 400)
        
        layout = QtWidgets.QVBoxLayout(dialog)
        
        # Title
        title_label = QtWidgets.QLabel(tr("settings.migration_success"))
        title_label.setStyleSheet("font-weight: bold; font-size: 12px; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # Summary section (statistics first)
        if summary_lines:
            summary_group = QtWidgets.QGroupBox(tr("settings.migration_statistics"))
            summary_layout = QtWidgets.QVBoxLayout(summary_group)
            
            summary_text = QtWidgets.QTextEdit()
            summary_text.setPlainText('\n'.join(summary_lines))
            summary_text.setReadOnly(True)
            summary_text.setMaximumHeight(100)
            summary_text.setStyleSheet("""
                QTextEdit {
                    background-color: transparent;
                    color: #ffffff;
                    border: 1px solid #4b5563;
                    border-radius: 4px;
                    padding: 8px;
                    font-family: monospace;
                    font-size: 10px;
                }
            """)
            summary_layout.addWidget(summary_text)
            layout.addWidget(summary_group)
        
        # Log section
        if log_lines:
            log_group = QtWidgets.QGroupBox(tr("settings.migration_details"))
            log_layout = QtWidgets.QVBoxLayout(log_group)
            
            log_text = QtWidgets.QTextEdit()
            log_text.setPlainText('\n'.join(log_lines))
            log_text.setReadOnly(True)
            log_text.setStyleSheet("""
                QTextEdit {
                    background-color: transparent;
                    color: #ffffff;
                    border: 1px solid #4b5563;
                    border-radius: 4px;
                    padding: 8px;
                    font-family: monospace;
                    font-size: 9px;
                }
            """)
            log_layout.addWidget(log_text)
            layout.addWidget(log_group)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        copy_button = QtWidgets.QPushButton(tr("settings.copy_to_clipboard"))
        copy_button.clicked.connect(lambda: self._copy_migration_summary(output))
        button_layout.addWidget(copy_button)
        
        button_layout.addStretch()
        
        close_button = QtWidgets.QPushButton(tr("settings.close"))
        close_button.clicked.connect(dialog.accept)
        close_button.setDefault(True)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
        dialog.exec()

    def _copy_migration_summary(self, text: str) -> None:
        """Copy the migration summary to clipboard."""
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(text)
        # Show a brief tooltip or status message
        if hasattr(self, 'statusBar'):
            self.statusBar().showMessage(tr("settings.copied_to_clipboard"), 2000)

    def _describe_duplicate_object(self, groups: List[Dict[str, object]]) -> str:
        for group in groups:
            catalog = group.get("catalog")
            common_ids = group.get("common_ids", [])
            if not isinstance(common_ids, list) or not common_ids:
                continue
            object_id = str(common_ids[0])
            name = self._lookup_object_name(catalog, object_id)
            return f"{object_id} ({name})" if name else object_id
        return "this object"

    def _lookup_object_name(self, catalog: object, object_id: str) -> str:
        if not isinstance(catalog, str):
            return ""
        config = self._build_preview_config()
        for entry in config.get("catalogs", []):
            if entry.get("name") != catalog:
                continue
            metadata_value = entry.get("metadata_file")
            if not metadata_value:
                return ""
            metadata_path = Path(metadata_value)
            if not metadata_path.is_absolute():
                metadata_path = (PROJECT_ROOT / metadata_path).resolve()
            if not metadata_path.exists():
                return ""
            try:
                data = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return ""
            catalog_data = data.get(catalog, {})
            if not isinstance(catalog_data, dict):
                return ""
            entry_data = catalog_data.get(object_id, {})
            if not isinstance(entry_data, dict):
                return ""
            return str(entry_data.get("name") or "").strip()
        return ""

    @staticmethod
    def _next_available_path(path: Path) -> Path:
        if not path.exists():
            return path
        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        counter = 1
        while True:
            candidate = parent / f"{stem}-{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1

    def _open_map_picker(self) -> None:
        if self._map_server is None:
            self._map_server = _MapHttpServer(self)
            self._map_server_thread = threading.Thread(
                target=self._map_server.serve_forever, daemon=True
            )
            self._map_server_thread.start()
            self._map_url = f"http://127.0.0.1:{self._map_server.port}/"
            self._map_open_timer = QtCore.QTimer(self)
            self._map_open_timer.setSingleShot(True)
            self._map_open_timer.setInterval(200)
            self._map_open_timer.timeout.connect(self._open_map_url)
            self._map_open_timer.start()
        else:
            self._open_map_url()

    def _open_map_url(self) -> None:
        if self._map_url:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(self._map_url))

    def _apply_location(self, lat: float, lon: float) -> None:
        self.latitude.setValue(lat)
        self.longitude.setValue(lon)
        self._emit_preview()

    @QtCore.Slot(float, float)
    def _post_location(self, lat: float, lon: float) -> None:
        self._apply_location(lat, lon)

    def _map_html(self) -> str:
        lat = self.latitude.value()
        lon = self.longitude.value()
        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{tr("settings.location_picker_title")}</title>
  <style>
    html, body, #map {{ height: 100%; margin: 0; background: #111; }}
    .controls {{
      position: absolute; top: 10px; left: 10px; z-index: 999;
      background: rgba(0,0,0,0.6); color: #fff; padding: 8px 10px;
      font-family: sans-serif; font-size: 14px; border-radius: 6px;
    }}
    .controls button {{ margin-right: 8px; }}
  </style>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
</head>
<body>
  <div id="map"></div>
  <div class="controls">
        <button id="geo">{tr("settings.location_use_my_location")}</button>
        <span id="status">{tr("settings.location_click_to_set")}</span>
  </div>
  <script>
    const map = L.map('map').setView([{lat}, {lon}], 3);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      maxZoom: 10,
      attribution: '&copy; OpenStreetMap'
    }}).addTo(map);
    const marker = L.marker([{lat}, {lon}]).addTo(map);
    function sendLocation(lat, lon) {{
      marker.setLatLng([lat, lon]);
      fetch('/set_location', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ lat, lon }})
      }}).catch(() => {{}});
            document.getElementById('status').textContent = `{tr("settings.location_selected", lat="${lat.toFixed(5)}", lon="${lon.toFixed(5)}")}`;
    }}
    map.on('click', (e) => sendLocation(e.latlng.lat, e.latlng.lng));
    document.getElementById('geo').addEventListener('click', () => {{
      navigator.geolocation.getCurrentPosition(
        (pos) => {{
          const lat = pos.coords.latitude;
          const lon = pos.coords.longitude;
          map.setView([lat, lon], 7);
          sendLocation(lat, lon);
        }},
                () => {{ document.getElementById('status').textContent = '{tr("settings.location_permission_denied")}'; }}
      );
    }});
  </script>
</body>
</html>"""

    def _shutdown_map_server(self) -> None:
        if self._map_server is not None:
            self._map_server.shutdown()
            self._map_server = None
        self._map_url = None
        if self._map_open_timer is not None:
            self._map_open_timer.stop()
            self._map_open_timer = None

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self._shutdown_map_server()
        super().closeEvent(event)

    def _emit_preview(self) -> None:
        self.previewChanged.emit(self._build_preview_config())

    def _build_preview_config(self) -> Dict:
        updated = dict(self._config)
        updated["ui_locale"] = str(self.ui_language.currentData() or "system")
        updated["observer"] = {
            "latitude": self.latitude.value(),
            "longitude": self.longitude.value(),
            "elevation_m": self.elevation.value(),
        }
        updated["master_image_dir"] = self.master_folder.text().strip()
        updated["archive_image_dir"] = self.archive_folder.text().strip()
        catalogs = []
        for catalog in updated.get("catalogs", []):
            name = catalog.get("name", "Unknown")
            field = self.catalog_fields.get(name)
            if field:
                value = field.text().strip()
                catalog["image_dirs"] = [value] if value else []
            catalogs.append(catalog)
        updated["catalogs"] = catalogs
        return updated


class _MapHttpServer:
    def __init__(self, dialog: QtCore.QObject) -> None:
        self.dialog = dialog

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                try:
                    path = urlparse(self.path).path
                    if path not in ("/", "/index.html"):
                        self.send_error(404)
                        return
                    dialog = self.server.dialog  # type: ignore[attr-defined]
                    if dialog is None:
                        self.send_error(410)
                        return
                    body = dialog._map_html()
                    data = body.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except Exception:
                    self.send_error(500)

            def do_POST(self) -> None:
                try:
                    path = urlparse(self.path).path
                    if path != "/set_location":
                        self.send_error(404)
                        return
                    dialog = self.server.dialog  # type: ignore[attr-defined]
                    if dialog is None:
                        self.send_error(410)
                        return
                    length = int(self.headers.get("Content-Length", "0"))
                    payload = self.rfile.read(length).decode("utf-8")
                    data = json.loads(payload)
                    lat = float(data.get("lat"))
                    lon = float(data.get("lon"))
                    QtCore.QMetaObject.invokeMethod(
                        dialog,
                        "_post_location",
                        QtCore.Qt.ConnectionType.QueuedConnection,
                        QtCore.Q_ARG(float, lat),
                        QtCore.Q_ARG(float, lon),
                    )
                    self.send_response(204)
                    self.end_headers()
                except Exception:
                    self.send_error(400)

            def log_message(self, _format: str, *args: object) -> None:
                return

        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self._server.dialog = self.dialog  # type: ignore[attr-defined]
        self.port = self._server.server_address[1]

    def serve_forever(self) -> None:
        self._server.serve_forever()

    def shutdown(self) -> None:
        self._server.shutdown()
        self._server.server_close()


class WelcomeDialog(QtWidgets.QDialog):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("welcome.title"))
        self.setMinimumWidth(560)

        title = QtWidgets.QLabel(tr("welcome.heading"))
        title.setObjectName("welcomeTitle")

        body = QtWidgets.QTextBrowser()
        body.setOpenExternalLinks(True)
        body.setObjectName("welcomeBody")
        body.setHtml(tr("welcome.body"))
        body.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body.document().setTextWidth(520)
        body.setMinimumHeight(int(body.document().size().height()) + 16)

        self.skip_checkbox = QtWidgets.QCheckBox(tr("welcome.skip"))

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
        )
        buttons.accepted.connect(self.accept)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(self.skip_checkbox)
        layout.addWidget(buttons)

    def skip_requested(self) -> bool:
        return self.skip_checkbox.isChecked()


class AboutDialog(QtWidgets.QDialog):
    check_updates_requested = QtCore.Signal()
    auto_check_toggled = QtCore.Signal(bool)

    def __init__(
        self,
        config: Dict,
        app_version: str,
        data_version: str,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("about.title"))
        self.setMinimumWidth(760)
        self._config = config
        self._app_version = app_version
        self._data_version = data_version

        title = QtWidgets.QLabel("AstroCat")
        title.setObjectName("aboutTitle")
        self.app_version_label = QtWidgets.QLabel(tr("about.app_version", version=app_version))
        self.app_version_label.setObjectName("aboutVersion")
        self.data_version_label = QtWidgets.QLabel(tr("about.data_version", version=data_version))
        self.data_version_label.setObjectName("aboutDataVersion")
        self.remote_data_version_label = QtWidgets.QLabel(tr("about.latest_data_version_checking"))
        self.remote_data_version_label.setObjectName("aboutVersion")

        about = QtWidgets.QLabel(
            tr("about.description")
        )
        about.setWordWrap(True)

        links = QtWidgets.QLabel(
            f'Repo: <a href="https://github.com/{UPDATE_REPO}">github.com/{UPDATE_REPO}</a>'
        )
        links.setOpenExternalLinks(True)
        links.setObjectName("aboutLinks")

        sponsor_box = QtWidgets.QGroupBox(tr("about.sponsors"))
        sponsor_layout = QtWidgets.QVBoxLayout(sponsor_box)
        self.supporters_status = QtWidgets.QLabel(tr("about.loading_supporters"))
        self.supporters_status.setWordWrap(True)
        self.supporters_status.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.supporters_status.setOpenExternalLinks(True)
        sponsor_scroll = QtWidgets.QScrollArea()
        sponsor_scroll.setWidgetResizable(True)
        sponsor_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        sponsor_scroll.setWidget(self.supporters_status)
        sponsor_layout.addWidget(sponsor_scroll)

        left = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(title)
        left_layout.addWidget(self.app_version_label)
        left_layout.addWidget(self.data_version_label)
        left_layout.addWidget(self.remote_data_version_label)
        left_layout.addSpacing(8)
        left_layout.addWidget(about)
        left_layout.addSpacing(10)
        left_layout.addWidget(links)
        left_layout.addSpacing(10)
        left_layout.addWidget(sponsor_box)
        left_layout.addStretch(1)

        quick_title = QtWidgets.QLabel(tr("about.quick_start"))
        quick_title.setObjectName("aboutSectionTitle")
        quick_list = QtWidgets.QLabel(tr("about.quick_start_list"))
        quick_list.setWordWrap(True)

        updates_title = QtWidgets.QLabel(tr("about.updates"))
        updates_title.setObjectName("aboutSectionTitle")
        self.update_status = QtWidgets.QLabel(tr("about.not_checked"))
        self.update_status.setObjectName("aboutUpdateStatus")
        self.update_status.setWordWrap(True)
        self.data_update_status = QtWidgets.QLabel(tr("about.checking_data_updates"))
        self.data_update_status.setObjectName("aboutUpdateStatus")
        self.data_update_status.setWordWrap(True)
        self.auto_check = QtWidgets.QCheckBox(tr("about.auto_check_updates"))
        self.auto_check.setChecked(bool(config.get("auto_check_updates", True)))
        self.auto_check.toggled.connect(self.auto_check_toggled.emit)
        self.check_updates = QtWidgets.QPushButton(tr("about.check_for_updates"))
        self.check_updates.clicked.connect(self.check_updates_requested.emit)

        right = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(quick_title)
        right_layout.addWidget(quick_list)
        right_layout.addSpacing(16)
        right_layout.addWidget(updates_title)
        right_layout.addWidget(self.update_status)
        right_layout.addWidget(self.data_update_status)
        right_layout.addWidget(self.auto_check)
        right_layout.addWidget(self.check_updates)
        right_layout.addStretch(1)

        content = QtWidgets.QHBoxLayout()
        content.addWidget(left, stretch=3)
        content.addWidget(right, stretch=2)
        content.setSpacing(24)

        close_button = QtWidgets.QPushButton(tr("settings.close"))
        close_button.clicked.connect(self.accept)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(content)
        layout.addWidget(close_button, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

        self._supporters_task: Optional[SupportersFetchTask] = None
        self._supporters_thread_pool = QtCore.QThreadPool.globalInstance()
        self._start_supporters_fetch()

    def set_update_status(self, status: str, latest: Optional[str], url: Optional[str]) -> None:
        if url:
            self.update_status.setText(f'{status} <a href="{url}">{tr("about.view_release")}</a>')
            self.update_status.setOpenExternalLinks(True)
        else:
            self.update_status.setText(status)
            self.update_status.setOpenExternalLinks(False)

    def set_data_version(self, version: str) -> None:
        if not version:
            return
        self._data_version = version
        self.data_version_label.setText(tr("about.data_version", version=version))

    def set_data_update_status(self, status: str) -> None:
        self.data_update_status.setText(status)

    def set_remote_data_version(self, version: Optional[str], installed: str) -> None:
        if not version:
            self.remote_data_version_label.setText(tr("about.latest_data_version_unavailable"))
            return
        if version != installed:
            self.remote_data_version_label.setText(tr("about.latest_data_version_available", version=version))
            return
        self.remote_data_version_label.setText(tr("about.latest_data_version_uptodate", version=version))

    def _start_supporters_fetch(self) -> None:
        task = SupportersFetchTask(SUPPORTERS_URL, user_agent=f"{APP_NAME}/{self._app_version}")
        task.signals.loaded.connect(self._apply_supporters)
        task.signals.failed.connect(self._supporters_failed)
        self._supporters_task = task
        self._supporters_thread_pool.start(task)

    def _apply_supporters(self, supporters: List[str]) -> None:
        if not supporters:
            self.supporters_status.setText(tr("about.no_supporters"))
            return
        self.supporters_status.setText("<br>".join(supporters))

    def _supporters_failed(self, message: str) -> None:
        self.supporters_status.setText(message)


class UpdateCheckTask(QtCore.QRunnable):
    def __init__(self, current_version: str) -> None:
        super().__init__()
        self.current_version = current_version
        self.signals = UpdateSignals()

    def run(self) -> None:
        if SHUTDOWN_EVENT.is_set():
            return
        try:
            payload = self._fetch_latest_release()
            tag = (payload.get("tag_name") or "").strip()
            html_url = (payload.get("html_url") or "").strip()
            latest = self._normalize_version(tag)
            current = self._normalize_version(self.current_version)
            if not latest:
                self._emit_failed(tr("updates.status_not_found"))
                return
            if latest != current:
                self._emit_available(tag, html_url)
            else:
                self._emit_up_to_date(tag)
        except Exception:
            self._emit_failed(tr("updates.status_failed"))
        finally:
            self._emit_finished()

    @staticmethod
    def _normalize_version(value: str) -> str:
        return value.strip().lstrip("vV")

    def _emit_available(self, tag: str, url: str) -> None:
        if SHUTDOWN_EVENT.is_set() or not isValid(self.signals):
            return
        try:
            self.signals.available.emit(tag, url)
        except RuntimeError:
            return

    def _emit_up_to_date(self, tag: str) -> None:
        if SHUTDOWN_EVENT.is_set() or not isValid(self.signals):
            return
        try:
            self.signals.up_to_date.emit(tag)
        except RuntimeError:
            return

    def _emit_failed(self, message: str) -> None:
        if SHUTDOWN_EVENT.is_set() or not isValid(self.signals):
            return
        try:
            self.signals.failed.emit(message)
        except RuntimeError:
            return

    def _emit_finished(self) -> None:
        if SHUTDOWN_EVENT.is_set() or not isValid(self.signals):
            return
        try:
            self.signals.finished.emit()
        except RuntimeError:
            return

    @staticmethod
    def _fetch_latest_release() -> Dict:
        if SHUTDOWN_EVENT.is_set():
            return {}
        creationflags = 0
        if sys.platform.startswith("win"):
            creationflags = subprocess.CREATE_NO_WINDOW
        url = f"https://api.github.com/repos/{UPDATE_REPO}/releases"
        result = subprocess.run(
            [
                "curl",
                "-sL",
                "--max-time",
                "8",
                "--retry",
                "2",
                "--retry-delay",
                "1",
                "-H",
                "User-Agent: AstroCat/1.0",
                url,
            ],
            check=True,
            capture_output=True,
            creationflags=creationflags,
        )
        payload = json.loads(result.stdout or "{}")
        if isinstance(payload, list) and payload:
            for entry in payload:
                if isinstance(entry, dict) and entry.get("tag_name"):
                    return entry
            return {}
        if isinstance(payload, dict):
            return payload
        return {}


class SupportersFetchTask(QtCore.QRunnable):
    def __init__(self, url: str, user_agent: Optional[str] = None) -> None:
        super().__init__()
        self.url = url
        self.user_agent = user_agent or f"{APP_NAME}/{APP_VERSION}"
        self.signals = SupportersSignals()

    def run(self) -> None:
        if SHUTDOWN_EVENT.is_set():
            return
        try:
            payload = self._fetch_payload()
            supporters = self._normalize_supporters(payload)
            self._emit_loaded(supporters)
        except Exception:
            self._emit_failed(tr("supporters.load_failed"))

    def _emit_loaded(self, supporters: List[str]) -> None:
        if SHUTDOWN_EVENT.is_set() or not isValid(self.signals):
            return
        try:
            self.signals.loaded.emit(supporters)
        except RuntimeError:
            return

    def _emit_failed(self, message: str) -> None:
        if SHUTDOWN_EVENT.is_set() or not isValid(self.signals):
            return
        try:
            self.signals.failed.emit(message)
        except RuntimeError:
            return

    def _fetch_payload(self) -> Dict:
        creationflags = 0
        if sys.platform.startswith("win"):
            creationflags = subprocess.CREATE_NO_WINDOW
        for url in self._candidate_urls():
            result = subprocess.run(
                [
                    "curl",
                    "-sL",
                    "--max-time",
                    "6",
                    "--retry",
                    "2",
                    "--retry-delay",
                    "1",
                    "-H",
                    f"User-Agent: {self.user_agent}",
                    url,
                ],
                check=False,
                capture_output=True,
                creationflags=creationflags,
            )
            if result.returncode != 0:
                continue
            payload = json.loads(result.stdout or "{}")
            if payload:
                return payload
        return {}

    def _candidate_urls(self) -> List[str]:
        if "/main/" in self.url:
            return [self.url, self.url.replace("/main/", "/master/")]
        return [self.url]

    @staticmethod
    def _normalize_supporters(payload) -> List[str]:
        if isinstance(payload, dict):
            payload = payload.get("supporters", payload.get("supporter", []))
        if isinstance(payload, list):
            stargazers: List[str] = []
            supporters: List[str] = []
            for entry in payload:
                if isinstance(entry, str):
                    supporters.append(entry)
                    continue
                if isinstance(entry, dict):
                    name = str(entry.get("name") or "").strip()
                    tier = str(entry.get("tier") or "").strip()
                    url = str(entry.get("url") or "").strip()
                    if not name:
                        continue
                    line = f"{name} — {tier}" if tier else name
                    if url:
                        line = f'{line} — <a href="{url}">YouTube</a>'
                    tier_key = tier.casefold()
                    if tier_key in {"stargazer", "stargazers"}:
                        stargazers.append(line)
                    else:
                        supporters.append(line)
            return stargazers + supporters
        return []


class DataVersionFetchTask(QtCore.QRunnable):
    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url
        self.signals = DataVersionSignals()

    def run(self) -> None:
        if SHUTDOWN_EVENT.is_set():
            return
        try:
            payload = self._fetch_payload()
            version = _extract_version(payload)
            if version:
                self._emit_loaded(version)
            else:
                self._emit_failed(tr("data.load_failed"))
        except Exception:
            self._emit_failed(tr("data.load_failed"))

    def _emit_loaded(self, version: str) -> None:
        if SHUTDOWN_EVENT.is_set() or not isValid(self.signals):
            return
        try:
            self.signals.loaded.emit(version)
        except RuntimeError:
            return

    def _emit_failed(self, message: str) -> None:
        if SHUTDOWN_EVENT.is_set() or not isValid(self.signals):
            return
        try:
            self.signals.failed.emit(message)
        except RuntimeError:
            return

    def _fetch_payload(self) -> Dict:
        creationflags = 0
        if sys.platform.startswith("win"):
            creationflags = subprocess.CREATE_NO_WINDOW
        for url in self._candidate_urls():
            result = subprocess.run(
                [
                    "curl",
                    "-sL",
                    "--max-time",
                    "6",
                    "--retry",
                    "2",
                    "--retry-delay",
                    "1",
                    "-H",
                    f"User-Agent: {APP_NAME}/{APP_VERSION}",
                    url,
                ],
                check=False,
                capture_output=True,
                creationflags=creationflags,
            )
            if result.returncode != 0:
                continue
            payload = json.loads(result.stdout or "{}")
            if payload:
                return payload
        return {}

    def _candidate_urls(self) -> List[str]:
        if "/main/" in self.url:
            return [self.url, self.url.replace("/main/", "/master/")]
        return [self.url]


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    QtCore.QLoggingCategory.setFilterRules("qt.gui.imageio=false\n")

    location = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.AppConfigLocation)
    if location:
        config_dir = Path(location)
    else:
        config_dir = PROJECT_ROOT
    config_path = config_dir / "config.json"
    photo_notes_path = config_dir / "photo_notes.json"
    db_path = database_path_from_config_path(config_path)

    # Auto-import legacy photo notes only when target tables are empty.
    try:
        migrate_photo_notes_to_sqlite(photo_notes_path, db_path, force=False)
    except Exception:
        # Startup must stay resilient even if migration hits malformed legacy data.
        pass

    window = MainWindow(config_path)
    app.aboutToQuit.connect(window._persist_ui_state)
    if window.config.get("show_welcome", True):
        welcome = WelcomeDialog(window)
        welcome.exec()
        if welcome.skip_requested():
            window.config["show_welcome"] = False
            save_config(config_path, window.config)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
