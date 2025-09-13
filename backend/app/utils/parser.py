import io

from pdfminer.high_level import extract_text


def parse_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes. For DOCX support, add python-docx parsing."""
    with io.BytesIO(pdf_bytes) as fh:
        text = extract_text(fh)
    # lightweight cleanup
    text = "\n".join([line.strip() for line in text.splitlines() if line.strip()])
    return text