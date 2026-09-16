import json
import zipfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from wordvault.classification.service import ClassificationService
from wordvault.storage.database import LibraryDatabase
from wordvault.ui.main_window import MainWindow


def test_main_window_shows_empty_library_guidance(qtbot, tmp_path: Path) -> None:
    database = LibraryDatabase.open(tmp_path / "资料库")
    window = MainWindow(database)
    qtbot.addWidget(window)

    assert window.windowTitle() == "文澜资料库"
    assert "导入 Word 文档" in window.empty_state.text()
    assert window.workspace_splitter.isHidden()

    database.close()


def test_main_window_assigns_one_category_and_copies_source_quote(qtbot, tmp_path: Path) -> None:
    source = tmp_path / "引用制度.docx"
    with zipfile.ZipFile(source, "w") as package:
        package.writestr(
            "word/document.xml",
            """<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body><w:p><w:r><w:t>引用这一段</w:t></w:r></w:p></w:body></w:document>""",
        )
    database = LibraryDatabase.open(tmp_path / "资料库")
    category = ClassificationService(database).create_category("规章制度")
    window = MainWindow(database)
    qtbot.addWidget(window)
    window.import_paths([source])
    window.document_list.setCurrentRow(0)

    category_index = window.category_combo.findData(category)
    window._assign_category(category_index)
    window._copy_with_source()
    assigned = database.connection.execute("SELECT category_id FROM documents").fetchone()[0]

    assert assigned == category
    assert QApplication.clipboard().text() == "引用这一段\n\n——来源：《引用制度.docx》，第1段"
    database.close()


def test_main_window_moves_document_to_trash_and_restores_it(qtbot, tmp_path: Path) -> None:
    source = tmp_path / "待删除.docx"
    with zipfile.ZipFile(source, "w") as package:
        package.writestr(
            "word/document.xml",
            """<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body><w:p><w:r><w:t>稍后恢复</w:t></w:r></w:p></w:body></w:document>""",
        )
    database = LibraryDatabase.open(tmp_path / "资料库")
    window = MainWindow(database)
    qtbot.addWidget(window)
    window.import_paths([source])
    window.document_list.setCurrentRow(0)

    window._move_current_to_trash(confirm=False)
    window._show_trash()
    window.document_list.setCurrentRow(0)
    window._restore_current()

    status = database.connection.execute("SELECT status FROM documents").fetchone()[0]
    assert status == "active"
    database.close()


def test_main_window_exports_sanitized_diagnostics(qtbot, tmp_path: Path) -> None:
    database = LibraryDatabase.open(tmp_path / "资料库")
    window = MainWindow(database)
    qtbot.addWidget(window)

    archive = window._export_diagnostics_to(tmp_path / "diagnostics.zip")

    with zipfile.ZipFile(archive) as package:
        assert set(package.namelist()) == {
            "collection-structure.json",
            "environment.json",
            "events.jsonl",
            "self-check.json",
        }
        assert "APP_STARTED" in package.read("events.jsonl").decode("utf-8")
        report = json.loads(package.read("self-check.json"))
        assert report["overall_status"] == "pass"
    database.close()


def test_change_timer_stops_if_database_was_closed(qtbot, tmp_path: Path) -> None:
    database = LibraryDatabase.open(tmp_path / "资料库")
    window = MainWindow(database)
    qtbot.addWidget(window)
    database.close()

    window._scan_external_changes()

    assert window.change_timer.isActive() is False


def test_main_window_imports_lists_and_previews_docx(qtbot, tmp_path: Path) -> None:
    source = tmp_path / "管理制度.docx"
    with zipfile.ZipFile(source, "w") as package:
        package.writestr(
            "word/document.xml",
            """<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body><w:p><w:r><w:t>本文件仅在本机使用</w:t></w:r></w:p></w:body></w:document>""",
        )
    database = LibraryDatabase.open(tmp_path / "资料库")
    window = MainWindow(database)
    qtbot.addWidget(window)

    window.import_paths([source])
    window.document_list.setCurrentRow(0)

    assert window.document_list.count() == 1
    assert window.document_list.item(0).text() == "管理制度.docx"
    assert "本文件仅在本机使用" in window.preview.toPlainText()

    database.close()


def test_categories_are_shown_as_a_nested_navigation_tree(qtbot, tmp_path: Path) -> None:
    database = LibraryDatabase.open(tmp_path / "资料库")
    categories = ClassificationService(database)
    parent = categories.create_category("行政管理")
    child = categories.create_category("规章制度", parent_id=parent)

    window = MainWindow(database)
    qtbot.addWidget(window)

    assert window.category_tree.topLevelItemCount() == 1
    parent_item = window.category_tree.topLevelItem(0)
    assert parent_item.text(0) == "行政管理"
    assert parent_item.child(0).text(0) == "规章制度"
    assert parent_item.child(0).data(0, Qt.ItemDataRole.UserRole) == child
    database.close()


def test_selecting_a_category_in_the_tree_filters_the_document_list(qtbot, tmp_path: Path) -> None:
    source = tmp_path / "制度.docx"
    with zipfile.ZipFile(source, "w") as package:
        package.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>制度正文</w:t></w:r></w:p></w:body></w:document>",
        )
    database = LibraryDatabase.open(tmp_path / "资料库")
    category = ClassificationService(database).create_category("规章制度")
    window = MainWindow(database)
    qtbot.addWidget(window)
    window.import_paths([source])
    document_id = database.connection.execute("SELECT id FROM documents").fetchone()[0]
    ClassificationService(database).assign(document_id, category)

    window._refresh_categories()
    window.category_tree.setCurrentItem(window.category_tree.topLevelItem(0))

    assert window.page_title.text() == "规章制度"
    assert window.document_list.count() == 1
    database.close()


def test_advanced_search_filters_are_hidden_until_requested(qtbot, tmp_path: Path) -> None:
    database = LibraryDatabase.open(tmp_path / "资料库")
    window = MainWindow(database)
    qtbot.addWidget(window)

    assert window.filter_panel.isHidden()
    qtbot.mouseClick(window.filter_button, Qt.MouseButton.LeftButton)
    assert not window.filter_panel.isHidden()
    database.close()
