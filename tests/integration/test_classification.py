from pathlib import Path

import pytest

from wordvault.classification.service import ClassificationService
from wordvault.library.importer import ImportService
from wordvault.storage.database import LibraryDatabase


def test_allows_three_levels_but_rejects_a_fourth(tmp_path: Path) -> None:
    with LibraryDatabase.open(tmp_path / "资料库") as database:
        service = ClassificationService(database)
        level1 = service.create_category("制度")
        level2 = service.create_category("安全制度", parent_id=level1)
        level3 = service.create_category("终端安全", parent_id=level2)

        with pytest.raises(ValueError, match="最多支持三级分类"):
            service.create_category("第四级", parent_id=level3)


def test_nonempty_category_requires_document_migration(tmp_path: Path) -> None:
    source = tmp_path / "报告.docx"
    source.write_bytes(b"content")
    with LibraryDatabase.open(tmp_path / "资料库") as database:
        document = ImportService(database).import_file(source)
        service = ClassificationService(database)
        source_category = service.create_category("原分类")
        target_category = service.create_category("目标分类")
        service.assign(document.document_id, source_category)

        with pytest.raises(ValueError, match="仍包含文档"):
            service.delete_category(source_category)

        service.delete_category(source_category, migrate_to=target_category)
        assigned = database.connection.execute(
            "SELECT category_id FROM documents WHERE id = ?", (document.document_id,)
        ).fetchone()[0]

    assert assigned == target_category


def test_recommends_from_keywords_and_marks_auto_assignment_for_review(tmp_path: Path) -> None:
    source = tmp_path / "终端制度.docx"
    source.write_bytes(b"placeholder")
    with LibraryDatabase.open(tmp_path / "资料库") as database:
        document = ImportService(database).import_file(source)
        database.connection.execute(
            "UPDATE documents SET content_text = ? WHERE id = ?",
            ("终端设备必须安装安全软件，禁止泄露秘密", document.document_id),
        )
        database.connection.commit()
        service = ClassificationService(database)
        category = service.create_category("终端安全", keywords=("终端", "安全软件", "泄露"))

        recommendation = service.recommend(document.document_id)
        service.accept_recommendation(document.document_id, recommendation, automatic=True)
        row = database.connection.execute(
            "SELECT category_id, needs_review FROM documents WHERE id = ?", (document.document_id,)
        ).fetchone()

    assert recommendation is not None
    assert recommendation.category_id == category
    assert recommendation.confidence == "high"
    assert "终端" in recommendation.reasons
    assert tuple(row) == (category, 1)

