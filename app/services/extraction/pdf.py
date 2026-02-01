"""Extract text from PDF files."""

from typing import Optional

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


def extract_text_from_pdf(data: bytes) -> tuple[str, Optional[float]]:
    """
    Extract text from PDF bytes.
    Returns (text, confidence). Confidence is None (we don't have a score from PyMuPDF).
    """
    if fitz is None:
        return "", None
    text_parts: list[str] = []
    doc = fitz.open(stream=data, filetype="pdf")
    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            text_parts.append(page.get_text())
    finally:
        doc.close()
    text = "\n\n".join(p.strip() for p in text_parts if p.strip())
    return text, None
