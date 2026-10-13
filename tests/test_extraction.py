import asyncio
import hashlib
import io
from pathlib import Path

import pytest
from pydantic import ValidationError
from pypdf import PdfWriter
from rag_core.errors import PlatformError
from rag_core.extraction import extract
from rag_core.schemas import Extraction
from rag_core.storage import BlobStore
from reportlab.pdfgen.canvas import Canvas


def extraction(tmp_path: Path, filename: str, content: bytes, limit: int = 10000) -> str:
    path = tmp_path / filename
    path.write_bytes(content)
    result = extract(path, filename, hashlib.sha256(content).hexdigest(), limit, 20)
    return "\n\n".join(section.text for section in result.sections)


def test_markdown_preserves_code_and_ignores_headings_inside_fences(tmp_path: Path) -> None:
    content = (
        b"# Transactions\n\n```sql\n# not a heading\nSELECT 1;\n```\n\n"
        b"## Isolation\nSerializable.\n"
    )
    path = tmp_path / "guide.md"
    path.write_bytes(content)
    result = extract(path, path.name, hashlib.sha256(content).hexdigest(), 10000, 20)
    assert len(result.sections) == 2
    assert result.sections[0].heading_path == ["Transactions"]
    assert "# not a heading\nSELECT 1;" in result.sections[0].text
    assert result.sections[1].heading_path == ["Transactions", "Isolation"]
    assert result.sections[1].source.start_line == 8


def test_html_strips_active_content_and_preserves_sql(tmp_path: Path) -> None:
    content = (
        b'<nav>menu</nav><main><h1 id="sql">SQL</h1><script>steal()</script>'
        b"<pre>SELECT\n  1;</pre><ul><li>Only once</li></ul></main>"
    )
    text = extraction(tmp_path, "guide.html", content)
    assert "steal" not in text and "menu" not in text
    assert "SELECT\n  1;" in text
    assert text.count("Only once") == 1


def test_skipped_heading_levels_do_not_nest_siblings(tmp_path: Path) -> None:
    content = b"# Root\n### First\nText.\n### Second\n  Indented code."
    path = tmp_path / "guide.md"
    path.write_bytes(content)
    result = extract(path, path.name, hashlib.sha256(content).hexdigest(), 10000, 20)
    assert result.sections[-1].heading_path == ["Root", "Second"]
    assert "  Indented code." in result.sections[-1].text


def test_text_normalizes_unicode_and_line_endings(tmp_path: Path) -> None:
    assert (
        extraction(tmp_path, "guide.txt", "Cafe\u0301\r\nSELECT 1;".encode()) == "Café\nSELECT 1;"
    )


@pytest.mark.parametrize(
    "content, code",
    [(b"\xff", "invalid_encoding"), (b"a\0b", "binary_document"), (b"   ", "no_text")],
)
def test_invalid_text_is_explicit(tmp_path: Path, content: bytes, code: str) -> None:
    with pytest.raises(PlatformError) as error:
        extraction(tmp_path, "guide.txt", content)
    assert error.value.code == code


def test_pdf_page_locations_and_no_ocr_claim(tmp_path: Path) -> None:
    stream = io.BytesIO()
    canvas = Canvas(stream)
    canvas.drawString(40, 700, "A transaction is atomic.")
    canvas.showPage()
    canvas.save()
    assert "transaction is atomic" in extraction(tmp_path, "guide.pdf", stream.getvalue())
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    blank = io.BytesIO()
    writer.write(blank)
    with pytest.raises(PlatformError, match="OCR"):
        extraction(tmp_path, "blank.pdf", blank.getvalue())
    writer.encrypt("secret")
    encrypted = io.BytesIO()
    writer.write(encrypted)
    with pytest.raises(PlatformError, match="Encrypted"):
        extraction(tmp_path, "encrypted.pdf", encrypted.getvalue())


def test_integrity_and_extraction_size_limits(tmp_path: Path) -> None:
    path = tmp_path / "guide.txt"
    path.write_bytes(b"too long")
    with pytest.raises(PlatformError, match="integrity"):
        extract(path, path.name, "0" * 64, 100, 20)
    with pytest.raises(PlatformError, match="limit"):
        extraction(tmp_path, "guide.txt", b"too long", limit=2)


def test_checkpoint_integrity_detects_modified_text(tmp_path: Path) -> None:
    path = tmp_path / "guide.txt"
    path.write_bytes(b"Evidence")
    result = extract(path, path.name, hashlib.sha256(b"Evidence").hexdigest(), 10000, 20)
    checkpoint = result.model_dump()
    checkpoint["sections"][0]["text"] = "Tampered"
    with pytest.raises(ValidationError, match="checksum"):
        Extraction.model_validate(checkpoint)


def test_bounded_upload_cleans_partial_files_and_blocks_traversal(tmp_path: Path) -> None:
    blobs = BlobStore(tmp_path)
    with pytest.raises(PlatformError):
        blobs.path("../outside.txt")
    chunks = iter([b"12345", b"67890", b""])

    async def read(_: int) -> bytes:
        return next(chunks)

    with pytest.raises(PlatformError) as error:
        asyncio.run(blobs.upload("guide.txt", read, 6))
    assert error.value.status == 413
    assert not list(tmp_path.rglob("*.txt"))
