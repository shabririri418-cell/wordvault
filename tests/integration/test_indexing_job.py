import zipfile
from pathlib import Path

from wordvault.library.importer import ImportService
from wordvault.search.indexing import IndexingJob, IndexingState
from wordvault.storage.database import LibraryDatabase


def make_docx(path: Path, text: str) -> None:
    with zipfile.ZipFile(path, "w") as package:
        package.writestr(
            "word/document.xml",
            f"""<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>""",
        )


def test_indexing_job_can_pause_resume_and_report_progress(tmp_path: Path) -> None:
    first = tmp_path / "一.docx"
    second = tmp_path / "二.docx"
    make_docx(first, "第一份资料")
    make_docx(second, "第二份资料")

    with LibraryDatabase.open(tmp_path / "资料库") as database:
        importer = ImportService(database)
        importer.import_file(first)
        importer.import_file(second)
        job = IndexingJob(database)

        initial = job.start()
        after_one = job.step()
        job.pause()
        paused = job.step()
        job.resume()
        completed = job.run_to_completion()

    assert initial.total == 2
    assert after_one.processed == 1
    assert paused.processed == 1
    assert paused.state is IndexingState.PAUSED
    assert completed.state is IndexingState.COMPLETED
    assert completed.successful == 2
    assert completed.failed == 0

