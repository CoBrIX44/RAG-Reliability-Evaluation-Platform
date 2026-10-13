"""Versioned source evidence; independent of future retrieval chunking."""

import hashlib
import unicodedata
from pathlib import Path

from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
from pypdf import PdfReader

from rag_core.errors import PlatformError
from rag_core.schemas import ExtractedSection, Extraction, SourceLocation

EXTRACTOR_VERSION = "source-v1"
FORMATS = {
    ".pdf": "pdf",
    ".html": "html",
    ".htm": "html",
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "text",
}


def normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n")).strip("\n")


def extract(
    path: Path, filename: str, expected_checksum: str, max_characters: int, max_pages: int
) -> Extraction:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_checksum:
        raise PlatformError("checksum_mismatch", "The stored original failed its integrity check.")
    kind = FORMATS.get(Path(filename).suffix.lower())
    sections: list[ExtractedSection] = []
    total = 0
    hierarchy: list[tuple[int, str]] = []

    def heading(level: int, title: str) -> list[str]:
        while hierarchy and hierarchy[-1][0] >= level:
            hierarchy.pop()
        hierarchy.append((level, title))
        return [item[1] for item in hierarchy]

    def add(text: str, headings: list[str], source: SourceLocation) -> None:
        nonlocal total
        value = normalize(text)
        if value.strip():
            total += len(value) + (2 if sections else 0)
            sections.append(
                ExtractedSection(text=value, heading_path=headings.copy(), source=source)
            )
            if total > max_characters:
                raise PlatformError(
                    "extraction_limit", "The document exceeds the extracted text limit."
                )

    if kind == "pdf":
        if not raw.startswith(b"%PDF-"):
            raise PlatformError("invalid_pdf", "The file is not a valid PDF.")
        try:
            reader = PdfReader(path)
            if reader.is_encrypted:
                raise PlatformError("encrypted_pdf", "Encrypted PDFs are not supported.")
            if len(reader.pages) > max_pages:
                raise PlatformError("extraction_limit", "The PDF exceeds the page limit.")
            for page, content in enumerate(reader.pages, 1):
                add(content.extract_text(), [], SourceLocation(format="pdf", page=page))
        except PlatformError:
            raise
        except Exception as error:
            raise PlatformError("invalid_pdf", "PDF text could not be extracted.") from error
    elif kind in ("text", "markdown", "html"):
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise PlatformError(
                "invalid_encoding", "Text documents must use UTF-8 encoding."
            ) from error
        if "\x00" in text:
            raise PlatformError("binary_document", "Binary content is not supported as text.")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        if kind == "text":
            add(
                text,
                [],
                SourceLocation(format="text", start_line=1, end_line=len(text.splitlines())),
            )
        elif kind == "markdown":
            lines = text.splitlines(keepends=True)
            tokens = MarkdownIt().parse(text)
            headings: list[str] = []
            start = 0
            for index, token in enumerate(tokens):
                if token.type != "heading_open" or token.map is None:
                    continue
                boundary = token.map[0]
                if boundary > start:
                    add(
                        "".join(lines[start:boundary]),
                        headings,
                        SourceLocation(format="markdown", start_line=start + 1, end_line=boundary),
                    )
                level = int(token.tag[1:])
                headings = heading(level, tokens[index + 1].content)
                start = boundary
            add(
                "".join(lines[start:]),
                headings,
                SourceLocation(format="markdown", start_line=start + 1, end_line=len(lines)),
            )
        else:
            soup = BeautifulSoup(text, "html.parser")
            for tag in soup.select("script,style,nav,footer,iframe,object,embed,noscript"):
                tag.decompose()
            root = soup.select_one("main,article,#content") or soup.body or soup
            headings = []
            candidates = root.find_all(
                ["h1", "h2", "h3", "h4", "h5", "h6", "p", "pre", "li", "table"]
            )
            candidate_ids = {id(tag) for tag in candidates}
            for tag in candidates:
                if any(id(parent) in candidate_ids for parent in tag.parents):
                    continue
                name = tag.name or ""
                if name.startswith("h") and name[1:].isdigit():
                    level = int(name[1:])
                    headings = heading(level, tag.get_text(" ", strip=True))
                value = tag.get_text("" if name == "pre" else "\n", strip=name != "pre")
                anchor = tag.get("id")
                add(
                    value,
                    headings,
                    SourceLocation(
                        format="html", anchor=anchor if isinstance(anchor, str) else None
                    ),
                )
            if not sections:
                add(root.get_text("\n", strip=True), [], SourceLocation(format="html"))
    else:
        raise PlatformError("unsupported_format", "Use PDF, HTML, Markdown, or UTF-8 text.")
    if not sections:
        raise PlatformError("no_text", "No readable text was found. Scanned PDFs need OCR first.")
    canonical = "\n\n".join(section.text for section in sections)
    return Extraction(
        extractor_version=EXTRACTOR_VERSION,
        input_checksum=expected_checksum,
        checksum=hashlib.sha256(canonical.encode()).hexdigest(),
        sections=sections,
        character_count=len(canonical),
    )
