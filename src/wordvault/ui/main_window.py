from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from wordvault.content.parsers import ParseError
from wordvault.content.service import ContentService
from wordvault.content.wps import WpsLauncher
from wordvault.library.importer import DuplicateConflict, DuplicateDecision, ImportService
from wordvault.search.service import SearchService
from wordvault.storage.database import LibraryDatabase


class MainWindow(QMainWindow):
    def __init__(self, database: LibraryDatabase) -> None:
        super().__init__()
        self.database = database
        self.import_service = ImportService(database)
        self.content_service = ContentService(database)
        self.search_service = SearchService(database)
        self.wps_launcher = WpsLauncher()
        self.setWindowTitle("文澜资料库")
        self.setMinimumSize(960, 640)
        self.resize(1180, 760)
        self._build_ui()
        self._apply_theme()
        self._load_documents()

    def _build_ui(self) -> None:
        shell = QWidget()
        layout = QHBoxLayout(shell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QFrame(objectName="archiveSpine")
        sidebar.setFixedWidth(232)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(24, 30, 24, 24)
        brand = QLabel("文澜\n资料库", objectName="brand")
        brand.setAccessibleName("文澜资料库")
        sidebar_layout.addWidget(brand)
        sidebar_layout.addSpacing(42)
        for label in ("全部文档", "未分类", "待复核", "回收站"):
            button = QPushButton(label, objectName="navButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            sidebar_layout.addWidget(button)
        sidebar_layout.addStretch()
        location = QLabel("资料存储于本机", objectName="localOnly")
        location.setWordWrap(True)
        sidebar_layout.addWidget(location)

        content = QWidget(objectName="content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(54, 42, 54, 42)
        header = QHBoxLayout()
        title = QLabel("全部文档", objectName="pageTitle")
        header.addWidget(title)
        header.addStretch()
        self.search_input = QLineEdit(objectName="searchInput")
        self.search_input.setPlaceholderText("搜索文件名和正文…")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.returnPressed.connect(self._search)
        header.addWidget(self.search_input)
        content_layout.addLayout(header)
        content_layout.addSpacing(22)

        actions = QHBoxLayout()
        import_button = QPushButton("导入文档", objectName="primaryButton")
        import_button.clicked.connect(self._choose_files)
        folder_button = QPushButton("导入文件夹", objectName="secondaryButton")
        folder_button.clicked.connect(self._choose_folder)
        open_button = QPushButton("用 WPS 打开", objectName="secondaryButton")
        open_button.clicked.connect(self._open_current_in_wps)
        copy_button = QPushButton("复制正文", objectName="secondaryButton")
        copy_button.clicked.connect(self._copy_preview)
        actions.addWidget(import_button)
        actions.addWidget(folder_button)
        actions.addWidget(open_button)
        actions.addWidget(copy_button)
        actions.addStretch()
        content_layout.addLayout(actions)
        content_layout.addSpacing(18)

        self.empty_state = QLabel(
            "这里还没有资料\n\n导入 Word 文档，开始建立可搜索的本地资料库。",
            objectName="emptyState",
        )
        self.empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_state.setWordWrap(True)

        self.document_list = QListWidget(objectName="documentList")
        self.document_list.currentItemChanged.connect(self._show_document)
        self.preview = QTextBrowser(objectName="preview")
        self.preview.setPlaceholderText("选择文档后在此阅读正文")
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.document_list)
        splitter.addWidget(self.preview)
        splitter.setSizes([330, 570])
        content_layout.addWidget(splitter, stretch=1)
        content_layout.addWidget(self.empty_state)

        layout.addWidget(sidebar)
        layout.addWidget(content, stretch=1)
        self.setCentralWidget(shell)

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget#content { background: #F3F6F8; color: #172433; }
            QFrame#archiveSpine { background: #142B3D; border: none; }
            QLabel#brand { color: #F5FAF8; font-size: 25px; font-weight: 700; line-height: 1.2; }
            QPushButton#navButton {
                background: transparent; color: #C7D4DC; border: none;
                border-left: 3px solid transparent; text-align: left;
                padding: 11px 12px; font-size: 15px;
            }
            QPushButton#navButton:hover { color: white; border-left-color: #39B48E; }
            QLabel#localOnly { color: #8299A7; font-size: 12px; }
            QLabel#pageTitle { color: #172433; font-size: 28px; font-weight: 700; }
            QLabel#emptyState { color: #61717C; font-size: 15px; line-height: 1.5; }
            QLineEdit#searchInput {
                min-width: 310px; background: white; border: 1px solid #D5DEE3;
                border-radius: 7px; padding: 10px 13px; font-size: 14px;
            }
            QLineEdit#searchInput:focus { border-color: #147D64; }
            QListWidget#documentList, QTextBrowser#preview {
                background: white; border: 1px solid #D8E0E5; border-radius: 8px;
                padding: 8px; font-size: 14px;
            }
            QListWidget#documentList::item { padding: 10px; border-radius: 5px; }
            QListWidget#documentList::item:selected { background: #DCEFE9; color: #103B31; }
            QPushButton#primaryButton {
                background: #147D64; color: white; border: none; border-radius: 6px;
                padding: 12px 18px; font-size: 15px; font-weight: 600;
            }
            QPushButton#primaryButton:hover { background: #0F6B55; }
            QPushButton#secondaryButton {
                background: white; color: #294251; border: 1px solid #CBD6DC;
                border-radius: 6px; padding: 11px 16px; font-size: 14px;
            }
            QPushButton#secondaryButton:hover { border-color: #147D64; color: #147D64; }
            QPushButton:focus { outline: 2px solid #67CDAE; }
            """
        )

    def import_paths(self, paths: list[Path]) -> None:
        failures = 0
        for path in paths:
            try:
                record = self.import_service.import_file(path)
                try:
                    self.content_service.parse_document(record.document_id)
                    self.search_service.index_document(record.document_id)
                except ParseError:
                    failures += 1
            except DuplicateConflict as conflict:
                record = self._resolve_duplicate(path, conflict)
                if record is None:
                    failures += 1
                    continue
                try:
                    self.content_service.parse_document(record.document_id)
                    self.search_service.index_document(record.document_id)
                except ParseError:
                    failures += 1
            except (OSError, ValueError):
                failures += 1
        self._load_documents()
        if failures:
            QMessageBox.warning(self, "部分文档未完成", f"有 {failures} 份文档需要处理或检查。")

    def _choose_files(self) -> None:
        selected, _ = QFileDialog.getOpenFileNames(
            self, "导入 Word 文档", "", "Word 文档 (*.doc *.docx)"
        )
        if selected:
            self.import_paths([Path(path) for path in selected])

    def _choose_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "导入文件夹")
        if not selected:
            return
        failures = 0
        for path in sorted(Path(selected).rglob("*")):
            if path.is_file() and path.suffix.lower() in ImportService.SUPPORTED_SUFFIXES:
                try:
                    self.import_paths([path])
                except (OSError, ValueError):
                    failures += 1
        if failures:
            QMessageBox.warning(self, "导入完成", f"有 {failures} 份文档未能导入。")

    def _load_documents(self, document_ids: list[str] | None = None) -> None:
        self.document_list.clear()
        if document_ids is None:
            rows = self.database.connection.execute(
                """
                SELECT id, original_name, parse_status FROM documents
                WHERE status = 'active' ORDER BY imported_at DESC
                """
            ).fetchall()
        elif not document_ids:
            rows = []
        else:
            placeholders = ",".join("?" for _ in document_ids)
            fetched = self.database.connection.execute(
                "SELECT id, original_name, parse_status "
                f"FROM documents WHERE id IN ({placeholders})",
                document_ids,
            ).fetchall()
            by_id = {row[0]: row for row in fetched}
            rows = [by_id[item] for item in document_ids if item in by_id]
        for document_id, original_name, parse_status in rows:
            suffix = "  · 解析失败" if str(parse_status).startswith("error:") else ""
            item = QListWidgetItem(f"{original_name}{suffix}")
            item.setData(Qt.ItemDataRole.UserRole, document_id)
            self.document_list.addItem(item)
        has_documents = self.document_list.count() > 0
        self.document_list.setVisible(has_documents)
        self.preview.setVisible(has_documents)
        self.empty_state.setVisible(not has_documents)

    def _show_document(self, current: QListWidgetItem | None) -> None:
        if current is None:
            self.preview.clear()
            return
        row = self.database.connection.execute(
            "SELECT content_text FROM documents WHERE id = ?",
            (current.data(Qt.ItemDataRole.UserRole),),
        ).fetchone()
        self.preview.setPlainText((row[0] if row else None) or "此文档暂时没有可预览的正文。")

    def _search(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            self._load_documents()
            return
        results = self.search_service.search(query)
        self._load_documents([result.document_id for result in results])

    def _resolve_duplicate(self, path: Path, conflict: DuplicateConflict):
        message = QMessageBox(self)
        message.setWindowTitle("发现重复文档")
        message.setText("资料库中已有同名或内容相同的文档。")
        overwrite = message.addButton("覆盖现有文档", QMessageBox.ButtonRole.DestructiveRole)
        keep = message.addButton("作为新文档保留", QMessageBox.ButtonRole.AcceptRole)
        message.addButton("取消导入", QMessageBox.ButtonRole.RejectRole)
        message.exec()
        if message.clickedButton() is overwrite:
            return self.import_service.import_file(
                path,
                decision=DuplicateDecision.OVERWRITE,
                replace_document_id=conflict.existing_id,
            )
        if message.clickedButton() is keep:
            return self.import_service.import_file(path, decision=DuplicateDecision.KEEP_BOTH)
        return None

    def _current_document_path(self) -> Path | None:
        item = self.document_list.currentItem()
        if item is None:
            return None
        row = self.database.connection.execute(
            "SELECT stored_name FROM documents WHERE id = ?",
            (item.data(Qt.ItemDataRole.UserRole),),
        ).fetchone()
        return self.database.root / "documents" / row[0] if row else None

    def _open_current_in_wps(self) -> None:
        path = self._current_document_path()
        if path is None:
            return
        try:
            self.wps_launcher.open(path)
        except (OSError, FileNotFoundError) as error:
            QMessageBox.warning(self, "无法打开文档", str(error))

    def _copy_preview(self) -> None:
        selected = self.preview.textCursor().selectedText()
        text = selected or self.preview.toPlainText()
        if text:
            from PySide6.QtWidgets import QApplication

            QApplication.clipboard().setText(text)
