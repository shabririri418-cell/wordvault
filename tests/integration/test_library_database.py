import sqlite3
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


def test_upgrade_creates_a_database_backup_before_migration(tmp_path: Path) -> None:
    root = tmp_path / "资料库"
    root.mkdir()
    database_path = root / "wordvault.sqlite3"
    connection = sqlite3.connect(database_path)
    connection.execute("CREATE TABLE schema_info(singleton INTEGER PRIMARY KEY, version INTEGER)")
    connection.execute("INSERT INTO schema_info VALUES (1, 2)")
    connection.execute(
        """
        CREATE TABLE documents(
            id TEXT PRIMARY KEY, original_name TEXT, stored_name TEXT, source_relative_path TEXT,
            sha256 TEXT, size_bytes INTEGER, modified_ns INTEGER, status TEXT,
            imported_at TEXT, deleted_at TEXT, parse_status TEXT, content_text TEXT
        )
        """
    )
    connection.commit()
    connection.close()

    with LibraryDatabase.open(root) as upgraded:
        assert upgraded.schema_version == LibraryDatabase.CURRENT_SCHEMA_VERSION

    backup = sqlite3.connect(root / "wordvault.sqlite3.pre-upgrade-v2")
    backup_version = backup.execute("SELECT version FROM schema_info").fetchone()[0]
    backup.close()
    assert backup_version == 2
