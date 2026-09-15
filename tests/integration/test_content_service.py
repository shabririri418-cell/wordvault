import zipfile
from pathlib import Path

from wordvault.content.service import ContentService, quote_selection
from wordvault.library.importer import ImportService
from wordvault.storage.database import LibraryDatabase


def test_parse_document_updates_searchable_content(tmp_path: Path) -> None:
    source = tmp_path / "制度.docx"
    with zipfile.ZipFile(source, "w") as package:
        package.writestr(
            "word/document.xml",
            """<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body><w:p><w:r><w:t>保密管理制度</w:t></w:r></w:p></w:body></w:document>""",
        )

    with LibraryDatabase.open(tmp_path / "资料库") as database:
        record = ImportService(database).import_file(source)
        result = ContentService(database).parse_document(record.document_id)
        row = database.connection.execute(
            "SELECT parse_status, content_text FROM documents WHERE id = ?", (record.document_id,)
        ).fetchone()

    assert result.text == "保密管理制度"
    assert tuple(row) == ("ready", "保密管理制度")


def test_quote_uses_paragraph_location_instead_of_page_number() -> None:
    quoted = quote_selection("重要内容", "制度.docx", paragraph_number=8, include_source=True)

    assert quoted == "重要内容\n\n——来源：《制度.docx》，第8段"

