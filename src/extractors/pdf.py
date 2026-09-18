"""
Extractor de texto para archivos PDF.
"""

from pathlib import Path

from src.core.models import (
    Block,
    BlockAttributes,
    Document,
    DocumentMetadata,
    DocumentSource,
    ExtractionWarning,
)
from src.extractors.base import TextExtractor


class PdfExtractor(TextExtractor):
    """
    Extractor para archivos .pdf usando pypdf.
    """

    extensions = (".pdf",)

    def __init__(self, ocr_provider=None) -> None:
        self.ocr_provider = ocr_provider

    def extract(self, path: Path) -> str:
        """
        Extrae texto de todas las páginas del PDF.
        """
        return self.extract_structured(path).to_plain_text()

    def extract_structured(self, path: Path) -> Document:
        """
        Extrae un bloque `page` por página, preservando el número de página,
        los metadatos disponibles y avisos para páginas sin capa de texto.
        """
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError(
                "Falta la dependencia pypdf para leer archivos PDF."
            ) from exc

        if self.ocr_provider is not None and not self.ocr_provider.is_available():
            raise ValueError(
                f"OCR provider '{self.ocr_provider.name}' is not available"
            )

        try:
            reader = PdfReader(str(path))

            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception as exc:
                    raise ValueError(
                        "El PDF está cifrado y no se puede leer."
                    ) from exc

            blocks: list[Block] = []
            warnings: list[ExtractionWarning] = []
            for page_number, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                if not text.strip() and self.ocr_provider is not None:
                    text = self._ocr_page(page)
                    if text.strip():
                        blocks.append(
                            Block(
                                kind="page",
                                text=text,
                                attrs=BlockAttributes(page_number=page_number),
                            )
                        )
                        warnings.append(
                            ExtractionWarning(
                                code="ocr_text",
                                message=(
                                    f"La página {page_number} se recuperó por OCR "
                                    "y puede contener errores."
                                ),
                                page_number=page_number,
                            )
                        )
                        continue
                blocks.append(
                    Block(
                        kind="page",
                        text=text,
                        attrs=BlockAttributes(page_number=page_number),
                    )
                )
                if not text.strip():
                    warnings.append(
                        ExtractionWarning(
                            code="empty_page",
                            message=(
                                f"La página {page_number} no contiene texto "
                                "extraíble (posible página escaneada)."
                            ),
                            page_number=page_number,
                        )
                    )

            info = reader.metadata
            return Document(
                source=DocumentSource.from_path(path),
                blocks=blocks,
                metadata=DocumentMetadata(
                    title=getattr(info, "title", None) or None,
                    author=getattr(info, "author", None) or None,
                    page_count=len(reader.pages),
                ),
                warnings=warnings,
            )

        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"PDF inválido o corrupto: {exc}") from exc

    def _ocr_page(self, page) -> str:
        assert self.ocr_provider is not None
        try:
            images = list(page.images)
        except Exception:
            return ""
        parts = []
        for image in images:
            text = self.ocr_provider.extract_text(image.data)
            if text.strip():
                parts.append(text)
        return "\n".join(parts)
