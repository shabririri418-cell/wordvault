from __future__ import annotations

import html
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from wordvault.storage.database import LibraryDatabase


@dataclass(frozen=True)
class SearchResult:
    document_id: str
    original_name: str
    highlighted_excerpt: str
    score: float


class SearchService:
    def __init__(self, database: LibraryDatabase) -> None:
        self.database = database
        self.fts_available = self._ensure_fts_table()

    def rebuild(self) -> tuple[int, int]:
        if not self.fts_available:
            return (0, 0)
        rows = self.database.connection.execute(
            """
            SELECT id, original_name, content_text FROM documents
            WHERE status = 'active' AND parse_status = 'ready' AND content_text IS NOT NULL
            """
        ).fetchall()
        with self.database.connection:
            self.database.connection.execute("DELETE FROM documents_fts")
            self.database.connection.executemany(
                """
                INSERT INTO documents_fts(document_id, original_name, content_text)
                VALUES (?, ?, ?)
                """,
                rows,
            )
        return (len(rows), 0)

    def index_document(self, document_id: str) -> None:
        if not self.fts_available:
            return
        row = self.database.connection.execute(
            """
            SELECT id, original_name, content_text FROM documents
            WHERE id = ? AND status = 'active' AND parse_status = 'ready'
            """,
            (document_id,),
        ).fetchone()
        with self.database.connection:
            self.database.connection.execute(
                "DELETE FROM documents_fts WHERE document_id = ?", (document_id,)
            )
            if row is not None:
                self.database.connection.execute(
                    """
                    INSERT INTO documents_fts(document_id, original_name, content_text)
                    VALUES (?, ?, ?)
                    """,
                    tuple(row),
                )

    def search(
        self,
        query: str,
        *,
        category_id: str | None = None,
        extension: str | None = None,
        imported_after: datetime | None = None,
        limit: int = 100,
    ) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []
        if self.fts_available and len(query) >= 3:
            try:
                rows = self._fts_search(query, category_id, extension, imported_after, limit)
            except sqlite3.DatabaseError:
                rows = self._fallback_search(
                    query, category_id, extension, imported_after, limit
                )
        else:
            rows = self._fallback_search(query, category_id, extension, imported_after, limit)
        return [
            SearchResult(row[0], row[1], self._highlight(row[2] or row[1], query), float(row[3]))
            for row in rows
        ]

    def _fts_search(
        self,
        query: str,
        category_id: str | None,
        extension: str | None,
        imported_after: datetime | None,
        limit: int,
    ):
        clauses = ["documents_fts MATCH ?", "d.status = 'active'"]
        parameters: list[object] = [f'"{query.replace(chr(34), chr(34) * 2)}"']
        self._add_filters(clauses, parameters, category_id, extension, imported_after)
        parameters.append(limit)
        return self.database.connection.execute(
            f"""
            SELECT d.id, d.original_name, d.content_text, -bm25(documents_fts, 4.0, 1.0)
            FROM documents_fts
            JOIN documents d ON d.id = documents_fts.document_id
            WHERE {' AND '.join(clauses)}
            ORDER BY bm25(documents_fts, 4.0, 1.0)
            LIMIT ?
            """,
            parameters,
        ).fetchall()

    def _fallback_search(
        self,
        query: str,
        category_id: str | None,
        extension: str | None,
        imported_after: datetime | None,
        limit: int,
    ):
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        clauses = [
            "status = 'active'",
            "parse_status = 'ready'",
            "(original_name LIKE ? ESCAPE '\\' OR content_text LIKE ? ESCAPE '\\')",
        ]
        where_parameters: list[object] = [pattern, pattern]
        self._add_filters(
            clauses, where_parameters, category_id, extension, imported_after
        )
        parameters: list[object] = [query, *where_parameters, limit]
        return self.database.connection.execute(
            f"""
            SELECT id, original_name, content_text,
                CASE WHEN instr(lower(original_name), lower(?)) > 0 THEN 2.0 ELSE 1.0 END AS score
            FROM documents
            WHERE {' AND '.join(clauses)}
            ORDER BY score DESC, imported_at DESC
            LIMIT ?
            """,
            parameters,
        ).fetchall()

    @staticmethod
    def _add_filters(
        clauses: list[str],
        parameters: list[object],
        category_id: str | None,
        extension: str | None,
        imported_after: datetime | None,
    ) -> None:
        if category_id is not None:
            category_field = (
                "d.category_id" if clauses[0].startswith("documents_fts") else "category_id"
            )
            clauses.append(f"{category_field} = ?")
            parameters.append(category_id)
        if extension is not None:
            field = "d.original_name" if clauses[0].startswith("documents_fts") else "original_name"
            clauses.append(f"lower({field}) LIKE ?")
            parameters.append(f"%{extension.casefold()}")
        if imported_after is not None:
            imported_field = (
                "d.imported_at" if clauses[0].startswith("documents_fts") else "imported_at"
            )
            clauses.append(f"{imported_field} >= ?")
            parameters.append(imported_after.isoformat())

    def _ensure_fts_table(self) -> bool:
        try:
            self.database.connection.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                    document_id UNINDEXED,
                    original_name,
                    content_text,
                    tokenize='trigram'
                )
                """
            )
            return True
        except sqlite3.DatabaseError:
            return False

    @staticmethod
    def _highlight(text: str, query: str) -> str:
        position = text.casefold().find(query.casefold())
        if position < 0:
            return html.escape(text[:120])
        start = max(0, position - 50)
        end = min(len(text), position + len(query) + 70)
        before = html.escape(text[start:position])
        match = html.escape(text[position : position + len(query)])
        after = html.escape(text[position + len(query) : end])
        prefix = "…" if start else ""
        suffix = "…" if end < len(text) else ""
        return f"{prefix}{before}<mark>{match}</mark>{after}{suffix}"
