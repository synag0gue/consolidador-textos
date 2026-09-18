import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from src.config import AppSettings  # noqa: E402
from src.core.models import ConsolidationFile  # noqa: E402
from src.ui.dedupe_dialog import (  # noqa: E402
    KEEP_BOTH,
    KEEP_FIRST,
    KEEP_SECOND,
    DuplicateReviewDialog,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _item(path: Path, text: str) -> ConsolidationFile:
    return ConsolidationFile(path, path.name, text)


def test_exact_group_default_removes_duplicates(qapp, tmp_path: Path) -> None:
    first = tmp_path / "a.txt"
    second = tmp_path / "b.txt"
    dialog = DuplicateReviewDialog([_item(first, "same"), _item(second, "same")])
    assert dialog.collect_removals() == [str(second)]


def test_near_pair_decisions_and_conflict_skip(qapp, tmp_path: Path) -> None:
    base = "the quick brown fox jumps over the lazy dog"
    files = [
        _item(tmp_path / "a.txt", base),
        _item(tmp_path / "b.txt", base + " today"),
        _item(tmp_path / "c.txt", base + " today!"),
    ]
    dialog = DuplicateReviewDialog(files)
    assert len(dialog._pair_combos) == 3
    for _, _, combo in dialog._pair_combos:
        combo.setCurrentIndex(combo.findData(KEEP_FIRST))
    removals = dialog.collect_removals()
    assert removals == [str(tmp_path / "c.txt"), str(tmp_path / "b.txt")]
    for _, _, combo in dialog._pair_combos:
        combo.setCurrentIndex(combo.findData(KEEP_BOTH))
    assert dialog.collect_removals() == []
    ab_pair = next(combo for first, _, combo in dialog._pair_combos if first == 0)
    ab_pair.setCurrentIndex(ab_pair.findData(KEEP_SECOND))
    assert dialog.collect_removals() == [str(tmp_path / "a.txt")]


def test_main_window_review_wiring(qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from src.ui import main_window as main_window_module
    from src.ui.main_window import MainWindow

    monkeypatch.setattr(main_window_module, "get_journal_path", lambda: tmp_path / "session.jsonl")
    window = MainWindow(AppSettings())
    window.review_duplicates()
    assert "al menos dos archivos" in window.status_label.text()

    first = tmp_path / "a.txt"
    first.write_bytes(b"same")
    second = tmp_path / "b.txt"
    second.write_bytes(b"same")
    for path in (first, second):
        window.files.append(ConsolidationFile(path, path.name, "same"))
        window._add_list_item(window.files[-1])

    class StubDialog:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def collect_removals(self) -> list:
            return [str(second)]

    monkeypatch.setattr(main_window_module, "DuplicateReviewDialog", StubDialog)
    window.review_duplicates()
    assert [item.name for item in window.files] == ["a.txt"]
    assert window.file_list.count() == 1
    assert "1 archivos duplicados" in window.status_label.text()
    window.close()
