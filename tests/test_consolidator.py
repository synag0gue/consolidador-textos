from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys

import pytest

from src.core.consolidator import build_output, extract_document
from src.core.models import Block, Document, DocumentSource, ConsolidationFile
from src.core.worker import extract_files
from src.extractors.base import TextExtractor
from src.extractors.registry import ExtractorRegistry

from src.core.consolidator import extract_file
from src.extractors.registry import create_default_registry


def test_extract_file_preserves_lf(tmp_path: Path) -> None:
    path = tmp_path / "sample.txt"
    path.write_bytes(b"Hello\nWorld")

    assert extract_file(path, create_default_registry()) == "Hello\nWorld"


@pytest.mark.parametrize("data", [b"", b"Hello\r\nWorld", "Olá".encode("utf-8"), b"caf\xe9"])
def test_legacy_adapter_preserves_text(tmp_path: Path, data: bytes) -> None:
    path = tmp_path / "sample.txt"
    path.write_bytes(data)
    registry = create_default_registry()
    extractor = registry.get_extractor(path)
    document = extract_document(path, registry)
    assert document.to_plain_text() == extractor.extract(path)
    assert document.source.size == len(data)
    assert document.source.path == path.resolve()


def test_invalid_inputs(tmp_path: Path) -> None:
    registry = create_default_registry()
    with pytest.raises(ValueError, match="existe"):
        extract_document(tmp_path / "missing.txt", registry)
    with pytest.raises(ValueError, match="válido"):
        extract_document(tmp_path, registry)
    path = tmp_path / "sample.unknown"
    path.touch()
    with pytest.raises(ValueError, match="soportado"):
        extract_document(path, registry)


def test_structured_override_is_used(tmp_path: Path) -> None:
    class StructuredExtractor(TextExtractor):
        extensions = (".custom",)

        def extract(self, path: Path) -> str:
            raise AssertionError("Legacy extraction must not be called")

        def extract_structured(self, path: Path) -> Document:
            return Document(DocumentSource.from_path(path), [Block("heading", "Structured")])

    path = tmp_path / "sample.custom"
    path.touch()
    registry = ExtractorRegistry()
    registry.register(StructuredExtractor())
    assert extract_file(path, registry) == "Structured"


@pytest.mark.parametrize("mode,custom,expected", [
    ("blank", "", "A\n\nB"),
    ("dashes", "", "A\n---\nB"),
    ("filename", "", "=== a.txt ===\nA\n\n=== b.txt ===\nB"),
    ("custom", r"\n{filename}\t", "A\nb.txt\tB"),
    ("unknown", "", "A\n\nB"),
])
def test_rendering_without_app_settings(mode: str, custom: str, expected: str) -> None:
    options = SimpleNamespace(separator_mode=mode, custom_separator=custom)
    files = [ConsolidationFile(Path("a.txt"), "a.txt", "A"), ConsolidationFile(Path("b.txt"), "b.txt", "B")]
    assert build_output(files, options) == expected
    assert build_output([], options) == ""


def test_batch_retains_documents_and_continues_after_errors(tmp_path: Path) -> None:
    path = tmp_path / "sample.txt"
    path.write_bytes(b"text")
    paths = [tmp_path / "missing.txt", path]
    progress = []
    items = list(extract_files(paths, create_default_registry(), progress=lambda *args: progress.append(args)))
    assert items[0].error is not None
    assert items[0].document is None
    assert items[1].error is None
    assert items[1].document.to_plain_text() == items[1].text == "text"
    assert progress == [(1, 2, "missing.txt"), (2, 2, "sample.txt")]


def test_batch_cancellation(tmp_path: Path) -> None:
    registry = create_default_registry()
    assert list(extract_files([tmp_path / "missing.txt"], registry, cancelled=lambda: True)) == []
    cancelled = False
    results = extract_files([tmp_path / "a.txt", tmp_path / "b.txt"], registry, cancelled=lambda: cancelled)
    assert next(results).name == "a.txt"
    cancelled = True
    assert list(results) == []


def test_core_imports_without_qt_or_app_settings() -> None:
    script = """
import importlib.abc
import sys
class BlockImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(('PySide6', 'src.ui', 'src.config')):
            raise ImportError(fullname)
sys.meta_path.insert(0, BlockImports())
from src.core.consolidator import build_output, extract_document
from src.core.worker import extract_files
from src.extractors.registry import create_default_registry
assert '.txt' in create_default_registry().supported_extensions()
"""
    result = subprocess.run([sys.executable, "-B", "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
