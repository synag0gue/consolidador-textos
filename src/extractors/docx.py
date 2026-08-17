"""
Extractor de texto para archivos DOCX.
"""

from pathlib import Path

from src.extractors.base import TextExtractor


class DocxExtractor(TextExtractor):
    """
    Extractor para archivos .docx usando python-docx.
    """

    extensions = (".docx",)

    def extract(self, path: Path) -> str:
        """
        Extrae el texto de los párrafos de un DOCX.

        No conserva estilos, colores ni tablas.
        """
        try:
            from docx import Document
        except ImportError as exc:
            raise ValueError(
                "Falta la dependencia python-docx para leer archivos DOCX."
            ) from exc

        try:
            document = Document(str(path))
            paragraphs = [paragraph.text for paragraph in document.paragraphs]
            return "\n".join(paragraphs)
        except Exception as exc:
            raise ValueError(f"DOCX inválido o corrupto: {exc}") from exc
