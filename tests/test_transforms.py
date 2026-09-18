from pathlib import Path

import pytest

from src.core.models import Block, BlockAttributes, Document, DocumentSource
from src.core.recipes import parse_recipe
from src.core.transforms import apply_transforms, available_transforms, parse_spec


def _doc(blocks: list[Block], path: Path | None = None) -> Document:
    target = path or Path("sample.txt")
    if not target.exists():
        target.write_bytes(b"x")
    return Document(DocumentSource.from_path(target), blocks=list(blocks))


def test_spec_parsing(tmp_path: Path) -> None:
    assert parse_spec("redact:\\d+,foo").name == "redact"
    assert parse_spec("redact:\\d+,foo").args == ("\\d+", "foo")
    assert parse_spec("normalize_whitespace").args == ()
    assert parse_spec(r"redact:token=[\w-]{20,},password=\S+").args == (
        r"token=[\w-]{20,}",
        r"password=\S+",
    )
    assert parse_spec(r"redact:[,\s]+").args == (r"[,\s]+",)
    with pytest.raises(ValueError):
        parse_spec("  ")


def test_redact_with_comma_quantifier(tmp_path: Path) -> None:
    path = tmp_path / "s.txt"
    path.write_bytes(b"x")
    document = Document(DocumentSource.from_path(path), blocks=[Block("paragraph", "token=abcdefghij1234567890 ok")])
    apply_transforms([document], [r"redact:token=[A-Za-z0-9-_]{20,}"])
    assert document.blocks[0].text == "[REDACTED] ok"


def test_normalize_whitespace(tmp_path: Path) -> None:
    document = _doc([Block("paragraph", "a  \r\n\r\n\r\nb\t")], tmp_path / "s.txt")
    apply_transforms([document], ["normalize_whitespace"])
    assert document.blocks[0].text == "a\n\nb"
    assert document.transforms_applied == ["normalize_whitespace"]


def test_strip_repeated_headers_footers(tmp_path: Path) -> None:
    pages = [
        Block("page", "Report 2026\nBody one\nPage 1 of 2", BlockAttributes(page_number=1)),
        Block("page", "Report 2026\nBody two\nPage 1 of 2", BlockAttributes(page_number=2)),
    ]
    document = _doc(pages, tmp_path / "s.txt")
    apply_transforms([document], ["strip_headers_footers"])
    assert document.blocks[0].text == "Body one"
    assert document.blocks[1].text == "Body two"


def test_strip_headers_requires_repetition(tmp_path: Path) -> None:
    pages = [
        Block("page", "Header A\nBody one", BlockAttributes(page_number=1)),
        Block("page", "Header B\nBody two", BlockAttributes(page_number=2)),
    ]
    document = _doc(pages, tmp_path / "s.txt")
    apply_transforms([document], ["strip_headers_footers"])
    assert document.blocks[0].text == "Header A\nBody one"


def test_redact_text_and_tables(tmp_path: Path) -> None:
    document = _doc(
        [
            Block("paragraph", "Contact ana@example.com now"),
            Block("table", attrs=BlockAttributes(table_data=[["ana@example.com", "ok"]])),
        ],
        tmp_path / "s.txt",
    )
    apply_transforms([document], ["redact:[\\w.]+@[\\w.]+"])
    assert document.blocks[0].text == "Contact [REDACTED] now"
    assert document.blocks[1].attrs.table_data == [["[REDACTED]", "ok"]]
    with pytest.raises(ValueError):
        apply_transforms([document], ["redact"])


def test_dedup_and_sort_lines(tmp_path: Path) -> None:
    document = _doc([Block("paragraph", "b\na\nb")], tmp_path / "s.txt")
    apply_transforms([document], ["dedup_lines"])
    assert document.blocks[0].text == "b\na"
    apply_transforms([document], ["sort_lines"])
    assert document.blocks[0].text == "a\nb"


def test_unknown_transform_rejected(tmp_path: Path) -> None:
    document = _doc([Block("paragraph", "x")], tmp_path / "s.txt")
    with pytest.raises(ValueError, match="Unknown transform"):
        apply_transforms([document], ["nope"])
    assert document.transforms_applied == []
    assert "normalize_whitespace" in available_transforms()


def test_recipe_transforms_field(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"a")
    data = {
        "version": 1,
        "inputs": [{"path": "a.txt"}],
        "outputs": [{"path": "out.txt"}],
        "transforms": ["normalize_whitespace"],
    }
    assert parse_recipe(data, tmp_path).transforms == ["normalize_whitespace"]
    bad = dict(data, transforms=["nope"])
    with pytest.raises(ValueError, match="Unknown transform"):
        parse_recipe(bad, tmp_path)
    bad_type = dict(data, transforms="normalize_whitespace")
    with pytest.raises(ValueError, match="transforms must be a list"):
        parse_recipe(bad_type, tmp_path)
