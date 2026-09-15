from pathlib import Path

from wordvault.content.parsers import DocxParser
from wordvault.content.service import ContentService
from wordvault.library.importer import ImportService
from wordvault.search.service import SearchService
from wordvault.storage.database import LibraryDatabase


def test_acceptance_samples_cover_import_parse_and_body_search(tmp_path: Path) -> None:
    samples = Path(__file__).resolve().parents[2] / "acceptance" / "samples"
    expected_queries = {
        "年度继续教育": "01-人事管理制度.docx",
        "有效票据": "02-财务报销办法.docx",
        "诊断日志": "03-项目会议纪要.docx",
    }

    with LibraryDatabase.open(tmp_path / "library") as database:
        imported = ImportService(database).import_folder(samples)
        assert len(imported) == 4
        content = ContentService(database)
        search = SearchService(database)
        for record in imported:
            parsed = content.parse_document(record.document_id)
            assert DocxParser().parse(samples / record.original_name).text == parsed.text
            search.index_document(record.document_id)

        for query, expected_title in expected_queries.items():
            results = search.search(query)
            assert results
            assert results[0].original_name == expected_title
