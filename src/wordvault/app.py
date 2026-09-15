from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from wordvault.storage.database import LibraryDatabase, LibraryInitializationError
from wordvault.ui.main_window import MainWindow


def run() -> int:
    application = QApplication.instance() or QApplication(sys.argv)
    application.setApplicationName("文澜资料库")
    application.setOrganizationName("WordVault")
    settings = QSettings()
    saved_root = settings.value("library_root", "", str)
    root = Path(saved_root) if saved_root else _choose_library_root()
    if root is None:
        return 0

    try:
        database = LibraryDatabase.open(root)
    except LibraryInitializationError as error:
        QMessageBox.critical(None, "无法打开资料库", str(error))
        return 1

    settings.setValue("library_root", str(database.root))
    window = MainWindow(database)
    window.show()
    exit_code = application.exec()
    database.close()
    return exit_code


def _choose_library_root() -> Path | None:
    selected = QFileDialog.getExistingDirectory(None, "选择资料库保存位置")
    return Path(selected) / "文澜资料库" if selected else None

