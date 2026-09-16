from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from wordvault.classification.service import ClassificationService
from wordvault.storage.database import LibraryDatabase
from wordvault.ui.main_window import MainWindow


def main() -> None:
    output = Path("build/ui-preview.png").resolve()
    database = LibraryDatabase.open(Path("build/ui-preview-library").resolve())
    if not database.connection.execute("SELECT count(*) FROM categories").fetchone()[0]:
        service = ClassificationService(database)
        administration = service.create_category("行政管理")
        service.create_category("通知公告", parent_id=administration)
        service.create_category("规章制度", parent_id=administration)
        projects = service.create_category("项目资料")
        service.create_category("项目甲", parent_id=projects)
        service.create_category("培训材料")
    application = QApplication.instance() or QApplication([])
    window = MainWindow(database)
    if not database.connection.execute("SELECT count(*) FROM documents").fetchone()[0]:
        samples = sorted(Path("acceptance/samples").glob("*.docx"))[:4]
        window.import_paths(samples)
        first_category = database.connection.execute(
            "SELECT id FROM categories WHERE name = '规章制度'"
        ).fetchone()[0]
        first_document = database.connection.execute(
            "SELECT id FROM documents ORDER BY imported_at LIMIT 1"
        ).fetchone()[0]
        ClassificationService(database).assign(first_document, first_category)
        window._load_documents()
    window.document_list.setCurrentRow(0)
    window.show()

    def capture() -> None:
        window.grab().save(str(output))
        window.close()
        database.close()
        application.quit()

    QTimer.singleShot(500, capture)
    application.exec()


if __name__ == "__main__":
    main()
