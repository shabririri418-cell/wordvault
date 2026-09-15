from pathlib import Path

import pytest

from wordvault.storage.database import LibraryDatabase, LibraryInitializationError


def test_initializes_and_reopens_a_library(tmp_path: Path) -> None:
    root = tmp_path / "资料库"

    with LibraryDatabase.open(root) as database:
        assert database.schema_version == 3
        database.connection.execute(
            "INSERT INTO settings(key, value) VALUES (?, ?)", ("theme", "light")
        )
        database.connection.commit()

    with LibraryDatabase.open(root) as reopened:
        value = reopened.connection.execute(
            "SELECT value FROM settings WHERE key = ?", ("theme",)
        ).fetchone()[0]

    assert value == "light"
    assert (root / "documents").is_dir()
    assert (root / "trash").is_dir()
    assert (root / "logs").is_dir()


def test_rejects_a_file_as_library_root(tmp_path: Path) -> None:
    root = tmp_path / "不是目录"
    root.write_text("x", encoding="utf-8")

    with pytest.raises(LibraryInitializationError, match="不是有效目录"):
        LibraryDatabase.open(root)


def test_reports_a_corrupt_database_without_replacing_it(tmp_path: Path) -> None:
    root = tmp_path / "资料库"
    root.mkdir()
    database_path = root / "wordvault.sqlite3"
    database_path.write_bytes(b"not-a-database")

    with pytest.raises(LibraryInitializationError, match="数据库无法打开"):
        LibraryDatabase.open(root)

    assert database_path.read_bytes() == b"not-a-database"
