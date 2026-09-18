import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core.jobs import run_recipe
from src.core.ocr import (
    EasyOcrProvider,
    TesseractProvider,
    available_ocr,
    get_provider,
)
from src.core.recipes import parse_recipe
from src.extractors.pdf import PdfExtractor
from src.extractors.registry import create_default_registry


class _FakeProvider:
    name = "fake"

    def __init__(self, text: str = "ocr-text") -> None:
        self.text = text
        self.calls: list[bytes] = []

    def is_available(self) -> bool:
        return True

    def extract_text(self, image_bytes: bytes) -> str:
        self.calls.append(image_bytes)
        return self.text


def test_tesseract_invocation(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_which(name: str) -> str | None:
        assert name == "tesseract"
        return "C:/fake/tesseract.exe"

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["input"] = kwargs["input"]
        return SimpleNamespace(returncode=0, stdout="línea\n".encode("utf-8"), stderr=b"")

    monkeypatch.setattr("src.core.ocr.shutil.which", fake_which)
    monkeypatch.setattr("src.core.ocr.subprocess.run", fake_run)
    provider = TesseractProvider()
    assert provider.is_available()
    assert provider.extract_text(b"image") == "línea\n"
    assert captured["cmd"][:3] == ["C:/fake/tesseract.exe", "stdin", "stdout"]
    assert captured["input"] == b"image"


def test_tesseract_unavailable_and_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.core.ocr.shutil.which", lambda name: None)
    provider = TesseractProvider()
    assert not provider.is_available()
    with pytest.raises(ValueError, match="not found on PATH"):
        provider.extract_text(b"image")

    monkeypatch.setattr("src.core.ocr.shutil.which", lambda name: "tesseract")
    monkeypatch.setattr(
        "src.core.ocr.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout=b"", stderr=b"boom"),
    )
    with pytest.raises(ValueError, match="exit 1"):
        provider.extract_text(b"image")


def test_easyocr_availability_uses_find_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.core.ocr.find_spec", lambda name: None)
    assert not EasyOcrProvider().is_available()
    monkeypatch.setattr("src.core.ocr.find_spec", lambda name: object())
    assert EasyOcrProvider().is_available()


def test_easyocr_missing_dependency_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "easyocr", None)
    with pytest.raises(ValueError, match="optional extra"):
        EasyOcrProvider().extract_text(b"image")


def test_ocr_module_import_is_light() -> None:
    import subprocess

    script = (
        "import sys; import src.core.ocr;"
        " assert 'easyocr' not in sys.modules, 'easyocr imported';"
        " assert 'torch' not in sys.modules, 'torch imported';"
        " print('light import ok')"
    )
    result = subprocess.run([sys.executable, "-B", "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_provider_registry() -> None:
    assert set(available_ocr()) == {"tesseract", "easyocr"}
    assert isinstance(get_provider("tesseract"), TesseractProvider)
    with pytest.raises(ValueError, match="Unknown OCR provider"):
        get_provider("bogus")


def test_pdf_ocr_wiring_with_fake_reader(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "scan.pdf"
    path.write_bytes(b"%PDF-1.4 fake")

    class FakeImage:
        data = b"imagedata"

    class FakePage:
        def extract_text(self) -> str:
            return "  "

        @property
        def images(self):
            return [FakeImage()]

    fake_provider = _FakeProvider()

    class FakeReader:
        is_encrypted = False
        metadata = SimpleNamespace(title=None, author=None)
        pages = [FakePage(), FakePage()]

        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

    monkeypatch.setattr("pypdf.PdfReader", FakeReader)
    document = PdfExtractor(ocr_provider=fake_provider).extract_structured(path)

    assert [block.text for block in document.blocks] == ["ocr-text", "ocr-text"]
    assert fake_provider.calls == [b"imagedata", b"imagedata"]
    assert [warning.code for warning in document.warnings] == ["ocr_text", "ocr_text"]


def test_pdf_ocr_unavailable_provider_raises(tmp_path: Path) -> None:
    path = tmp_path / "scan.pdf"
    path.write_bytes(b"%PDF-1.4 fake")

    class Unavailable:
        name = "unavailable"

        def is_available(self) -> bool:
            return False

        def extract_text(self, image_bytes: bytes) -> str:
            raise AssertionError("must not be called")

    with pytest.raises(ValueError, match="not available"):
        PdfExtractor(ocr_provider=Unavailable()).extract_structured(path)


def test_default_registry_unchanged_and_ocr_option(tmp_path: Path) -> None:
    plain = create_default_registry()
    assert plain.get_extractor(tmp_path / "x.pdf").ocr_provider is None
    fake = _FakeProvider()
    registry = create_default_registry(ocr=fake)
    assert registry.get_extractor(tmp_path / "x.pdf").ocr_provider is fake
    with pytest.raises(ValueError, match="not available"):
        create_default_registry(ocr="tesseract" if not TesseractProvider().is_available() else "easyocr")


def test_recipe_ocr_field_and_job_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "a.txt").write_bytes(b"a")
    base = {"version": 1, "inputs": [{"path": "a.txt"}], "outputs": [{"path": "out.txt"}]}
    assert parse_recipe({**base, "ocr": "tesseract"}, tmp_path).ocr == "tesseract"
    assert parse_recipe(base, tmp_path).ocr is None
    with pytest.raises(ValueError, match="Unknown OCR provider"):
        parse_recipe({**base, "ocr": "bogus"}, tmp_path)

    seen = {}

    def fake_factory(ocr=None):
        seen["ocr"] = ocr
        return create_default_registry()

    monkeypatch.setattr("src.core.jobs.create_default_registry", fake_factory)
    result = run_recipe(parse_recipe({**base, "ocr": "tesseract"}, tmp_path), overwrite=True)
    assert seen["ocr"] == "tesseract"
    assert result.exit_code == 0
