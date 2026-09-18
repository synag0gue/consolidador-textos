"""
Extractor de texto para archivos DOCX.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from src.core.models import (
    Block,
    BlockAttributes,
    Document,
    DocumentMetadata,
    DocumentSource,
)
from src.extractors.base import TextExtractor

if TYPE_CHECKING:
    from docx.text.paragraph import Paragraph


def _heading_level(paragraph: "Paragraph") -> int | None:
    from docx.oxml.ns import qn

    elements = [paragraph._p]
    style = paragraph.style
    seen: set[str] = set()
    while style is not None and style.style_id not in seen:
        seen.add(style.style_id)
        elements.append(style.element)
        style = style.base_style
    for element in elements:
        values = element.xpath("./w:pPr/w:outlineLvl")
        if values:
            value = values[0].get(qn("w:val"))
            if value is not None:
                level = int(value)
                return level + 1 if 0 <= level <= 8 else None
    return None


class DocxExtractor(TextExtractor):
    """
    Extractor para archivos .docx usando python-docx.
    """

    extensions = (".docx",)

    def extract(self, path: Path) -> str:
        return self.extract_structured(path).to_plain_text()

    def extract_structured(self, path: Path) -> Document:
        try:
            from docx import Document as WordDocument
            from docx.table import Table
            from docx.text.paragraph import Paragraph
        except ImportError as exc:
            raise ValueError(
                "Falta la dependencia python-docx para leer archivos DOCX."
            ) from exc

        try:
            word = WordDocument(str(path))
            blocks: list[Block] = []
            for item in word.iter_inner_content():
                if isinstance(item, Paragraph):
                    level = _heading_level(item)
                    blocks.append(Block(
                        kind="heading" if level is not None else "paragraph",
                        text=item.text,
                        attrs=BlockAttributes(level=level),
                    ))
                elif isinstance(item, Table):
                    blocks.append(Block(
                        kind="table",
                        attrs=BlockAttributes(table_data=[
                            [cell.text for cell in row.cells] for row in item.rows
                        ]),
                    ))
            properties = word.core_properties
            return Document(
                source=DocumentSource.from_path(path),
                blocks=blocks,
                metadata=DocumentMetadata(
                    title=properties.title or None,
                    author=properties.author or None,
                    created=properties.created,
                    modified=properties.modified,
                ),
            )
        except Exception as exc:
            raise ValueError(f"DOCX inválido o corrupto: {exc}") from exc
