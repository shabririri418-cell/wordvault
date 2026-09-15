from __future__ import annotations

import hashlib
from dataclasses import dataclass

from wordvault.content.parsers import ParseError
from wordvault.content.service import ContentService
from wordvault.search.service import SearchService
from wordvault.storage.database import LibraryDatabase


@dataclass(frozen=True)
class ChangeScanResult:
    changed: int
    failed: int


class ChangeMonitorService:
    def __init__(self, database: LibraryDatabase) -> None:
        self.database = database
        self.content = ContentService(database)
        self.search = SearchService(database)

    def scan(self) -> ChangeScanResult:
        rows = self.database.connection.execute(
            """
            SELECT id, stored_name, size_bytes, modified_ns FROM documents
            WHERE status = 'active'
            """
        ).fetchall()
        changed = failed = 0
        for document_id, stored_name, old_size, old_modified_ns in rows:
            path = self.database.root / "documents" / stored_name
            try:
                stat = path.stat()
            except OSError:
                failed += 1
                continue
            if stat.st_size == old_size and stat.st_mtime_ns == old_modified_ns:
                continue
            try:
                self.content.parse_document(document_id)
                digest = self._sha256(path)
                with self.database.connection:
                    self.database.connection.execute(
                        """
                        UPDATE documents SET sha256 = ?, size_bytes = ?, modified_ns = ?
                        WHERE id = ?
                        """,
                        (digest, stat.st_size, stat.st_mtime_ns, document_id),
                    )
                self.search.index_document(document_id)
                changed += 1
            except (OSError, ParseError, ValueError):
                failed += 1
        return ChangeScanResult(changed, failed)

    @staticmethod
    def _sha256(path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

