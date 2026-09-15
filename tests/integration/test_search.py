from datetime import UTC, datetime, timedelta
from pathlib import Path

from wordvault.classification.service import ClassificationService
from wordvault.library.importer import ImportService
from wordvault.search.service import SearchService
from wordvault.storage.database import LibraryDatabase


def add_document(database: LibraryDatabase, source: Path, content: str):
    source.write_bytes(source.name.encode("utf-8"))
    record = ImportService(database).import_file(source)
    database.connection.execute(
        "UPDATE documents SET content_text = ?, parse_status = 'ready' WHERE id = ?",
        (content, record.document_id),
    )
    database.connection.commit()
    return record


def test_searches_chinese_content_and_highlights_match(tmp_path: Path) -> None:
    with LibraryDatabase.open(tmp_path / "资料库") as database:
        document = add_document(database, tmp_path / "制度.docx", "必须遵守保密管理制度和操作要求")
        search = SearchService(database)
        search.rebuild()

        results = search.search("保密管理")

    assert [result.document_id for result in results] == [document.document_id]
    assert "<mark>保密管理</mark>" in results[0].highlighted_excerpt


def test_filters_by_category_and_extension(tmp_path: Path) -> None:
    with LibraryDatabase.open(tmp_path / "资料库") as database:
        first = add_document(database, tmp_path / "甲.docx", "设备采购合同")
        add_document(database, tmp_path / "乙.doc", "设备维修合同")
        categories = ClassificationService(database)
        category = categories.create_category("采购")
        categories.assign(first.document_id, category)
        search = SearchService(database)
        search.rebuild()

        results = search.search("设备", category_id=category, extension=".docx")

    assert [result.document_id for result in results] == [first.document_id]


def test_short_chinese_query_uses_safe_fallback(tmp_path: Path) -> None:
    with LibraryDatabase.open(tmp_path / "资料库") as database:
        document = add_document(database, tmp_path / "规范.docx", "终端安全管理规范")
        search = SearchService(database)
        search.rebuild()

        results = search.search("终端")

    assert [result.document_id for result in results] == [document.document_id]


def test_filters_by_import_time(tmp_path: Path) -> None:
    with LibraryDatabase.open(tmp_path / "资料库") as database:
        old = add_document(database, tmp_path / "旧.docx", "相同检索内容")
        recent = add_document(database, tmp_path / "新.docx", "相同检索内容")
        database.connection.execute(
            "UPDATE documents SET imported_at = ? WHERE id = ?",
            ((datetime.now(UTC) - timedelta(days=90)).isoformat(), old.document_id),
        )
        database.connection.commit()
        search = SearchService(database)
        search.rebuild()

        results = search.search(
            "相同检索",
            imported_after=datetime.now(UTC) - timedelta(days=30),
        )

    assert [result.document_id for result in results] == [recent.document_id]
