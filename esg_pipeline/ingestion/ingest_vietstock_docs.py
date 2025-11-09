import argparse, asyncio, json, os, re, csv, time
from pathlib import Path
from urllib.parse import urljoin
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any

import pandas as pd
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from slugify import slugify
from playwright.async_api import async_playwright, TimeoutError as PWTimeout
import zipfile

try:
    from tqdm import tqdm
    HAS_TQDM = True
except Exception:
    HAS_TQDM = False

try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except Exception:
    HAS_FITZ = False

BASE = "https://finance.vietstock.vn"
DOC_PAGE_TMPL = "{base}/{symbol}/tai-tai-lieu.htm?doctype="
DOWNLOAD_PREFIX = "/downloadedoc/"
YEAR_RE = re.compile(r"(?<!\d)(20\d{2}|19\d{2})(?!\d)")
DATE_RE = re.compile(r"(\d{1,2}[/-]\d{1,2}[/-](\d{2,4}))", re.I)

DOC_TYPE_KEYWORDS = {
    "báo cáo tài chính": "Financial Statements",
    "giải trình": "P&L Explanation",
    "báo cáo quản trị": "Governance Report",
    "báo cáo thường niên": "Annual Report",
    "nghị quyết": "AGM Resolution",
    "tài liệu đhđcđ": "AGM Documents",
    # en
    "financial statements": "Financial Statements",
    "governance report": "Governance Report",
    "annual report": "Annual Report",
    "resolutions of agm": "AGM Resolution",
    "documents of agm": "AGM Documents",
}

YEAR_RE = re.compile(r"(?<!\d)(20\d{2}|19\d{2})(?!\d)")
DATE_RE = re.compile(r"(\d{1,2}[/-]\d{1,2}[/-](\d{2,4}))", re.I)

def parse_links_from_html(html: str) -> List[Dict[str, Any]]:
    """
    Lightweight HTML link parser to extract document links and nearby metadata from a
    Vietstock-like HTML snippet. Dependency-free so it can be unit-tested without
    Playwright or other heavy runtime dependencies.
    """
    links: List[Dict[str, Any]] = []
    anchor_re = re.compile(r'<a[^>]+href=["\'](?P<href>[^"\']+)["\'][^>]*?(?:title=["\'](?P<title>[^"\']*)["\'])?[^>]*>(?P<inner>.*?)</a>', re.S | re.I)
    span_lastupdate_re = re.compile(r'<span[^>]*class=["\'][^"\']*lastupdate[^"\']*["\'][^>]*>(?P<date>[^<]+)</span>', re.I)

    for m in anchor_re.finditer(html):
        href = m.group('href')
        title_attr = m.group('title') or ''
        inner = m.group('inner') or ''

        inner_text = re.sub(r'<[^>]+>', ' ', inner).strip()
        title_text = (title_attr.strip() or inner_text).strip()

        posted_raw = None
        s = span_lastupdate_re.search(inner)
        if s:
            posted_raw = s.group('date').strip()
        else:
            post_chunk = html[m.end(): m.end()+200]
            s2 = span_lastupdate_re.search(post_chunk)
            if s2:
                posted_raw = s2.group('date').strip()

        ctx_start = max(0, m.start()-200)
        ctx_end = min(len(html), m.end()+200)
        context = re.sub(r'\s+', ' ', html[ctx_start:ctx_end]).strip()

        myear = YEAR_RE.search((context or '') + ' ' + title_text)
        year = int(myear.group(1)) if myear else None

        full = urljoin(BASE, href)

        href_l = href.lower()
        is_download_proxy = DOWNLOAD_PREFIX in href
        is_static_file = any(ext in href_l for ext in ['.pdf', '.zip', '.csv', '.xlsx', '.xls', '.doc', '.docx']) or 'static2.vietstock.vn' in href_l or '/data/' in href_l
        if not (is_download_proxy or is_static_file):
            continue

        links.append({
            'url': full,
            'title': title_text,
            'context': context,
            'posted_date_raw': posted_raw,
            'year_guess': year
        })

    return links

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
    esg_hint: Optional[str] = None
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
        return "G"
    return None

def sanitize_filename(s: str) -> str:
    s = s.strip().replace("\n", " ").replace("\r", " ")
    s = re.sub(r"\s+", " ", s)
    return slugify(s)[:180] or "document"

def _pick_ext_from_headers(url: str, headers: Dict[str, str], default: str = ".pdf") -> str:
    ct = (headers.get("Content-Type") or "").lower()
    cd = (headers.get("Content-Disposition") or "").lower()

    def has(name: str) -> bool:
        return (name in ct) or (name in cd)

    if has("pdf"):
        return ".pdf"
    if has("csv"):
        return ".csv"
    if has("excel") or has("sheet") or has("xlsx"):
        return ".xlsx"
    if has("msword") or re.search(r"\bdoc(;|,|$|\b)", ct):
        return ".doc"
    if has("wordprocessingml") or ".docx" in cd:
        return ".docx"
    if has("zip"):
        return ".zip"
    if has("rar"):
        return ".rar"

    # fallback by URL
    m = re.search(r"\.([a-z0-9]{2,5})(?:$|\?)", url.lower())
    if m:
        return f".{m.group(1)}"
    return default

@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=1, max=15),
       retry=retry_if_exception_type((httpx.HTTPError,)))
async def download_file(client: httpx.AsyncClient, url: str, out_stub: Path) -> tuple[int, Path]:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ESG-ThesisBot/1.0)",
        "Referer": BASE
    }
    print(f"    Downloading from {url}...")
    async with client.stream("GET", url, headers=headers, timeout=90) as r:
        r.raise_for_status()
        ext = _pick_ext_from_headers(url, r.headers, default=".pdf")
        out_path = out_stub.with_suffix(ext)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        bytes_written = 0
        total = int(r.headers.get("Content-Length") or 0)
        # Use tqdm if available for a nicer progress bar
        if HAS_TQDM:
            with open(out_path, "wb") as f, tqdm(total=total, unit='B', unit_scale=True, desc=out_path.name, leave=False) as pbar:
                async for chunk in r.aiter_bytes():
                    f.write(chunk)
                    bytes_written += len(chunk)
                    pbar.update(len(chunk))
        else:
            with open(out_path, "wb") as f:
                async for chunk in r.aiter_bytes():
                    f.write(chunk)
                    bytes_written += len(chunk)
                    if bytes_written % (1024*1024) == 0:  # every MB
                        print(f"    Downloaded: {bytes_written/1024/1024:.1f}MB", end="\r")
    if not HAS_TQDM:
        print(f"    Total downloaded: {bytes_written/1024/1024:.1f}MB")
    return bytes_written, out_path

async def _collect_downloads_on_current_page(page, links_seen: Dict[str, Dict[str, Any]]):
    # Collect anchors that either use the /downloadedoc/ proxy or are direct static file links
    anchors = await page.locator('a[href]').all()
    for a in anchors:
        try:
            href = await a.get_attribute("href")
            if not href:
                continue

            href_l = href.lower()
            is_download_proxy = DOWNLOAD_PREFIX in href
            is_static_file = any(ext in href_l for ext in ['.pdf', '.zip', '.csv', '.xlsx', '.xls', '.doc', '.docx']) or 'static2.vietstock.vn' in href_l or '/data/' in href_l
            if not (is_download_proxy or is_static_file):
                continue

            full = urljoin(BASE, href)
            if full in links_seen:
                continue

            # Prefer explicit title attribute if present, otherwise the visible text
            title_attr = await a.get_attribute('title')
            title_text = (title_attr or (await a.inner_text() or "")).strip()

            # Try to capture posted date from nearby DOM if available
            # Many Vietstock anchors include a sibling span with class 'doc__ttl--lastupdate'
            posted_raw = None
            try:
                # check sibling span
                span = a.locator("xpath=following-sibling::span[contains(@class,'lastupdate')][1]")
                if await span.count() > 0:
                    posted_raw = (await span.first.inner_text() or '').strip()
            except Exception:
                posted_raw = None

            # Fallback: look at ancestor block text for dates and context
            parent = a.locator("xpath=ancestor-or-self::*[position()<=3]").first
            text_blob = await parent.inner_text() if parent else await a.inner_text()
            if posted_raw is None:
                mdate = DATE_RE.search(text_blob or "")
                posted_raw = mdate.group(1) if mdate else None

            myear = YEAR_RE.search((text_blob or "") + " " + title_text)
            year = int(myear.group(1)) if myear else None

            links_seen[full] = {
                "url": full,
                "title": title_text,
                "context": text_blob,
                "posted_date_raw": posted_raw,
                "year_guess": year
            }
        except Exception:
            continue

async def _open_folders_and_collect(page, links_seen: Dict[str, Dict[str, Any]]):
    # Các mục có icon folder chứa nhiều tệp đính kèm
    folder_icons = await page.locator("i[class*='folder'], i.fa-folder, span[class*='folder']").all()
    for ic in folder_icons:
        try:
            row = ic.locator("xpath=ancestor::tr[1] | xpath=ancestor::li[1] | xpath=ancestor::div[contains(@class,'row')][1]").first
            await row.click()
            # chờ modal/khối mở và thu link
            await page.wait_for_timeout(600)
            await _collect_downloads_on_current_page(page, links_seen)
            # thử đóng modal nếu có
            for sel in [".modal.show button.close", ".modal.show .btn:has-text('Đóng')",
                        "button[aria-label='Close']"]:
                if await page.locator(sel).count() > 0:
                    await page.locator(sel).first.click()
                    await page.wait_for_timeout(300)
                    break
        except Exception:
            continue

async def collect_all_pages(page, max_pages: int = 200, max_wait: int = 20) -> List[Dict[str, Any]]:
    await page.wait_for_load_state("domcontentloaded")
    links_seen: Dict[str, Dict[str, Any]] = {}
    page_idx = 0
    while page_idx < max_pages:
        await _collect_downloads_on_current_page(page, links_seen)
        await _open_folders_and_collect(page, links_seen)

        # tìm nút next
        next_clicked = False
        for sel in [
            "a[aria-label*='Next']", "a[title*='Sau']", "a.page-link[rel='next']",
            "li.next a", "a:has(i.fa-angle-right)", "a:has-text('›')", "a:has-text('»')"
        ]:
            loc = page.locator(sel).first
            try:
                if await loc.count() > 0 and await loc.is_enabled():
                    await loc.click()
                    await page.wait_for_timeout(800)
                    await page.wait_for_load_state("domcontentloaded")
                    next_clicked = True
                    break
            except Exception:
                continue
        if not next_clicked:
            break
        page_idx += 1

    return list(links_seen.values())

async def ingest_symbol(symbol: str, out_dir: Path, max_wait: int = 25,
                        pdf_text: bool = False, only_year_from: Optional[int] = None,
                        doctype_filters: Optional[List[str]] = None) -> List[DocMeta]:
    url = DOC_PAGE_TMPL.format(base=BASE, symbol=symbol.lower())
    out_dir.mkdir(parents=True, exist_ok=True)

    # Phase 1: Crawl all document metadata from web UI
    print(f"\n[*] Phase 1: Crawling document list for {symbol}...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        page = await ctx.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)

        items = await collect_all_pages(page, max_pages=200, max_wait=max_wait)

        await ctx.close()
        await browser.close()

    # Pre-process all items to extract doctype, year etc. before downloading
    print("[*] Processing metadata...")
    processed_items = []
    for it in items:
        href = it["url"]
        m = re.search(r"/downloadedoc/(\d+)", href)
        doc_id = m.group(1) if m else re.sub(r"\W+", "", href)[-10:]
        title = it.get("title") or f"document-{doc_id}"
        context = (it.get("context") or "") + " " + (title or "")
        doctype = guess_doctype_from_context(context)
        year = it.get("year_guess")
        # Try to find year in various places if not found
        for pat in [title, it.get("posted_date_raw"), context]:
            if pat and not year:
                my = YEAR_RE.search(pat)
                if my:
                    try:
                        year = int(my.group(1))
                        break
                    except:
                        pass

        if only_year_from and year and year < only_year_from:
            continue
        # filter by doctype if requested (case-insensitive substring match against doctype/title/context)
        if doctype_filters:
            filters = [f.lower() for f in doctype_filters]
            hay = " ".join([str(doctype or ""), str(title or ""), str(context or "")]).lower()
            if not any(f in hay for f in filters):
                continue
        
        processed_items.append({
            "doc_id": doc_id,
            "url": href,
            "title": title,
            "context": context,
            "doctype": doctype,
            "year": year,
            "posted_date_raw": it.get("posted_date_raw")
        })

    print(f"[+] Found {len(processed_items)} documents for {symbol}")
    
    # Phase 2: Download files and extract content
    print("\n[*] Phase 2: Downloading documents...")
    # Phase 2: Download files and extract content
    print("\n[*] Phase 2: Downloading documents...")
    client = httpx.AsyncClient(follow_redirects=True, timeout=90)
    metas: List[DocMeta] = []

    for it in processed_items:
        doc_id = it["doc_id"]
        href = it["url"]
        title = it["title"]
        doctype = it["doctype"]
        year = it["year"]

        doctype_folder = doctype or "Unknown"
        year_folder = str(year) if year else "UnknownYear"
        filedir = out_dir / symbol.upper() / doctype_folder / year_folder
        fname_stub = filedir / f"{sanitize_filename(title)}-{doc_id}"

        print(f"\n[*] Downloading: {title}")
        print(f"    URL: {href}")
        try:
            bytes_written, out_path = await download_file(client, href, fname_stub)
            final_path = str(out_path)
            print(f"[+] Saved to: {final_path}")
        except Exception as e:
            print(f"[-] Download failed: {str(e)}")
            metas.append(DocMeta(
                symbol=symbol.upper(), doc_id=doc_id, url=href, title=title,
                doctype_ui=doctype, year=year, posted_date_raw=it.get("posted_date_raw"),
                file_path=None, content_text_path=None, bytes=None,
                esg_hint=esg_hint_from_doctype(doctype)
            ))
            continue

        # If zip, optionally extract and create meta entries for contents.
        text_path = None
        if pdf_text and HAS_FITZ and final_path.lower().endswith(".pdf"):
            print("[*] Extracting text from PDF...")
            try:
                text_out = Path(final_path).with_suffix(".txt")
                with fitz.open(final_path) as doc:
                    out = [page.get_text("text") for page in doc]
                text_out.write_text("\n".join(out), encoding="utf-8")
                text_path = str(text_out)
                print(f"[+] Text saved to: {text_path}")
            except Exception as e:
                print(f"[-] Text extraction failed: {str(e)}")
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

        # Auto-unzip: if downloaded file is a zip, extract contents into a folder
        # next to the zip and append DocMeta entries for each extracted file.
        try:
            if final_path.lower().endswith('.zip'):
                zpath = Path(final_path)
                extract_dir = zpath.with_suffix('')
                extract_dir.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(zpath, 'r') as zf:
                    for info in zf.infolist():
                        # skip directories
                        if info.is_dir():
                            continue
                        extracted_name = info.filename
                        # sanitize and prevent path traversal
                        target = extract_dir / Path(extracted_name).name
                        with zf.open(info) as src, open(target, 'wb') as dst:
                            data = src.read()
                            dst.write(data)
                        # create a new meta entry for the extracted file
                        extracted_doc_id = f"{doc_id}_{Path(extracted_name).stem}"
                        extracted_bytes = len(data)
                        extracted_path = str(target)
                        extracted_text_path = None
                        if pdf_text and HAS_FITZ and extracted_path.lower().endswith('.pdf'):
                            try:
                                text_out = Path(extracted_path).with_suffix('.txt')
                                with fitz.open(extracted_path) as doc:
                                    out = [page.get_text('text') for page in doc]
                                text_out.write_text('\n'.join(out), encoding='utf-8')
                                extracted_text_path = str(text_out)
                            except Exception:
                                extracted_text_path = None

                        metas.append(DocMeta(
                            symbol=symbol.upper(),
                            doc_id=extracted_doc_id,
                            url=href,
                            title=f"{title} :: {Path(extracted_name).name}",
                            doctype_ui=doctype,
                            year=year,
                            posted_date_raw=it.get('posted_date_raw'),
                            file_path=extracted_path,
                            content_text_path=extracted_text_path,
                            bytes=extracted_bytes,
                            esg_hint=esg_hint_from_doctype(doctype)
                        ))
        except Exception:
            # non-fatal: if extraction fails, continue
            pass

    await client.aclose()
    return metas

def write_outputs(symbol: str, metas: List[DocMeta], out_dir: Path):
    meta_dir = out_dir / symbol.upper()
    meta_dir.mkdir(parents=True, exist_ok=True)
    jpath = meta_dir / f"{symbol.upper()}_vietstock_docs.jsonl"
    with open(jpath, "w", encoding="utf-8") as f:
        for m in metas:
            f.write(json.dumps(asdict(m), ensure_ascii=False) + "\n")
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
    ap.add_argument("--max-wait", type=int, default=25, help="Max seconds per page")
    ap.add_argument("--pdf-text", action="store_true", help="Extract PDF text with PyMuPDF")
    ap.add_argument("--year-from", type=int, default=None, help="Only keep docs with year >= this")
    ap.add_argument("--doctype", action="append", help="Filter by doctype/title/context (case-insensitive substring). Can be used multiple times")
    args = ap.parse_args()

    out_dir = Path(args.out)
    metas = asyncio.run(ingest_symbol(
        symbol=args.symbol,
        out_dir=out_dir,
        max_wait=args.max_wait,
        pdf_text=args.pdf_text,
        only_year_from=args.year_from,
        doctype_filters=args.doctype
    ))
    write_outputs(args.symbol, metas, out_dir)

if __name__ == "__main__":
    main()
