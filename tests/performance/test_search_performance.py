import time
from datetime import UTC, datetime
from pathlib import Path

from wordvault.search.service import SearchService
from wordvault.storage.database import LibraryDatabase


def test_search_one_thousand_documents_in_under_two_seconds(tmp_path: Path) -> None:
    with LibraryDatabase.open(tmp_path / "资料库") as database:
        now = datetime.now(UTC).isoformat()
        rows = [
            (
                f"doc-{index}",
                f"第{index}号管理制度.docx",
                f"doc-{index}.docx",
                f"hash-{index}",
                now,
                "包含终端安全和保密管理要求" if index == 777 else "普通资料内容",
            )
            for index in range(1000)
        ]
        database.connection.executemany(
            """
            INSERT INTO documents(
                id, original_name, stored_name, sha256, size_bytes, modified_ns,
                imported_at, parse_status, content_text
            ) VALUES (?, ?, ?, ?, 1, 1, ?, 'ready', ?)
            """,
            rows,
        )
        database.connection.commit()
        search = SearchService(database)
        search.rebuild()

        started = time.perf_counter()
        results = search.search("保密管理")
        elapsed = time.perf_counter() - started

    assert results[0].document_id == "doc-777"
    assert elapsed < 2.0

