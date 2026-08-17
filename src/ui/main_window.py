"""
Ventana principal de la aplicación.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont
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

from src.config import AppSettings
from src.core.consolidator import build_output
from src.core.models import ConsolidationFile
from src.core.worker import ExtractionWorker
from src.extractors.registry import create_default_registry
from src.ui.theme import apply_theme


class MainWindow(QMainWindow):
    """
    Ventana principal del Consolidador de Textos.
    """

    def __init__(self, settings: AppSettings) -> None:
        super().__init__()

        self.settings = settings
        self.registry = create_default_registry()
        self.files: List[ConsolidationFile] = []
        self.errors: List[ConsolidationFile] = []
        self.worker: Optional[ExtractionWorker] = None

        self._setup_ui()
        self._update_recent_combo()
        self._update_custom_edit_enabled()
        self.refresh_preview()

        self.setWindowTitle("Consolidador de Textos")
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

        files_label = QLabel("Archivos de la sesión")
        files_label.setStyleSheet("font-weight: bold;")

        self.file_list = QListWidget()
        self.file_list.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove
        )
        self.file_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.file_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.file_list.setAlternatingRowColors(True)
        self.file_list.setToolTip("Arrastra para reordenar")

        btn_row1 = QHBoxLayout()
        self.btn_add_files = QPushButton("Agregar archivos...")
        self.btn_add_folder = QPushButton("Agregar carpeta...")
        btn_row1.addWidget(self.btn_add_files)
        btn_row1.addWidget(self.btn_add_folder)

        btn_row2 = QHBoxLayout()
        self.btn_remove = QPushButton("Quitar")
        self.btn_clear = QPushButton("Limpiar")
        self.btn_up = QPushButton("↑")
        self.btn_down = QPushButton("↓")

        self.btn_remove.setToolTip("Eliminar archivos seleccionados de la sesión")
        self.btn_clear.setToolTip("Limpiar la sesión actual")
        self.btn_up.setToolTip("Subir el archivo seleccionado")
        self.btn_down.setToolTip("Bajar el archivo seleccionado")

        btn_row2.addWidget(self.btn_remove)
        btn_row2.addWidget(self.btn_clear)
        btn_row2.addStretch(1)
        btn_row2.addWidget(self.btn_up)
        btn_row2.addWidget(self.btn_down)

        self.recursive_check = QCheckBox("Incluir subcarpetas")
        self.recent_combo = QComboBox()
        self.recent_combo.setToolTip(
            "Selecciona una carpeta reciente para volver a procesarla"
        )

        left_layout.addWidget(files_label)
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

        settings_box = QGroupBox("Configuración de consolidación")
        settings_layout = QVBoxLayout(settings_box)

        separator_label = QLabel("Separador entre archivos")
        separator_label.setStyleSheet("font-weight: bold;")

        self.radio_blank = QRadioButton("Línea en blanco simple")
        self.radio_dashes = QRadioButton("Línea de guiones (---)")
        self.radio_filename = QRadioButton("Nombre del archivo como encabezado")
        self.radio_custom = QRadioButton("Separador personalizado")

        mode = self.settings.separator_mode
        self.radio_blank.setChecked(mode == "blank")
        self.radio_dashes.setChecked(mode == "dashes")
        self.radio_filename.setChecked(mode == "filename")
        self.radio_custom.setChecked(mode == "custom")

        self.custom_edit = QLineEdit(self.settings.custom_separator)
        self.custom_edit.setPlaceholderText(
            "Usa \\n para salto de línea y {filename} para el siguiente archivo"
        )
        self.custom_edit.setToolTip(
            "Texto literal entre archivos. Soporta \\n, \\t y {filename}."
        )

        output_row = QHBoxLayout()
        output_label = QLabel("Formato de salida")
        self.output_combo = QComboBox()
        self.output_combo.addItems([".txt", ".docx"])
        self.output_combo.setCurrentText(self.settings.output_format)
        output_row.addWidget(output_label)
        output_row.addWidget(self.output_combo)
        output_row.addStretch(1)

        settings_layout.addWidget(separator_label)
        settings_layout.addWidget(self.radio_blank)
        settings_layout.addWidget(self.radio_dashes)
        settings_layout.addWidget(self.radio_filename)
        settings_layout.addWidget(self.radio_custom)
        settings_layout.addWidget(self.custom_edit)
        settings_layout.addLayout(output_row)

        self.preview_label = QLabel("Vista previa")
        self.preview_label.setStyleSheet("font-weight: bold;")

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.preview.setFont(QFont("Consolas", 10))
        self.preview.setToolTip("Contenido exacto que se guardará")

        status_row = QHBoxLayout()
        self.status_label = QLabel("Listo")
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(self.progress_bar, 1)

        right_layout.addWidget(settings_box)
        right_layout.addWidget(self.preview_label)
        right_layout.addWidget(self.preview, 1)
        right_layout.addLayout(status_row)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([430, 850])

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
        self.action_save.triggered.connect(self.save_output)
        self.action_export_log.triggered.connect(self.export_log)
        self.action_exit.triggered.connect(self.close)
        self.action_dark.toggled.connect(self._on_theme_toggled)
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
        self.action_add_files = QAction("Agregar archivos...", self)
        self.action_add_files.setShortcut("Ctrl+F")

        self.action_add_folder = QAction("Agregar carpeta...", self)
        self.action_add_folder.setShortcut("Ctrl+D")

        self.action_save = QAction("Guardar consolidado...", self)
        self.action_save.setShortcut("Ctrl+S")

        self.action_export_log = QAction("Exportar informe de errores...", self)
        self.action_exit = QAction("Salir", self)

        file_menu = self.menuBar().addMenu("&Archivo")
        file_menu.addAction(self.action_add_files)
        file_menu.addAction(self.action_add_folder)
        file_menu.addSeparator()
        file_menu.addAction(self.action_save)
        file_menu.addAction(self.action_export_log)
        file_menu.addSeparator()
        file_menu.addAction(self.action_exit)

        self.action_dark = QAction("Modo oscuro", self)
        self.action_dark.setCheckable(True)
        self.action_dark.setChecked(self.settings.dark_mode)

        view_menu = self.menuBar().addMenu("&Ver")
        view_menu.addAction(self.action_dark)

        self.action_about = QAction("Acerca de", self)
        help_menu = self.menuBar().addMenu("A&yuda")
        help_menu.addAction(self.action_about)

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
            self.action_save,
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

    def _update_recent_combo(self) -> None:
        self.recent_combo.blockSignals(True)
        self.recent_combo.clear()
        self.recent_combo.addItem("Carpetas recientes...")

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
            "Archivos soportados ("
            + " ".join(f"*{ext}" for ext in extensions)
            + ");;Todos los archivos (*)"
        )

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Seleccionar archivos",
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
            "Seleccionar carpeta",
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
                "Error",
                f"No se pudo leer la carpeta:\n{exc}",
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
                "Carpeta",
                "No se encontraron archivos soportados en la carpeta seleccionada.",
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
                "Carpeta reciente",
                "La carpeta ya no existe.",
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
                "Procesando",
                "Espera a que termine el proceso actual.",
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
            self.status_label.setText(
                "No se agregaron archivos nuevos (duplicados o vacíos)."
            )
            return

        self.worker = ExtractionWorker(unique_paths, self.registry, self)
        self.worker.progress.connect(self._on_progress)
        self.worker.file_ready.connect(self._on_file_ready)
        self.worker.finished_all.connect(self._on_worker_finished)

        self.progress_bar.setRange(0, len(unique_paths))
        self.progress_bar.setValue(0)

        self._set_busy(True)
        self.status_label.setText("Procesando archivos...")
        self.worker.start()

    def _on_progress(self, current: int, total: int, name: str) -> None:
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_label.setText(f"Procesando {current}/{total}: {name}")

    def _on_file_ready(self, item: ConsolidationFile) -> None:
        if item.error is None:
            self.files.append(item)
            self._add_list_item(item)
            self.refresh_preview()
        else:
            self.errors.append(item)

    def _on_worker_finished(self, ok_items: list, error_items: list) -> None:
        if self.worker is not None:
            self.worker.deleteLater()

        self.worker = None
        self._set_busy(False)
        self.refresh_preview()

        if error_items:
            self.status_label.setText(
                f"Completado con {len(error_items)} omitidos."
            )

            answer = QMessageBox.warning(
                self,
                "Archivos omitidos",
                f"Se procesaron {len(ok_items)} archivos correctamente.\n"
                f"{len(error_items)} archivos se omitieron.\n\n"
                "¿Quieres ver el informe?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if answer == QMessageBox.StandardButton.Yes:
                self._show_error_report()
        else:
            self.status_label.setText(
                f"Completado: {len(ok_items)} archivos procesados."
            )

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
        self.refresh_preview()

    def remove_selected(self) -> None:
        selected = self.file_list.selectedItems()

        if not selected:
            self.status_label.setText(
                "Selecciona uno o más archivos para quitar."
            )
            return

        for item in selected:
            self.file_list.takeItem(self.file_list.row(item))

        self._sync_files_from_list()
        self.status_label.setText("Archivos quitados de la sesión.")

    def clear_all(self) -> None:
        if self.file_list.count() == 0 and not self.errors:
            return

        answer = QMessageBox.question(
            self,
            "Limpiar sesión",
            "¿Quitar todos los archivos y errores de la sesión actual?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self.file_list.clear()
        self.files.clear()
        self.errors.clear()

        self.refresh_preview()
        self.status_label.setText("Sesión limpia.")

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

        self.preview_label.setText(
            f"Vista previa ({len(self.files)} archivos, {len(output):,} caracteres)"
        )

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
                "Guardar",
                "No hay archivos en la sesión para consolidar.",
            )
            return

        if self.settings.output_format == ".docx":
            file_filter = "Documento Word (*.docx)"
            default_name = "consolidado.docx"
        else:
            file_filter = "Texto plano (*.txt)"
            default_name = "consolidado.txt"

        start_dir = (
            self.settings.recent_folders[0]
            if self.settings.recent_folders
            else str(Path.home())
        )

        start_path = str(Path(start_dir) / default_name)

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar consolidado",
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

            message = f"Archivo guardado en:\n{path}"

            if log_path:
                message += f"\n\nInforme de errores guardado en:\n{log_path}"

            QMessageBox.information(self, "Guardado", message)

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Error",
                f"No se pudo guardar el archivo:\n{exc}",
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

    def _write_error_log(self, output_path: Path) -> Path:
        log_path = output_path.parent / f"{output_path.stem}_errores.log"
        log_path.write_text(self._build_error_report(), encoding="utf-8")
        return log_path

    # ------------------------------------------------------------------
    # Informe de errores
    # ------------------------------------------------------------------

    def _build_error_report(self) -> str:
        lines = [
            "Informe de archivos omitidos",
            f"Fecha: {datetime.now().isoformat(timespec='seconds')}",
            f"Total omitidos: {len(self.errors)}",
            "",
        ]

        for item in self.errors:
            lines.append(f"Archivo: {item.path}")
            lines.append(f"Motivo: {item.error}")
            lines.append("")

        return "\n".join(lines)

    def export_log(self) -> None:
        if not self.errors:
            QMessageBox.information(
                self,
                "Informe",
                "No hay archivos omitidos en la sesión actual.",
            )
            return

        default_path = str(Path.home() / "errores_consolidacion.log")

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar informe de errores",
            default_path,
            "Registro (*.log);;Texto (*.txt)",
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
                "Informe",
                f"Informe guardado en:\n{path}",
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Error",
                f"No se pudo guardar el informe:\n{exc}",
            )

    def _show_error_report(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Informe de archivos omitidos")

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
            "Acerca de",
            "Consolidador de Textos MVP\n"
            "Herramienta open source para consolidar texto de múltiples archivos.\n\n"
            "Licencia MIT.\n"
            "Dependencias: PySide6, python-docx, pypdf.",
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
