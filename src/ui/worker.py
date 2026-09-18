from __future__ import annotations

from pathlib import Path
from threading import Event
from typing import Sequence

from PySide6.QtCore import QObject, QThread, Signal

from src.core.models import ConsolidationFile
from src.core.worker import extract_files
from src.extractors.registry import ExtractorRegistry


class ExtractionWorker(QThread):
    progress = Signal(int, int, str)
    file_ready = Signal(object)
    finished_all = Signal(object, object)

    def __init__(
        self,
        paths: Sequence[Path],
        registry: ExtractorRegistry,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.paths = list(paths)
        self.registry = registry
        self._cancelled = Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def run(self) -> None:
        ok_items: list[ConsolidationFile] = []
        error_items: list[ConsolidationFile] = []
        for item in extract_files(
            self.paths,
            self.registry,
            cancelled=self._cancelled.is_set,
            progress=self.progress.emit,
        ):
            if item.error is None:
                ok_items.append(item)
            else:
                error_items.append(item)
            self.file_ready.emit(item)
        self.finished_all.emit(ok_items, error_items)
