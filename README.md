# ESG Thesis Codebase — End-to-End Pipeline (Banks, VN)

This repository provides a **production-grade, end-to-end** ESG data pipeline for Vietnamese banks: from **PDF ingestion → OCR/text/table extraction → heuristic & LLM-assisted KPI extraction → schema mapping (IFRS S1/S2, GRI, OECD) → data quality & coverage audit → feature store → ML (XGBoost) with **SHAP** explainability → API & Streamlit dashboard**.

> No fake data. You run this on **real annual/sustainability reports** (PDF) by providing bank names and URLs. The pipeline is deterministic for heuristic steps and configurable for LLM extraction.

## 1) Quickstart

### Option A — Conda (Windows/macOS/Linux)
```bash
conda env create -f environment.yml
conda activate esg-thesis-codebase
# Install system deps if needed:
# - Windows: install Tesseract OCR (https://github.com/UB-Mannheim/tesseract/wiki) and add to PATH
# - macOS: brew install tesseract
#           brew install poppler
# - Linux: apt-get install -y tesseract-ocr poppler-utils
python -m pip install -e .
```

### Option B — Pip (if you already have Python 3.10)
```bash
python -m venv .venv && source .venv/bin/activate  # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pip install -e .
```

### Configure LLM (optional)
Export your key if using OpenAI:
```bash
export OPENAI_API_KEY=sk-...    # Windows PowerShell: $Env:OPENAI_API_KEY="sk-..."
```
Or **Ollama** (local):
```bash
ollama pull qwen2.5:7b-instruct
# set in config/config.yaml: extraction.llm.provider=ollama
```

### ingess data from page vietstock: 
```bash
# 1) Tạo venv + cài phụ thuộc
python -m venv .venv && . .venv/bin/activate  # (Windows: .venv\Scripts\activate)
pip install playwright httpx pandas pymupdf tenacity python-slugify tqdm
python -m playwright install chromium

# 2) Chạy ingest TPBank
python ./esg_pipeline/ingestion/ingest_vietstock_docs.py --symbol TPB --out ./data/raw --max-wait 25 --pdf-text
# điều chỉnh doc-type để lấy dữ liệu từ vietstock
python ./esg_pipeline/ingestion/ingest_vietstock_docs.py --symbol TPB --out ./data/raw --max-wait 25 --pdf-text

```

### Provide inputs
Edit `data/banks.csv` with **real** bank names, report URLs, and year. Example row is included.

### Run the full pipeline
```bash
python cli/main.py ingest --config config/config.yaml
python cli/main.py extract --config config/config.yaml --strategy heuristic
python cli/main.py extract --config config/config.yaml --strategy llm     # optional
# example using pip in venv
pip install -r requirements.txt
# ensure needed extras
pip install tenacity httpx playwright pymupdf tqdm python-slugify rapidfuzz
# install Playwright browsers (bắt buộc nếu dùng Playwright crawling)
python -m playwright install
python -m esg_pipeline.ingestion.ingest_vietstock_docs --symbol TPB --out ./data/raw --pdf-text --year-from 2018
python -m esg_pipeline.extraction.run_extract --symbol TPB --in ./data/raw --method llm --map --rules ./config/bank_rules.yaml --schema ./schema/esg_schema.json

python cli/main.py map --config config/config.yaml
python cli/main.py quality --config config/config.yaml
python cli/main.py store --config config/config.yaml
python cli/main.py model --config config/config.yaml
python cli/main.py shap --config config/config.yaml
```

Serve API and dashboard:
```bash
# REST API (FastAPI)
python cli/main.py serve --config config/config.yaml
# Streamlit dashboard
python cli/main.py dashboard --config config/config.yaml
```

## 2) Project Structure

```
esg_thesis/
  cli/main.py                    # single entrypoint for all stages
  config/config.yaml
  schema/esg_schema.csv|json     # parsed from your uploaded schema (IFRS/GRI-aligned)
  esg_pipeline/
    __init__.py
    schema.py                    # Pydantic models & loaders
    normalizer.py                # unit & numeric normalization
    utils.py                     # common helpers
    ingestion/
      pdf_downloader.py          # download PDFs from URLs
      pdf_parser.py              # text + table + OCR extraction
    extraction/
      heuristic.py               # regex/keyword rules + confidence
      llm.py                     # OpenAI/Ollama structured extraction
    mapping/
      mapper.py                  # fuzzy map → canonical schema fields
    quality/
      audit.py                   # coverage, confidence, duplicates
    storage/
      datalake.py                # parquet/csv writers + catalog
    modeling/
      features.py                # feature assembly
      train_xgb.py               # XGB model for financial targets
      explain_shap.py            # SHAP values/plots
    app/
      api.py                     # FastAPI app
      dashboard.py               # Streamlit analytics
  data/
    banks.csv                    # input list of bank reports (edit this!)
    raw/                         # downloaded PDFs
    interim/                     # parsed text jsonl / tables
    extracted/                   # KPI candidates (heuristic/llm)
    mapped/                      # mapped to schema
    quality/                     # metrics
    features/                    # ML features
    labels/                      # financials (ROA/ROE/NIM...) if available
  outputs/
    reports/                     # coverage reports, charts
    models/                      # trained models
    shap/                        # SHAP outputs
  docs/
    methodology.md               # scientific design & references
    api_contract.md              # REST API spec
  tests/
    test_normalizer.py
    test_mapper.py
  requirements.txt
  environment.yml
  pyproject.toml
  README.md
```

## 3) Scientific Method & Validity

- **Standards alignment:** schema parsed from your file aligns to **IFRS S1/S2, GRI 2021, OECD 2023, PCAF** (see `schema/`).  
- **Reproducibility:** deterministic heuristic rules (seeded), config versioned (`config.yaml`).  
- **No fake data:** pipeline requires **real PDFs**; LLM steps are optional and logged with prompts/outputs.  
- **Evaluation:** precision/recall for heuristic vs LLM can be computed if you fill `data/labels/gold.jsonl`.  
- **Explainability:** SHAP explanations for models predicting **financial targets** (e.g., ROA) from ESG features.

See full details in `docs/methodology.md`.

## 4) Minimal Commands (Windows friendly)

```powershell
# 1) Create env
conda env create -f environment.yml
conda activate esg-thesis

# 2) System deps (once)
# - Install Tesseract OCR for Windows (UB Mannheim build) and add to PATH
# - Optional: install Ghostscript for Camelot; or set tables.engine=stream

# 3) Run
python cli/main.py ingest
python cli/main.py extract --strategy llm
pip install pyyaml ollama pymupdf tenacity httpx tqdm python-slugify rapidfuzz
python -m esg_pipeline.extraction.run_extract \
  --symbol TPB \
  --in ./data/raw \
  --method llm \
  --provider ollama \
  --model qwen2.5:7b-instruct \
  --map \
  --rules ./config/bank_rules.yaml \
  --schema ./schema/esg_schema.json
python cli/main.py map
python cli/main.py quality
python cli/main.py store
python cli/main.py model
python cli/main.py shap
```
