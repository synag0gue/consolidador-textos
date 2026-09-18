from __future__ import annotations

import shutil
import subprocess
from importlib.util import find_spec
from typing import Any, Protocol


class OcrProvider(Protocol):
    name: str

    def is_available(self) -> bool:
        ...

    def extract_text(self, image_bytes: bytes) -> str:
        ...


class TesseractProvider:
    name = "tesseract"

    def is_available(self) -> bool:
        return shutil.which("tesseract") is not None

    def extract_text(self, image_bytes: bytes) -> str:
        binary = shutil.which("tesseract")
        if binary is None:
            raise ValueError("Tesseract requested but not found on PATH")
        try:
            completed = subprocess.run(
                [binary, "stdin", "stdout", "--psm", "6"],
                input=image_bytes,
                capture_output=True,
                timeout=120,
            )
        except Exception as exc:
            raise ValueError(f"Tesseract failed: {exc}") from exc
        if completed.returncode != 0:
            detail = completed.stderr.decode("utf-8", "replace").strip()[-500:]
            raise ValueError(f"Tesseract failed (exit {completed.returncode}): {detail}")
        return completed.stdout.decode("utf-8", "replace")


class EasyOcrProvider:
    name = "easyocr"

    def __init__(self, languages: tuple[str, ...] = ("en",), model_dir: str | None = None) -> None:
        self.languages = languages
        self.model_dir = model_dir
        self._reader: Any = None

    def is_available(self) -> bool:
        return find_spec("easyocr") is not None and find_spec("torch") is not None

    def extract_text(self, image_bytes: bytes) -> str:
        try:
            import easyocr
        except ImportError as exc:
            raise ValueError(
                "EasyOCR is an optional extra (pip install easyocr torch); "
                "it is not installed"
            ) from exc
        if self._reader is None:
            kwargs = {"lang_list": list(self.languages), "gpu": False, "verbose": False}
            if self.model_dir is not None:
                kwargs["model_storage_directory"] = self.model_dir
            self._reader = easyocr.Reader(**kwargs)
        results = self._reader.readtext(image_bytes)
        return "\n".join(str(item[1]) for item in results)


_providers: dict[str, OcrProvider] = {
    TesseractProvider.name: TesseractProvider(),
    EasyOcrProvider.name: EasyOcrProvider(),
}


def available_ocr() -> tuple[str, ...]:
    return tuple(sorted(_providers))


def get_provider(name: str) -> OcrProvider:
    try:
        return _providers[name]
    except KeyError:
        raise ValueError(f"Unknown OCR provider: {name}") from None
