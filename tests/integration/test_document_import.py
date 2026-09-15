from pathlib import Path

import pytest

from wordvault.library.importer import DuplicateConflict, DuplicateDecision, ImportService
from wordvault.storage.database import LibraryDatabase


def test_import_copies_word_file_and_keeps_source(tmp_path: Path) -> None:
    source = tmp_path / "来源" / "项目 方案.docx"
    source.parent.mkdir()
    source.write_bytes(b"first document")

    with LibraryDatabase.open(tmp_path / "资料库") as database:
        imported = ImportService(database).import_file(source)

        assert source.read_bytes() == b"first document"
        assert imported.original_name == "项目 方案.docx"
        assert imported.stored_path.read_bytes() == b"first document"
        assert imported.stored_path.parent == database.root / "documents"
        assert imported.stored_path.name != imported.original_name


def test_duplicate_requires_an_explicit_decision(tmp_path: Path) -> None:
    source = tmp_path / "报告.doc"
    source.write_bytes(b"version one")

    with LibraryDatabase.open(tmp_path / "资料库") as database:
        service = ImportService(database)
        original = service.import_file(source)

        with pytest.raises(DuplicateConflict) as conflict:
            service.import_file(source)

        assert conflict.value.existing_id == original.document_id
        assert conflict.value.same_content is True


def test_keep_both_and_overwrite_have_distinct_outcomes(tmp_path: Path) -> None:
    first = tmp_path / "a" / "报告.docx"
    second = tmp_path / "b" / "报告.docx"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"version one")
    second.write_bytes(b"version two")

    with LibraryDatabase.open(tmp_path / "资料库") as database:
        service = ImportService(database)
        original = service.import_file(first)
        kept = service.import_file(second, decision=DuplicateDecision.KEEP_BOTH)
        assert kept.document_id != original.document_id

        second.write_bytes(b"version three")
        overwritten = service.import_file(
            second,
            decision=DuplicateDecision.OVERWRITE,
            replace_document_id=original.document_id,
        )

        assert overwritten.document_id == original.document_id
        assert overwritten.stored_path.read_bytes() == b"version three"
        assert len(list((database.root / "documents").glob("*"))) == 2


def test_folder_import_recurses_and_ignores_non_word_files(tmp_path: Path) -> None:
    source = tmp_path / "待导入"
    (source / "子目录").mkdir(parents=True)
    (source / "根文档.docx").write_bytes(b"root")
    (source / "子目录" / "旧文档.doc").write_bytes(b"nested")
    (source / "说明.txt").write_text("ignored", encoding="utf-8")

    with LibraryDatabase.open(tmp_path / "资料库") as database:
        results = ImportService(database).import_folder(source)

    assert [result.original_name for result in results] == ["根文档.docx", "旧文档.doc"]

