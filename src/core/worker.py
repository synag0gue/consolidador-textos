"""
Procesamiento en segundo plano para no bloquear la interfaz.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Sequence

from PySide6.QtCore import QThread, Signal

from src.core.consolidator import extract_file
from src.core.models import ConsolidationFile
from src.extractors.registry import ExtractorRegistry


class ExtractionWorker(QThread):
    """
    Hilo que extrae texto de una lista de archivos.
    """

    progress = Signal(int, int, str)
    file_ready = Signal(object)
    finished_all = Signal(object, object)

    def __init__(
        self,
        paths: Sequence[Path],
        registry: ExtractorRegistry,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.paths = list(paths)
        self.registry = registry
        self._cancelled = False

    def cancel(self) -> None:
        """
        Solicita la cancelación del procesamiento.
        """
        self._cancelled = True

    def run(self) -> None:
        """
        Procesa cada archivo en orden.
        """
        ok_items: List[ConsolidationFile] = []
        error_items: List[ConsolidationFile] = []
        total = len(self.paths)

        for index, path in enumerate(self.paths, start=1):
            if self._cancelled:
                break

            self.progress.emit(index, total, path.name)

            item = ConsolidationFile(path=path, name=path.name)

            try:
                item.text = extract_file(path, self.registry)
                ok_items.append(item)
            except Exception as exc:
                item.error = str(exc) or exc.__class__.__name__
                error_items.append(item)

            self.file_ready.emit(item)

        self.finished_all.emit(ok_items, error_items)
