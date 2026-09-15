from __future__ import annotations

import os
import shutil
import sqlite3
from pathlib import Path
from types import TracebackType


class LibraryInitializationError(RuntimeError):
    """Raised when a document library cannot be safely initialized."""


class LibraryDatabase:
    DATABASE_NAME = "wordvault.sqlite3"
    CURRENT_SCHEMA_VERSION = 3

    def __init__(self, root: Path, connection: sqlite3.Connection) -> None:
        self.root = root
        self.connection = connection

    @classmethod
    def open(cls, root: Path) -> LibraryDatabase:
        resolved = root.expanduser().resolve()
        if resolved.exists() and not resolved.is_dir():
            raise LibraryInitializationError("所选资料库位置不是有效目录")

        try:
            resolved.mkdir(parents=True, exist_ok=True)
            for directory in ("documents", "trash", "logs"):
                (resolved / directory).mkdir(exist_ok=True)
        except OSError as error:
            raise LibraryInitializationError("无法创建资料库目录，请检查权限和磁盘空间") from error

        database_path = resolved / cls.DATABASE_NAME
        backup_path: Path | None = None
        try:
            connection = sqlite3.connect(database_path)
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            database = cls(resolved, connection)
            backup_path = database._backup_before_upgrade()
            database._initialize_schema()
            return database
        except sqlite3.DatabaseError as error:
            if "connection" in locals():
                connection.close()
            if backup_path is not None:
                cls._restore_failed_upgrade(database_path, backup_path)
            raise LibraryInitializationError("资料库数据库无法打开，原文件未被替换") from error

    def _initialize_schema(self) -> None:
        with self.connection:
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_info (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    version INTEGER NOT NULL
                )
                """
            )
            self.connection.execute(
                """
                INSERT OR IGNORE INTO schema_info(singleton, version)
                VALUES (1, ?)
                """,
                (self.CURRENT_SCHEMA_VERSION,),
            )
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS categories (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    parent_id TEXT REFERENCES categories(id) ON DELETE RESTRICT,
                    description TEXT NOT NULL DEFAULT '',
                    keywords_json TEXT NOT NULL DEFAULT '[]',
                    UNIQUE(parent_id, name)
                )
                """
            )
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    original_name TEXT NOT NULL,
                    stored_name TEXT NOT NULL UNIQUE,
                    source_relative_path TEXT,
                    sha256 TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    modified_ns INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'trash')),
                    imported_at TEXT NOT NULL,
                    deleted_at TEXT,
                    parse_status TEXT NOT NULL DEFAULT 'pending',
                    content_text TEXT,
                    category_id TEXT REFERENCES categories(id) ON DELETE RESTRICT,
                    needs_review INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            columns = {
                row[1] for row in self.connection.execute("PRAGMA table_info(documents)").fetchall()
            }
            if "category_id" not in columns:
                self.connection.execute(
                    "ALTER TABLE documents ADD COLUMN category_id TEXT REFERENCES categories(id)"
                )
            if "needs_review" not in columns:
                self.connection.execute(
                    "ALTER TABLE documents ADD COLUMN needs_review INTEGER NOT NULL DEFAULT 0"
                )
            self.connection.execute(
                "UPDATE schema_info SET version = ? WHERE singleton = 1",
                (self.CURRENT_SCHEMA_VERSION,),
            )

    def _backup_before_upgrade(self) -> Path | None:
        has_schema = self.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_info'"
        ).fetchone()
        if has_schema is None:
            return None
        row = self.connection.execute(
            "SELECT version FROM schema_info WHERE singleton = 1"
        ).fetchone()
        if row is None or int(row[0]) >= self.CURRENT_SCHEMA_VERSION:
            return None
        old_version = int(row[0])
        destination = self.root / f"{self.DATABASE_NAME}.pre-upgrade-v{old_version}"
        temporary = self.root / f".{destination.name}.part"
        temporary.unlink(missing_ok=True)
        backup = sqlite3.connect(temporary)
        try:
            self.connection.backup(backup)
        finally:
            backup.close()
        os.replace(temporary, destination)
        return destination

    @staticmethod
    def _restore_failed_upgrade(database_path: Path, backup_path: Path) -> None:
        for suffix in ("-wal", "-shm"):
            Path(f"{database_path}{suffix}").unlink(missing_ok=True)
        temporary = database_path.with_name(f".{database_path.name}.restore")
        temporary.unlink(missing_ok=True)
        shutil.copy2(backup_path, temporary)
        os.replace(temporary, database_path)

    @property
    def schema_version(self) -> int:
        row = self.connection.execute(
            "SELECT version FROM schema_info WHERE singleton = 1"
        ).fetchone()
        if row is None:
            raise LibraryInitializationError("资料库缺少数据库版本信息")
        return int(row[0])

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> LibraryDatabase:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
