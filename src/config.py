"""
Configuración persistente de la aplicación.

Guarda:
- tema claro/oscuro
- separador seleccionado
- separador personalizado
- formato de salida
- carpetas recientes
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

APP_DIR_NAME = "ConsolidadorTextos"


def get_settings_path() -> Path:
    """
    Obtiene la ruta del archivo de configuración.

    En Windows usa:
        %APPDATA%/ConsolidadorTextos/settings.json

    En otros sistemas usa:
        ~/.config/ConsolidadorTextos/settings.json
    """
    appdata = os.getenv("APPDATA")
    if appdata:
        base = Path(appdata)
    else:
        base = Path.home() / ".config"

    folder = base / APP_DIR_NAME
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "settings.json"


@dataclass
class AppSettings:
    dark_mode: bool = False
    separator_mode: str = "blank"
    custom_separator: str = r"\n---\n"
    output_format: str = ".txt"
    recent_folders: List[str] = field(default_factory=list)
    max_recent_folders: int = 10

    @classmethod
    def load(cls) -> "AppSettings":
        """
        Carga la configuración desde disco.

        Si el archivo no existe o está corrupto, devuelve valores por defecto.
        """
        path = get_settings_path()

        try:
            data = json.loads(path.read_text(encoding="utf-8"))

            if not isinstance(data, dict):
                return cls()

            if data.get("separator_mode") not in {
                "blank",
                "dashes",
                "filename",
                "custom",
            }:
                data["separator_mode"] = "blank"

            if data.get("output_format") not in {".txt", ".docx"}:
                data["output_format"] = ".txt"

            if not isinstance(data.get("recent_folders"), list):
                data["recent_folders"] = []

            if not isinstance(data.get("custom_separator"), str):
                data["custom_separator"] = r"\n---\n"

            if not isinstance(data.get("dark_mode"), bool):
                data["dark_mode"] = False

            if not isinstance(data.get("max_recent_folders"), int):
                data["max_recent_folders"] = 10

            valid_fields = cls.__dataclass_fields__.keys()
            clean_data = {
                key: value
                for key, value in data.items()
                if key in valid_fields
            }

            return cls(**clean_data)

        except Exception:
            return cls()

    def save(self) -> None:
        """
        Guarda la configuración actual en disco.
        """
        path = get_settings_path()
        path.write_text(
            json.dumps(self.__dict__, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add_recent_folder(self, folder: str) -> None:
        """
        Agrega una carpeta al historial de carpetas recientes.
        """
        try:
            resolved = Path(folder).resolve(strict=False)
        except OSError:
            return

        if not resolved.is_dir():
            return

        folder_str = str(resolved)

        if folder_str in self.recent_folders:
            self.recent_folders.remove(folder_str)

        self.recent_folders.insert(0, folder_str)
        self.recent_folders = self.recent_folders[: self.max_recent_folders]
        self.save()
