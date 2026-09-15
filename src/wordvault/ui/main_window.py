from __future__ import annotations

import json
import sqlite3
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from wordvault.classification.service import ClassificationService
from wordvault.content.change_monitor import ChangeMonitorService
from wordvault.content.parsers import ParseError
from wordvault.content.service import ContentService, quote_selection
from wordvault.content.wps import WpsLauncher
from wordvault.diagnostics.environment import EnvironmentInspector
from wordvault.diagnostics.self_check import SelfCheckService
from wordvault.diagnostics.service import DiagnosticsService
from wordvault.library.exporter import ExportConflictDecision, ExportService
from wordvault.library.importer import DuplicateConflict, DuplicateDecision, ImportService
from wordvault.library.lifecycle import LibraryLifecycleService
from wordvault.library.migration import LibraryMigrationService
from wordvault.search.indexing import IndexingJob, IndexingState
from wordvault.search.service import SearchService
from wordvault.storage.database import LibraryDatabase


class MainWindow(QMainWindow):
    def __init__(self, database: LibraryDatabase) -> None:
        super().__init__()
        self.database = database
        self.import_service = ImportService(database)
        self.content_service = ContentService(database)
        self.change_monitor = ChangeMonitorService(database)
        self.classification_service = ClassificationService(database)
        self.export_service = ExportService(database)
        self.lifecycle_service = LibraryLifecycleService(database)
        self.migration_service = LibraryMigrationService(database)
        self.diagnostics = DiagnosticsService(database.root / "logs")
        self.environment_inspector = EnvironmentInspector()
        self.diagnostics.record("APP_STARTED", app_version="0.1.0")
        self.search_service = SearchService(database)
        self.indexing_job = IndexingJob(database)
        self.index_timer = QTimer(self)
        self.index_timer.timeout.connect(self._index_step)
        self.change_timer = QTimer(self)
        self.change_timer.timeout.connect(self._scan_external_changes)
        self.change_timer.start(3000)
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
        navigation = (
            ("全部文档", self._show_all_documents),
            ("未分类", self._show_uncategorized),
            ("待复核", self._show_needs_review),
            ("回收站", self._show_trash),
        )
        for label, handler in navigation:
            button = QPushButton(label, objectName="navButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(handler)
            sidebar_layout.addWidget(button)
        sidebar_layout.addStretch()
        export_diagnostics = QPushButton("导出诊断包", objectName="navButton")
        export_diagnostics.clicked.connect(self._choose_diagnostics_destination)
        clear_logs = QPushButton("清除日志", objectName="navButton")
        clear_logs.clicked.connect(self._clear_diagnostics)
        empty_trash = QPushButton("清空回收站", objectName="navButton")
        empty_trash.clicked.connect(self._empty_trash)
        migrate_library = QPushButton("迁移资料库", objectName="navButton")
        migrate_library.clicked.connect(self._choose_library_migration)
        sidebar_layout.addWidget(migrate_library)
        sidebar_layout.addWidget(export_diagnostics)
        sidebar_layout.addWidget(clear_logs)
        sidebar_layout.addWidget(empty_trash)
        location = QLabel("资料存储于本机", objectName="localOnly")
        location.setWordWrap(True)
        sidebar_layout.addWidget(location)

        content = QWidget(objectName="content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(54, 42, 54, 42)
        header = QHBoxLayout()
        self.page_title = QLabel("全部文档", objectName="pageTitle")
        header.addWidget(self.page_title)
        header.addStretch()
        self.search_input = QLineEdit(objectName="searchInput")
        self.search_input.setPlaceholderText("搜索文件名和正文…")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.returnPressed.connect(self._search)
        header.addWidget(self.search_input)
        content_layout.addLayout(header)
        filters = QHBoxLayout()
        filters.addWidget(QLabel("筛选", objectName="fieldLabel"))
        self.search_category_combo = QComboBox(objectName="searchFilter")
        self.search_category_combo.setMinimumWidth(145)
        self.format_filter = QComboBox(objectName="searchFilter")
        self.format_filter.addItem("全部格式", None)
        self.format_filter.addItem("DOCX", ".docx")
        self.format_filter.addItem("DOC", ".doc")
        self.time_filter = QComboBox(objectName="searchFilter")
        self.time_filter.addItem("全部时间", None)
        self.time_filter.addItem("最近7天", 7)
        self.time_filter.addItem("最近30天", 30)
        self.time_filter.addItem("最近一年", 365)
        search_button = QPushButton("搜索", objectName="secondaryButton")
        search_button.clicked.connect(self._search)
        filters.addWidget(self.search_category_combo)
        filters.addWidget(self.format_filter)
        filters.addWidget(self.time_filter)
        filters.addWidget(search_button)
        filters.addStretch()
        content_layout.addLayout(filters)
        content_layout.addSpacing(18)

        actions = QHBoxLayout()
        import_button = QPushButton("导入文档", objectName="primaryButton")
        import_button.clicked.connect(self._choose_files)
        folder_button = QPushButton("导入文件夹", objectName="secondaryButton")
        folder_button.clicked.connect(self._choose_folder)
        open_button = QPushButton("用 WPS 打开", objectName="secondaryButton")
        open_button.clicked.connect(self._open_current_in_wps)
        copy_button = QPushButton("复制正文", objectName="secondaryButton")
        copy_button.clicked.connect(self._copy_preview)
        quote_button = QPushButton("复制并附来源", objectName="secondaryButton")
        quote_button.clicked.connect(self._copy_with_source)
        export_button = QPushButton("导出", objectName="secondaryButton")
        export_button.clicked.connect(self._choose_export_directory)
        trash_button = QPushButton("移入回收站", objectName="dangerButton")
        trash_button.clicked.connect(lambda: self._move_current_to_trash())
        restore_button = QPushButton("恢复", objectName="secondaryButton")
        restore_button.clicked.connect(self._restore_current)
        self.category_combo = QComboBox(objectName="categoryCombo")
        self.category_combo.setMinimumWidth(150)
        self.category_combo.activated.connect(self._assign_category)
        category_button = QPushButton("新建分类", objectName="secondaryButton")
        category_button.clicked.connect(self._create_category)
        edit_category_button = QPushButton("编辑分类", objectName="secondaryButton")
        edit_category_button.clicked.connect(self._edit_selected_category)
        delete_category_button = QPushButton("删除分类", objectName="dangerButton")
        delete_category_button.clicked.connect(self._delete_selected_category)
        recommend_button = QPushButton("推荐分类", objectName="primaryButton")
        recommend_button.clicked.connect(self._recommend_category)
        export_category_button = QPushButton("导出本分类", objectName="secondaryButton")
        export_category_button.clicked.connect(self._choose_category_export)
        self.auto_threshold = QComboBox(objectName="searchFilter")
        self.auto_threshold.addItem("高可信度", "high")
        self.auto_threshold.addItem("中可信度", "medium")
        self.auto_threshold.addItem("低可信度", "low")
        auto_classify_button = QPushButton("自动归类", objectName="secondaryButton")
        auto_classify_button.clicked.connect(self._auto_classify)
        actions.addWidget(import_button)
        actions.addWidget(folder_button)
        actions.addWidget(open_button)
        actions.addWidget(copy_button)
        actions.addWidget(quote_button)
        actions.addWidget(export_button)
        actions.addWidget(trash_button)
        actions.addWidget(restore_button)
        actions.addStretch()
        content_layout.addLayout(actions)
        classification_actions = QHBoxLayout()
        classification_actions.addWidget(QLabel("当前分类", objectName="fieldLabel"))
        classification_actions.addWidget(self.category_combo)
        classification_actions.addWidget(category_button)
        classification_actions.addWidget(edit_category_button)
        classification_actions.addWidget(delete_category_button)
        classification_actions.addWidget(recommend_button)
        classification_actions.addWidget(export_category_button)
        classification_actions.addWidget(self.auto_threshold)
        classification_actions.addWidget(auto_classify_button)
        classification_actions.addStretch()
        content_layout.addLayout(classification_actions)
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

        index_footer = QHBoxLayout()
        self.index_status = QLabel("索引就绪", objectName="fieldLabel")
        self.index_progress = QProgressBar()
        self.index_progress.setTextVisible(False)
        self.index_progress.setMaximumWidth(180)
        rebuild_button = QPushButton("重建索引", objectName="secondaryButton")
        rebuild_button.clicked.connect(self._start_reindex)
        self.pause_index_button = QPushButton("暂停", objectName="secondaryButton")
        self.pause_index_button.clicked.connect(self._toggle_index_pause)
        self.pause_index_button.setEnabled(False)
        index_footer.addWidget(self.index_status)
        index_footer.addWidget(self.index_progress)
        index_footer.addWidget(rebuild_button)
        index_footer.addWidget(self.pause_index_button)
        index_footer.addStretch()
        content_layout.addLayout(index_footer)

        layout.addWidget(sidebar)
        layout.addWidget(content, stretch=1)
        self.setCentralWidget(shell)

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                font-family: "Noto Sans CJK SC", "Microsoft YaHei UI", sans-serif;
            }
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
            QLabel#fieldLabel { color: #657580; font-size: 13px; }
            QLabel#emptyState { color: #61717C; font-size: 15px; line-height: 1.5; }
            QLineEdit#searchInput {
                min-width: 310px; background: white; border: 1px solid #D5DEE3;
                border-radius: 7px; padding: 10px 13px; font-size: 14px;
            }
            QLineEdit#searchInput:focus { border-color: #147D64; }
            QComboBox#categoryCombo, QComboBox#searchFilter {
                background: white; color: #294251; border: 1px solid #CBD6DC;
                border-radius: 6px; padding: 9px 12px; font-size: 14px;
            }
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
            QPushButton#dangerButton {
                background: transparent; color: #9B3A3A; border: none; padding: 10px;
            }
            QPushButton#dangerButton:hover { color: #C22F2F; }
            QPushButton:focus { outline: 2px solid #67CDAE; }
            """
        )
        self._refresh_categories()

    def import_paths(self, paths: list[Path]) -> None:
        failures = 0
        for path in paths:
            started = time.monotonic()
            try:
                record = self.import_service.import_file(path)
                failures += self._parse_and_index(record.document_id, path.suffix, started)
            except DuplicateConflict as conflict:
                record = self._resolve_duplicate(path, conflict)
                if record is None:
                    self.diagnostics.record("IMPORT_CANCELLED", format=path.suffix.lower())
                    failures += 1
                    continue
                failures += self._parse_and_index(record.document_id, path.suffix, started)
            except (OSError, ValueError):
                self.diagnostics.record("IMPORT_FAILED", error_code="IMPORT_IO_OR_INPUT")
                failures += 1
        self._load_documents()
        if failures:
            QMessageBox.warning(self, "部分文档未完成", f"有 {failures} 份文档需要处理或检查。")

    def _parse_and_index(self, document_id: str, suffix: str, started: float) -> int:
        try:
            self.content_service.parse_document(document_id)
            self.search_service.index_document(document_id)
            duration = round((time.monotonic() - started) * 1000)
            self.diagnostics.record(
                "IMPORT_COMPLETED",
                format=suffix.lower(),
                duration_ms=duration,
                status="ready",
            )
            return 0
        except ParseError as error:
            self.diagnostics.record(
                "DOC_PARSE_FAILED", format=suffix.lower(), error_code=error.code
            )
            return 1

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

    def _load_by_where(self, title: str, where_clause: str, parameters: tuple = ()) -> None:
        self.page_title.setText(title)
        rows = self.database.connection.execute(
            f"""
            SELECT id, original_name, parse_status FROM documents
            WHERE {where_clause} ORDER BY imported_at DESC
            """,
            parameters,
        ).fetchall()
        self._populate_documents(rows)

    def _populate_documents(self, rows) -> None:
        self.document_list.clear()
        for document_id, original_name, parse_status in rows:
            suffix = "  · 解析失败" if str(parse_status).startswith("error:") else ""
            item = QListWidgetItem(f"{original_name}{suffix}")
            item.setData(Qt.ItemDataRole.UserRole, document_id)
            self.document_list.addItem(item)
        has_documents = self.document_list.count() > 0
        self.document_list.setVisible(has_documents)
        self.preview.setVisible(has_documents)
        self.empty_state.setVisible(not has_documents)

    def _show_all_documents(self) -> None:
        self.page_title.setText("全部文档")
        self._load_documents()

    def _show_uncategorized(self) -> None:
        self._load_by_where("未分类", "status = 'active' AND category_id IS NULL")

    def _show_needs_review(self) -> None:
        self._load_by_where("待复核", "status = 'active' AND needs_review = 1")

    def _show_trash(self) -> None:
        self._load_by_where("回收站", "status = 'trash'")

    def _show_document(self, current: QListWidgetItem | None) -> None:
        if current is None:
            self.preview.clear()
            return
        row = self.database.connection.execute(
            "SELECT content_text, category_id FROM documents WHERE id = ?",
            (current.data(Qt.ItemDataRole.UserRole),),
        ).fetchone()
        self.preview.setPlainText((row[0] if row else None) or "此文档暂时没有可预览的正文。")
        self.category_combo.blockSignals(True)
        self.category_combo.setCurrentIndex(self.category_combo.findData(row[1] if row else None))
        self.category_combo.blockSignals(False)

    def _search(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            self._load_documents()
            return
        days = self.time_filter.currentData()
        imported_after = datetime.now(UTC) - timedelta(days=days) if days else None
        results = self.search_service.search(
            query,
            category_id=self.search_category_combo.currentData(),
            extension=self.format_filter.currentData(),
            imported_after=imported_after,
        )
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
            QApplication.clipboard().setText(text)

    def _copy_with_source(self) -> None:
        item = self.document_list.currentItem()
        if item is None:
            return
        cursor = self.preview.textCursor()
        selected = cursor.selectedText() or self.preview.toPlainText()
        if not selected:
            return
        row = self.database.connection.execute(
            "SELECT original_name FROM documents WHERE id = ?",
            (item.data(Qt.ItemDataRole.UserRole),),
        ).fetchone()
        if row:
            QApplication.clipboard().setText(
                quote_selection(
                    selected,
                    row[0],
                    paragraph_number=cursor.blockNumber() + 1,
                    include_source=True,
                )
            )

    def _current_document_id(self) -> str | None:
        item = self.document_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _move_current_to_trash(self, *, confirm: bool = True) -> None:
        document_id = self._current_document_id()
        if document_id is None:
            return
        if confirm:
            answer = QMessageBox.question(
                self, "移入回收站", "确定将所选文档移入回收站吗？"
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.lifecycle_service.move_to_trash(document_id)
        self._show_all_documents()

    def _restore_current(self) -> None:
        document_id = self._current_document_id()
        if document_id is None:
            return
        row = self.database.connection.execute(
            "SELECT status FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
        if row and row[0] == "trash":
            self.lifecycle_service.restore(document_id)
            self._show_trash()

    def _refresh_categories(self) -> None:
        current = self.category_combo.currentData() if self.category_combo.count() else None
        search_current = (
            self.search_category_combo.currentData() if self.search_category_combo.count() else None
        )
        self.category_combo.blockSignals(True)
        self.search_category_combo.blockSignals(True)
        self.category_combo.clear()
        self.search_category_combo.clear()
        self.category_combo.addItem("未分类", None)
        self.search_category_combo.addItem("全部分类", None)
        rows = self.database.connection.execute(
            "SELECT id, name, parent_id FROM categories ORDER BY name"
        ).fetchall()
        by_parent: dict[str | None, list[tuple[str, str]]] = {}
        for category_id, name, parent_id in rows:
            by_parent.setdefault(parent_id, []).append((category_id, name))

        def add_children(parent_id: str | None, depth: int) -> None:
            for category_id, name in by_parent.get(parent_id, []):
                self.category_combo.addItem(f"{'　' * depth}{name}", category_id)
                self.search_category_combo.addItem(f"{'　' * depth}{name}", category_id)
                add_children(category_id, depth + 1)

        add_children(None, 0)
        found = self.category_combo.findData(current)
        search_found = self.search_category_combo.findData(search_current)
        self.category_combo.setCurrentIndex(max(0, found))
        self.search_category_combo.setCurrentIndex(max(0, search_found))
        self.category_combo.blockSignals(False)
        self.search_category_combo.blockSignals(False)

    def _assign_category(self, index: int) -> None:
        document_id = self._current_document_id()
        if document_id is not None and index >= 0:
            self.classification_service.assign(document_id, self.category_combo.itemData(index))

    def _create_category(self) -> None:
        name, accepted = QInputDialog.getText(self, "新建分类", "分类名称")
        if not accepted or not name.strip():
            return
        keywords_text, keywords_accepted = QInputDialog.getText(
            self, "分类关键词", "关键词（使用逗号分隔，可留空）"
        )
        if not keywords_accepted:
            return
        parent_id = self.category_combo.currentData()
        keywords = tuple(
            item.strip() for item in keywords_text.replace("，", ",").split(",") if item.strip()
        )
        try:
            self.classification_service.create_category(
                name, parent_id=parent_id, keywords=keywords
            )
            self._refresh_categories()
        except ValueError as error:
            QMessageBox.warning(self, "无法创建分类", str(error))

    def _delete_selected_category(self) -> None:
        category_id = self.category_combo.currentData()
        if category_id is None:
            return
        answer = QMessageBox.question(
            self,
            "删除分类",
            "删除分类后，其中的文档将转入“未分类”。确定继续吗？",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.classification_service.delete_category(
                category_id, move_to_uncategorized=True
            )
            self._refresh_categories()
            self._show_all_documents()
        except ValueError as error:
            QMessageBox.warning(self, "无法删除分类", str(error))

    def _edit_selected_category(self) -> None:
        category_id = self.category_combo.currentData()
        if category_id is None:
            return
        row = self.database.connection.execute(
            "SELECT name, description, keywords_json FROM categories WHERE id = ?",
            (category_id,),
        ).fetchone()
        if row is None:
            return
        name, accepted = QInputDialog.getText(
            self, "编辑分类", "分类名称", text=row[0]
        )
        if not accepted:
            return
        current_keywords = "，".join(json.loads(row[2]))
        keywords_text, keywords_accepted = QInputDialog.getText(
            self, "编辑分类关键词", "关键词（使用逗号分隔）", text=current_keywords
        )
        if not keywords_accepted:
            return
        keywords = tuple(
            item.strip() for item in keywords_text.replace("，", ",").split(",") if item.strip()
        )
        try:
            self.classification_service.update_category(
                category_id, name=name, description=row[1], keywords=keywords
            )
            self._refresh_categories()
        except ValueError as error:
            QMessageBox.warning(self, "无法修改分类", str(error))

    def _recommend_category(self) -> None:
        document_id = self._current_document_id()
        if document_id is None:
            return
        recommendation = self.classification_service.recommend(document_id)
        if recommendation is None:
            QMessageBox.information(
                self,
                "暂无分类建议",
                "请先为分类设置关键词，或积累更多人工分类样本。",
            )
            return
        index = self.category_combo.findData(recommendation.category_id)
        category_name = self.category_combo.itemText(index).strip()
        confidence_names = {"high": "高", "medium": "中", "low": "低"}
        reasons = "、".join(recommendation.reasons) or "已分类样本"
        answer = QMessageBox.question(
            self,
            "分类建议",
            f"建议分类：{category_name}\n可信度：{confidence_names[recommendation.confidence]}"
            f"\n依据：{reasons}\n\n是否采用？",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.classification_service.accept_recommendation(
                document_id, recommendation, automatic=False
            )
            self.category_combo.setCurrentIndex(index)

    def _auto_classify(self) -> None:
        answer = QMessageBox.question(
            self,
            "自动归类未分类文档",
            "符合可信度要求的文档将自动归类，并进入“待复核”。是否继续？",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        result = self.classification_service.auto_assign_unclassified(
            threshold=self.auto_threshold.currentData()
        )
        self.diagnostics.record(
            "AUTO_CLASSIFY_COMPLETED", count=result.assigned, status="completed"
        )
        QMessageBox.information(
            self,
            "自动归类完成",
            f"已归类 {result.assigned} 份，跳过 {result.skipped} 份。请在“待复核”中检查。",
        )
        self._show_needs_review()

    def _choose_export_directory(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "选择导出位置")
        if selected:
            exported = self._export_current_to(Path(selected))
            if exported is not None:
                QMessageBox.information(self, "导出完成", "文档已复制到所选目录。")

    def _export_current_to(self, destination: Path) -> Path | None:
        document_id = self._current_document_id()
        if document_id is None:
            return None
        row = self.database.connection.execute(
            "SELECT original_name FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
        if row is None:
            return None
        target = destination.resolve() / Path(row[0]).name
        decision = ExportConflictDecision.SKIP
        if target.exists():
            message = QMessageBox(self)
            message.setWindowTitle("导出位置已有同名文件")
            overwrite = message.addButton("覆盖", QMessageBox.ButtonRole.DestructiveRole)
            rename = message.addButton("自动重命名", QMessageBox.ButtonRole.AcceptRole)
            message.addButton("跳过", QMessageBox.ButtonRole.RejectRole)
            message.exec()
            if message.clickedButton() is overwrite:
                decision = ExportConflictDecision.OVERWRITE
            elif message.clickedButton() is rename:
                decision = ExportConflictDecision.AUTO_RENAME
            else:
                return None
        return self.export_service.export_document(document_id, destination, decision=decision)

    def _start_reindex(self) -> None:
        progress = self.indexing_job.start()
        self.index_progress.setRange(0, max(1, progress.total))
        self.index_progress.setValue(0)
        if progress.state is IndexingState.COMPLETED:
            self.index_status.setText("没有需要索引的文档")
            return
        self.pause_index_button.setEnabled(True)
        self.pause_index_button.setText("暂停")
        self.index_timer.start(0)

    def _index_step(self) -> None:
        progress = self.indexing_job.step()
        self.index_progress.setValue(progress.processed)
        self.index_status.setText(
            f"正在索引 {progress.processed}/{progress.total} · "
            f"成功 {progress.successful} · 失败 {progress.failed}"
        )
        if progress.state is IndexingState.COMPLETED:
            self.index_timer.stop()
            self.pause_index_button.setEnabled(False)
            self.index_status.setText(
                f"索引完成 · 成功 {progress.successful} · 失败 {progress.failed}"
            )
            self._load_documents()

    def _toggle_index_pause(self) -> None:
        if self.indexing_job.state is IndexingState.RUNNING:
            self.indexing_job.pause()
            self.index_timer.stop()
            self.pause_index_button.setText("继续")
            self.index_status.setText("索引已暂停")
        elif self.indexing_job.state is IndexingState.PAUSED:
            self.indexing_job.resume()
            self.index_timer.start(0)
            self.pause_index_button.setText("暂停")

    def _choose_diagnostics_destination(self) -> None:
        selected, _ = QFileDialog.getSaveFileName(
            self, "导出脱敏诊断包", "文澜诊断包.zip", "ZIP 压缩包 (*.zip)"
        )
        if selected:
            destination = Path(selected)
            if destination.suffix.lower() != ".zip":
                destination = destination.with_suffix(".zip")
            self._export_diagnostics_to(destination)
            QMessageBox.information(
                self,
                "诊断包已导出",
                "诊断包不包含正文、文件名、路径、搜索词或分类名称。",
            )

    def _export_diagnostics_to(self, destination: Path) -> Path:
        result = SelfCheckService(
            inspector=self.environment_inspector,
            event_log_directory=self.database.root / "logs",
        ).run(self.database.root, destination)
        return result.destination

    def _clear_diagnostics(self) -> None:
        answer = QMessageBox.question(self, "清除日志", "确定清除全部本地诊断日志吗？")
        if answer == QMessageBox.StandardButton.Yes:
            self.diagnostics.clear()

    def _empty_trash(self) -> None:
        count = self.database.connection.execute(
            "SELECT count(*) FROM documents WHERE status = 'trash'"
        ).fetchone()[0]
        if not count:
            QMessageBox.information(self, "回收站", "回收站为空。")
            return
        answer = QMessageBox.warning(
            self,
            "永久删除",
            f"将永久删除回收站中的 {count} 份文档，且无法恢复。确定继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.lifecycle_service.empty_trash()
            self._show_trash()

    def _choose_category_export(self) -> None:
        category_id = self.category_combo.currentData()
        if category_id is None:
            QMessageBox.information(self, "导出分类", "请先选择一个具体分类。")
            return
        selected = QFileDialog.getExistingDirectory(self, "选择分类导出位置")
        if not selected:
            return
        exported = self.export_service.export_category(
            category_id,
            Path(selected),
            decision=ExportConflictDecision.AUTO_RENAME,
        )
        QMessageBox.information(
            self,
            "分类导出完成",
            f"已导出 {len(exported)} 份文档；同名文件已自动重命名。",
        )

    def _scan_external_changes(self) -> None:
        if self.indexing_job.state in (IndexingState.RUNNING, IndexingState.PAUSED):
            return
        try:
            result = self.change_monitor.scan()
        except sqlite3.ProgrammingError as error:
            if "closed" not in str(error).lower():
                raise
            self.change_timer.stop()
            return
        if result.changed:
            self.index_status.setText(f"已更新 {result.changed} 份在 WPS 中修改的文档")
            self._load_documents()
        elif result.failed:
            self.index_status.setText(f"有 {result.failed} 份文档需要检查")

    def _choose_library_migration(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "选择新的资料库上级目录")
        if not selected:
            return
        destination = Path(selected).resolve() / "文澜资料库"
        try:
            migrated = self.migration_service.migrate(destination)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "资料库迁移失败", str(error))
            return
        QSettings().setValue("library_root", str(migrated))
        QMessageBox.information(
            self,
            "资料库迁移完成",
            "全部内容校验成功。程序将关闭，下次启动使用新资料库；旧资料库仍然保留。",
        )
        QApplication.quit()
