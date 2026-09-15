import json
import zipfile
from pathlib import Path

from wordvault.diagnostics.document_structure import DocumentStructureInspector
from wordvault.storage.database import LibraryDatabase


def test_collects_docx_structure_without_exporting_names_or_text(tmp_path: Path) -> None:
    database = LibraryDatabase.open(tmp_path / "涉密资料库")
    stored_name = "random-id.docx"
    document = database.root / "documents" / stored_name
    secret = "绝密项目天穹七号"
    with zipfile.ZipFile(document, "w") as package:
        package.writestr(
            "word/document.xml",
            f'''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body><w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
            <w:r><w:t>{secret}</w:t></w:r></w:p>
            <w:tbl><w:tr><w:tc><w:p/></w:tc><w:tc><w:p/></w:tc></w:tr></w:tbl>
            <w:sectPr/></w:body></w:document>''',
        )
        package.writestr("word/header1.xml", "<root/>")
        package.writestr("word/comments.xml", "<root/>")
    database.connection.execute(
        """INSERT INTO documents(
            id, original_name, stored_name, sha256, size_bytes, modified_ns, imported_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            "internal-secret-id",
            "涉密方案.docx",
            stored_name,
            "deadbeef",
            document.stat().st_size,
            1,
            "now",
        ),
    )
    database.connection.commit()

    report = DocumentStructureInspector().inspect_library(database)
    serialized = json.dumps(report, ensure_ascii=False)

    assert report["document_count"] == 1
    assert report["documents"][0]["anonymous_id"] == "D-0001"
    assert report["documents"][0]["paragraph_bucket"] == "1_to_5"
    assert report["documents"][0]["table_bucket"] == "1_to_5"
    assert report["documents"][0]["has_header"] is True
    assert report["documents"][0]["has_comments"] is True
    forbidden_values = (
        secret,
        "涉密方案",
        stored_name,
        "internal-secret-id",
        "deadbeef",
        str(database.root),
    )
    for forbidden in forbidden_values:
        assert forbidden not in serialized
    database.close()


def test_invalid_docx_is_reported_with_safe_code(tmp_path: Path) -> None:
    database = LibraryDatabase.open(tmp_path / "library")
    document = database.root / "documents" / "broken.docx"
    document.write_bytes(b"not-a-document")
    database.connection.execute(
        """INSERT INTO documents(
            id, original_name, stored_name, sha256, size_bytes, modified_ns, imported_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("id", "secret.docx", document.name, "hash", document.stat().st_size, 1, "now"),
    )
    database.connection.commit()

    report = DocumentStructureInspector().inspect_library(database)

    assert report["documents"][0]["structure_status"] == "invalid_or_encrypted"
    database.close()
