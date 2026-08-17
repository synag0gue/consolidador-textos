"""
Arranque de la aplicación.
"""

import sys

from PySide6.QtWidgets import QApplication

from src.config import AppSettings
from src.ui.main_window import MainWindow
from src.ui.theme import apply_theme


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Consolidador de Textos")
    app.setOrganizationName("OpenSourceMVP")

    settings = AppSettings.load()
    apply_theme(app, settings.dark_mode)

    window = MainWindow(settings)
    window.show()

    exit_code = app.exec()
    settings.save()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
