"""
Registro de extractores soportados.

Este módulo centraliza la arquitectura extensible:
para agregar un nuevo formato, se crea el extractor y se registra aquí.
"""

from pathlib import Path
from typing import Dict, Optional, Tuple

from src.extractors.base import TextExtractor
from src.extractors.docx import DocxExtractor
from src.extractors.pdf import PdfExtractor
from src.extractors.txt import PlainTextExtractor


class ExtractorRegistry:
    """
    Registro de extractores por extensión.
    """

    def __init__(self) -> None:
        self._by_extension: Dict[str, TextExtractor] = {}

    def register(self, extractor: TextExtractor) -> None:
        """
        Registra un extractor para todas sus extensiones.
        """
        for extension in extractor.extensions:
            self._by_extension[extension.lower()] = extractor

    def supported_extensions(self) -> Tuple[str, ...]:
        """
        Devuelve todas las extensiones soportadas.
        """
        return tuple(sorted(self._by_extension.keys()))

    def is_supported(self, path: Path) -> bool:
        """
        Indica si un archivo está soportado por su extensión.
        """
        return path.suffix.lower() in self._by_extension

    def get_extractor(self, path: Path) -> Optional[TextExtractor]:
        """
        Devuelve el extractor adecuado para un archivo.
        """
        return self._by_extension.get(path.suffix.lower())


def create_default_registry() -> ExtractorRegistry:
    """
    Crea el registro con los extractores incluidos por defecto.
    """
    registry = ExtractorRegistry()
    registry.register(PlainTextExtractor())
    registry.register(DocxExtractor())
    registry.register(PdfExtractor())
    return registry
