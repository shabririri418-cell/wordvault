from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import uuid
from pathlib import Path

from wordvault.storage.database import LibraryDatabase


class LibraryMigrationService:
    def __init__(self, database: LibraryDatabase) -> None:
        self.database = database

    def migrate(self, destination: Path) -> Path:
        destination = destination.expanduser().resolve()
        source = self.database.root.resolve()
        if destination.exists():
            raise ValueError("目标资料库目录已经存在")
        if destination.is_relative_to(source):
            raise ValueError("新资料库不能放在当前资料库内部")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.parent / f".{destination.name}.migration-{uuid.uuid4().hex}"
        temporary.mkdir()
        try:
            for directory in ("documents", "trash", "logs"):
                shutil.copytree(source / directory, temporary / directory)
            self._backup_database(temporary / LibraryDatabase.DATABASE_NAME)
            self._verify(temporary)
            os.replace(temporary, destination)
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
        return destination

    def _backup_database(self, destination: Path) -> None:
        backup = sqlite3.connect(destination)
        try:
            self.database.connection.backup(backup)
        finally:
            backup.close()

    def _verify(self, root: Path) -> None:
        rows = self.database.connection.execute(
            "SELECT stored_name, sha256, status FROM documents"
        ).fetchall()
        for stored_name, expected_digest, status in rows:
            directory = "trash" if status == "trash" else "documents"
            path = root / directory / stored_name
            if not path.is_file() or self._sha256(path) != expected_digest:
                raise OSError("资料库迁移校验失败，原资料库保持不变")

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

