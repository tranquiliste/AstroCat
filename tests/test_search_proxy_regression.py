from __future__ import annotations

import sys
import unittest
from pathlib import Path

from PySide6 import QtCore, QtGui


ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from catalog import CatalogItem, apply_global_image_deduplication  # noqa: E402
from main import CatalogFilterProxy  # noqa: E402


class CatalogFilterProxySearchRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])

    class _ProxyParent(QtCore.QObject):
        def __init__(self, items_global_dedup: list[CatalogItem]) -> None:
            super().__init__()
            self._model_uses_global_dedup = False
            self.items_global_dedup = items_global_dedup

    def _make_item(
        self,
        *,
        object_id: str,
        catalog: str = "NGC",
        name: str,
        image_name: str | None,
        related: dict[str, list[str]],
        deduped_image_count: int = 0,
        thumbnail_name: str | None = None,
    ) -> CatalogItem:
        image_paths = [Path(image_name)] if image_name else []
        return CatalogItem(
            object_id=object_id,
            catalog=catalog,
            name=name,
            object_type="Galaxy",
            distance_ly=None,
            discoverer=None,
            discovery_year=None,
            best_months=None,
            constellation=None,
            description=None,
            notes=None,
            image_notes={},
            external_link=None,
            wiki_thumbnail=None,
            ra_hours=None,
            dec_deg=None,
            image_paths=image_paths,
            thumbnail_path=Path(thumbnail_name) if thumbnail_name else None,
            related_image_objects=related,
            deduped_image_count=deduped_image_count,
        )

    def _proxy_for_item(self, item: CatalogItem, *, status: str = "Captured") -> CatalogFilterProxy:
        model = QtGui.QStandardItemModel()
        model.setColumnCount(1)
        model.setRowCount(1)
        index = model.index(0, 0)
        model.setData(index, item, QtCore.Qt.ItemDataRole.UserRole)

        proxy = CatalogFilterProxy()
        proxy.setSourceModel(model)
        proxy.set_status_filter(status)
        proxy.set_catalog_filter("")
        self._last_model = model
        self._last_proxy = proxy
        return proxy

    def _proxy_for_items(
        self,
        items: list[CatalogItem],
        *,
        status: str = "Captured",
        catalog: str = "",
    ) -> CatalogFilterProxy:
        model = QtGui.QStandardItemModel()
        model.setColumnCount(1)
        model.setRowCount(len(items))
        for row, item in enumerate(items):
            model.setData(model.index(row, 0), item, QtCore.Qt.ItemDataRole.UserRole)

        parent = self._ProxyParent(items)
        proxy = CatalogFilterProxy(parent)
        proxy.setSourceModel(model)
        proxy.set_status_filter(status)
        proxy.set_catalog_filter(catalog)
        self._last_model = model
        self._last_proxy = proxy
        self._last_parent = parent
        return proxy

    def test_search_m81_matches_related_object_id_in_shared_image(self) -> None:
        item = self._make_item(
            object_id="NGC3031",
            name="Bode Galaxy",
            image_name="NGC3031_M82_Final.jpg",
            related={"NGC3031_M82_Final.jpg": ["M81", "M82"]},
        )
        proxy = self._proxy_for_item(item)

        proxy.set_search_text("m81")

        self.assertTrue(proxy.filterAcceptsRow(0, QtCore.QModelIndex()))

    def test_missing_status_keeps_item_without_images_in_dedup_mode(self) -> None:
        item = self._make_item(
            object_id="M81",
            name="Bode Galaxy",
            image_name=None,
            related={},
            deduped_image_count=0,
        )
        proxy = self._proxy_for_item(item, status="Missing")

        self.assertTrue(proxy.filterAcceptsRow(0, QtCore.QModelIndex()))

    def test_deduped_object_not_shown_as_missing_when_covered_by_shared_image(self) -> None:
        """M82 should NOT appear in 'Missing' when its photo was deduplicated to M81."""
        item = self._make_item(
            object_id="M82",
            name="Cigar Galaxy",
            image_name=None,
            related={},
            deduped_image_count=1,  # m81-M82.jpg was stripped away by dedup
        )
        proxy = self._proxy_for_item(item, status="Missing")

        self.assertFalse(proxy.filterAcceptsRow(0, QtCore.QModelIndex()))

    def test_deduped_object_shown_as_captured(self) -> None:
        """M82 with no remaining local image should be hidden in 'Captured'."""
        item = self._make_item(
            object_id="M82",
            name="Cigar Galaxy",
            image_name=None,
            related={},
            deduped_image_count=1,
        )
        proxy = self._proxy_for_item(item, status="Captured")

        self.assertFalse(proxy.filterAcceptsRow(0, QtCore.QModelIndex()))

    def test_search_m81_matches_image_filename(self) -> None:
        item = self._make_item(
            object_id="NGC3031",
            name="Bode Galaxy",
            image_name="M81_capture_v2.jpg",
            related={},
        )
        proxy = self._proxy_for_item(item)

        proxy.set_search_text("m81")

        self.assertTrue(proxy.filterAcceptsRow(0, QtCore.QModelIndex()))

    def test_search_m81_matches_ngc_alias_without_related_metadata(self) -> None:
        item = self._make_item(
            object_id="NGC3031",
            name="Bode Galaxy",
            image_name="bode_galaxy_final.jpg",
            related={},
        )
        proxy = self._proxy_for_item(item)

        proxy.set_search_text("m81")

        self.assertTrue(proxy.filterAcceptsRow(0, QtCore.QModelIndex()))

    def test_search_respects_catalog_filter(self) -> None:
        messier_item = self._make_item(
            object_id="M81",
            catalog="Messier",
            name="Bode Galaxy",
            image_name="M81_M82.jpg",
            related={"M81_M82.jpg": ["M82"]},
        )
        ngc_item = self._make_item(
            object_id="NGC3031",
            name="Bode Galaxy",
            image_name="M81_M82.jpg",
            related={"M81_M82.jpg": ["M81", "M82"]},
        )

        model = QtGui.QStandardItemModel()
        model.setColumnCount(1)
        model.setRowCount(2)
        model.setData(model.index(0, 0), messier_item, QtCore.Qt.ItemDataRole.UserRole)
        model.setData(model.index(1, 0), ngc_item, QtCore.Qt.ItemDataRole.UserRole)

        proxy = CatalogFilterProxy()
        proxy.setSourceModel(model)
        proxy.set_status_filter("Captured")
        proxy.set_catalog_filter("Messier")
        proxy.set_search_text("m81")

        self.assertTrue(proxy.filterAcceptsRow(0, QtCore.QModelIndex()))
        self.assertFalse(proxy.filterAcceptsRow(1, QtCore.QModelIndex()))

    def test_deduped_messier_item_is_hidden_in_catalog_view(self) -> None:
        item = self._make_item(
            object_id="M82",
            catalog="Messier",
            name="Cigar Galaxy",
            image_name=None,
            related={},
            deduped_image_count=1,
        )
        proxy = self._proxy_for_item(item, status="Captured")
        proxy.set_catalog_filter("Messier")
        proxy.set_search_text("m82")

        self.assertFalse(proxy.filterAcceptsRow(0, QtCore.QModelIndex()))

    def test_global_dedup_keeps_thumbnail_for_deduped_item(self) -> None:
        owner = self._make_item(
            object_id="M81",
            catalog="Messier",
            name="Bode Galaxy",
            image_name="M81_M82.jpg",
            related={"M81_M82.jpg": ["M81", "M82"]},
            thumbnail_name="M81_M82.jpg",
        )
        deduped = self._make_item(
            object_id="M82",
            catalog="Messier",
            name="Cigar Galaxy",
            image_name="M81_M82.jpg",
            related={"M81_M82.jpg": ["M81", "M82"]},
            thumbnail_name="M81_M82.jpg",
        )

        first_after, second_after = apply_global_image_deduplication([owner, deduped])

        retained = [item for item in (first_after, second_after) if item.image_paths]
        removed = [item for item in (first_after, second_after) if not item.image_paths]

        self.assertEqual(len(retained), 1)
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0].thumbnail_path, Path("M81_M82.jpg"))


if __name__ == "__main__":
    unittest.main()