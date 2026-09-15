import time
import zipfile
from pathlib import Path

from wordvault.content.change_monitor import ChangeMonitorService
from wordvault.content.service import ContentService
from wordvault.library.importer import ImportService
from wordvault.storage.database import LibraryDatabase


def write_docx(path: Path, text: str) -> None:
    with zipfile.ZipFile(path, "w") as package:
        package.writestr(
            "word/document.xml",
            f"""<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>""",
        )


def test_reparses_document_changed_by_wps(tmp_path: Path) -> None:
    source = tmp_path / "制度.docx"
    write_docx(source, "修改前")
    with LibraryDatabase.open(tmp_path / "资料库") as database:
        record = ImportService(database).import_file(source)
        ContentService(database).parse_document(record.document_id)
        time.sleep(0.01)
        write_docx(record.stored_path, "修改后内容")

        result = ChangeMonitorService(database).scan()
        row = database.connection.execute(
            "SELECT content_text FROM documents WHERE id = ?", (record.document_id,)
        ).fetchone()

    assert result.changed == 1
    assert result.failed == 0
    assert row[0] == "修改后内容"
