import zipfile
from pathlib import Path

import pytest

from wordvault.content.parsers import DocxParser, LegacyDocParser, ParseError


def make_docx(path: Path, body_xml: str) -> None:
    with zipfile.ZipFile(path, "w") as package:
        package.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        package.writestr("word/document.xml", body_xml)


def test_extracts_paragraphs_and_table_cells_in_reading_order(tmp_path: Path) -> None:
    path = tmp_path / "中文.docx"
    make_docx(
        path,
        """<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
        <w:body>
          <w:p><w:r><w:t>第一段</w:t></w:r><w:r><w:t>继续</w:t></w:r></w:p>
          <w:tbl><w:tr><w:tc><w:p><w:r><w:t>甲</w:t></w:r></w:p></w:tc>
          <w:tc><w:p><w:r><w:t>乙</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
        </w:body></w:document>""",
    )

    result = DocxParser().parse(path)

    assert result.paragraphs == ("第一段继续", "甲", "乙")
    assert result.text == "第一段继续\n甲\n乙"


def test_reports_corrupt_docx_with_stable_error_code(tmp_path: Path) -> None:
    path = tmp_path / "损坏.docx"
    path.write_bytes(b"broken")

    with pytest.raises(ParseError) as error:
        DocxParser().parse(path)

    assert error.value.code == "DOCX_INVALID"


def test_legacy_doc_parser_prefers_local_tika_without_using_a_shell(tmp_path: Path) -> None:
    java = tmp_path / "java"
    tika = tmp_path / "tika-app.jar"
    document = tmp_path / "旧格式.doc"
    java.write_bytes(b"")
    tika.write_bytes(b"")
    document.write_bytes(b"")

    command = LegacyDocParser(tika_jar=tika, java_executable=java).build_command(document)

    assert command == [
        str(java.resolve()),
        "-jar",
        str(tika.resolve()),
        "--text",
        str(document.resolve()),
    ]
