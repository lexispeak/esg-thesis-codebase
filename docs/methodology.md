# Phương pháp & Thiết kế khoa học

## Câu hỏi nghiên cứu
1) Có thể **tự động trích xuất** bộ chỉ tiêu ESG của ngân hàng Việt Nam từ báo cáo PDF một cách tin cậy không?  
2) Các chỉ tiêu **E/S/G** ảnh hưởng thế nào đến **kết quả tài chính** (ROA/ROE/NIM/CAR)?

## Thiết kế
- **Nguồn dữ liệu chính:** Báo cáo thường niên/Bền vững của ngân hàng (PDF).  
- **Chuẩn tham chiếu:** IFRS S1/S2 (2023), GRI (2021), OECD Corporate Governance (2023), PCAF.  
- **Lược đồ dữ liệu:** xem `schema/esg_schema.csv|json` (được parse từ file bạn cung cấp).  
- **Trích xuất:** 
  - Văn bản: PyMuPDF, pdfminer.
  - Bảng: Camelot (lattice/stream).
  - OCR fallback: Tesseract (vie+eng) cho ảnh/scan.
- **Chiến lược:** 
  - `heuristic`: regex, từ khóa, luật cấu trúc bảng.
  - `llm`: OpenAI/Ollama → prompt có cấu trúc, output JSON schema.
- **Ánh xạ:** RapidFuzz (token_sort/partial) → canonical field; chuẩn hoá đơn vị (tCO2e, kWh, m³, …).
- **Đảm bảo chất lượng:** coverage, confidence, kiểm tra đơn vị, kiểm tra outlier.
- **ML & giải thích:** XGBoost dự đoán **ROA** từ đặc trưng ESG, dùng **SHAP** để giải thích biến tác động.

## Không giả lập
- Không “random”. Toàn bộ giá trị KPI phải đến từ **báo cáo thật** hoặc ước lượng theo công thức rõ ràng (ví dụ PCAF khi có dư nợ theo ngành). LLM chỉ **hỗ trợ đọc hiểu**, không tự bịa con số.
