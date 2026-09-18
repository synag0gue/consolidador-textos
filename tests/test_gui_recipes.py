import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from src.config import AppSettings  # noqa: E402
from src.core.models import ConsolidationFile  # noqa: E402
from src.core.recipes import (  # noqa: E402
    InputSpec,
    JobOptions,
    OutputSpec,
    Recipe,
    dump_recipe,
    load_recipe,
)
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


class _Dialogs:
    save_path: str = ""
    open_path: str = ""
    messages: list = []

    @staticmethod
    def getSaveFileName(*args, **kwargs):
        return (_Dialogs.save_path, "")

    @staticmethod
    def getOpenFileName(*args, **kwargs):
        return (_Dialogs.open_path, "")

    @staticmethod
    def information(*args, **kwargs):
        _Dialogs.messages.append(("information", args[1] if len(args) > 1 else ""))

    @staticmethod
    def warning(*args, **kwargs):
        _Dialogs.messages.append(("warning", args[-1] if args else ""))

    @staticmethod
    def critical(*args, **kwargs):
        _Dialogs.messages.append(("critical", args[-1] if args else ""))


@pytest.fixture
def dialogs(monkeypatch: pytest.MonkeyPatch):
    _Dialogs.save_path = ""
    _Dialogs.open_path = ""
    _Dialogs.messages = []
    monkeypatch.setattr(main_window_module, "QFileDialog", _Dialogs)
    monkeypatch.setattr(main_window_module, "QMessageBox", _Dialogs)
    return _Dialogs


def test_dump_parse_round_trip(tmp_path: Path) -> None:
    first = tmp_path / "a.txt"
    first.write_bytes(b"a")
    recipe = Recipe(
        inputs=[InputSpec(first), InputSpec(tmp_path / "folder", recursive=True, include=["*.txt"])],
        outputs=[OutputSpec(tmp_path / "out/file.TXT", ".TXT")],
        options=JobOptions("custom", r"\n{filename} "),
        order="filename",
        descending=True,
        transforms=["normalize_whitespace"],
        ocr="tesseract",
        dedup="near",
        dedup_threshold=0.8,
    )
    path = tmp_path / "job.yaml"
    dump_recipe(recipe, path)
    reloaded = load_recipe(path)
    assert [str(spec.path) for spec in reloaded.inputs] == [str(first), str(tmp_path / "folder")]
    assert [(str(output.path), output.format) for output in reloaded.outputs] == [(str(tmp_path / "out/file.TXT"), "txt")]
    assert (reloaded.options.separator_mode, reloaded.options.custom_separator) == ("custom", r"\n{filename} ")
    assert (reloaded.order, reloaded.descending) == ("filename", True)
    assert reloaded.transforms == ["normalize_whitespace"]
    assert reloaded.ocr == "tesseract"
    assert (reloaded.dedup, reloaded.dedup_threshold) == ("near", 0.8)


def test_dump_omits_defaults(tmp_path: Path) -> None:
    path = tmp_path / "job.yaml"
    dump_recipe(
        Recipe(inputs=[InputSpec(tmp_path / "a.txt")], outputs=[OutputSpec(tmp_path / "o.txt", "txt")]),
        path,
    )
    text = path.read_text(encoding="utf-8")
    assert "custom_separator" not in text and "transforms" not in text and "dedup" not in text


def test_gui_save_recipe(window: MainWindow, tmp_path: Path, dialogs) -> None:
    first = tmp_path / "b.txt"
    second = tmp_path / "a.txt"
    for path in (first, second):
        path.write_bytes(b"x")
        window.files.append(ConsolidationFile(path, path.name, "x"))
    dialogs.save_path = str(tmp_path / "job.yaml")
    window.save_recipe()
    reloaded = load_recipe(tmp_path / "job.yaml")
    assert [str(spec.path) for spec in reloaded.inputs] == [str(first), str(second)]
    assert reloaded.outputs[0].path == tmp_path / "job_consolidado.txt"
    assert any(kind == "information" for kind, _ in dialogs.messages)


def test_gui_save_recipe_empty_session(window: MainWindow, dialogs) -> None:
    dialogs.save_path = "unused.yaml"
    window.save_recipe()
    assert any(kind == "information" for kind, _ in dialogs.messages)


def test_gui_load_recipe_applies_inputs_and_separator(
    window: MainWindow, tmp_path: Path, dialogs, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "a.txt").write_bytes(b"A")
    recipe_path = tmp_path / "job.yaml"
    recipe_path.write_text(
        "version: 1\ninputs:\n  - folder: docs\nseparator: dashes\n"
        "outputs:\n  - path: out.docx\n",
        encoding="utf-8",
    )
    captured: list = []
    monkeypatch.setattr(MainWindow, "_process_paths", lambda self, paths: captured.extend(paths))
    dialogs.open_path = str(recipe_path)
    window.load_recipe()
    assert captured == [folder / "a.txt"]
    assert window.settings.separator_mode == "dashes"
    assert window.radio_dashes.isChecked()
    assert window.output_combo.currentText() == ".docx"
    assert dialogs.messages == []


def test_gui_load_recipe_warns_on_unsupported_features(
    window: MainWindow, tmp_path: Path, dialogs, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "a.txt").write_bytes(b"A")
    recipe_path = tmp_path / "job.yaml"
    recipe_path.write_text(
        "version: 1\ninputs:\n  - path: a.txt\ntransforms: [normalize_whitespace]\n"
        "dedup: exact\nocr: tesseract\noutputs:\n  - path: out.jsonl\n",
        encoding="utf-8",
    )
    captured: list = []
    monkeypatch.setattr(MainWindow, "_process_paths", lambda self, paths: captured.extend(paths))
    dialogs.open_path = str(recipe_path)
    window.load_recipe()
    assert captured == [tmp_path / "a.txt"]
    assert len(dialogs.messages) == 1
    kind, text = dialogs.messages[0]
    assert kind == "warning"
    assert "normalize_whitespace" in text and "exact" in text and "tesseract" in text and "jsonl" in text


def test_gui_load_recipe_invalid_file(window: MainWindow, tmp_path: Path, dialogs) -> None:
    missing = tmp_path / "missing.yaml"
    dialogs.open_path = str(missing)
    window.load_recipe()
    assert any(kind == "critical" for kind, _ in dialogs.messages)
