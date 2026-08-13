from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import fitz
from docx import Document
from apps.api.config import settings
from packages.ingestion.ocr import ocr_pixmap


@dataclass(slots=True)
class ParsedPage:
    page_number: int | None
    section: str | None
    text: str
    extraction_method: str = "text"


def parse_document(data: bytes, name: str, mime: str | None = None) -> list[ParsedPage]:
    ext = Path(name).suffix.lower()
    if ext == ".pdf":
        doc = fitz.open(stream=data, filetype="pdf")
        pages: list[ParsedPage] = []
        for i, page in enumerate(doc):
            text = page.get_text("text").strip()
            method="text"
            if settings.ocr_enabled and len(text) < 40:
                pix=page.get_pixmap(matrix=fitz.Matrix(2,2),alpha=False)
                ocr=ocr_pixmap(pix,settings.tesseract_cmd)
                if len(ocr) > len(text):
                    text=ocr
                    method="ocr"
            if text:
                pages.append(ParsedPage(i + 1, None, text,method))
        return pages

    if ext == ".docx":
        doc = Document(BytesIO(data))
        out: list[ParsedPage] = []
        current_section: str | None = None
        buf: list[str] = []
        for paragraph in doc.paragraphs:
            paragraph_text = paragraph.text.strip()
            if not paragraph_text:
                continue
            if paragraph.style and paragraph.style.name.startswith("Heading"):
                if buf:
                    out.append(ParsedPage(None, current_section, "\n".join(buf)))
                    buf = []
                current_section = paragraph_text
            else:
                buf.append(paragraph_text)
        if buf:
            out.append(ParsedPage(None, current_section, "\n".join(buf)))
        return out

    return [ParsedPage(None, None, data.decode("utf-8", errors="replace"))]
