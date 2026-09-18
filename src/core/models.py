"""
Modelos de datos de la aplicación.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional, Protocol


BlockKind = Literal["heading", "paragraph", "table", "list", "page", "page_break"]


class ConsolidationOptions(Protocol):
    separator_mode: str
    custom_separator: str


@dataclass(frozen=True)
class DocumentSource:
    path: Path
    size: int
    mtime: datetime
    sha256: str
    format: str
    encoding: Optional[str] = None

    @classmethod
    def from_path(cls, path: Path, encoding: Optional[str] = None) -> DocumentSource:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        stat = path.stat()
        return cls(
            path=path.resolve(),
            size=stat.st_size,
            mtime=datetime.fromtimestamp(stat.st_mtime, timezone.utc),
            sha256=digest.hexdigest(),
            format=path.suffix.lower(),
            encoding=encoding,
        )


@dataclass
class BlockAttributes:
    level: Optional[int] = None
    table_data: list[list[str]] = field(default_factory=list)
    page_number: Optional[int] = None
    bbox: Optional[tuple[float, float, float, float]] = None


@dataclass
class Block:
    kind: BlockKind
    text: str = ""
    attrs: BlockAttributes = field(default_factory=BlockAttributes)

    def to_plain_text(self) -> str:
        if self.kind == "table" and self.attrs.table_data:
            return "\n".join("\t".join(row) for row in self.attrs.table_data)
        return self.text


@dataclass
class DocumentMetadata:
    title: Optional[str] = None
    author: Optional[str] = None
    created: Optional[datetime] = None
    modified: Optional[datetime] = None
    page_count: Optional[int] = None


@dataclass(frozen=True)
class ExtractionWarning:
    code: str
    message: str
    page_number: Optional[int] = None


@dataclass
class Document:
    source: DocumentSource
    blocks: list[Block] = field(default_factory=list)
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)
    warnings: list[ExtractionWarning] = field(default_factory=list)
    transforms_applied: list[str] = field(default_factory=list)

    def to_plain_text(self) -> str:
        return "\n".join(block.to_plain_text() for block in self.blocks)


@dataclass
class ConsolidationFile:
    """
    Representa un archivo dentro de la sesión de consolidación.
    """

    path: Path
    name: str
    text: str = ""
    error: Optional[str] = None
    document: Optional[Document] = None
