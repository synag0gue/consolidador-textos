from pathlib import Path

from pypdf import PdfWriter

from src.core.consolidator import extract_document, extract_file
from src.extractors.pdf import PdfExtractor
from src.extractors.registry import create_default_registry


def _build_pdf(path: Path, page_texts: list[str], title: str | None = None, author: str | None = None) -> None:
    objects: list[bytes] = []
    kids = " ".join(f"{3 + index * 2} 0 R" for index in range(len(page_texts)))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_texts)} >>".encode("latin-1"))
    font_ref = 3 + len(page_texts) * 2
    for index, text in enumerate(page_texts):
        page_ref = 3 + index * 2
        content_ref = page_ref + 1
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_ref} 0 R >> >> /Contents {content_ref} 0 R >>".encode("latin-1")
        )
        content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET\n".encode("latin-1")
        objects.append(b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"endstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    info_ref = ""
    if title is not None or author is not None:
        info = b"<<"
        if title is not None:
            info += b" /Title (" + title.encode("latin-1") + b")"
        if author is not None:
            info += b" /Author (" + author.encode("latin-1") + b")"
        info += b" >>"
        objects.append(info)
        info_ref = f" /Info {len(objects)} 0 R"
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R{info_ref} >>\n"
        f"startxref\n{xref}\n%%EOF"
    ).encode()
    path.write_bytes(bytes(out))


def test_pdf_preserves_page_order_and_metadata(tmp_path: Path) -> None:
    path = tmp_path / "doc.pdf"
    _build_pdf(path, ["First page", "Second page"], title="Report", author="Author")

    document = extract_document(path, create_default_registry())

    assert [b.kind for b in document.blocks] == ["page", "page"]
    assert [b.attrs.page_number for b in document.blocks] == [1, 2]
    assert document.blocks[0].text.strip() == "First page"
    assert document.warnings == []
    assert document.metadata.title == "Report"
    assert document.metadata.author == "Author"
    assert document.metadata.page_count == 2
    assert document.source.format == ".pdf"
    assert document.to_plain_text() == PdfExtractor().extract(path) == extract_file(path, create_default_registry())


def test_pdf_empty_page_raises_scanned_warning(tmp_path: Path) -> None:
    path = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with path.open("wb") as stream:
        writer.write(stream)

    document = PdfExtractor().extract_structured(path)

    assert len(document.blocks) == 1
    assert document.blocks[0].attrs.page_number == 1
    assert len(document.warnings) == 1
    warning = document.warnings[0]
    assert warning.code == "empty_page"
    assert warning.page_number == 1
