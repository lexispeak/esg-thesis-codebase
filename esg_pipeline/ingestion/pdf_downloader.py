import os, requests, logging
from urllib.parse import urlparse
from typing import List, Dict

def download_many(rows: List[Dict], out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    saved = []
    for r in rows:
        url = r["report_url"]
        name = f'{r["bank"]}_{r["year"]}.pdf'.replace(" ", "_")
        path = os.path.join(out_dir, name)
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            with open(path, "wb") as f:
                f.write(resp.content)
            saved.append({"bank": r["bank"], "year": r["year"], "path": path})
        except Exception as e:
            logging.warning(f"Failed to download {url}: {e}")
    return saved
