"""
Ventana principal de la aplicación.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QFont, QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.config import AppSettings, get_journal_path
from src.core import recipes
from src.core.jobs import discover_inputs
from src.core.session import SessionJournal
from src.core.consolidator import build_output, render_separator
from src.core.models import ConsolidationFile
from src.ui.worker import ExtractionWorker
from src.extractors.registry import create_default_registry
from src.ui.dedupe_dialog import DuplicateReviewDialog
from src.ui.strings import get_language, set_language, tr
from src.ui.theme import apply_theme


class MainWindow(QMainWindow):
    """
    Ventana principal del Consolidador de Textos.
    """

    def __init__(self, settings: AppSettings) -> None:
        super().__init__()

        self.settings = settings
        set_language(settings.language)
        self.registry = create_default_registry()
        self.files: List[ConsolidationFile] = []
        self.errors: List[ConsolidationFile] = []
        self.worker: Optional[ExtractionWorker] = None
        self.journal = SessionJournal(get_journal_path())
        self._preview_chars = 0

        self._setup_ui()
        self._update_recent_combo()
        self._update_custom_edit_enabled()
        self.refresh_preview()
        self._restore_session()

        self.setWindowTitle(tr("app.title"))
        self.resize(1280, 760)

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        # --------------------------------------------------------------
        # Panel izquierdo: lista de archivos
        # --------------------------------------------------------------
        left = QFrame()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 4, 8)

        self.files_label = QLabel(tr("files.title"))
        self.files_label.setStyleSheet("font-weight: bold;")

        self.file_list = QListWidget()
        self.file_list.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove
        )
        self.file_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.file_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.file_list.setAlternatingRowColors(True)
        self.file_list.setToolTip(tr("files.tooltip"))

        btn_row1 = QHBoxLayout()
        self.btn_add_files = QPushButton(tr("act.add_files"))
        self.btn_add_folder = QPushButton(tr("act.add_folder"))
        btn_row1.addWidget(self.btn_add_files)
        btn_row1.addWidget(self.btn_add_folder)

        btn_row2 = QHBoxLayout()
        self.btn_remove = QPushButton(tr("btn.remove"))
        self.btn_clear = QPushButton(tr("btn.clear"))
        self.btn_up = QPushButton("↑")
        self.btn_down = QPushButton("↓")

        self.btn_remove.setToolTip(tr("tip.remove"))
        self.btn_clear.setToolTip(tr("tip.clear"))
        self.btn_up.setToolTip(tr("tip.up"))
        self.btn_up.setAccessibleName(tr("name.up"))
        self.btn_up.setAccessibleDescription(tr("tip.up"))
        self.btn_down.setToolTip(tr("tip.down"))
        self.btn_down.setAccessibleName(tr("name.down"))
        self.btn_down.setAccessibleDescription(tr("tip.down"))

        btn_row2.addWidget(self.btn_remove)
        btn_row2.addWidget(self.btn_clear)
        btn_row2.addStretch(1)
        btn_row2.addWidget(self.btn_up)
        btn_row2.addWidget(self.btn_down)

        self.recursive_check = QCheckBox(tr("check.recursive"))
        self.recent_combo = QComboBox()
        self.recent_combo.setToolTip(tr("tip.recent"))

        left_layout.addWidget(self.files_label)
        left_layout.addWidget(self.file_list, 1)
        left_layout.addLayout(btn_row1)
        left_layout.addLayout(btn_row2)
        left_layout.addWidget(self.recursive_check)
        left_layout.addWidget(self.recent_combo)

        # --------------------------------------------------------------
        # Panel derecho: configuración + preview
        # --------------------------------------------------------------
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 8, 8, 8)

        self.settings_box = QGroupBox(tr("settings.title"))
        settings_layout = QVBoxLayout(self.settings_box)

        self.separator_label = QLabel(tr("sep.title"))
        self.separator_label.setStyleSheet("font-weight: bold;")

        self.radio_blank = QRadioButton(tr("sep.blank"))
        self.radio_dashes = QRadioButton(tr("sep.dashes"))
        self.radio_filename = QRadioButton(tr("sep.filename"))
        self.radio_custom = QRadioButton(tr("sep.custom"))

        mode = self.settings.separator_mode
        self.radio_blank.setChecked(mode == "blank")
        self.radio_dashes.setChecked(mode == "dashes")
        self.radio_filename.setChecked(mode == "filename")
        self.radio_custom.setChecked(mode == "custom")

        self.custom_edit = QLineEdit(self.settings.custom_separator)
        self.custom_edit.setPlaceholderText(tr("custom.placeholder"))
        self.custom_edit.setToolTip(tr("custom.tooltip"))

        output_row = QHBoxLayout()
        self.output_label = QLabel(tr("output.label"))
        self.output_combo = QComboBox()
        self.output_combo.addItems([".txt", ".docx"])
        self.output_combo.setCurrentText(self.settings.output_format)
        output_row.addWidget(self.output_label)
        output_row.addWidget(self.output_combo)
        output_row.addStretch(1)

        settings_layout.addWidget(self.separator_label)
        settings_layout.addWidget(self.radio_blank)
        settings_layout.addWidget(self.radio_dashes)
        settings_layout.addWidget(self.radio_filename)
        settings_layout.addWidget(self.radio_custom)
        settings_layout.addWidget(self.custom_edit)
        settings_layout.addLayout(output_row)

        self.preview_label = QLabel()
        self.preview_label.setStyleSheet("font-weight: bold;")

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.preview.setFont(QFont("Consolas", 10))
        self.preview.setToolTip(tr("preview.tooltip"))

        status_row = QHBoxLayout()
        self.status_label = QLabel(tr("status.ready"))
        self.progress_bar = QProgressBar()
        self.progress_bar.setAccessibleDescription(tr("a11y.progress"))
        self.progress_bar.setVisible(False)

        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(self.progress_bar, 1)

        right_layout.addWidget(self.settings_box)
        right_layout.addWidget(self.preview_label)
        right_layout.addWidget(self.preview, 1)
        right_layout.addLayout(status_row)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([430, 850])

        self.files_label.setBuddy(self.file_list)
        self.separator_label.setBuddy(self.radio_blank)
        self.output_label.setBuddy(self.output_combo)
        self.preview_label.setBuddy(self.preview)

        self.setTabOrder(self.file_list, self.btn_add_files)
        self.setTabOrder(self.btn_add_files, self.btn_add_folder)
        self.setTabOrder(self.btn_add_folder, self.btn_remove)
        self.setTabOrder(self.btn_remove, self.btn_clear)
        self.setTabOrder(self.btn_clear, self.btn_up)
        self.setTabOrder(self.btn_up, self.btn_down)
        self.setTabOrder(self.btn_down, self.recursive_check)
        self.setTabOrder(self.recursive_check, self.recent_combo)
        self.setTabOrder(self.recent_combo, self.radio_blank)
        self.setTabOrder(self.radio_blank, self.radio_dashes)
        self.setTabOrder(self.radio_dashes, self.radio_filename)
        self.setTabOrder(self.radio_filename, self.radio_custom)
        self.setTabOrder(self.radio_custom, self.custom_edit)
        self.setTabOrder(self.custom_edit, self.output_combo)
        self.setTabOrder(self.output_combo, self.preview)

        self._setup_menu()

        # --------------------------------------------------------------
        # Conexiones
        # --------------------------------------------------------------
        self.btn_add_files.clicked.connect(self.choose_files)
        self.btn_add_folder.clicked.connect(self.choose_folder)
        self.btn_remove.clicked.connect(self.remove_selected)
        self.btn_clear.clicked.connect(self.clear_all)
        self.btn_up.clicked.connect(lambda: self._move_current(-1))
        self.btn_down.clicked.connect(lambda: self._move_current(1))

        self.action_add_files.triggered.connect(self.choose_files)
        self.action_add_folder.triggered.connect(self.choose_folder)
        self.action_review_duplicates.triggered.connect(self.review_duplicates)
        self.action_save.triggered.connect(self.save_output)
        self.action_save_recipe.triggered.connect(self.save_recipe)
        self.action_load_recipe.triggered.connect(self.load_recipe)
        self.action_export_log.triggered.connect(self.export_log)
        self.action_exit.triggered.connect(self.close)
        self.action_dark.toggled.connect(self._on_theme_toggled)
        self.action_lang_es.triggered.connect(lambda: self._on_language_changed("es"))
        self.action_lang_en.triggered.connect(lambda: self._on_language_changed("en"))
        self.action_about.triggered.connect(self._show_about)

        self.radio_blank.toggled.connect(
            lambda checked: self._on_separator_mode_changed("blank", checked)
        )
        self.radio_dashes.toggled.connect(
            lambda checked: self._on_separator_mode_changed("dashes", checked)
        )
        self.radio_filename.toggled.connect(
            lambda checked: self._on_separator_mode_changed("filename", checked)
        )
        self.radio_custom.toggled.connect(
            lambda checked: self._on_separator_mode_changed("custom", checked)
        )

        self.custom_edit.textChanged.connect(self._on_custom_separator_changed)
        self.output_combo.currentTextChanged.connect(self._on_output_format_changed)
        self.recent_combo.activated.connect(self._on_recent_folder_selected)

        # Sincroniza el orden después de drag & drop.
        self.file_list.model().rowsMoved.connect(self._sync_files_from_list)

    def _setup_menu(self) -> None:
        self.action_add_files = QAction(tr("act.add_files"), self)
        self.action_add_files.setShortcut("Ctrl+F")

        self.action_add_folder = QAction(tr("act.add_folder"), self)
        self.action_add_folder.setShortcut("Ctrl+D")

        self.action_save = QAction(tr("act.save"), self)
        self.action_save.setShortcut("Ctrl+S")

        self.action_save_recipe = QAction(tr("act.save_recipe"), self)
        self.action_save_recipe.setShortcut("Ctrl+Shift+S")

        self.action_load_recipe = QAction(tr("act.load_recipe"), self)
        self.action_load_recipe.setShortcut("Ctrl+O")

        self.action_export_log = QAction(tr("act.export_log"), self)
        self.action_export_log.setShortcut("Ctrl+E")
        self.action_exit = QAction(tr("act.exit"), self)
        self.action_exit.setShortcut("Ctrl+Q")

        self.action_review_duplicates = QAction(tr("act.review_duplicates"), self)
        self.action_review_duplicates.setShortcut("Ctrl+U")

        self.tools_menu = self.menuBar().addMenu(tr("menu.tools"))
        self.tools_menu.addAction(self.action_review_duplicates)

        self.file_menu = self.menuBar().addMenu(tr("menu.file"))
        self.file_menu.addAction(self.action_add_files)
        self.file_menu.addAction(self.action_add_folder)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.action_save)
        self.file_menu.addAction(self.action_export_log)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.action_save_recipe)
        self.file_menu.addAction(self.action_load_recipe)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.action_exit)

        self.action_dark = QAction(tr("act.dark"), self)
        self.action_dark.setCheckable(True)
        self.action_dark.setChecked(self.settings.dark_mode)

        self.view_menu = self.menuBar().addMenu(tr("menu.view"))
        self.view_menu.addAction(self.action_dark)

        self.language_menu = self.view_menu.addMenu(tr("menu.language"))
        self.language_group = QActionGroup(self)
        self.action_lang_es = QAction("Español", self)
        self.action_lang_es.setCheckable(True)
        self.action_lang_es.setData("es")
        self.action_lang_en = QAction("English", self)
        self.action_lang_en.setCheckable(True)
        self.action_lang_en.setData("en")
        self.language_group.addAction(self.action_lang_es)
        self.language_group.addAction(self.action_lang_en)
        self.language_menu.addAction(self.action_lang_es)
        self.language_menu.addAction(self.action_lang_en)
        self._sync_language_checks()

        self.action_about = QAction(tr("act.about"), self)
        self.help_menu = self.menuBar().addMenu(tr("menu.help"))
        self.help_menu.addAction(self.action_about)

    # ------------------------------------------------------------------
    # Estado / helpers UI
    # ------------------------------------------------------------------

    def _set_busy(self, busy: bool) -> None:
        """
        Habilita o deshabilita controles durante el procesamiento.
        """
        enabled = not busy

        widgets = [
            self.btn_add_files,
            self.btn_add_folder,
            self.btn_remove,
            self.btn_clear,
            self.btn_up,
            self.btn_down,
            self.recursive_check,
            self.recent_combo,
            self.action_add_files,
            self.action_add_folder,
            self.action_review_duplicates,
            self.action_save,
            self.action_save_recipe,
            self.action_load_recipe,
            self.action_export_log,
            self.output_combo,
            self.radio_blank,
            self.radio_dashes,
            self.radio_filename,
            self.radio_custom,
            self.custom_edit,
        ]

        for widget in widgets:
            widget.setEnabled(enabled)

        self.progress_bar.setVisible(busy)

        if not busy:
            self._update_custom_edit_enabled()

    def _update_custom_edit_enabled(self) -> None:
        self.custom_edit.setEnabled(self.settings.separator_mode == "custom")

    def _sync_language_checks(self) -> None:
        self.action_lang_es.setChecked(self.settings.language == "es")
        self.action_lang_en.setChecked(self.settings.language == "en")

    def _on_language_changed(self, language: str) -> None:
        set_language(language)
        self.settings.language = get_language()
        self.settings.save()
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("app.title"))
        self.file_menu.setTitle(tr("menu.file"))
        self.tools_menu.setTitle(tr("menu.tools"))
        self.view_menu.setTitle(tr("menu.view"))
        self.help_menu.setTitle(tr("menu.help"))
        self.language_menu.setTitle(tr("menu.language"))
        self.action_add_files.setText(tr("act.add_files"))
        self.action_add_folder.setText(tr("act.add_folder"))
        self.action_save.setText(tr("act.save"))
        self.action_save_recipe.setText(tr("act.save_recipe"))
        self.action_load_recipe.setText(tr("act.load_recipe"))
        self.action_export_log.setText(tr("act.export_log"))
        self.action_exit.setText(tr("act.exit"))
        self.action_review_duplicates.setText(tr("act.review_duplicates"))
        self.action_dark.setText(tr("act.dark"))
        self.action_about.setText(tr("act.about"))
        self.files_label.setText(tr("files.title"))
        self.file_list.setToolTip(tr("files.tooltip"))
        self.btn_add_files.setText(tr("act.add_files"))
        self.btn_add_folder.setText(tr("act.add_folder"))
        self.btn_remove.setText(tr("btn.remove"))
        self.btn_remove.setToolTip(tr("tip.remove"))
        self.btn_clear.setText(tr("btn.clear"))
        self.btn_clear.setToolTip(tr("tip.clear"))
        self.btn_up.setToolTip(tr("tip.up"))
        self.btn_up.setAccessibleName(tr("name.up"))
        self.btn_up.setAccessibleDescription(tr("tip.up"))
        self.btn_down.setToolTip(tr("tip.down"))
        self.btn_down.setAccessibleName(tr("name.down"))
        self.btn_down.setAccessibleDescription(tr("tip.down"))
        self.recursive_check.setText(tr("check.recursive"))
        self.recent_combo.setToolTip(tr("tip.recent"))
        self.settings_box.setTitle(tr("settings.title"))
        self.separator_label.setText(tr("sep.title"))
        self.radio_blank.setText(tr("sep.blank"))
        self.radio_dashes.setText(tr("sep.dashes"))
        self.radio_filename.setText(tr("sep.filename"))
        self.radio_custom.setText(tr("sep.custom"))
        self.custom_edit.setPlaceholderText(tr("custom.placeholder"))
        self.custom_edit.setToolTip(tr("custom.tooltip"))
        self.output_label.setText(tr("output.label"))
        self.preview.setToolTip(tr("preview.tooltip"))
        self.progress_bar.setAccessibleDescription(tr("a11y.progress"))
        self._sync_language_checks()
        self._update_recent_combo()
        self.refresh_preview()
        self.status_label.setText(tr("status.ready"))

    def _update_recent_combo(self) -> None:
        self.recent_combo.blockSignals(True)
        self.recent_combo.clear()
        self.recent_combo.addItem(tr("recent.placeholder"))

        for folder in self.settings.recent_folders:
            self.recent_combo.addItem(folder)

        self.recent_combo.setCurrentIndex(0)
        self.recent_combo.blockSignals(False)

    def _add_list_item(self, item: ConsolidationFile) -> None:
        list_item = QListWidgetItem(item.name)
        list_item.setData(Qt.ItemDataRole.UserRole, str(item.path))
        list_item.setToolTip(str(item.path))
        self.file_list.addItem(list_item)

    # ------------------------------------------------------------------
    # Selección de archivos / carpetas
    # ------------------------------------------------------------------

    def choose_files(self) -> None:
        start_dir = (
            self.settings.recent_folders[0]
            if self.settings.recent_folders
            else str(Path.home())
        )

        extensions = self.registry.supported_extensions()
        filter_text = (
            tr("filter.supported", exts=" ".join(f"*{ext}" for ext in extensions))
            + ";;"
            + tr("filter.all")
        )

        files, _ = QFileDialog.getOpenFileNames(
            self,
            tr("dlg.select_files"),
            start_dir,
            filter_text,
        )

        if not files:
            return

        paths = [Path(file_path) for file_path in files]

        self.settings.add_recent_folder(str(paths[0].parent))
        self._update_recent_combo()

        self._process_paths(paths)

    def choose_folder(self) -> None:
        start_dir = (
            self.settings.recent_folders[0]
            if self.settings.recent_folders
            else str(Path.home())
        )

        folder = QFileDialog.getExistingDirectory(
            self,
            tr("dlg.select_folder"),
            start_dir,
        )

        if folder:
            self._open_folder(Path(folder))

    def _open_folder(self, folder: Path) -> None:
        if not folder.is_dir():
            return

        self.settings.add_recent_folder(str(folder))
        self._update_recent_combo()

        pattern = "**/*" if self.recursive_check.isChecked() else "*"

        try:
            candidates = sorted(folder.glob(pattern))
        except OSError as exc:
            QMessageBox.critical(
                self,
                tr("error.title"),
                tr("folder.read_error", detail=exc),
            )
            return

        paths = [
            path
            for path in candidates
            if path.is_file() and self.registry.is_supported(path)
        ]

        if not paths:
            QMessageBox.information(
                self,
                tr("folder.title"),
                tr("folder.empty"),
            )
            return

        self._process_paths(paths)

    def _on_recent_folder_selected(self, index: int) -> None:
        if index <= 0:
            return

        folder = Path(self.recent_combo.itemText(index))
        self.recent_combo.setCurrentIndex(0)

        if not folder.is_dir():
            QMessageBox.warning(
                self,
                tr("recent.title"),
                tr("recent.gone"),
            )

            if str(folder) in self.settings.recent_folders:
                self.settings.recent_folders.remove(str(folder))
                self.settings.save()
                self._update_recent_combo()

            return

        self._open_folder(folder)

    # ------------------------------------------------------------------
    # Procesamiento
    # ------------------------------------------------------------------

    def _process_paths(self, paths: List[Path]) -> None:
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(
                self,
                tr("processing.title"),
                tr("processing.busy"),
            )
            return

        existing = {str(file_item.path) for file_item in self.files}
        unique_paths: List[Path] = []
        seen = set(existing)

        for path in paths:
            try:
                resolved = path.resolve(strict=False)
            except OSError:
                resolved = path

            key = str(resolved)

            if key in seen:
                continue

            seen.add(key)
            unique_paths.append(resolved)

        if not unique_paths:
            self.status_label.setText(tr("status.nothing_new"))
            return

        self.worker = ExtractionWorker(unique_paths, self.registry, self)
        self.worker.progress.connect(self._on_progress)
        self.worker.file_ready.connect(self._on_file_ready)
        self.worker.finished_all.connect(self._on_worker_finished)

        self.progress_bar.setRange(0, len(unique_paths))
        self.progress_bar.setValue(0)

        self._set_busy(True)
        self.status_label.setText(tr("status.processing"))
        self.worker.start()

    def _on_progress(self, current: int, total: int, name: str) -> None:
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_label.setText(tr("status.progress", current=current, total=total, name=name))

    def _on_file_ready(self, item: ConsolidationFile) -> None:
        if item.error is None:
            self.files.append(item)
            self._add_list_item(item)
            self.journal.append_add([item.path])
            self._append_preview(item)
        else:
            self.errors.append(item)

    def _on_worker_finished(self, ok_items: list, error_items: list) -> None:
        if self.worker is not None:
            self.worker.deleteLater()

        self.worker = None
        self._set_busy(False)
        self.refresh_preview()

        if error_items:
            self.status_label.setText(tr("status.done_errors", count=len(error_items)))

            answer = QMessageBox.warning(
                self,
                tr("errors.title"),
                tr("errors.body", ok=len(ok_items), errors=len(error_items)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if answer == QMessageBox.StandardButton.Yes:
                self._show_error_report()
        else:
            self.status_label.setText(tr("status.done_ok", count=len(ok_items)))

    # ------------------------------------------------------------------
    # Lista de archivos
    # ------------------------------------------------------------------

    def _sync_files_from_list(self, *args) -> None:
        """
        Reconstruye self.files según el orden actual de la QListWidget.
        """
        path_map = {str(file_item.path): file_item for file_item in self.files}
        new_files: List[ConsolidationFile] = []

        for index in range(self.file_list.count()):
            item = self.file_list.item(index)
            path = item.data(Qt.ItemDataRole.UserRole)

            if path in path_map:
                new_files.append(path_map[path])

        self.files = new_files
        self.journal.append_reorder([item.path for item in new_files])
        self.refresh_preview()

    def review_duplicates(self) -> None:
        if len(self.files) < 2:
            self.status_label.setText(tr("dupes.need_two"))
            return

        dialog = DuplicateReviewDialog(self.files, self)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        removals = set(dialog.collect_removals())

        if not removals:
            self.status_label.setText(tr("dupes.no_change"))
            return

        for row in range(self.file_list.count() - 1, -1, -1):
            item = self.file_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) in removals:
                self.file_list.takeItem(row)

        self._sync_files_from_list()
        self.status_label.setText(tr("dupes.removed", count=len(removals)))

    def _restore_session(self) -> None:
        recorded = self.journal.load()

        if not recorded:
            return

        existing = [path for path in recorded if Path(path).is_file()]
        missing = [path for path in recorded if not Path(path).is_file()]

        for path in missing:
            missing_path = Path(path)
            self.errors.append(
                ConsolidationFile(
                    path=missing_path,
                    name=missing_path.name,
                    error=tr("restore.missing_error"),
                )
            )

        if existing:
            self.journal.snapshot(existing)
            self._process_paths([Path(path) for path in existing])

        if missing:
            self.status_label.setText(
                tr("status.restored", ok=len(existing), missing=len(missing))
            )

    def remove_selected(self) -> None:
        selected = self.file_list.selectedItems()

        if not selected:
            self.status_label.setText(tr("status.select_remove"))
            return

        for item in selected:
            self.file_list.takeItem(self.file_list.row(item))

        self._sync_files_from_list()
        self.status_label.setText(tr("status.removed"))

    def clear_all(self) -> None:
        if self.file_list.count() == 0 and not self.errors:
            return

        answer = QMessageBox.question(
            self,
            tr("clear.title"),
            tr("clear.body"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self.file_list.clear()
        self.files.clear()
        self.errors.clear()
        self.journal.append_clear()

        self.refresh_preview()
        self.status_label.setText(tr("status.cleared"))

    def _move_current(self, delta: int) -> None:
        row = self.file_list.currentRow()

        if row < 0:
            return

        new_row = row + delta

        if new_row < 0 or new_row >= self.file_list.count():
            return

        item = self.file_list.takeItem(row)
        self.file_list.insertItem(new_row, item)
        self.file_list.setCurrentItem(item)

        self._sync_files_from_list()

    # ------------------------------------------------------------------
    # Preview y configuración
    # ------------------------------------------------------------------

    def refresh_preview(self) -> None:
        output = build_output(self.files, self.settings)
        self.preview.setPlainText(output)
        self._preview_chars = len(output)
        self._update_preview_label()

    def _update_preview_label(self) -> None:
        self.preview_label.setText(
            tr("preview.label", count=len(self.files), chars=f"{self._preview_chars:,}")
        )

    def _append_preview(self, item: ConsolidationFile) -> None:
        # Válido porque toda mutación (reorden, borrado, ajustes) pasa por
        # refresh_preview; las llegadas solo agregan al final.
        if not self.files or self.files[-1] is not item:
            self.refresh_preview()
            return

        if len(self.files) == 1:
            if self.settings.separator_mode == "filename":
                chunk = f"=== {item.name} ===\n{item.text}"
            else:
                chunk = item.text
        elif self.settings.separator_mode == "filename":
            chunk = f"\n\n=== {item.name} ===\n{item.text}"
        else:
            chunk = render_separator(self.settings, item) + item.text

        cursor = self.preview.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(chunk)
        self.preview.setTextCursor(cursor)
        self._preview_chars += len(chunk)
        self._update_preview_label()

    def _on_theme_toggled(self, checked: bool) -> None:
        self.settings.dark_mode = checked

        app = QApplication.instance()
        if app:
            apply_theme(app, checked)

        self.settings.save()

    def _on_separator_mode_changed(self, mode: str, checked: bool) -> None:
        if not checked:
            return

        self.settings.separator_mode = mode
        self._update_custom_edit_enabled()
        self.refresh_preview()
        self.settings.save()

    def _on_custom_separator_changed(self, text: str) -> None:
        self.settings.custom_separator = text

        if self.settings.separator_mode == "custom":
            self.refresh_preview()

        self.settings.save()

    def _on_output_format_changed(self, text: str) -> None:
        if text in {".txt", ".docx"}:
            self.settings.output_format = text
            self.settings.save()

    # ------------------------------------------------------------------
    # Guardado
    # ------------------------------------------------------------------

    def save_output(self) -> None:
        if not self.files:
            QMessageBox.information(
                self,
                tr("dlg.save"),
                tr("save.empty"),
            )
            return

        if self.settings.output_format == ".docx":
            file_filter = tr("filter.docx")
            default_name = tr("default.output_docx")
        else:
            file_filter = tr("filter.txt")
            default_name = tr("default.output_txt")

        start_dir = (
            self.settings.recent_folders[0]
            if self.settings.recent_folders
            else str(Path.home())
        )

        start_path = str(Path(start_dir) / default_name)

        filename, _ = QFileDialog.getSaveFileName(
            self,
            tr("dlg.save"),
            start_path,
            file_filter,
        )

        if not filename:
            return

        path = Path(filename)

        if path.suffix.lower() != self.settings.output_format:
            path = path.with_suffix(self.settings.output_format)

        try:
            output = build_output(self.files, self.settings)

            if path.suffix.lower() == ".docx":
                self._write_docx(path, output)
            else:
                path.write_text(output, encoding="utf-8")

            log_path = None
            if self.errors:
                log_path = self._write_error_log(path)

            message = tr("save.done", path=path)

            if log_path:
                message += tr("save.done_log", path=log_path)

            QMessageBox.information(self, tr("dlg.save"), message)

        except Exception as exc:
            QMessageBox.critical(
                self,
                tr("error.title"),
                tr("save.failed", detail=exc),
            )

    def _write_docx(self, path: Path, text: str) -> None:
        try:
            from docx import Document
        except ImportError as exc:
            raise RuntimeError(
                "Falta la dependencia python-docx para guardar DOCX."
            ) from exc

        document = Document()

        for line in text.splitlines():
            document.add_paragraph(line)

        document.save(str(path))

    def save_recipe(self) -> None:
        if not self.files:
            QMessageBox.information(
                self,
                tr("dlg.save_recipe"),
                tr("recipe.empty"),
            )
            return

        start_dir = (
            self.settings.recent_folders[0]
            if self.settings.recent_folders
            else str(Path.home())
        )

        filename, _ = QFileDialog.getSaveFileName(
            self,
            tr("dlg.save_recipe"),
            str(Path(start_dir) / tr("default.recipe_name")),
            tr("filter.yaml"),
        )

        if not filename:
            return

        recipe_path = Path(filename)

        if not recipe_path.suffix:
            recipe_path = recipe_path.with_suffix(".yaml")

        output_path = (
            recipe_path.parent
            / f"{recipe_path.stem}{tr('recipe.output_suffix')}{self.settings.output_format}"
        )
        recipe = recipes.Recipe(
            inputs=[recipes.InputSpec(path=item.path) for item in self.files],
            outputs=[recipes.OutputSpec(output_path, self.settings.output_format)],
            options=recipes.JobOptions(
                self.settings.separator_mode,
                self.settings.custom_separator,
            ),
            order="input",
        )

        try:
            recipes.dump_recipe(recipe, recipe_path)
        except OSError as exc:
            QMessageBox.critical(
                self,
                tr("error.title"),
                tr("recipe.save_failed", detail=exc),
            )
            return

        QMessageBox.information(
            self,
            tr("dlg.save_recipe"),
            tr("recipe.saved", recipe=recipe_path, output=output_path),
        )

    def load_recipe(self) -> None:
        start_dir = (
            self.settings.recent_folders[0]
            if self.settings.recent_folders
            else str(Path.home())
        )

        filename, _ = QFileDialog.getOpenFileName(
            self,
            tr("dlg.load_recipe"),
            start_dir,
            tr("filter.yaml"),
        )

        if not filename:
            return

        try:
            recipe = recipes.load_recipe(Path(filename))
            paths = discover_inputs(recipe, self.registry)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(
                self,
                tr("error.title"),
                tr("recipe.load_failed", detail=exc),
            )
            return

        ignored = []

        if recipe.transforms:
            ignored.append(tr("recipe.ignored.transforms", items=", ".join(recipe.transforms)))

        if recipe.dedup != "off":
            ignored.append(tr("recipe.ignored.dedup", mode=recipe.dedup))

        if recipe.ocr:
            ignored.append(tr("recipe.ignored.ocr", name=recipe.ocr))

        unsupported = [
            output.format
            for output in recipe.outputs
            if output.format.lower().lstrip(".") not in ("txt", "docx")
        ]

        if unsupported:
            ignored.append(tr("recipe.ignored.formats", items=", ".join(unsupported)))

        if ignored:
            QMessageBox.warning(
                self,
                tr("dlg.load_recipe"),
                tr("recipe.ignored", items="\n- ".join(ignored)),
            )

        radios = {
            "blank": self.radio_blank,
            "dashes": self.radio_dashes,
            "filename": self.radio_filename,
            "custom": self.radio_custom,
        }
        radios[recipe.options.separator_mode].setChecked(True)
        self.custom_edit.setText(recipe.options.custom_separator)

        if recipe.outputs:
            supported = recipe.outputs[0].format.lower().lstrip(".")

            if supported in ("txt", "docx"):
                self.output_combo.setCurrentText(f".{supported}")

        self._process_paths(paths)

    def _write_error_log(self, output_path: Path) -> Path:
        log_path = output_path.parent / f"{output_path.stem}{tr('log.suffix')}.log"
        log_path.write_text(self._build_error_report(), encoding="utf-8")
        return log_path

    # ------------------------------------------------------------------
    # Informe de errores
    # ------------------------------------------------------------------

    def _build_error_report(self) -> str:
        lines = [
            tr("report.header"),
            tr("report.date", date=datetime.now().isoformat(timespec="seconds")),
            tr("report.total", count=len(self.errors)),
            "",
        ]

        for item in self.errors:
            lines.append(tr("report.file", path=item.path))
            lines.append(tr("report.reason", reason=item.error))
            lines.append("")

        return "\n".join(lines)

    def export_log(self) -> None:
        if not self.errors:
            QMessageBox.information(
                self,
                tr("log.title"),
                tr("log.empty"),
            )
            return

        default_path = str(Path.home() / tr("default.log_name"))

        filename, _ = QFileDialog.getSaveFileName(
            self,
            tr("dlg.export_log"),
            default_path,
            tr("filter.log"),
        )

        if not filename:
            return

        path = Path(filename)

        if not path.suffix:
            path = path.with_suffix(".log")

        try:
            path.write_text(self._build_error_report(), encoding="utf-8")
            QMessageBox.information(
                self,
                tr("log.title"),
                tr("log.saved", path=path),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                tr("error.title"),
                tr("log.save_failed", detail=exc),
            )

    def _show_error_report(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("report.title"))

        layout = QVBoxLayout(dialog)

        text_edit = QPlainTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(self._build_error_report())

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.clicked.connect(lambda _: dialog.close())

        layout.addWidget(text_edit)
        layout.addWidget(buttons)

        dialog.resize(720, 420)
        dialog.exec()

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            tr("act.about"),
            tr("about.body"),
        )

    # ------------------------------------------------------------------
    # Eventos
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(1500)

        self.settings.save()
        super().closeEvent(event)
