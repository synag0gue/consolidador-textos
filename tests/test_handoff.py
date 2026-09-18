import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from pypdf import PdfWriter

from src.core.handoff import PACKAGE_FILES, build_handoff
from src.core.models import ConsolidationFile


def _options(**overrides):
    values = {"separator_mode": "filename", "custom_separator": ""}
    values.update(overrides)
    return SimpleNamespace(**values)


def test_handoff_package_contents(tmp_path: Path) -> None:
    first = tmp_path / "a.txt"
    first.write_bytes("Hello Olá\n".encode("utf-8"))
    second = tmp_path / "b.txt"
    second.write_bytes(b"Second")
    out = tmp_path / "package"
    files = [
        ConsolidationFile(first, first.name, "Hello Olá\n"),
        ConsolidationFile(second, second.name, "Second"),
    ]

    created = build_handoff(files, _options(), out)

    assert [path.name for path in created] == list(PACKAGE_FILES)
    assert all(path.is_file() for path in created)
    md = (out / "consolidated.md").read_text(encoding="utf-8")
    assert "Hello Olá" in md and "Second" in md
    rows = [(out / "blocks.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows[0]) == 2
    first_row = json.loads(rows[0][0])
    assert first_row["block"]["text"] == "Hello Olá\n"
    assert first_row["source"]["path"] == str(first)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["document_count"] == 2
    assert manifest["documents"][0]["name"] == "a.txt"
    assert manifest["options"]["separator_mode"] == "filename"
    prompt = (out / "PROMPT.md").read_text(encoding="utf-8")
    assert "a.txt" in prompt and "b.txt" in prompt


def test_handoff_propagates_warnings(tmp_path: Path) -> None:
    blank = tmp_path / "scan.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with blank.open("wb") as stream:
        writer.write(stream)
    from src.core.consolidator import extract_document
    from src.extractors.registry import create_default_registry

    document = extract_document(blank, create_default_registry())
    assert document.warnings
    out = tmp_path / "package"
    build_handoff(
        [ConsolidationFile(blank, blank.name, document.to_plain_text(), document=document)],
        _options(),
        out,
    )
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["documents"][0]["warnings"][0]["code"] == "empty_page"
    prompt = (out / "PROMPT.md").read_text(encoding="utf-8")
    assert "scan.pdf" in prompt and "warning" in prompt.lower()


def test_handoff_destination_safety(tmp_path: Path) -> None:
    source = tmp_path / "input.txt"
    source.write_bytes(b"data")
    files = [ConsolidationFile(source, source.name, "data")]
    with pytest.raises(ValueError, match="not a directory"):
        build_handoff(files, _options(), source)
    out = tmp_path / "package"
    build_handoff(files, _options(), out)
    with pytest.raises(FileExistsError, match="already exists"):
        build_handoff(files, _options(), out)
    build_handoff(files, _options(), out, overwrite=True)
    with pytest.raises(ValueError, match="failed extraction"):
        build_handoff(
            [ConsolidationFile(source, source.name, error="boom")], _options(), tmp_path / "other"
        )


def test_cli_handoff_end_to_end(tmp_path: Path) -> None:
    source = tmp_path / "sample.txt"
    source.write_bytes("Hello\n".encode("utf-8"))
    out = tmp_path / "package"
    result = subprocess.run(
        [sys.executable, "-m", "src.cli", "handoff", str(source), "-o", str(out)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert all((out / name).is_file() for name in PACKAGE_FILES)
