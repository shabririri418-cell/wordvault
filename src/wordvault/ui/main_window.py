from __future__ import annotations

import json
import sqlite3
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction
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
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
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
        sidebar.setFixedWidth(248)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(18, 24, 18, 18)
        sidebar_layout.setSpacing(6)
        brand = QLabel("文澜资料库", objectName="brand")
        brand.setAccessibleName("文澜资料库")
        sidebar_layout.addWidget(brand)
        local_badge = QLabel("● 资料只保存在本机", objectName="localOnly")
        sidebar_layout.addWidget(local_badge)
        sidebar_layout.addSpacing(22)
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

        category_header = QHBoxLayout()
        category_header.addWidget(QLabel("我的分类", objectName="sectionLabel"))
        category_header.addStretch()
        self.add_category_button = QPushButton("＋", objectName="addCategoryButton")
        self.add_category_button.setToolTip("新建一级分类")
        self.add_category_button.setAccessibleName("新建一级分类")
        self.add_category_button.clicked.connect(self._create_top_level_category)
        category_header.addWidget(self.add_category_button)
        sidebar_layout.addSpacing(16)
        sidebar_layout.addLayout(category_header)
        self.category_tree = QTreeWidget(objectName="categoryTree")
        self.category_tree.setHeaderHidden(True)
        self.category_tree.setIndentation(18)
        self.category_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.category_tree.customContextMenuRequested.connect(self._show_category_menu)
        self.category_tree.currentItemChanged.connect(self._show_category_from_tree)
        sidebar_layout.addWidget(self.category_tree, stretch=1)

        settings_button = QPushButton("设置与帮助", objectName="settingsButton")
        settings_menu = QMenu(settings_button)
        settings_menu.addAction("迁移资料库", self._choose_library_migration)
        settings_menu.addAction("导出诊断包", self._choose_diagnostics_destination)
        settings_menu.addAction("重建搜索索引", self._start_reindex)
        settings_menu.addSeparator()
        settings_menu.addAction("清除诊断日志", self._clear_diagnostics)
        settings_menu.addAction("清空回收站", self._empty_trash)
        settings_button.setMenu(settings_menu)
        sidebar_layout.addWidget(settings_button)

        content = QWidget(objectName="content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(30, 24, 30, 20)
        content_layout.setSpacing(14)
        header = QHBoxLayout()
        self.page_title = QLabel("全部文档", objectName="pageTitle")
        header.addWidget(self.page_title)
        header.addStretch()
        self.search_input = QLineEdit(objectName="searchInput")
        self.search_input.setPlaceholderText("搜索文件名和正文…")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.returnPressed.connect(self._search)
        header.addWidget(self.search_input)
        self.filter_button = QPushButton("筛选", objectName="quietButton")
        self.filter_button.setCheckable(True)
        self.filter_button.clicked.connect(self._toggle_filters)
        header.addWidget(self.filter_button)
        content_layout.addLayout(header)

        self.filter_panel = QFrame(objectName="filterPanel")
        filters = QHBoxLayout(self.filter_panel)
        filters.setContentsMargins(12, 10, 12, 10)
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
        self.filter_panel.hide()
        content_layout.addWidget(self.filter_panel)

        actions = QHBoxLayout()
        import_button = QPushButton("导入文档", objectName="primaryButton")
        import_button.clicked.connect(self._choose_files)
        folder_button = QPushButton("导入文件夹", objectName="secondaryButton")
        folder_button.clicked.connect(self._choose_folder)
        more_button = QPushButton("更多", objectName="quietButton")
        more_menu = QMenu(more_button)
        more_menu.addAction("自动归类未分类文档", self._auto_classify)
        more_menu.addAction("导出当前分类", self._choose_category_export)
        more_button.setMenu(more_menu)
        self.category_combo = QComboBox(objectName="categoryCombo")
        self.category_combo.activated.connect(self._assign_category)
        self.category_combo.hide()
        self.auto_threshold = QComboBox(objectName="searchFilter")
        self.auto_threshold.addItem("高可信度", "high")
        self.auto_threshold.addItem("中可信度", "medium")
        self.auto_threshold.addItem("低可信度", "low")
        self.auto_threshold.hide()
        actions.addWidget(import_button)
        actions.addWidget(folder_button)
        actions.addStretch()
        actions.addWidget(more_button)
        content_layout.addLayout(actions)

        self.empty_state = QLabel(
            "这里还没有资料\n\n导入 Word 文档或文件夹，开始建立本地资料库。",
            objectName="emptyState",
        )
        self.empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_state.setWordWrap(True)

        self.document_list = QListWidget(objectName="documentList")
        self.document_list.currentItemChanged.connect(self._show_document)
        list_panel = QFrame(objectName="documentPanel")
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(8)
        list_layout.addWidget(QLabel("文档", objectName="paneTitle"))
        list_layout.addWidget(self.document_list)

        self.preview = QTextBrowser(objectName="preview")
        self.preview.setPlaceholderText("选择文档后在此阅读正文")
        preview_panel = QFrame(objectName="previewPanel")
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(8)
        preview_actions = QHBoxLayout()
        preview_actions.addWidget(QLabel("正文预览", objectName="paneTitle"))
        preview_actions.addStretch()
        move_button = QPushButton("移动到分类", objectName="quietButton")
        self.move_category_menu = QMenu(move_button)
        move_button.setMenu(self.move_category_menu)
        open_button = QPushButton("用 WPS 打开", objectName="secondaryButton")
        open_button.clicked.connect(self._open_current_in_wps)
        copy_button = QPushButton("复制正文", objectName="secondaryButton")
        copy_button.clicked.connect(self._copy_preview)
        preview_more = QPushButton("更多", objectName="quietButton")
        preview_menu = QMenu(preview_more)
        preview_menu.addAction("复制并附来源", self._copy_with_source)
        preview_menu.addAction("推荐分类", self._recommend_category)
        preview_menu.addAction("导出文档", self._choose_export_directory)
        preview_menu.addSeparator()
        preview_menu.addAction("移入回收站", self._move_current_to_trash)
        preview_menu.addAction("从回收站恢复", self._restore_current)
        preview_more.setMenu(preview_menu)
        preview_actions.addWidget(move_button)
        preview_actions.addWidget(open_button)
        preview_actions.addWidget(copy_button)
        preview_actions.addWidget(preview_more)
        preview_layout.addLayout(preview_actions)
        preview_layout.addWidget(self.preview)

        self.workspace_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.workspace_splitter.addWidget(list_panel)
        self.workspace_splitter.addWidget(preview_panel)
        self.workspace_splitter.setSizes([360, 620])
        content_layout.addWidget(self.workspace_splitter, stretch=1)
        content_layout.addWidget(self.empty_state)

        index_footer = QHBoxLayout()
        self.index_status = QLabel("索引就绪", objectName="fieldLabel")
        self.index_progress = QProgressBar()
        self.index_progress.setTextVisible(False)
        self.index_progress.setMaximumWidth(180)
        self.index_progress.hide()
        self.pause_index_button = QPushButton("暂停", objectName="secondaryButton")
        self.pause_index_button.clicked.connect(self._toggle_index_pause)
        self.pause_index_button.setEnabled(False)
        self.pause_index_button.hide()
        index_footer.addWidget(self.index_status)
        index_footer.addWidget(self.index_progress)
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
                color: #24343F;
            }
            QMainWindow, QWidget#content { background: #F4F7F8; }
            QFrame#archiveSpine {
                background: #E8EFF0; border: none; border-right: 1px solid #CFDADC;
            }
            QLabel#brand { color: #173E3A; font-size: 23px; font-weight: 700; }
            QLabel#sectionLabel {
                color: #607175; font-size: 12px; font-weight: 700;
            }
            QPushButton#navButton {
                background: transparent; color: #34494D; border: none;
                border-radius: 6px; text-align: left; padding: 10px 12px; font-size: 14px;
            }
            QPushButton#navButton:hover { background: #D7E4E3; color: #173E3A; }
            QLabel#localOnly { color: #4F746D; font-size: 12px; }
            QLabel#pageTitle { color: #1F3039; font-size: 25px; font-weight: 700; }
            QLabel#paneTitle { color: #53656D; font-size: 13px; font-weight: 700; }
            QLabel#fieldLabel { color: #6A7980; font-size: 12px; }
            QLabel#emptyState { color: #61717C; font-size: 15px; }
            QTreeWidget#categoryTree {
                background: transparent; border: none; color: #34494D; font-size: 14px;
                outline: none;
            }
            QTreeWidget#categoryTree::item { min-height: 34px; border-radius: 5px; }
            QTreeWidget#categoryTree::item:hover { background: #DCE7E7; }
            QTreeWidget#categoryTree::item:selected {
                background: #C9DEDA; color: #123F37;
            }
            QPushButton#addCategoryButton {
                min-width: 30px; max-width: 30px; min-height: 30px; border: none;
                border-radius: 6px; background: transparent; color: #315E57; font-size: 20px;
            }
            QPushButton#addCategoryButton:hover { background: #D4E2E0; }
            QPushButton#settingsButton {
                background: transparent; color: #52666A; border: 1px solid #C8D5D6;
                border-radius: 6px; text-align: left; padding: 9px 12px;
            }
            QLineEdit#searchInput {
                min-width: 340px; background: white; border: 1px solid #CBD6DA;
                border-radius: 8px; padding: 10px 14px; font-size: 14px;
            }
            QLineEdit#searchInput:focus { border: 2px solid #247A69; }
            QFrame#filterPanel {
                background: #EAF0F2; border: 1px solid #D4DEE1; border-radius: 8px;
            }
            QComboBox#categoryCombo, QComboBox#searchFilter {
                background: white; color: #314650; border: 1px solid #C7D3D7;
                border-radius: 6px; padding: 8px 11px; font-size: 13px;
            }
            QListWidget#documentList, QTextBrowser#preview {
                background: white; border: 1px solid #D4DEE2; border-radius: 8px;
                padding: 8px; font-size: 14px; selection-background-color: #D6E9E4;
            }
            QListWidget#documentList::item {
                padding: 12px 10px; border-radius: 5px; border-bottom: 1px solid #EEF2F3;
            }
            QListWidget#documentList::item:selected { background: #D6E9E4; color: #123F37; }
            QPushButton#primaryButton {
                background: #176B5B; color: white; border: none; border-radius: 7px;
                padding: 10px 18px; font-size: 14px; font-weight: 600;
            }
            QPushButton#primaryButton:hover { background: #12594C; }
            QPushButton#secondaryButton {
                background: white; color: #304852; border: 1px solid #C8D4D8;
                border-radius: 7px; padding: 9px 13px; font-size: 13px;
            }
            QPushButton#secondaryButton:hover { border-color: #247A69; color: #176B5B; }
            QPushButton#quietButton {
                background: transparent; color: #52666F; border: none; border-radius: 6px;
                padding: 9px 12px; font-size: 13px;
            }
            QPushButton#quietButton:hover { background: #E4EBED; color: #1C554B; }
            QPushButton:focus { border: 2px solid #4B9A88; }
            QMenu {
                background: white; color: #2C414A; border: 1px solid #CCD7DB;
                padding: 6px; font-size: 13px;
            }
            QMenu::item { padding: 8px 26px 8px 12px; border-radius: 4px; }
            QMenu::item:selected { background: #DCEBE7; color: #174F44; }
            QSplitter::handle { background: transparent; width: 10px; }
            """
        )
        self._refresh_categories()

    def _toggle_filters(self, checked: bool) -> None:
        self.filter_panel.setVisible(checked)
        self.filter_button.setText("收起筛选" if checked else "筛选")

    def _show_category_from_tree(
        self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None
    ) -> None:
        if current is None:
            return
        category_id = current.data(0, Qt.ItemDataRole.UserRole)
        index = self.category_combo.findData(category_id)
        if index >= 0:
            self.category_combo.setCurrentIndex(index)
        self._load_by_where(
            current.text(0),
            "status = 'active' AND category_id = ?",
            (category_id,),
        )

    def _show_category_menu(self, position) -> None:
        item = self.category_tree.itemAt(position)
        if item is not None:
            self.category_tree.setCurrentItem(item)
        menu = QMenu(self)
        menu.addAction("新建子分类", self._create_child_category)
        if item is not None:
            menu.addAction("重命名与关键词", self._edit_selected_category)
            menu.addAction("导出该分类", self._choose_category_export)
            menu.addSeparator()
            menu.addAction("删除分类", self._delete_selected_category)
        menu.exec(self.category_tree.viewport().mapToGlobal(position))

    def _assign_category_id(self, category_id: str | None) -> None:
        document_id = self._current_document_id()
        if document_id is None:
            return
        self.classification_service.assign(document_id, category_id)
        self._show_document(self.document_list.currentItem())

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
        self.workspace_splitter.setVisible(has_documents)
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
        self.workspace_splitter.setVisible(has_documents)
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
        self.category_tree.clear()
        self.move_category_menu.clear()
        self.category_combo.addItem("未分类", None)
        self.search_category_combo.addItem("全部分类", None)
        self.move_category_menu.addAction(
            "未分类", lambda: self._assign_category_id(None)
        )
        self.move_category_menu.addSeparator()
        rows = self.database.connection.execute(
            "SELECT id, name, parent_id FROM categories ORDER BY name"
        ).fetchall()
        by_parent: dict[str | None, list[tuple[str, str]]] = {}
        for category_id, name, parent_id in rows:
            by_parent.setdefault(parent_id, []).append((category_id, name))

        def add_children(
            parent_id: str | None,
            depth: int,
            tree_parent: QTreeWidgetItem | None = None,
        ) -> None:
            for category_id, name in by_parent.get(parent_id, []):
                self.category_combo.addItem(f"{'　' * depth}{name}", category_id)
                self.search_category_combo.addItem(f"{'　' * depth}{name}", category_id)
                tree_item = QTreeWidgetItem([name])
                tree_item.setData(0, Qt.ItemDataRole.UserRole, category_id)
                tree_item.setToolTip(0, "单击查看分类；右键管理分类")
                if tree_parent is None:
                    self.category_tree.addTopLevelItem(tree_item)
                else:
                    tree_parent.addChild(tree_item)
                action = QAction(f"{'　' * depth}{name}", self.move_category_menu)
                action.triggered.connect(
                    lambda _checked=False, item_id=category_id: self._assign_category_id(item_id)
                )
                self.move_category_menu.addAction(action)
                add_children(category_id, depth + 1, tree_item)

        add_children(None, 0)
        self.category_tree.expandAll()
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

    def _create_top_level_category(self) -> None:
        self._create_category(parent_id=None)

    def _create_child_category(self) -> None:
        current = self.category_tree.currentItem()
        if current is None:
            return
        self._create_category(parent_id=current.data(0, Qt.ItemDataRole.UserRole))

    def _create_category(self, *, parent_id: str | None) -> None:
        title = "新建一级分类" if parent_id is None else "新建子分类"
        name, accepted = QInputDialog.getText(self, title, "分类名称")
        if not accepted or not name.strip():
            return
        keywords_text, keywords_accepted = QInputDialog.getText(
            self, "分类关键词", "关键词（使用逗号分隔，可留空）"
        )
        if not keywords_accepted:
            return
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
        self.index_progress.show()
        self.pause_index_button.show()
        self.index_progress.setRange(0, max(1, progress.total))
        self.index_progress.setValue(0)
        if progress.state is IndexingState.COMPLETED:
            self.index_status.setText("没有需要索引的文档")
            self.index_progress.hide()
            self.pause_index_button.hide()
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
            self.index_progress.hide()
            self.pause_index_button.hide()
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
                "诊断包已包含运行环境、自检结果、脱敏事件和匿名文档结构。\n\n"
                "不包含正文、文件名、路径、搜索词、分类名称或文档哈希。",
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
