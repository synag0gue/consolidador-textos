import subprocess
import sys
import time
from pathlib import Path

import pytest

from src.core.recipes import InputSpec, OutputSpec, Recipe
from src.core.watch import iter_runs, snapshot, snapshot_changed


def _recipe(tmp_path: Path) -> Recipe:
    return Recipe(
        inputs=[InputSpec(tmp_path / "in", recursive=False, include=["*.txt"], exclude=[])],
        outputs=[OutputSpec(tmp_path / "out.txt", "txt")],
    )


def test_snapshot_change_detection(tmp_path: Path) -> None:
    folder = tmp_path / "in"
    folder.mkdir()
    (folder / "a.txt").write_bytes(b"one")
    recipe = _recipe(tmp_path)
    before = snapshot(recipe)
    assert not snapshot_changed(before, snapshot(recipe))
    time.sleep(0.01)
    (folder / "a.txt").write_bytes(b"two!")
    assert snapshot_changed(before, snapshot(recipe))
    (folder / "b.txt").write_bytes(b"new file")
    assert snapshot_changed(before, snapshot(recipe))


def test_watcher_reruns_on_change(tmp_path: Path) -> None:
    folder = tmp_path / "in"
    folder.mkdir()
    source = folder / "a.txt"
    source.write_bytes(b"v1")
    recipe = _recipe(tmp_path)

    runs = iter_runs(recipe, interval=0.05, overwrite=True, max_runs=2)
    first = next(runs)
    assert first.exit_code == 0
    source.write_bytes(b"v2-longer")
    second = next(runs)
    assert second.exit_code == 0
    assert (tmp_path / "out.txt").read_bytes() == b"v2-longer"
    with pytest.raises(StopIteration):
        next(runs)


def test_watcher_stop_flag(tmp_path: Path) -> None:
    folder = tmp_path / "in"
    folder.mkdir()
    (folder / "a.txt").write_bytes(b"data")
    results = list(iter_runs(_recipe(tmp_path), interval=0.05, overwrite=True, should_stop=lambda: True))
    assert len(results) == 1


def test_watcher_bad_interval(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="interval must be positive"):
        list(iter_runs(_recipe(tmp_path), interval=0))


def test_cli_watch_single_run_then_stops(tmp_path: Path) -> None:
    folder = tmp_path / "in"
    folder.mkdir()
    (folder / "a.txt").write_bytes(b"data")
    recipe_path = tmp_path / "job.yaml"
    recipe_path.write_text(
        "version: 1\ninputs:\n  - folder: in\noutputs:\n  - path: out.txt\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-m", "src.cli", "watch", str(recipe_path),
         "--interval", "0.05", "--max-runs", "1", "--overwrite"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "out.txt").read_bytes() == b"data"
