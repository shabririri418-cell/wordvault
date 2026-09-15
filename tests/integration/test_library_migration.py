from pathlib import Path

import pytest

from wordvault.library.importer import ImportService
from wordvault.library.migration import LibraryMigrationService
from wordvault.storage.database import LibraryDatabase


def test_migrates_library_without_deleting_the_source(tmp_path: Path) -> None:
    source_file = tmp_path / "文档.docx"
    source_file.write_bytes(b"document-content")
    source_root = tmp_path / "原资料库"
    destination = tmp_path / "新资料库"

    with LibraryDatabase.open(source_root) as database:
        record = ImportService(database).import_file(source_file)
        migrated = LibraryMigrationService(database).migrate(destination)

    assert migrated == destination.resolve()
    assert record.stored_path.exists()
    with LibraryDatabase.open(destination) as reopened:
        row = reopened.connection.execute(
            "SELECT stored_name FROM documents WHERE id = ?", (record.document_id,)
        ).fetchone()
        assert (destination / "documents" / row[0]).read_bytes() == b"document-content"


def test_refuses_to_replace_an_existing_destination(tmp_path: Path) -> None:
    destination = tmp_path / "已有目录"
    destination.mkdir()
    with (
        LibraryDatabase.open(tmp_path / "原资料库") as database,
        pytest.raises(ValueError, match="已经存在"),
    ):
        LibraryMigrationService(database).migrate(destination)
