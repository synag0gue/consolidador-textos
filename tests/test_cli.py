import subprocess
import sys
from pathlib import Path
import json

import pytest

from src.core.jobs import run_recipe
from src.core.recipes import load_recipe, parse_recipe


def test_cli_merge_txt_end_to_end(tmp_path: Path) -> None:
    source = tmp_path / "sample.txt"
    output = tmp_path / "merged.txt"
    source.write_bytes("Hello\nOlá\n".encode("utf-8"))
    result = subprocess.run(
        [sys.executable, "-m", "src.cli", "merge", str(source),
         "-o", str(output), "--format", "txt"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert output.read_bytes() == source.read_bytes()
    assert str(output) in result.stdout


def test_cli_recipe_uses_recipe_relative_paths_and_multiple_outputs(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"A")
    (tmp_path / "b.txt").write_bytes(b"B")
    recipe = tmp_path / "job.yaml"
    recipe.write_text('''version: 1
inputs:
  - folder: .
    include: ["*.txt"]
order: {by: filename, direction: desc}
separator: dashes
outputs:
  - path: merged.txt
  - path: merged.jsonl
''', encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "src.cli", "run", str(recipe)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "merged.txt").read_bytes() == b"B\n---\nA"
    records = [json.loads(line) for line in (tmp_path / "merged.jsonl").read_text().splitlines()]
    assert [record["block"]["text"] for record in records] == ["B", "A"]
    second = subprocess.run([sys.executable, "-m", "src.cli", "run", str(recipe), "--overwrite"], capture_output=True, text=True)
    assert second.returncode == 0, second.stderr
    assert (tmp_path / "merged.txt").read_bytes() == b"B\n---\nA"


def test_cli_partial_failure_and_total_failure(tmp_path: Path) -> None:
    good = tmp_path / "good.txt"
    good.write_bytes(b"Good")
    bad = tmp_path / "bad.docx"
    bad.write_bytes(b"broken")
    output = tmp_path / "out.txt"
    args = [sys.executable, "-m", "src.cli", "merge", str(good), str(bad), "-o", str(output)]
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 1
    assert "Skipped" in result.stderr
    assert output.read_bytes() == b"Good"
    output.unlink()
    result = subprocess.run([sys.executable, "-m", "src.cli", "merge", str(bad), "-o", str(output)], capture_output=True, text=True)
    assert result.returncode == 2
    assert not output.exists()


@pytest.mark.parametrize("patch", [
    {"version": 2}, {"version": True}, {"typo": 1}, {"transforms": ["unsupported"]},
    {"inputs": []}, {"outputs": []}, {"separator": "oops"},
    {"inputs": [{"path": "a.txt", "recursive": "false"}]},
    {"outputs": [{"path": "out.txt", "typo": True}]},
    {"order": {"by": "mtime"}},
])
def test_invalid_recipes_rejected(tmp_path: Path, patch: dict) -> None:
    data = {"version": 1, "inputs": [{"path": "a.txt"}], "outputs": [{"path": "out.txt"}], **patch}
    with pytest.raises(ValueError):
        parse_recipe(data, tmp_path)


def test_unsafe_yaml_rejected(tmp_path: Path) -> None:
    path = tmp_path / "job.yaml"
    path.write_text("!!python/object:builtins.object {}", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid recipe"):
        load_recipe(path)


def test_job_preflights_all_outputs(tmp_path: Path) -> None:
    source = tmp_path / "a.txt"
    source.write_bytes(b"original")
    data = {"version": 1, "inputs": [{"path": "a.txt"}],
            "outputs": [{"path": "out.txt"}, {"path": "a.txt"}]}
    with pytest.raises(ValueError, match="source"):
        run_recipe(parse_recipe(data, tmp_path), overwrite=True)
    assert source.read_bytes() == b"original"
    assert not (tmp_path / "out.txt").exists()


def test_cli_runs_without_qt_imports(tmp_path: Path) -> None:
    source = tmp_path / "a.txt"
    source.write_bytes(b"text")
    script = '''
import importlib.abc
import sys
class NoQt(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(('PySide6', 'src.ui', 'src.config')):
            raise ImportError(fullname)
sys.meta_path.insert(0, NoQt())
from src.cli import main
sys.exit(main(sys.argv[1:]))
'''
    result = subprocess.run([sys.executable, "-c", script, "merge", str(source), "-o", str(tmp_path / "out.txt")], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
