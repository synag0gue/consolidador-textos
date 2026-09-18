from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

from src.core.consolidator import extract_document
from src.core.models import ConsolidationFile
from src.extractors.registry import ExtractorRegistry


def extract_files(
    paths: Sequence[Path],
    registry: ExtractorRegistry,
    cancelled: Callable[[], bool] | None = None,
    progress: Callable[[int, int, str], None] | None = None,
) -> Iterator[ConsolidationFile]:
    total = len(paths)
    for index, path in enumerate(paths, start=1):
        if cancelled is not None and cancelled():
            break
        if progress is not None:
            progress(index, total, path.name)
        item = ConsolidationFile(path=path, name=path.name)
        try:
            item.document = extract_document(path, registry)
            item.text = item.document.to_plain_text()
        except Exception as exc:
            item.error = str(exc) or exc.__class__.__name__
        yield item
