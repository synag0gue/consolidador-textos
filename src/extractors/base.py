"""
Clase base para extractores de texto.

Para agregar un nuevo formato:
1. Crear una clase que herede de TextExtractor.
2. Definir extensions.
3. Implementar extract().
4. Registrarla en registry.py.
"""

from abc import ABC, abstractmethod
from pathlib import Path


class TextExtractor(ABC):
    """
    Interfaz base para extractores de contenido texto.
    """

    extensions: tuple[str, ...] = ()

    @abstractmethod
    def extract(self, path: Path) -> str:
        """
        Extrae el texto plano desde un archivo.

        Debe lanzar una excepción si el archivo no puede procesarse.
        """
        raise NotImplementedError
