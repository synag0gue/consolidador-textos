"""
Modelos de datos de la aplicación.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ConsolidationFile:
    """
    Representa un archivo dentro de la sesión de consolidación.
    """

    path: Path
    name: str
    text: str = ""
    error: Optional[str] = None
