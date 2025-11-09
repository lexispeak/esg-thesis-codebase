import subprocess
import fitz
from typing import Dict, Any
from .ocr_tables import ocr_tables_from_pdf

def extract_text_pymupdf(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    texts = [page.get_text() for page in doc]
    return "\n".join(texts)

def pdftotext_fallback(pdf_path: str) -> str:
    try:
        out = subprocess.check_output(["pdftotext", pdf_path, "-"], stderr=subprocess.DEVNULL)
        return out.decode("utf-8", errors="ignore")
    except Exception:
        return ""

def parse_pdf(pdf_path: str, use_paddle_ocr=True) -> Dict[str, Any]:
    text = extract_text_pymupdf(pdf_path) or pdftotext_fallback(pdf_path)
    if use_paddle_ocr:
        ocr_tables = ocr_tables_from_pdf(pdf_path, lang="vie")
        if ocr_tables.strip():
            text = text + "\n\n# OCR_TABLES\n" + ocr_tables
    return {"path": pdf_path, "text": text, "meta": {}}
