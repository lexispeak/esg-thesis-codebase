import logging
from typing import List
try:
    from paddleocr import PaddleOCR
    _HAS_PADDLE = True
except Exception:
    _HAS_PADDLE = False

import fitz

def _grid_from_ocr(lines: List, y_tol=10):
    rows = {}
    for item in lines:
        box, (txt, conf) = item[0], item[1]
        ys = [p[1] for p in box]; xs = [p[0] for p in box]
        y = sum(ys)/len(ys); x = min(xs)
        ry = round(y / y_tol) * y_tol
        rows.setdefault(ry, []); rows[ry].append((x, txt.strip()))
    out = []
    for ry in sorted(rows.keys()):
        cells = [t for _, t in sorted(rows[ry], key=lambda z: z[0]) if t]
        if cells: out.append("\t".join(cells))
    return "\n".join(out)

def ocr_tables_from_pdf(pdf_path: str, lang="vie"):
    if not _HAS_PADDLE:
        logging.warning("PaddleOCR not installed. Skip OCR tables."); return ""
    ocr = PaddleOCR(lang=lang, use_angle_cls=True, show_log=False)
    doc = fitz.open(pdf_path)
    collected = []
    for page in doc:
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tf:
            tf.write(img_bytes); tf.flush()
            res = ocr.ocr(tf.name, cls=True)
        if not res or not res[0]: continue
        tsv = _grid_from_ocr(res[0])
        if tsv.strip(): collected.append(tsv)
    return "\n\n".join(collected)
