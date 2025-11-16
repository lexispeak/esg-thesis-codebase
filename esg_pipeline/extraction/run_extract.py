"""Run extraction (heuristic or LLM) over ingested Vietstock documents for a symbol.

Usage examples:
  python -m esg_pipeline.extraction.run_extract --symbol TPB

Outputs:
  - data/processed/<SYMBOL>_extracted.jsonl  (raw extractions)
  - data/processed/<SYMBOL>_mapped.jsonl     (mapped to schema, if mapping enabled)
"""
import argparse, json, os
from pathlib import Path
from typing import List, Dict, Any

from ..extraction import heuristic, llm
from ..mapping import mapper
from ..schema import load_schema_json

try:
    import fitz
    HAS_FITZ = True
except Exception:
    HAS_FITZ = False


def load_meta_lines(meta_path: Path) -> List[Dict[str, Any]]:
    out = []
    if meta_path.suffix == '.jsonl':
        with open(meta_path, 'r', encoding='utf-8') as f:
            for line in f:
                out.append(json.loads(line))
    else:
        # try csv
        import csv
        with open(meta_path, newline='', encoding='utf-8') as f:
            r = csv.DictReader(f)
            for row in r:
                out.append(row)
    return out


def extract_text_from_pdf(path: Path) -> str:
    if not HAS_FITZ:
        raise RuntimeError('PyMuPDF (fitz) not installed')
    t = []
    with fitz.open(path) as doc:
        for p in doc:
            t.append(p.get_text('text'))
    return '\n'.join(t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--symbol', required=True)
    ap.add_argument('--in', dest='indir', default='./data/raw')
    ap.add_argument('--rules', default='./config/bank_rules.yaml')
    ap.add_argument('--bank', default=None, help='Bank key for rules (e.g., TPB or mapping in rules)')
    ap.add_argument('--method', choices=['heuristic','llm'], default='heuristic')
    ap.add_argument('--schema', default='./schema/esg_schema.json')
    ap.add_argument('--provider', choices=['openai','ollama'], default=None,
                    help='LLM provider to use when --method=llm. If omitted, will prefer OLLAMA when OLLAMA_BASE_URL is set.')
    ap.add_argument('--model', default=None, help='Model name for the selected provider')
    ap.add_argument('--map', action='store_true', help='Map extractions to schema')
    args = ap.parse_args()

    # Auto-select provider if not passed: prefer Ollama when OLLAMA_BASE_URL is set
    if args.method == 'llm' and (args.provider is None):
        if os.environ.get('OLLAMA_BASE_URL'):
            args.provider = 'ollama'
        else:
            args.provider = os.environ.get('ESG_LLM_PROVIDER', 'openai')

    indir = Path(args.indir)
    meta_json = indir / args.symbol.upper() / f"{args.symbol.upper()}_vietstock_docs.jsonl"
    if not meta_json.exists():
        print(f'Cannot find metadata JSONL at {meta_json}. Did you run ingest?')
        return

    metas = load_meta_lines(meta_json)
    print(f'Loaded {len(metas)} metadata entries')

    out_dir = Path('data/processed')
    out_dir.mkdir(parents=True, exist_ok=True)

    extracted = []
    for m in metas:
        file_path = m.get('content_text_path') or m.get('file_path')
        if not file_path:
            continue
        p = Path(file_path)
        if p.exists() and p.suffix.lower() == '.txt':
            text = p.read_text(encoding='utf-8', errors='ignore')
        elif p.exists() and p.suffix.lower() == '.pdf':
            if not HAS_FITZ:
                print('PDF found but PyMuPDF not installed; skipping', p)
                continue
            text = extract_text_from_pdf(p)
        else:
            print('Skipping non-existing or unsupported file', p)
            continue

        if args.method == 'heuristic':
            hits = heuristic.extract(text, bank=args.bank or args.symbol.upper(), rules_path=args.rules)
        else:
                model = args.model
                # choose a default model per provider if not provided
                if model is None:
                    model = 'gpt-4o-mini' if args.provider=='openai' else 'qwen2.5:7b-instruct'
                hits = llm.extract_with_llm(text, schema_path=args.schema, provider=args.provider, model=model)

        for h in hits:
            # enrich with meta
            h['source_file'] = str(p)
            h['report_title'] = m.get('title')
            h['report_url'] = m.get('url')
            h['symbol'] = args.symbol.upper()
        extracted.extend(hits)

    out_raw = out_dir / f"{args.symbol.upper()}_extracted.jsonl"
    with open(out_raw, 'w', encoding='utf-8') as f:
        for e in extracted:
            f.write(json.dumps(e, ensure_ascii=False) + '\n')
    print('Wrote', out_raw)

    if args.map:
        schema = args.schema
        mapped = mapper.map_to_schema(extracted, schema)
        out_map = out_dir / f"{args.symbol.upper()}_mapped.jsonl"
        with open(out_map, 'w', encoding='utf-8') as f:
            for e in mapped:
                f.write(json.dumps(e, ensure_ascii=False) + '\n')
        print('Wrote', out_map)

if __name__ == '__main__':
    main()
