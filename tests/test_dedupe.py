import subprocess
import sys
from pathlib import Path

import pytest

from src.core.dedupe import apply_dedup, find_exact_groups, find_near_pairs
from src.core.jobs import run_recipe
from src.core.models import ConsolidationFile
from src.core.recipes import parse_recipe


def _item(name: str, text: str) -> ConsolidationFile:
    return ConsolidationFile(Path(name), name, text)


def test_exact_groups_and_skip_keeps_first() -> None:
    files = [_item("a", "same"), _item("b", "same"), _item("c", "other"), _item("d", "same")]
    assert find_exact_groups(files) == [[0, 1, 3]]
    result = apply_dedup(files, "exact")
    assert [item.name for item in result.kept] == ["a", "c"]
    assert [item.name for item in result.skipped_exact] == ["b", "d"]
    assert result.candidates == []


def test_off_mode_is_passthrough() -> None:
    files = [_item("a", "same"), _item("b", "same")]
    result = apply_dedup(files, "off")
    assert result.kept == files
    assert result.skipped_exact == [] and result.candidates == []
    with pytest.raises(ValueError, match="Unknown dedup mode"):
        apply_dedup(files, "bogus")


def test_near_pairs_ranked_and_empty_safe() -> None:
    base = "the quick brown fox jumps over the lazy dog"
    files = [_item("a", base), _item("b", base + " today"), _item("c", "completely different words here"), _item("d", "")]
    pairs = find_near_pairs(files, 0.8)
    assert [(pair.first, pair.second) for pair in pairs] == [(0, 1)]
    assert pairs[0].ratio >= 0.8
    assert len(pairs[0].first_preview) <= 200
    assert find_near_pairs(files, 0.99) == []
    with pytest.raises(ValueError, match="threshold"):
        find_near_pairs(files, 0)


def test_prefilter_keeps_genuine_near_duplicates() -> None:
    base = " ".join(f"word{i}" for i in range(2000))
    files = [
        _item("a", base),
        _item("b", base + " appendix with extra content here"),
        _item("c", " ".join(f"other{i}" for i in range(2000))),
    ]
    pairs = find_near_pairs(files, 0.9)
    assert [(pair.first, pair.second) for pair in pairs] == [(0, 1)]
    assert pairs[0].ratio >= 0.9


def test_recipe_dedup_fields(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"a")
    base = {"version": 1, "inputs": [{"path": "a.txt"}], "outputs": [{"path": "out.txt"}]}
    recipe = parse_recipe({**base, "dedup": "exact", "dedup_threshold": 0.95}, tmp_path)
    assert (recipe.dedup, recipe.dedup_threshold) == ("exact", 0.95)
    assert parse_recipe(base, tmp_path).dedup == "off"
    with pytest.raises(ValueError, match="dedup must be"):
        parse_recipe({**base, "dedup": "sometimes"}, tmp_path)
    with pytest.raises(ValueError, match="dedup_threshold"):
        parse_recipe({**base, "dedup_threshold": 2}, tmp_path)


def test_job_exact_dedup_end_to_end(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"identical")
    (tmp_path / "b.txt").write_bytes(b"identical")
    (tmp_path / "c.txt").write_bytes(b"unique")
    data = {
        "version": 1,
        "inputs": [{"folder": ".", "include": ["*.txt"]}],
        "outputs": [{"path": "out.txt"}],
        "order": {"by": "filename"},
        "dedup": "exact",
    }
    result = run_recipe(parse_recipe(data, tmp_path), overwrite=True)
    assert result.exit_code == 0
    assert [item.name for item in result.skipped_duplicates] == ["b.txt"]
    assert (tmp_path / "out.txt").read_bytes() == b"identical\n\nunique"


def test_job_near_mode_reports_without_skipping(tmp_path: Path) -> None:
    base = "the quick brown fox jumps over the lazy dog"
    (tmp_path / "a.txt").write_bytes(base.encode())
    (tmp_path / "b.txt").write_bytes((base + " today").encode())
    data = {
        "version": 1,
        "inputs": [{"folder": ".", "include": ["*.txt"]}],
        "outputs": [{"path": "out.txt"}],
        "order": {"by": "filename"},
        "dedup": "near",
        "dedup_threshold": 0.8,
    }
    result = run_recipe(parse_recipe(data, tmp_path), overwrite=True)
    assert result.skipped_duplicates == []
    assert len(result.duplicate_candidates) == 1
    assert len(result.exported) == 2


def test_cli_dedup_flags(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"dup")
    (tmp_path / "b.txt").write_bytes(b"dup")
    out = tmp_path / "out.txt"
    result = subprocess.run(
        [sys.executable, "-m", "src.cli", "merge", str(tmp_path / "a.txt"), str(tmp_path / "b.txt"),
         "-o", str(out), "--dedup", "exact"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert out.read_bytes() == b"dup"
    assert "Skipped duplicate" in result.stderr
