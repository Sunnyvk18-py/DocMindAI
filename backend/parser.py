"""
PDF text extraction for DocMind AI (Phase 2).

Uses pypdf to read each page and combine extracted text. This text is later
split into chunks for RAG-style workflows (Phase 3 chunker).
"""

from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError


def extract_text_from_pdf(file_path: str) -> str:
    """
    Read a PDF from disk and return all page text as one string.

    Pages are separated by newlines so structure stays somewhat readable.
    Extraction is "best effort": some PDFs (scans, odd encodings) may return
    little or no text; that is still a successful read, not an exception.

    Args:
        file_path: Absolute or relative path to a .pdf file on disk.

    Returns:
        Combined plain text from every page.

    Raises:
        FileNotFoundError: If the path does not exist or is not a file.
        ValueError: If the file is not a valid PDF or cannot be opened.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"No PDF file at path: {file_path}")

    # PdfReader opens the file and parses the PDF structure.
    try:
        reader = PdfReader(str(path))
    except PdfReadError as exc:
        # Common when the file is corrupt, truncated, or not really a PDF.
        raise ValueError(f"Invalid or unreadable PDF: {exc}") from exc
    except OSError as exc:
        # Rare: permission or I/O errors while reading bytes from disk.
        raise ValueError(f"Could not read PDF file: {exc}") from exc

    page_texts: list[str] = []
    for page_index, page in enumerate(reader.pages):
        # extract_text() can fail on unusual page objects; isolate per page.
        try:
            raw = page.extract_text()
        except Exception as exc:  # noqa: BLE001 — pypdf may raise varied types
            raise ValueError(
                f"Failed to extract text from page {page_index + 1}: {exc}"
            ) from exc
        page_texts.append(raw if raw else "")

    # Join pages with newlines so callers can split or search predictably.
    return "\n".join(page_texts)
