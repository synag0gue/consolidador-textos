import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from src.config import AppSettings  # noqa: E402
from src.core.models import ConsolidationFile  # noqa: E402
from src.ui import main_window as main_window_module  # noqa: E402
from src.ui.dedupe_dialog import DuplicateReviewDialog  # noqa: E402
from src.ui.main_window import MainWindow  # noqa: E402
from src.ui.strings import (  # noqa: E402
    SUPPORTED_LANGUAGES,
    STRINGS,
    get_language,
    set_language,
    tr,
)


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


def test_table_is_complete_both_ways() -> None:
    assert set(SUPPORTED_LANGUAGES) == {"es", "en"}
    assert set(STRINGS["es"]) == set(STRINGS["en"])
    for key in STRINGS["es"]:
        assert STRINGS["es"][key] and STRINGS["en"][key]


def test_tr_fallback_and_validation() -> None:
    assert tr("app.title") == "Consolidador de Textos"
    assert tr("missing.key") == "missing.key"
    assert set_language("en") == "en"
    assert tr("app.title") == "Text Consolidator"
    assert tr("preview.label", count=2, chars="1,000") == "Preview (2 files, 1,000 characters)"
    assert set_language("xx") == "es"
    assert get_language() == "es"


def test_language_setting_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import src.config as config_module

    path = tmp_path / "settings.json"
    monkeypatch.setattr(config_module, "get_settings_path", lambda: path)
    settings = AppSettings(language="en")
    settings.save()
    assert json.loads(path.read_text(encoding="utf-8"))["language"] == "en"
    assert AppSettings.load().language == "en"
    path.write_text('{"language": "xx"}', encoding="utf-8")
    assert AppSettings.load().language == "es"


def test_gui_switches_language_live(window: MainWindow) -> None:
    assert window.windowTitle() == "Consolidador de Textos"
    assert window.btn_add_files.text() == "Agregar archivos..."
    assert window.file_menu.title() == "&Archivo"
    assert window.radio_blank.text() == "Línea en blanco simple"
    assert "Vista previa" in window.preview_label.text()

    window._on_language_changed("en")

    assert window.settings.language == "en"
    assert window.windowTitle() == "Text Consolidator"
    assert window.btn_add_files.text() == "Add files..."
    assert window.file_menu.title() == "&File"
    assert window.tools_menu.title() == "&Tools"
    assert window.view_menu.title() == "&View"
    assert window.help_menu.title() == "&Help"
    assert window.radio_blank.text() == "Single blank line"
    assert window.action_dark.text() == "Dark mode"
    assert window.recent_combo.itemText(0) == "Recent folders..."
    assert "Preview" in window.preview_label.text()
    assert window.action_lang_en.isChecked()
    assert not window.action_lang_es.isChecked()

    window.files.append(ConsolidationFile(Path("a.txt"), "a.txt", "x"))
    window.refresh_preview()
    assert window.preview_label.text() == "Preview (1 files, 1 characters)"

    window._on_language_changed("es")
    assert window.windowTitle() == "Consolidador de Textos"
    assert window.btn_add_files.text() == "Agregar archivos..."


def test_fresh_launch_honors_saved_language(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main_window_module, "get_journal_path", lambda: tmp_path / "session.jsonl")
    window = MainWindow(AppSettings(language="en"))
    assert window.windowTitle() == "Text Consolidator"
    assert window.btn_add_files.text() == "Add files..."
    assert window.action_lang_en.isChecked()
    window.close()


def test_dialog_follows_language(qapp, tmp_path: Path) -> None:
    first = tmp_path / "a.txt"
    second = tmp_path / "b.txt"
    files = [ConsolidationFile(first, "a.txt", "same"), ConsolidationFile(second, "b.txt", "same")]
    assert DuplicateReviewDialog(files).windowTitle() == "Revisar duplicados"
    set_language("en")
    assert DuplicateReviewDialog(files).windowTitle() == "Review duplicates"
