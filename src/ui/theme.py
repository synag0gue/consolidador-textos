"""
Temas claro y oscuro usando Fusion + QPalette.
"""

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def apply_theme(app: QApplication, dark: bool) -> None:
    """
    Aplica el tema claro u oscuro a toda la aplicación.
    """
    app.setStyle("Fusion")

    palette = QPalette()
    role = QPalette.ColorRole

    if dark:
        window = QColor(32, 32, 34)
        base = QColor(24, 24, 26)
        text = QColor(225, 225, 228)
        button = QColor(45, 45, 48)
        alternate_base = QColor(38, 38, 41)
        highlight = QColor(0, 120, 215)
        highlighted_text = QColor(255, 255, 255)
        link = QColor(86, 156, 255)
        placeholder = QColor(140, 140, 145)

        palette.setColor(role.Window, window)
        palette.setColor(role.WindowText, text)
        palette.setColor(role.Base, base)
        palette.setColor(role.AlternateBase, alternate_base)
        palette.setColor(role.Text, text)
        palette.setColor(role.Button, button)
        palette.setColor(role.ButtonText, text)
        palette.setColor(role.ToolTipBase, button)
        palette.setColor(role.ToolTipText, text)
        palette.setColor(role.Highlight, highlight)
        palette.setColor(role.HighlightedText, highlighted_text)
        palette.setColor(role.Link, link)
        palette.setColor(role.PlaceholderText, placeholder)

    else:
        window = QColor(243, 243, 243)
        base = QColor(255, 255, 255)
        text = QColor(25, 25, 25)
        button = QColor(228, 228, 230)
        alternate_base = QColor(235, 235, 237)
        highlight = QColor(0, 120, 215)
        highlighted_text = QColor(255, 255, 255)
        link = QColor(0, 90, 180)
        placeholder = QColor(120, 120, 120)

        palette.setColor(role.Window, window)
        palette.setColor(role.WindowText, text)
        palette.setColor(role.Base, base)
        palette.setColor(role.AlternateBase, alternate_base)
        palette.setColor(role.Text, text)
        palette.setColor(role.Button, button)
        palette.setColor(role.ButtonText, text)
        palette.setColor(role.ToolTipBase, button)
        palette.setColor(role.ToolTipText, text)
        palette.setColor(role.Highlight, highlight)
        palette.setColor(role.HighlightedText, highlighted_text)
        palette.setColor(role.Link, link)
        palette.setColor(role.PlaceholderText, placeholder)

    app.setPalette(palette)

    tooltip_background = palette.color(role.ToolTipBase).name()
    tooltip_text = palette.color(role.ToolTipText).name()
    border_color = "#555555" if dark else "#bbbbbb"

    app.setStyleSheet(
        "QToolTip {"
        f" background-color: {tooltip_background};"
        f" color: {tooltip_text};"
        f" border: 1px solid {border_color};"
        " padding: 4px;"
        "}"
    )
