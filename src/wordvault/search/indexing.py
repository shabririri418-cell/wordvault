from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum

from wordvault.content.parsers import ParseError
from wordvault.content.service import ContentService
from wordvault.search.service import SearchService
from wordvault.storage.database import LibraryDatabase


class IndexingState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


@dataclass(frozen=True)
class IndexingProgress:
    state: IndexingState
    total: int
    processed: int
    successful: int
    failed: int
    estimated_remaining_seconds: int | None


class IndexingJob:
    def __init__(self, database: LibraryDatabase) -> None:
        self.database = database
        self.content = ContentService(database)
        self.search = SearchService(database)
        self.state = IndexingState.IDLE
        self.document_ids: list[str] = []
        self.processed = 0
        self.successful = 0
        self.failed = 0
        self.started_at: float | None = None

    def start(self) -> IndexingProgress:
        rows = self.database.connection.execute(
            "SELECT id FROM documents WHERE status = 'active' ORDER BY imported_at"
        ).fetchall()
        self.document_ids = [row[0] for row in rows]
        self.processed = self.successful = self.failed = 0
        self.started_at = time.monotonic()
        self.state = IndexingState.RUNNING if self.document_ids else IndexingState.COMPLETED
        if self.search.fts_available:
            with self.database.connection:
                self.database.connection.execute("DELETE FROM documents_fts")
        return self.progress()

    def step(self) -> IndexingProgress:
        if self.state is not IndexingState.RUNNING:
            return self.progress()
        document_id = self.document_ids[self.processed]
        try:
            self.content.parse_document(document_id)
            self.search.index_document(document_id)
            self.successful += 1
        except (ParseError, OSError, ValueError):
            self.failed += 1
        self.processed += 1
        if self.processed >= len(self.document_ids):
            self.state = IndexingState.COMPLETED
        return self.progress()

    def pause(self) -> IndexingProgress:
        if self.state is IndexingState.RUNNING:
            self.state = IndexingState.PAUSED
        return self.progress()

    def resume(self) -> IndexingProgress:
        if self.state is IndexingState.PAUSED:
            self.state = IndexingState.RUNNING
        return self.progress()

    def run_to_completion(self) -> IndexingProgress:
        while self.state is IndexingState.RUNNING:
            self.step()
        return self.progress()

    def progress(self) -> IndexingProgress:
        remaining = None
        if (
            self.processed
            and self.started_at is not None
            and self.state is not IndexingState.COMPLETED
        ):
            elapsed = time.monotonic() - self.started_at
            pending = len(self.document_ids) - self.processed
            remaining = round((elapsed / self.processed) * pending)
        return IndexingProgress(
            self.state,
            len(self.document_ids),
            self.processed,
            self.successful,
            self.failed,
            remaining,
        )
