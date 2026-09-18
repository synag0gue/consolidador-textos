import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QPalette  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from src.config import AppSettings  # noqa: E402
from src.ui import main_window as main_window_module  # noqa: E402
from src.ui.main_window import MainWindow  # noqa: E402
from src.ui.strings import set_language, tr  # noqa: E402
from src.ui.theme import apply_theme  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _restore_language():
    yield
    set_language("es")


@pytest.fixture
def window(qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> MainWindow:
    monkeypatch.setattr(main_window_module, "get_journal_path", lambda: tmp_path / "session.jsonl")
    view = MainWindow(AppSettings())
    yield view
    view.close()


def _luminance(color) -> float:
    def channel(value: int) -> float:
        value /= 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue, _ = color.getRgb()
    return 0.2126 * channel(red) + 0.7152 * channel(green) + 0.0722 * channel(blue)


def _ratio(fore, back) -> float:
    lighter, darker = sorted((_luminance(fore), _luminance(back)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


@pytest.mark.parametrize("dark", [False, True])
def test_text_contrast_meets_wcag_aa(qapp, dark: bool) -> None:
    apply_theme(qapp, dark)
    palette = qapp.palette()
    role = QPalette.ColorRole
    pairs = [
        (role.WindowText, role.Window),
        (role.Text, role.Base),
        (role.ButtonText, role.Button),
        (role.HighlightedText, role.Highlight),
        (role.ToolTipText, role.ToolTipBase),
        (role.PlaceholderText, role.Base),
        (role.Link, role.Base),
    ]
    for fg_role, bg_role in pairs:
        assert _ratio(palette.color(fg_role), palette.color(bg_role)) >= 4.5


def test_menu_actions_reachable_by_keyboard(window: MainWindow) -> None:
    for menu_action in window.menuBar().actions():
        menu = menu_action.menu()
        assert "&" in menu_action.text()
        for action in menu.actions():
            if action.isSeparator() or action.menu() is not None:
                continue
            if action.text() in (tr("act.about"), tr("act.dark")):
                continue
            assert action.shortcut().toString(), action.text()


def test_logical_tab_order(window: MainWindow) -> None:
    expected = [
        window.file_list, window.btn_add_files, window.btn_add_folder,
        window.btn_remove, window.btn_clear, window.btn_up, window.btn_down,
        window.recursive_check, window.recent_combo, window.radio_blank,
        window.radio_dashes, window.radio_filename, window.radio_custom,
        window.custom_edit, window.output_combo, window.preview,
    ]
    chain, seen, current = [], set(), expected[0]
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        current = current.nextInFocusChain()
    positions = [chain.index(widget) for widget in expected]
    assert positions == sorted(positions)


def test_screen_reader_names_and_buddies(window: MainWindow) -> None:
    assert window.btn_up.accessibleName() == tr("name.up")
    assert window.btn_down.accessibleName() == tr("name.down")
    assert window.btn_up.accessibleDescription() == tr("tip.up")
    assert window.progress_bar.accessibleDescription() == tr("a11y.progress")
    assert window.files_label.buddy() is window.file_list
    assert window.output_label.buddy() is window.output_combo
    assert window.preview_label.buddy() is window.preview
    window._on_language_changed("en")
    assert window.btn_up.accessibleName() == "Move up"
    assert window.progress_bar.accessibleDescription() == "Ongoing extraction progress"
