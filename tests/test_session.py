from pathlib import Path

import pytest

from src.core.session import SessionJournal


def test_replay_add_remove_reorder_clear(tmp_path: Path) -> None:
    journal = SessionJournal(tmp_path / "session.jsonl")
    assert journal.load() == []
    journal.append_add(["a", "b", "c"])
    journal.append_add(["b", "d"])
    assert journal.load() == ["a", "b", "c", "d"]
    journal.append_remove(["b"])
    assert journal.load() == ["a", "c", "d"]
    journal.append_reorder(["d", "a", "c"])
    assert journal.load() == ["d", "a", "c"]
    journal.append_clear()
    assert journal.load() == []


def test_snapshot_replaces_history(tmp_path: Path) -> None:
    journal = SessionJournal(tmp_path / "session.jsonl")
    journal.append_add(["a", "b"])
    journal.snapshot(["b", "c"])
    assert journal.load() == ["b", "c"]
    assert journal.path.read_text(encoding="utf-8").count("\n") == 1


def test_corrupt_lines_are_skipped(tmp_path: Path) -> None:
    path = tmp_path / "session.jsonl"
    path.write_text(
        '{"op": "add", "paths": ["a"]}\n'
        "not json at all\n"
        '{"op": "add"}\n'
        '{"op": "add", "paths": "nope"}\n'
        '{"op": "add", "paths": ["b"]}\n'
        '{"op": "add", "paths": ["c"]',
        encoding="utf-8",
    )
    assert SessionJournal(path).load() == ["a", "b"]


def test_missing_journal_loads_empty(tmp_path: Path) -> None:
    assert SessionJournal(tmp_path / "absent.jsonl").load() == []


def test_restore_reprocesses_existing_and_flags_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from src.config import AppSettings
    from src.core.session import SessionJournal
    from src.ui import main_window as main_window_module
    from src.ui.main_window import MainWindow

    QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_window_module, "get_journal_path", lambda: tmp_path / "session.jsonl")

    present = tmp_path / "present.txt"
    present.write_bytes(b"hello")
    journal = SessionJournal(tmp_path / "session.jsonl")
    journal.append_add([str(present), str(tmp_path / "gone.txt")])

    captured: list = []
    monkeypatch.setattr(MainWindow, "_process_paths", lambda self, paths: captured.extend(paths))
    window = MainWindow(AppSettings())

    assert captured == [present]
    assert [item.name for item in window.errors] == ["gone.txt"]
    assert "1 ya no existen" in window.status_label.text()
    assert journal.load() == [str(present)]
    window.close()


def test_compaction_bounds_file_growth(tmp_path: Path) -> None:
    journal = SessionJournal(tmp_path / "session.jsonl", max_lines=5)
    for index in range(12):
        journal.append_add([f"file-{index}"])
    assert journal.path.read_text(encoding="utf-8").count("\n") <= 6
    assert journal.load() == [f"file-{index}" for index in range(12)]
