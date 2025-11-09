import argparse, os, csv, json, yaml, logging, pandas as pd
from esg_pipeline.utils import setup_logger, write_jsonl
from esg_pipeline.ingestion.pdf_downloader import download_many
from esg_pipeline.ingestion.pdf_parser import parse_pdf
from esg_pipeline.extraction.heuristic import extract as extract_heur
from esg_pipeline.extraction.llm import extract_with_llm
from esg_pipeline.mapping.mapper import map_to_schema
from esg_pipeline.quality.audit import audit_coverage

def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def cmd_ingest(args, cfg):
    setup_logger(cfg.get("log_level","INFO"))
    rows = []
    with open("data/banks.csv","r",encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader: rows.append(r)
    saved = download_many(rows, os.path.join(cfg["data_dir"], "raw"))
    print(f"Downloaded: {len(saved)} files")

def cmd_extract(args, cfg):
    data_dir = cfg["data_dir"]
    raw_dir = os.path.join(data_dir, "raw")
    interim_dir = os.path.join(data_dir, "interim")
    os.makedirs(interim_dir, exist_ok=True)
    for fn in os.listdir(raw_dir):
        if not fn.lower().endswith(".pdf"): continue
        pdf_path = os.path.join(raw_dir, fn)
        parsed = parse_pdf(pdf_path)
        text = parsed.get("text","")
        candidates = []
        if args.strategy == "heuristic":
            candidates = extract_heur(text)
        elif args.strategy == "llm":
            llmcfg = cfg["extraction"]["llm"]
            candidates = extract_with_llm(text, "schema/esg_schema.json", provider=llmcfg["provider"], model=llmcfg["openai_model"] if llmcfg["provider"]=="openai" else llmcfg["ollama_model"])
        out_path = os.path.join(data_dir, "extracted", f"{os.path.splitext(fn)[0]}.{args.strategy}.jsonl")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        write_jsonl(out_path, candidates)
        print("Extracted ->", out_path)

def cmd_map(args, cfg):
    data_dir = cfg["data_dir"]
    extr_dir = os.path.join(data_dir, "extracted")
    out_dir = os.path.join(data_dir, "mapped")
    os.makedirs(out_dir, exist_ok=True)
    for fn in os.listdir(extr_dir):
        if not fn.endswith(".jsonl"): continue
        in_path = os.path.join(extr_dir, fn)
        rows = [json.loads(l) for l in open(in_path, "r", encoding="utf-8") if l.strip()]
        mapped = map_to_schema(rows, "schema/esg_schema.json", threshold=cfg["mapping"]["fuzzy_threshold"])
        out_path = os.path.join(out_dir, fn.replace(".jsonl",".mapped.jsonl"))
        write_jsonl(out_path, mapped)
        print("Mapped ->", out_path)

def cmd_quality(args, cfg):
    data_dir = cfg["data_dir"]
    mapped_dir = os.path.join(data_dir, "mapped")
    reports_dir = os.path.join("outputs","reports")
    os.makedirs(reports_dir, exist_ok=True)
    for fn in os.listdir(mapped_dir):
        if not fn.endswith(".mapped.jsonl"): continue
        in_path = os.path.join(mapped_dir, fn)
        rows = [json.loads(l) for l in open(in_path,"r",encoding="utf-8") if l.strip()]
        q = audit_coverage(rows)
        out_path = os.path.join(reports_dir, fn.replace(".mapped.jsonl",".coverage.json"))
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(q, f, ensure_ascii=False, indent=2)
        print("Quality ->", out_path)

def cmd_store(args, cfg):
    # In this minimal example, mapped jsonl are the canonical records.
    print("Data stored as JSONL under data/mapped/*.mapped.jsonl")

def cmd_model(args, cfg):
    # Placeholder: requires user-provided labels in data/labels/financials.csv
    from esg_pipeline.modeling.features import assemble_features
    from esg_pipeline.modeling.train_xgb import train_xgb
    mapped_any = None
    # pick the first mapped file
    mp_dir = os.path.join(cfg["data_dir"], "mapped")
    for fn in os.listdir(mp_dir):
        if fn.endswith(".mapped.jsonl"):
            mapped_any = os.path.join(mp_dir, fn); break
    if not mapped_any:
        print("No mapped data found.")
        return
    X, labels = assemble_features(mapped_any, "data/labels/financials.csv")
    if X is None or labels is None or cfg["modeling"]["target"] not in labels.columns:
        print("Please provide labels with target column.")
        return
    y = labels[cfg["modeling"]["target"]]
    # align columns by intersection
    common = [c for c in X.columns if c in labels.columns]
    if not common:
        # simple demo: use all X columns after dropping non-numeric
        X = X.select_dtypes(include="number")
    else:
        X = labels[common]
    res = train_xgb(X, y)
    os.makedirs("outputs/models", exist_ok=True)
    import pickle
    with open("outputs/models/xgb.pkl","wb") as f:
        pickle.dump(res["model"], f)
    with open("outputs/models/metrics.json","w",encoding="utf-8") as f:
        json.dump(res["metrics"], f, indent=2)
    print("Model trained. Metrics:", res["metrics"])

def cmd_shap(args, cfg):
    import pickle, pandas as pd, json
    from esg_pipeline.modeling.features import assemble_features
    from esg_pipeline.modeling.explain_shap import shap_values
    model_path = "outputs/models/xgb.pkl"
    if not os.path.exists(model_path):
        print("Train model first.")
        return
    with open(model_path,"rb") as f:
        model = pickle.load(f)
    mapped_any = None
    mp_dir = os.path.join(cfg["data_dir"], "mapped")
    for fn in os.listdir(mp_dir):
        if fn.endswith(".mapped.jsonl"):
            mapped_any = os.path.join(mp_dir, fn); break
    X, _ = assemble_features(mapped_any, "data/labels/financials.csv")
    if X is None:
        print("No features.")
        return
    X = X.select_dtypes(include="number").fillna(0)
    sv, base = shap_values(model, X)
    os.makedirs("outputs/shap", exist_ok=True)
    with open("outputs/shap/values.json","w",encoding="utf-8") as f:
        json.dump({"base": base, "shape": [len(X), len(X.columns)]}, f, indent=2)
    print("SHAP computed. Save raw values in notebook if needed.")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/config.yaml")
    sub = ap.add_subparsers(dest="cmd")

    sub_ing = sub.add_parser("ingest")
    sub_ext = sub.add_parser("extract")
    sub_ext.add_argument("--strategy", choices=["heuristic","llm"], default="heuristic")
    sub_map = sub.add_parser("map")
    sub_q = sub.add_parser("quality")
    sub_s = sub.add_parser("store")
    sub_m = sub.add_parser("model")
    sub_sh = sub.add_parser("shap")
    sub_srv = sub.add_parser("serve")
    sub_dash = sub.add_parser("dashboard")

    args = ap.parse_args()
    cfg = load_config(args.config)

    if args.cmd == "ingest": cmd_ingest(args, cfg)
    elif args.cmd == "extract": cmd_extract(args, cfg)
    elif args.cmd == "map": cmd_map(args, cfg)
    elif args.cmd == "quality": cmd_quality(args, cfg)
    elif args.cmd == "store": cmd_store(args, cfg)
    elif args.cmd == "model": cmd_model(args, cfg)
    elif args.cmd == "shap": cmd_shap(args, cfg)
    elif args.cmd == "serve":
        import uvicorn
        uvicorn.run("esg_pipeline.app.api:app", host=cfg["serving"]["host"], port=cfg["serving"]["port"], reload=False)
    elif args.cmd == "dashboard":
        os.system("streamlit run esg_pipeline/app/dashboard.py")
    else:
        ap.print_help()

if __name__ == "__main__":
    main()
