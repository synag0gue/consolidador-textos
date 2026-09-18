import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from src.config import AppSettings  # noqa: E402
from src.core.consolidator import build_output as real_build_output  # noqa: E402
from src.core.models import ConsolidationFile  # noqa: E402
from src.ui import main_window as main_window_module  # noqa: E402
from src.ui.main_window import MainWindow  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> MainWindow:
    monkeypatch.setattr(main_window_module, "get_journal_path", lambda: tmp_path / "session.jsonl")
    view = MainWindow(AppSettings())
    yield view
    view.close()


def _feed(window: MainWindow, *texts: str) -> list:
    items = []
    for index, text in enumerate(texts):
        item = ConsolidationFile(Path(f"f{index}.txt"), f"f{index}.txt", text)
        window._on_file_ready(item)
        items.append(item)
    return items


@pytest.mark.parametrize("mode,custom", [
    ("blank", ""),
    ("dashes", ""),
    ("filename", ""),
    ("custom", r"\n[{filename}] "),
])
def test_incremental_matches_full_render(window: MainWindow, mode: str, custom: str) -> None:
    window.settings.custom_separator = custom
    window._on_separator_mode_changed(mode, True)
    items = _feed(window, "alpha", "", "gamma\nwith newline", "último ó")
    assert window.preview.toPlainText() == real_build_output(items, window.settings)
    assert f"({len(items)} archivos," in window.preview_label.text()


def test_arrivals_skip_full_rebuild(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    original = main_window_module.build_output

    def counting(files, settings):
        calls.append(len(files))
        return original(files, settings)

    monkeypatch.setattr(main_window_module, "build_output", counting)
    _feed(window, "one", "two", "three")
    assert calls == []
    assert window.preview.toPlainText() == real_build_output(window.files, window.settings)


def test_settings_change_rebuilds_with_new_semantics(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []
    original = main_window_module.build_output

    def counting(files, settings):
        calls.append(len(files))
        return original(files, settings)

    _feed(window, "one", "two")
    monkeypatch.setattr(main_window_module, "build_output", counting)
    window._on_separator_mode_changed("dashes", True)
    assert calls == [2]
    _feed(window, "three")
    assert window.preview.toPlainText() == real_build_output(window.files, window.settings)


def test_remove_rebuilds(window: MainWindow) -> None:
    _feed(window, "one", "two", "three")
    window.file_list.setCurrentRow(1)
    window.remove_selected()
    assert window.preview.toPlainText() == real_build_output(window.files, window.settings)
    assert [item.name for item in window.files] == ["f0.txt", "f2.txt"]


def test_error_items_leave_preview_untouched(window: MainWindow) -> None:
    _feed(window, "one")
    before = window.preview.toPlainText()
    window._on_file_ready(ConsolidationFile(Path("bad.txt"), "bad.txt", error="boom"))
    assert window.preview.toPlainText() == before
    assert len(window.errors) == 1
