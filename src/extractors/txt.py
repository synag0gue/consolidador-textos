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

    _chunk_size = 1024 * 1024
    _head_size = 12288

    def extract(self, path: Path) -> str:
        """
        Lee el archivo de texto intentando varias codificaciones.

        Decodifica por bloques para no retener el contenido binario
        completo junto a la cadena decodificada.
        """
        with open(path, "rb") as stream:
            head = stream.read(self._head_size)

        # Manejo básico de BOM comunes.
        if head.startswith(codecs.BOM_UTF8):
            forced: str | None = "utf-8-sig"
        elif head.startswith(codecs.BOM_UTF16_LE) or head.startswith(codecs.BOM_UTF16_BE):
            forced = "utf-16"
        else:
            forced = None
            # Si hay bytes nulos al inicio, probablemente sea binario.
            if b"\0" in head[:8192]:
                raise ValueError("El archivo parece binario y no texto plano.")

        last_error: Exception | None = None

        for encoding in (forced,) if forced else self._encodings:
            try:
                return stream_decode(path, encoding, self._chunk_size)
            except UnicodeDecodeError as exc:
                last_error = exc

        # latin-1 normalmente no falla, pero se deja por robustez.
        try:
            return stream_decode(path, "latin-1", self._chunk_size)
        except Exception as exc:
            raise ValueError(
                f"No se pudo decodificar el archivo de texto: {exc}"
            ) from last_error


def stream_decode(path: Path, encoding: str, chunk_size: int = 1024 * 1024) -> str:
    """
    Decodifica un archivo por bloques con el mismo resultado que
    ``path.read_bytes().decode(encoding)``.
    """
    decoder = codecs.getincrementaldecoder(encoding)()
    parts: list[str] = []

    with open(path, "rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            parts.append(decoder.decode(chunk))

    parts.append(decoder.decode(b"", final=True))
    return "".join(parts)
