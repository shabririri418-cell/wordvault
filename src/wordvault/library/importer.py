from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from wordvault.storage.database import LibraryDatabase


class DuplicateDecision(Enum):
    OVERWRITE = "overwrite"
    KEEP_BOTH = "keep_both"
    CANCEL = "cancel"


class DuplicateConflict(RuntimeError):
    def __init__(self, existing_id: str, same_content: bool) -> None:
        super().__init__("文档已存在，需要选择覆盖、保留两份或取消")
        self.existing_id = existing_id
        self.same_content = same_content


class ImportCancelled(RuntimeError):
    pass


@dataclass(frozen=True)
class DocumentRecord:
    document_id: str
    original_name: str
    stored_path: Path
    sha256: str
    size_bytes: int


class ImportService:
    SUPPORTED_SUFFIXES = frozenset({".doc", ".docx"})

    def __init__(self, database: LibraryDatabase) -> None:
        self.database = database

    def import_file(
        self,
        source: Path,
        *,
        decision: DuplicateDecision | None = None,
        replace_document_id: str | None = None,
        source_root: Path | None = None,
    ) -> DocumentRecord:
        source = source.expanduser().resolve()
        if not source.is_file() or source.suffix.lower() not in self.SUPPORTED_SUFFIXES:
            raise ValueError("只能导入有效的 .doc 或 .docx 文件")

        digest = self._sha256(source)
        conflict = self._find_conflict(source.name, digest)
        if conflict is not None and decision is None:
            raise DuplicateConflict(conflict["id"], conflict["sha256"] == digest)
        if decision is DuplicateDecision.CANCEL:
            raise ImportCancelled("已取消导入")
        if decision is DuplicateDecision.OVERWRITE:
            target_id = replace_document_id or (conflict["id"] if conflict else None)
            if target_id is None:
                raise ValueError("覆盖操作缺少目标文档")
            return self._overwrite(target_id, source, digest, source_root)
        return self._insert(source, digest, source_root)

    def import_folder(self, source_root: Path) -> list[DocumentRecord]:
        source_root = source_root.expanduser().resolve()
        if not source_root.is_dir():
            raise ValueError("待导入位置不是文件夹")
        candidates = [
            path
            for path in source_root.rglob("*")
            if path.is_file() and path.suffix.lower() in self.SUPPORTED_SUFFIXES
        ]
        candidates.sort(key=lambda path: (len(path.relative_to(source_root).parts), str(path)))
        return [self.import_file(path, source_root=source_root) for path in candidates]

    def _insert(self, source: Path, digest: str, source_root: Path | None) -> DocumentRecord:
        document_id = str(uuid.uuid4())
        stored_name = f"{document_id}{source.suffix.lower()}"
        destination = self.database.root / "documents" / stored_name
        temporary = destination.with_suffix(destination.suffix + ".part")
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
        stat = source.stat()
        relative = self._relative_source(source, source_root)
        try:
            with self.database.connection:
                self.database.connection.execute(
                    """
                    INSERT INTO documents(
                        id, original_name, stored_name, source_relative_path, sha256,
                        size_bytes, modified_ns, imported_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        document_id,
                        source.name,
                        stored_name,
                        relative,
                        digest,
                        stat.st_size,
                        stat.st_mtime_ns,
                        datetime.now(UTC).isoformat(),
                    ),
                )
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        return DocumentRecord(document_id, source.name, destination, digest, stat.st_size)

    def _overwrite(
        self, document_id: str, source: Path, digest: str, source_root: Path | None
    ) -> DocumentRecord:
        row = self.database.connection.execute(
            "SELECT stored_name FROM documents WHERE id = ? AND status = 'active'", (document_id,)
        ).fetchone()
        if row is None:
            raise ValueError("要覆盖的文档不存在")
        destination = self.database.root / "documents" / row[0]
        temporary = destination.with_suffix(destination.suffix + ".part")
        rollback = destination.with_suffix(destination.suffix + ".rollback")
        shutil.copy2(source, temporary)
        stat = source.stat()
        try:
            os.replace(destination, rollback)
            os.replace(temporary, destination)
            with self.database.connection:
                self.database.connection.execute(
                    """
                    UPDATE documents SET original_name = ?, source_relative_path = ?, sha256 = ?,
                        size_bytes = ?, modified_ns = ?, imported_at = ?, parse_status = 'pending',
                        content_text = NULL
                    WHERE id = ?
                    """,
                    (
                        source.name,
                        self._relative_source(source, source_root),
                        digest,
                        stat.st_size,
                        stat.st_mtime_ns,
                        datetime.now(UTC).isoformat(),
                        document_id,
                    ),
                )
        except Exception:
            destination.unlink(missing_ok=True)
            if rollback.exists():
                os.replace(rollback, destination)
            raise
        rollback.unlink(missing_ok=True)
        return DocumentRecord(document_id, source.name, destination, digest, stat.st_size)

    def _find_conflict(self, name: str, digest: str):
        self.database.connection.row_factory = __import__("sqlite3").Row
        return self.database.connection.execute(
            """
            SELECT id, sha256 FROM documents
            WHERE status = 'active' AND (sha256 = ? OR lower(original_name) = lower(?))
            ORDER BY CASE WHEN sha256 = ? THEN 0 ELSE 1 END, imported_at DESC
            LIMIT 1
            """,
            (digest, name, digest),
        ).fetchone()

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _relative_source(source: Path, source_root: Path | None) -> str | None:
        if source_root is None:
            return None
        return str(source.relative_to(source_root.resolve()))

