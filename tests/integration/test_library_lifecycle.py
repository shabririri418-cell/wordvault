from pathlib import Path

from wordvault.library.exporter import ExportConflictDecision, ExportService
from wordvault.library.importer import ImportService
from wordvault.library.lifecycle import LibraryLifecycleService
from wordvault.storage.database import LibraryDatabase


def test_trash_restore_and_permanent_delete(tmp_path: Path) -> None:
    source = tmp_path / "资料.docx"
    source.write_bytes(b"content")

    with LibraryDatabase.open(tmp_path / "资料库") as database:
        record = ImportService(database).import_file(source)
        lifecycle = LibraryLifecycleService(database)

        lifecycle.move_to_trash(record.document_id)
        assert not record.stored_path.exists()
        assert (database.root / "trash" / record.stored_path.name).exists()

        lifecycle.restore(record.document_id)
        assert record.stored_path.exists()

        lifecycle.move_to_trash(record.document_id)
        lifecycle.empty_trash()
        count = database.connection.execute("SELECT count(*) FROM documents").fetchone()[0]
        assert count == 0
        assert list((database.root / "trash").iterdir()) == []


def test_export_restores_name_and_can_auto_rename_conflict(tmp_path: Path) -> None:
    source = tmp_path / "涉密 报告.doc"
    source.write_bytes(b"managed content")
    export_root = tmp_path / "导出"
    export_root.mkdir()
    (export_root / source.name).write_bytes(b"existing")

    with LibraryDatabase.open(tmp_path / "资料库") as database:
        record = ImportService(database).import_file(source)
        exported = ExportService(database).export_document(
            record.document_id,
            export_root,
            decision=ExportConflictDecision.AUTO_RENAME,
        )

    assert exported.name == "涉密 报告 (2).doc"
    assert exported.read_bytes() == b"managed content"
    assert (export_root / source.name).read_bytes() == b"existing"


def test_consistency_check_reports_missing_and_unknown_files(tmp_path: Path) -> None:
    first = tmp_path / "一.docx"
    first.write_bytes(b"one")

    with LibraryDatabase.open(tmp_path / "资料库") as database:
        record = ImportService(database).import_file(first)
        record.stored_path.unlink()
        unknown = database.root / "documents" / "unknown.docx"
        unknown.write_bytes(b"unknown")

        report = LibraryLifecycleService(database).check_consistency()

    assert report.missing_document_ids == (record.document_id,)
    assert report.unknown_file_names == ("unknown.docx",)

