import hashlib
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.core.models import (
    Block,
    BlockAttributes,
    ConsolidationFile,
    Document,
    DocumentMetadata,
    DocumentSource,
    ExtractionWarning,
)


@pytest.fixture
def source(tmp_path: Path) -> DocumentSource:
    path = tmp_path / "source.TXT"
    path.write_bytes(b"sample")
    return DocumentSource.from_path(path, encoding="utf-8")


def test_source_fingerprint(source: DocumentSource) -> None:
    assert source.path.is_absolute()
    assert source.size == 6
    assert source.sha256 == hashlib.sha256(b"sample").hexdigest()
    assert source.format == ".txt"
    assert source.encoding == "utf-8"
    assert source.mtime.tzinfo == timezone.utc
    with pytest.raises(FrozenInstanceError):
        source.size = 0


def test_missing_source(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        DocumentSource.from_path(tmp_path / "missing.txt")


def test_chunked_hash(tmp_path: Path) -> None:
    path = tmp_path / "large.txt"
    data = b"x" * (1024 * 1024 + 17)
    path.write_bytes(data)
    assert DocumentSource.from_path(path).sha256 == hashlib.sha256(data).hexdigest()


def test_ordered_rendering(source: DocumentSource) -> None:
    document = Document(source, blocks=[
        Block("heading", "Title", BlockAttributes(level=1)),
        Block("paragraph", "Text"),
        Block("table", attrs=BlockAttributes(table_data=[["A", "B"], ["1", "2"]])),
        Block("page_break"),
        Block("list", "Last"),
    ])
    assert document.to_plain_text() == "Title\nText\nA\tB\n1\t2\n\nLast"
    assert Document(source).to_plain_text() == ""


def test_mutable_defaults_are_independent(source: DocumentSource) -> None:
    first, second = Document(source), Document(source)
    first.blocks.append(Block("paragraph", "one"))
    first.warnings.append(ExtractionWarning("empty_page", "No text", 2))
    first.metadata.title = "First"
    assert second.blocks == []
    assert second.warnings == []
    assert second.metadata.title is None
    left, right = Block("table"), Block("table")
    left.attrs.table_data.append(["cell"])
    assert right.attrs.table_data == []


def test_metadata_and_warning_retention(source: DocumentSource) -> None:
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    document = Document(
        source,
        blocks=[Block("page", "", BlockAttributes(page_number=2, bbox=(0, 0, 10, 10)))],
        metadata=DocumentMetadata("Title", "Author", created, created, 2),
        warnings=[ExtractionWarning("empty_page", "No extractable text", 2)],
    )
    assert document.metadata.created == created
    assert document.blocks[0].attrs.page_number == 2
    assert document.warnings[0].page_number == 2
    assert document.to_plain_text() == ""


def test_legacy_session_constructor(source: DocumentSource) -> None:
    item = ConsolidationFile(source.path, "source.TXT", "original", None)
    assert item.text == "original"
    assert item.document is None
