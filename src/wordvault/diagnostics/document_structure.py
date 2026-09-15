from __future__ import annotations

import sqlite3
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from wordvault.storage.database import LibraryDatabase


class DocumentStructureInspector:
    """Describe document shape without returning names, paths, hashes, or text."""

    W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

    def inspect_root(self, library_root: Path) -> dict[str, object]:
        database_path = library_root / LibraryDatabase.DATABASE_NAME
        connection = sqlite3.connect(f"file:{database_path.as_posix()}?mode=ro", uri=True)
        try:
            return self._inspect(connection, library_root)
        finally:
            connection.close()

    def inspect_library(self, database: LibraryDatabase) -> dict[str, object]:
        return self._inspect(database.connection, database.root)

    def _inspect(
        self, connection: sqlite3.Connection, library_root: Path
    ) -> dict[str, object]:
        rows = connection.execute(
            """SELECT stored_name, size_bytes, parse_status
               FROM documents WHERE status = 'active' ORDER BY imported_at, id"""
        ).fetchall()
        documents = []
        for index, (stored_name, size_bytes, parse_status) in enumerate(rows, start=1):
            path = library_root / "documents" / stored_name
            suffix = Path(stored_name).suffix.lower()
            base: dict[str, object] = {
                "anonymous_id": f"D-{index:04d}",
                "format": suffix.removeprefix(".") if suffix in {".doc", ".docx"} else "other",
                "size_bucket": self._size_bucket(int(size_bytes)),
                "parse_status": self._safe_parse_status(parse_status),
            }
            if suffix == ".docx":
                base.update(self._inspect_docx(path))
            else:
                base["structure_status"] = "limited_legacy_format"
            documents.append(base)
        return {
            "schema_version": 1,
            "document_count": len(documents),
            "documents": documents,
        }

    def _inspect_docx(self, path: Path) -> dict[str, object]:
        try:
            with zipfile.ZipFile(path) as package:
                names = set(package.namelist())
                root = ET.fromstring(package.read("word/document.xml"))
        except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError):
            return {"structure_status": "invalid_or_encrypted"}

        def count(tag: str) -> int:
            return sum(1 for _ in root.iter(f"{{{self.W}}}{tag}"))
        return {
            "structure_status": "readable",
            "paragraph_bucket": self._count_bucket(count("p")),
            "table_bucket": self._count_bucket(count("tbl")),
            "table_row_bucket": self._count_bucket(count("tr")),
            "section_bucket": self._count_bucket(max(1, count("sectPr"))),
            "heading_bucket": self._count_bucket(count("pStyle")),
            "field_bucket": self._count_bucket(count("fldSimple") + count("instrText")),
            "drawing_bucket": self._count_bucket(count("drawing") + count("pict")),
            "tracked_change_bucket": self._count_bucket(count("ins") + count("del")),
            "has_header": any(name.startswith("word/header") for name in names),
            "has_footer": any(name.startswith("word/footer") for name in names),
            "has_comments": "word/comments.xml" in names,
            "has_footnotes": "word/footnotes.xml" in names,
            "has_endnotes": "word/endnotes.xml" in names,
            "has_embedded_objects": any(name.startswith("word/embeddings/") for name in names),
            "has_macros": "word/vbaProject.bin" in names,
        }

    @staticmethod
    def _count_bucket(value: int) -> str:
        if value == 0:
            return "0"
        if value <= 5:
            return "1_to_5"
        if value <= 10:
            return "1_to_10"
        if value <= 50:
            return "11_to_50"
        if value <= 200:
            return "51_to_200"
        return "over_200"

    @staticmethod
    def _size_bucket(value: int) -> str:
        if value < 100 * 1024:
            return "under_100_kib"
        if value < 1024 * 1024:
            return "100_kib_to_1_mib"
        if value < 10 * 1024 * 1024:
            return "1_to_10_mib"
        if value < 50 * 1024 * 1024:
            return "10_to_50_mib"
        return "over_50_mib"

    @staticmethod
    def _safe_parse_status(value: object) -> str:
        return str(value) if value in {"pending", "parsed", "failed"} else "unknown"
