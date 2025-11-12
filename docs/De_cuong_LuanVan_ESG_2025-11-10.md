# ĐỀ CƯƠNG LUẬN VĂN
**Học viên:** Phạm Quang Thịnh 
**Chuyên ngành:** Khoa học Máy tính  
**Đề tài (tạm):** *Xây dựng Data Pipeline ESG cho ngân hàng Việt Nam và mô hình XAI giải thích điểm ESG bằng SHAP*  
**Ngày:** 2025-11-10

---

## 1. Đăt vấn đề
- Báo cáo ESG/Thường niên của ngân hàng Việt Nam phân tán, không chuẩn hóa, nhiều bảng/đồ thị/hình ảnh khó trích xuất tự động. Thường thì không có báo cáo ESG riêng, mà gần đây từ năm 2020 mới gộp một phần báo cáo phát triển bền vững làm một chương trong báo cáo thường niên. Trong báo cáo dữ liệu và các thuộc tính cho đánh gía ESG nằm rải rác trong báo cáo, dữ liệu chứa trong ảnh, biểu đồ, bảng, sơ đồ, văn bản. Số liệu và đơn vị không thống nhất giữa các tổ chức ngân hàng.
- Nhu cầu đánh giá minh bạch (Disclosure Quality), rủi ro khí hậu (IFRS S2) và quản trị (OECD 2023) tăng mạnh từ nhà đầu tư & cơ quan quản lý.
- Luận văn hướng tới: pipeline end‑to‑end thu thập → chuẩn hóa → đánh dấu chất lượng dữ liệu → huấn luyện mô hình → giải thích bằng SHAP.

## 2. Mục tiêu nghiên cứu
1) Xây dựng ESG Data Pipeline cho dữ liệu ngân hàng Việt Nam, thực nghiệm trên MacOS/Colab với các nguồn báo cáo công khai của các ngân hàng tại Việt Nam.  
2) Đề xuất bộ tiêu chí ESG (ưu tiên G) để đánh giá mức độ công bố & chất lượng minh bạch.  
3) Huấn luyện mô hình Machine Learning (XGBoost) dự đoán ESG score và phân tích tác động bằng SHAP.  
4) So sánh **baseline heuristic** vs **LLM‑assisted extraction** về độ phủ và độ chính xác trên tập báo cáo thật.

## 3. Câu hỏi nghiên cứu
- Q1: Những thuộc tính ESG nào (đặc biệt là G) phản ánh tốt nhất chất lượng ESG của ngân hàng?  
- Q2: Mức cải thiện khi dùng LLM kết hợp OCR cho bảng/hình/biểu đồ so với heuristic/regex thuần?  
- Q3: SHAP cho thấy nhóm yếu tố nào giải thích chính biến phụ thuộc (ESG‑Score)?

## 4. Phạm vi & Đối tượng
- Đối tượng: 30 ngân hàng thương mại Việt Nam (VCB, BID, CTG, TCB, MBB, ACB, VPB, HDB, TPB, STB...).  
- Tài liệu: Báo cáo thường niên/ESG/Quản trị 2015–2025 (tiếng Việt); tin tức tiêu cực liên quan quản trị/xã hội/môi trường.  
- Không bao gồm: dữ liệu tài chính chuyên sâu ngoài các chỉ số ngữ cảnh (ROA/ROE, NPL, CAR...).

## 5. Đóng góp dự kiến
- Bộ dữ liệu ESG ngân hàng VN (chuẩn hóa, có metadata & chất lượng).  
- Pipeline E2E reproducible (ingest → parse/extract → normalize → QA → features → train → explain).  
- Báo cáo SHAP minh bạch yếu tố ảnh hưởng theo nhóm chỉ tiêu E/S/G.

## 6. Phương pháp & Kiến trúc
- Thu thập: Playwright crawler (Vietstock/website ngân hàng), HTTPX tải PDF; quản lý queue & retry.  
- Trích xuất: PyMuPDF (text/blocks), PaddleOCR cho bảng ảnh, cấu trúc layout (tiêu đề/mục lục/bảng/biểu đồ).  
- Chuẩn hóa: Hàm chuẩn hóa số liệu, đơn vị, percent/absolute; kiểm tra tính nhất quán; ánh xạ về ESG schema.  
- LLM‑assisted: Prompt phân loại đoạn văn theo E/S/G, phát hiện mục tiêu/net zero, kiểm tra viện dẫn tiêu chuẩn (IFRS/GRI/TCFD).  
- Chất lượng dữ liệu: Coverage, completeness, consistency;
- So sánh: Heuristic vs LLM trên cùng tập báo cáo thật; thống kê độ phủ (recall của trường), độ chính xác (precision).  
- Mô hình XGBoost.
- Hạ tầng: Chạy được trên MacOS (Miniconda) và Google Colab (GPU/CPU).

## 7. Biến & Dữ liệu
- Tiêu chí: chọn từ E/S/G (ưu tiên Governance) và ngữ cảnh tài chính.  
- Nguồn: Báo cáo ngân hàng; chỉ số tài chính công bố định kỳ.

### 7.1. Phụ lục A — Danh mục chỉ tiêu (rút gọn)
**E:** `GHG_Scope1`, `GHG_Scope2`, `Energy_Consumption`, `Renewable_Energy_Share`, `Water_Consumption`, `Waste_Generated`, `Financed_Emissions_Total`.  
**S:** `Female_Board_Ratio`, `Employee_Count`, `Employee_Turnover`, `Customer_Complaints`, `Customer_Data_Breaches`.  
**G (ưu tiên):** `Board_Size`, `Board_Independence_Ratio`, `Board_Chair_CEO_Duality`, `Risk_Committee_Existence`, `ThirdParty_Assurance_ESG`, `Exec_Comp_Disclosure`, `ESG_Washing_Index`, `TCFD_Alignment_Level`.  
**Ngữ cảnh:** `ROA`, `ROE`, `CAR`, `NPL_Ratio`, `Bank_Size`.

> Ghi chú: Bộ schema đầy đủ >150 trường (E/S/G/Context/Text/Events/Graph) được duy trì kèm repository; bản rút gọn trên dùng cho train ban đầu.

## 8. Thực nghiệm & Đánh giá
- **Tập thử nghiệm:** ≥ 150 báo cáo (2020–2024), 30 ngân hàng × 5 năm.  
- **Metric trích xuất:** Field‑level precision/recall/F1; table‑cell accuracy với bảng chỉ tiêu.  
- **Metric mô hình:** MAE/RMSE cho dự đoán Disclosure_Quality; **SHAP summary** theo nhóm E/S/G; kiểm định khác biệt giữa heuristic vs LLM.  
- **Ablation:** bỏ từng nhóm biến (E/S/G/Context) để đo ảnh hưởng đến MAE và biến động SHAP.

## 9. Kế hoạch & Mốc thời gian
- **Tuần 1 (đến 2025‑11‑28):** Kho dữ liệu v0.1 (10 ngân hàng, 2023–2024); hoàn tất parser bảng + OCR; checklist chất lượng.  
- **Tuần 2 (đến 2025‑12‑05):** Hoàn tất ánh xạ schema; baseline heuristic; báo cáo độ phủ & sai số.  
- **Tuần 3 (đến 2025‑12‑12):** Tích hợp LLM‑assisted; benchmark heuristic vs LLM; nháp thước đo Disclosure_Quality.  
- **Tuần 4 (đến 2025‑12‑31):** Train mô hình lần 1; SHAP (global/local); soạn chương Phương pháp.  
- **Tháng 1/2026:** Bản thảo Kết quả; biểu đồ SHAP theo nhóm ngân hàng.  
- **Tháng 2/2026:** Bản luận văn gần hoàn thiện; xin phản biện nội bộ.  

## 10. Rủi ro
- **PDF phức tạp/ảnh nhiều:** dùng PaddleOCR + heuristic vị trí; fallback thủ công cho outliers.  
- **Dữ liệu thiếu/không đồng nhất:** gắn cờ `PCAF_Data_Quality`, `Units_Notes`; rule điền thiếu.  
- **Compute hạn chế:** tối ưu batch, cache layout, dùng Colab Pro khi cần.  
- **Định nghĩa chỉ số gây tranh luận:** cung cấp mô tả ngắn + ví dụ; mở phụ lục thước đo.

## 11. Yêu cầu góp ý từ thầy (checklist)
- Phạm vi ngân hàng & khung thời gian 2020–2024 có phù hợp không, có cần thêm các nguồn dữ liệu khác (Tin xấu)?  
- Định nghĩa Schema ESG đã phù hợp chưa?  
- Thiết kế thực nghiệm so sánh heuristic vs LLM đã đủ thuyết phục chưa?  
- Mốc thời gian có khả thi với khối lượng hiện tại?

## 12. Tài liệu tham khảo (sẽ cập nhật chi tiết trong bản chính)
- IFRS S1/S2 (Disclosure & Climate), GRI 2021, OECD 2023 Corporate Governance Principles, PCAF Global Standard, cùng các nghiên cứu liên quan XAI/SHAP trong ESG.

---

**Phụ lục B — Kiến trúc pipeline (tóm tắt)**  
Ingest → Parse (text/layout/OCR) → Normalize/Map → QA/Scoring → Feature Store → Train/Explain (SHAP) → Dashboard/Export.

**Trạng thái hiện tại:** Schema/ingest/parse nền tảng đã hoàn thiện cơ bản; đang hoàn thiện ánh xạ & thước đo chất lượng; chuẩn bị thực nghiệm heuristic vs LLM và SHAP.
