import zipfile
from pathlib import Path

from wordvault.storage.database import LibraryDatabase
from wordvault.ui.main_window import MainWindow


def test_main_window_shows_empty_library_guidance(qtbot, tmp_path: Path) -> None:
    database = LibraryDatabase.open(tmp_path / "资料库")
    window = MainWindow(database)
    qtbot.addWidget(window)

    assert window.windowTitle() == "文澜资料库"
    assert "导入 Word 文档" in window.empty_state.text()

    database.close()


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
