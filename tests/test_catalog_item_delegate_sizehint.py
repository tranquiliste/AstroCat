from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from main import CatalogItemDelegate  # noqa: E402


class CatalogItemDelegateSizeHintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_size_hint_uses_list_view_grid_size(self) -> None:
        view = QtWidgets.QListView()
        view.setGridSize(QtCore.QSize(146, 172))
        delegate = CatalogItemDelegate(view)
        model = QtGui.QStandardItemModel(1, 1)
        index = model.index(0, 0)
        option = QtWidgets.QStyleOptionViewItem()
        option.widget = view

        size = delegate.sizeHint(option, index)

        self.assertEqual(size, QtCore.QSize(146, 172))


if __name__ == "__main__":
    unittest.main()