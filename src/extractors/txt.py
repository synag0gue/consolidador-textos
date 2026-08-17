"""
Extractor de archivos de texto plano.
"""

import codecs
from pathlib import Path

from src.extractors.base import TextExtractor


class PlainTextExtractor(TextExtractor):
    """
    Extractor para archivos de texto plano.

    Soporta extensiones comunes de texto.
    """

    extensions = (".txt", ".text", ".md", ".log", ".csv")

    _encodings = (
        "utf-8-sig",
        "utf-8",
        "cp1252",
        "latin-1",
    )

    def extract(self, path: Path) -> str:
        """
        Lee el archivo de texto intentando varias codificaciones.
        """
        data = path.read_bytes()

        # Manejo básico de BOM comunes.
        if data.startswith(codecs.BOM_UTF8):
            return data.decode("utf-8-sig")

        if data.startswith(codecs.BOM_UTF16_LE) or data.startswith(codecs.BOM_UTF16_BE):
            return data.decode("utf-16")

        # Si hay bytes nulos al inicio, probablemente sea binario.
        if b"\0" in data[:8192]:
            raise ValueError("El archivo parece binario y no texto plano.")

        last_error: Exception | None = None

        for encoding in self._encodings:
            try:
                return data.decode(encoding)
            except UnicodeDecodeError as exc:
                last_error = exc

        # latin-1 normalmente no falla, pero se deja por robustez.
        try:
            return data.decode("latin-1")
        except Exception as exc:
            raise ValueError(
                f"No se pudo decodificar el archivo de texto: {exc}"
            ) from last_error
