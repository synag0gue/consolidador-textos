"""
Lógica de extracción y consolidación de texto.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from src.config import AppSettings
from src.core.models import ConsolidationFile
from src.extractors.registry import ExtractorRegistry


def extract_file(path: Path, registry: ExtractorRegistry) -> str:
    """
    Extrae el texto de un archivo usando el extractor adecuado.
    """
    if not path.exists():
        raise ValueError("El archivo no existe.")

    if not path.is_file():
        raise ValueError("La ruta no es un archivo válido.")

    extractor = registry.get_extractor(path)

    if extractor is None:
        suffix = path.suffix or "sin extensión"
        raise ValueError(f"Formato no soportado: {suffix}")

    return extractor.extract(path)


def render_separator(
    settings: AppSettings,
    next_file: Optional[ConsolidationFile] = None,
) -> str:
    """
    Devuelve el separador que se inserta entre archivos.
    """
    mode = settings.separator_mode

    if mode == "blank":
        return "\n\n"

    if mode == "dashes":
        return "\n---\n"

    if mode == "filename":
        return "\n\n"

    if mode == "custom":
        separator = settings.custom_separator

        # Soporte para escapes simples.
        separator = separator.replace(r"\n", "\n")
        separator = separator.replace(r"\t", "\t")

        if next_file is not None:
            separator = separator.replace("{filename}", next_file.name)

        return separator

    return "\n\n"


def build_output(
    files: List[ConsolidationFile],
    settings: AppSettings,
) -> str:
    """
    Construye el texto consolidado final.

    Este texto es exactamente el que se muestra en la vista previa
    y el que se guarda en el archivo de salida.
    """
    if not files:
        return ""

    # Modo encabezado: cada archivo lleva su nombre antes del contenido.
    if settings.separator_mode == "filename":
        segments = []

        for file_item in files:
            segments.append(f"=== {file_item.name} ===\n{file_item.text}")

        return "\n\n".join(segments)

    # Otros modos: concatena contenido + separador entre archivos.
    output = files[0].text

    for next_file in files[1:]:
        output += render_separator(settings, next_file)
        output += next_file.text

    return output
