# REST API Contract (FastAPI)

- `POST /api/v1/ingest` {banks: [{name, year, url}]} → tải PDF
- `POST /api/v1/extract` {strategy: "heuristic"|"llm"} → trích xuất
- `POST /api/v1/map` → ánh xạ schema
- `GET  /api/v1/quality` → trả coverage/confidence
- `GET  /api/v1/records?bank=...&year=...` → bản ghi đã map
- `POST /api/v1/model/train` → huấn luyện từ `data/features + data/labels`
- `GET  /api/v1/model/shap?bank=...&year=...` → SHAP values
