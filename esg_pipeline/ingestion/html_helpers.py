import re
from typing import List, Dict, Any
from urllib.parse import urljoin

BASE = "https://finance.vietstock.vn"
DOWNLOAD_PREFIX = "/downloadedoc/"
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
