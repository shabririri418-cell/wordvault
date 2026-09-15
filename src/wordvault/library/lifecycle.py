from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime

from wordvault.storage.database import LibraryDatabase


@dataclass(frozen=True)
class ConsistencyReport:
    missing_document_ids: tuple[str, ...]
    unknown_file_names: tuple[str, ...]


class LibraryLifecycleService:
    def __init__(self, database: LibraryDatabase) -> None:
        self.database = database

    def move_to_trash(self, document_id: str) -> None:
        row = self._active_document(document_id)
        source = self.database.root / "documents" / row[0]
        destination = self.database.root / "trash" / row[0]
        if not source.is_file():
            raise FileNotFoundError("资料库中的文档文件不存在")
        os.replace(source, destination)
        try:
            with self.database.connection:
                self.database.connection.execute(
                    "UPDATE documents SET status = 'trash', deleted_at = ? WHERE id = ?",
                    (datetime.now(UTC).isoformat(), document_id),
                )
        except Exception:
            os.replace(destination, source)
            raise

    def restore(self, document_id: str) -> None:
        row = self.database.connection.execute(
            "SELECT stored_name FROM documents WHERE id = ? AND status = 'trash'", (document_id,)
        ).fetchone()
        if row is None:
            raise ValueError("回收站中没有该文档")
        source = self.database.root / "trash" / row[0]
        destination = self.database.root / "documents" / row[0]
        if destination.exists():
            raise FileExistsError("资料库中存在冲突文件，无法恢复")
        os.replace(source, destination)
        try:
            with self.database.connection:
                self.database.connection.execute(
                    "UPDATE documents SET status = 'active', deleted_at = NULL WHERE id = ?",
                    (document_id,),
                )
        except Exception:
            os.replace(destination, source)
            raise

    def empty_trash(self) -> None:
        rows = self.database.connection.execute(
            "SELECT id, stored_name FROM documents WHERE status = 'trash'"
        ).fetchall()
        for _, stored_name in rows:
            (self.database.root / "trash" / stored_name).unlink(missing_ok=True)
        with self.database.connection:
            self.database.connection.execute("DELETE FROM documents WHERE status = 'trash'")

    def check_consistency(self) -> ConsistencyReport:
        rows = self.database.connection.execute(
            "SELECT id, stored_name FROM documents WHERE status = 'active'"
        ).fetchall()
        expected = {stored_name: document_id for document_id, stored_name in rows}
        actual = {
            path.name
            for path in (self.database.root / "documents").iterdir()
            if path.is_file() and not path.name.endswith((".part", ".rollback"))
        }
        missing = tuple(sorted(expected[name] for name in expected.keys() - actual))
        unknown = tuple(sorted(actual - expected.keys()))
        return ConsistencyReport(missing, unknown)

    def _active_document(self, document_id: str):
        row = self.database.connection.execute(
            "SELECT stored_name FROM documents WHERE id = ? AND status = 'active'", (document_id,)
        ).fetchone()
        if row is None:
            raise ValueError("文档不存在或已经在回收站中")
        return row

