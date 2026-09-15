from __future__ import annotations

from pathlib import Path

from wordvault.content.parsers import DocxParser, LegacyDocParser, ParsedContent, ParseError
from wordvault.storage.database import LibraryDatabase


class ContentService:
    def __init__(self, database: LibraryDatabase) -> None:
        self.database = database
        self.parsers = {".docx": DocxParser(), ".doc": LegacyDocParser()}

    def parse_document(self, document_id: str) -> ParsedContent:
        row = self.database.connection.execute(
            "SELECT stored_name FROM documents WHERE id = ? AND status = 'active'", (document_id,)
        ).fetchone()
        if row is None:
            raise ValueError("文档不存在")
        stored_path = self.database.root / "documents" / row[0]
        parser = self.parsers.get(Path(row[0]).suffix.lower())
        if parser is None:
            raise ValueError("文档格式不受支持")
        try:
            result = parser.parse(stored_path)
        except ParseError as error:
            with self.database.connection:
                self.database.connection.execute(
                    "UPDATE documents SET parse_status = ?, content_text = NULL WHERE id = ?",
                    (f"error:{error.code}", document_id),
                )
            raise
        with self.database.connection:
            self.database.connection.execute(
                "UPDATE documents SET parse_status = 'ready', content_text = ? WHERE id = ?",
                (result.text, document_id),
            )
        return result


def quote_selection(
    selection: str,
    document_name: str,
    *,
    paragraph_number: int,
    include_source: bool,
) -> str:
    if not include_source:
        return selection
    safe_name = Path(document_name).name
    return f"{selection}\n\n——来源：《{safe_name}》，第{paragraph_number}段"

