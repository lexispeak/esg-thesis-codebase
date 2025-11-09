import os, io, json, logging
import fitz  # PyMuPDF
from typing import Dict, Any, List, Optional
import subprocess
import tempfile

def extract_text_pymupdf(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    texts = []
    for page in doc:
        texts.append(page.get_text())
    return "\n".join(texts)

def pdftotext_fallback(pdf_path: str) -> str:
    try:
        out = subprocess.check_output(["pdftotext", pdf_path, "-"], stderr=subprocess.DEVNULL)
        return out.decode("utf-8", errors="ignore")
    except Exception:
        return ""

def parse_pdf(pdf_path: str) -> Dict[str, Any]:
    text = extract_text_pymupdf(pdf_path)
    if not text.strip():
        text = pdftotext_fallback(pdf_path)
    return {
        "path": pdf_path,
        "text": text,
        "meta": {}
    }
