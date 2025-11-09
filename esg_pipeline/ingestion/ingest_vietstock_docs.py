# ingest_vietstock_docs.py
import argparse, asyncio, json, os, re, csv, time, sys
from pathlib import Path
from urllib.parse import urljoin
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any

import pandas as pd
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from slugify import slugify

# Playwright
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

# PDF text extract (optional)
try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except Exception:
    HAS_FITZ = False

BASE = "https://finance.vietstock.vn"
DOC_PAGE_TMPL = "{base}/{symbol}/tai-tai-lieu.htm?doctype="  # giữ giống URL bạn đưa
DOWNLOAD_PREFIX = "/downloadedoc/"

# Tên loại tài liệu trên giao diện Vietstock để map sơ bộ -> phục vụ ESG (đặc biệt G)
DOC_TYPE_KEYWORDS = {
    "báo cáo tài chính": "Financial Statements",
    "giải trình": "P&L Explanation",
    "báo cáo quản trị": "Governance Report",
    "báo cáo thường niên": "Annual Report",
    "nghị quyết": "AGM Resolution",
    "tài liệu ĐHĐCĐ": "AGM Documents",
    # fallback tiếng Anh
    "financial statements": "Financial Statements",
    "governance report": "Governance Report",
    "annual report": "Annual Report",
    "resolutions of agm": "AGM Resolution",
    "documents of agm": "AGM Documents",
}

YEAR_RE = re.compile(r"(?<!\d)(20\d{2}|19\d{2})(?!\d)")
DATE_RE = re.compile(r"(\d{1,2}[/-]\d{1,2}[/-](\d{2,4}))")

@dataclass
class DocMeta:
    symbol: str
    doc_id: str
    url: str
    title: str
    doctype_ui: Optional[str]
    year: Optional[int]
    posted_date_raw: Optional[str]
    file_path: Optional[str]
    content_text_path: Optional[str]
    bytes: Optional[int]

    # hooks for ESG pipeline
    esg_hint: Optional[str] = None  # e.g., "G" if Governance-heavy
    source: str = "VietstockDocuments"
    ts_crawled: float = time.time()

def guess_doctype_from_context(text_blob: str) -> Optional[str]:
    x = (text_blob or "").lower()
    for k, v in DOC_TYPE_KEYWORDS.items():
        if k in x:
            return v
    return None

def esg_hint_from_doctype(doctype: Optional[str]) -> Optional[str]:
    if not doctype:
        return None
    d = doctype.lower()
    if "governance" in d or "agm" in d or "nghị quyết" in d or "quản trị" in d:
        return "G"
    if "annual report" in d or "báo cáo thường niên" in d:
        return "G"  # Annual report thường có phần G lớn; E/S có thể có nhưng chưa chắc nhất quán
    if "financial statements" in d:
        return None  # dùng cho baseline, không ESG core
    return None

def sanitize_filename(s: str) -> str:
    s = s.strip().replace("\n", " ").replace("\r", " ")
    s = re.sub(r"\s+", " ", s)
    return slugify(s)[:180] or "document"

@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=1, max=15),
       retry=retry_if_exception_type((httpx.HTTPError,)))
async def download_file(client: httpx.AsyncClient, url: str, out_path: Path) -> int:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ESG-ThesisBot/1.0; +https://example.local)",
        "Referer": BASE
    }
    async with client.stream("GET", url, headers=headers, timeout=60) as r:
        r.raise_for_status()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        bytes_written = 0
        with open(out_path, "wb") as f:
            async for chunk in r.aiter_bytes():
                f.write(chunk)
                bytes_written += len(chunk)
    return bytes_written

async def scroll_collect_download_links(page, max_wait: int = 20) -> List[Dict[str, Any]]:
    """
    Cuộn trang và bắt tất cả thẻ <a href="/downloadedoc/{id}"> cùng text lân cận (tiêu đề/ngày/loại).
    """
    # chờ phần thân trang hiện diện
    await page.wait_for_load_state("domcontentloaded")
    # cho JS render
    try:
        await page.wait_for_selector(f'a[href*="{DOWNLOAD_PREFIX}"]', timeout=max_wait*1000)
    except PWTimeout:
        # có thể cần tương tác: thử bấm các tab "Tài liệu cổ đông" nếu có
        pass

    last_height = 0
    same_count = 0
    links_seen = {}
    t0 = time.time()
    while True:
        anchors = await page.locator(f'a[href*="{DOWNLOAD_PREFIX}"]').all()
        for a in anchors:
            try:
                href = await a.get_attribute("href")
                if not href or DOWNLOAD_PREFIX not in href:
                    continue
                full = urljoin(BASE, href)
                if full in links_seen:
                    continue
                # lấy context xung quanh link để suy đoán tiêu đề/ngày/loại
                parent = a.locator("xpath=ancestor-or-self::*[position()<=3]").first
                text_blob = await parent.inner_text() if parent else await a.inner_text()
                title = await a.inner_text()
                # posted date (nếu có)
                mdate = DATE_RE.search(text_blob or "")
                year = None
                myear = YEAR_RE.search(text_blob or "")
                if myear:
                    try:
                        year = int(myear.group(1))
                    except:
                        year = None
                links_seen[full] = {
                    "url": full,
                    "title": (title or "").strip(),
                    "context": text_blob,
                    "posted_date_raw": mdate.group(1) if mdate else None,
                }
            except Exception:
                continue

        # cuộn xuống
        await page.evaluate("""() => { window.scrollBy(0, document.body.scrollHeight); }""")
        await page.wait_for_timeout(800)

        # kiểm tra dừng: nếu chiều cao không đổi nhiều lần, coi như hết
        height = await page.evaluate("() => document.body.scrollHeight")
        if height == last_height:
            same_count += 1
        else:
            same_count = 0
        last_height = height

        if same_count >= 4:
            break
        if time.time() - t0 > max_wait:
            break

    return list(links_seen.values())

async def ingest_symbol(symbol: str, out_dir: Path, max_wait: int = 25,
                        pdf_text: bool = False, only_year_from: Optional[int] = None) -> List[DocMeta]:
    url = DOC_PAGE_TMPL.format(base=BASE, symbol=symbol.lower())
    out_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
        page = await ctx.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)

        # Thu thập các link downloadedoc
        items = await scroll_collect_download_links(page, max_wait=max_wait)

        await ctx.close()
        await browser.close()

    client = httpx.AsyncClient(follow_redirects=True)
    metas: List[DocMeta] = []

    for it in items:
        href = it["url"]
        # trích doc_id
        m = re.search(r"/downloadedoc/(\d+)", href)
        doc_id = m.group(1) if m else re.sub(r"\W+", "", href)[-10:]
        title = it.get("title") or f"document-{doc_id}"
        context = (it.get("context") or "") + " " + (title or "")
        doctype = guess_doctype_from_context(context)
        year = None
        # ưu tiên năm gần title, nếu không thấy thì lấy từ posted_date hoặc context
        for pat in [title, it.get("posted_date_raw"), context]:
            if not pat: 
                continue
            myear = YEAR_RE.search(pat)
            if myear:
                try:
                    year = int(myear.group(1))
                    break
                except:
                    pass

        if only_year_from and year and year < only_year_from:
            continue

        # dựng path
        doctype_folder = doctype or "Unknown"
        year_folder = str(year) if year else "UnknownYear"
        filedir = out_dir / symbol.upper() / doctype_folder / year_folder
        fname = f"{sanitize_filename(title)}-{doc_id}"
        file_pdf = filedir / f"{fname}.pdf"  # mặc định .pdf, sẽ hiệu chỉnh theo header

        # tải file
        bytes_written = None
        final_path = None
        try:
            bytes_written = await download_file(client, href, file_pdf)
            final_path = str(file_pdf)
            # nếu không phải PDF, thử đoán từ header bằng request HEAD
            try:
                r = await client.head(href, timeout=30)
                ct = r.headers.get("Content-Type", "").lower()
                if "pdf" not in ct and not final_path.lower().endswith(".pdf"):
                    pass
                elif "pdf" not in ct and final_path.lower().endswith(".pdf"):
                    # rename theo content-type nếu cần (ví dụ xlsx)
                    if "excel" in ct or "sheet" in ct or "xlsx" in ct:
                        newp = file_pdf.with_suffix(".xlsx")
                        os.replace(file_pdf, newp)
                        final_path = str(newp)
            except Exception:
                pass
        except Exception as e:
            # ghi meta lỗi nhưng không dừng pipeline
            metas.append(DocMeta(
                symbol=symbol.upper(), doc_id=doc_id, url=href, title=title,
                doctype_ui=doctype, year=year, posted_date_raw=it.get("posted_date_raw"),
                file_path=None, content_text_path=None, bytes=None,
                esg_hint=esg_hint_from_doctype(doctype)
            ))
            continue

        text_path = None
        if pdf_text and HAS_FITZ and final_path and final_path.lower().endswith(".pdf"):
            try:
                text_out = Path(final_path).with_suffix(".txt")
                with fitz.open(final_path) as doc:
                    out = []
                    for page in doc:
                        out.append(page.get_text("text"))
                text_out.write_text("\n".join(out), encoding="utf-8")
                text_path = str(text_out)
            except Exception:
                text_path = None

        metas.append(DocMeta(
            symbol=symbol.upper(),
            doc_id=doc_id,
            url=href,
            title=title,
            doctype_ui=doctype,
            year=year,
            posted_date_raw=it.get("posted_date_raw"),
            file_path=final_path,
            content_text_path=text_path,
            bytes=bytes_written,
            esg_hint=esg_hint_from_doctype(doctype)
        ))

    await client.aclose()
    return metas

def write_outputs(symbol: str, metas: List[DocMeta], out_dir: Path):
    meta_dir = out_dir / symbol.upper()
    meta_dir.mkdir(parents=True, exist_ok=True)
    # JSONL
    jpath = meta_dir / f"{symbol.upper()}_vietstock_docs.jsonl"
    with open(jpath, "w", encoding="utf-8") as f:
        for m in metas:
            f.write(json.dumps(asdict(m), ensure_ascii=False) + "\n")
    # CSV
    cpath = meta_dir / f"{symbol.upper()}_vietstock_docs.csv"
    fields = list(asdict(metas[0]).keys()) if metas else [
        "symbol","doc_id","url","title","doctype_ui","year","posted_date_raw",
        "file_path","content_text_path","bytes","esg_hint","source","ts_crawled"
    ]
    with open(cpath, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for m in metas:
            w.writerow(asdict(m))
    print(f"[OK] Wrote metadata: {jpath} and {cpath}")

def main():
    ap = argparse.ArgumentParser(description="Ingest Vietstock Documents for a given symbol")
    ap.add_argument("--symbol", required=True, help="Stock code, e.g., TPB")
    ap.add_argument("--out", default="./data/raw", help="Output root dir")
    ap.add_argument("--max-wait", type=int, default=25, help="Max seconds to scroll+load")
    ap.add_argument("--pdf-text", action="store_true", help="Extract PDF text with PyMuPDF")
    ap.add_argument("--year-from", type=int, default=None, help="Only keep docs with year >= this")
    args = ap.parse_args()

    out_dir = Path(args.out)
    # Run
    metas = asyncio.run(ingest_symbol(
        symbol=args.symbol,
        out_dir=out_dir,
        max_wait=args.max_wait,
        pdf_text=args.pdf_text,
        only_year_from=args.year_from
    ))
    write_outputs(args.symbol, metas, out_dir)

if __name__ == "__main__":
    main()
