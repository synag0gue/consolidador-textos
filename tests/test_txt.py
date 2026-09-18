from pathlib import Path

import pytest

from src.extractors.txt import PlainTextExtractor, stream_decode


def test_stream_decode_matches_whole_decode(tmp_path: Path) -> None:
    text = "Hola Olá 日本語 🎉\nsecond line with ñ and ü\n"
    path = tmp_path / "sample.txt"
    path.write_bytes(text.encode("utf-8"))
    expected = path.read_bytes().decode("utf-8")
    for chunk_size in (1, 2, 3, 5, 7, 64, 1024 * 1024):
        assert stream_decode(path, "utf-8", chunk_size) == expected


def test_stream_decode_other_encodings(tmp_path: Path) -> None:
    cases = [
        ("utf-8-sig", "BOM bye".encode("utf-8-sig")),
        ("utf-16", "unicode".encode("utf-16")),
        ("cp1252", "caf\xe9 naïve".encode("cp1252")),
        ("latin-1", bytes(range(1, 256))),
    ]
    for encoding, data in cases:
        path = tmp_path / f"sample-{encoding}.txt"
        path.write_bytes(data)
        for chunk_size in (1, 9, 65536):
            assert stream_decode(path, encoding, chunk_size) == data.decode(encoding)


def test_extractor_matches_legacy_behavior(tmp_path: Path) -> None:
    extractor = PlainTextExtractor()
    cases = {
        "utf8.txt": "Olá 🎉\n".encode("utf-8"),
        "bom.txt": "text".encode("utf-8-sig"),
        "utf16.txt": "text".encode("utf-16"),
        "cp1252.txt": "caf\xe9".encode("cp1252"),
        "empty.txt": b"",
    }
    for name, data in cases.items():
        path = tmp_path / name
        path.write_bytes(data)
        assert extractor.extract(path) == data.decode(
            "utf-8-sig" if name == "bom.txt" else "utf-8" if name in ("utf8.txt", "empty.txt")
            else "utf-16" if name == "utf16.txt" else "cp1252"
        )


def test_binary_rejected_without_full_read(tmp_path: Path) -> None:
    path = tmp_path / "binary.txt"
    path.write_bytes(b"text\x00binary" + b"x" * 100000)
    with pytest.raises(ValueError, match="binario"):
        PlainTextExtractor().extract(path)
