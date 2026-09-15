from __future__ import annotations

import os
import shutil
from enum import Enum
from pathlib import Path

from wordvault.storage.database import LibraryDatabase


class ExportConflictDecision(Enum):
    OVERWRITE = "overwrite"
    AUTO_RENAME = "auto_rename"
    SKIP = "skip"


class ExportService:
    def __init__(self, database: LibraryDatabase) -> None:
        self.database = database

    def export_document(
        self,
        document_id: str,
        destination_directory: Path,
        *,
        decision: ExportConflictDecision = ExportConflictDecision.SKIP,
    ) -> Path | None:
        row = self.database.connection.execute(
            """
            SELECT original_name, stored_name FROM documents
            WHERE id = ? AND status = 'active'
            """,
            (document_id,),
        ).fetchone()
        if row is None:
            raise ValueError("要导出的文档不存在")

        destination_directory = destination_directory.expanduser().resolve()
        if not destination_directory.is_dir():
            raise ValueError("导出位置不是有效目录")
        safe_name = Path(row[0]).name
        destination = destination_directory / safe_name
        if destination.exists():
            if decision is ExportConflictDecision.SKIP:
                return None
            if decision is ExportConflictDecision.AUTO_RENAME:
                destination = self._available_name(destination)

        source = self.database.root / "documents" / row[1]
        temporary = destination.with_name(f".{destination.name}.part")
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
        return destination

    def export_category(
        self,
        category_id: str,
        destination_directory: Path,
        *,
        decision: ExportConflictDecision = ExportConflictDecision.SKIP,
    ) -> list[Path]:
        rows = self.database.connection.execute(
            """
            SELECT id FROM documents
            WHERE category_id = ? AND status = 'active'
            ORDER BY imported_at
            """,
            (category_id,),
        ).fetchall()
        exported = []
        for row in rows:
            path = self.export_document(row[0], destination_directory, decision=decision)
            if path is not None:
                exported.append(path)
        return exported

    @staticmethod
    def _available_name(destination: Path) -> Path:
        number = 2
        while True:
            candidate = destination.with_name(f"{destination.stem} ({number}){destination.suffix}")
            if not candidate.exists():
                return candidate
            number += 1
