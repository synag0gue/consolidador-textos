"""
Extractor de texto para archivos PDF.
"""

from pathlib import Path

from src.extractors.base import TextExtractor


class PdfExtractor(TextExtractor):
    """
    Extractor para archivos .pdf usando pypdf.
    """

    extensions = (".pdf",)

    def extract(self, path: Path) -> str:
        """
        Extrae texto de todas las páginas del PDF.
        """
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError(
                "Falta la dependencia pypdf para leer archivos PDF."
            ) from exc

        try:
            reader = PdfReader(str(path))

            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception as exc:
                    raise ValueError(
                        "El PDF está cifrado y no se puede leer."
                    ) from exc

            pages = []
            for page in reader.pages:
                text = page.extract_text() or ""
                pages.append(text)

            return "\n".join(pages)

        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"PDF inválido o corrupto: {exc}") from exc
