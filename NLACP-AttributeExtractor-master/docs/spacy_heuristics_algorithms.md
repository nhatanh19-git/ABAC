# Heuristic Fixes & Algorithm Updates cho NLACP Pipeline

Tài liệu này ghi chú các bản vá Thuật toán (Heuristic Rules) đã thiết lập để khắc phục các lỗi cố hữu của trình phân tích SpaCy (Dependency Parser) trên bộ dataset Policy. Nó giúp tránh việc làm hỏng luồng chạy của các sửa đổi sau này.

## 1. Lỗi SpaCy gộp toàn bộ câu thành 1 Object Noun Phrase (Bỏ qua Subject/Action)
**Trường hợp lỗi điển hình:**
> *"A teaching assistant modifies course grades in the lab."*

**Lý do lỗi (Root Cause):**
- Trình phân tích `spaCy` gán sai chức năng ngữ pháp (POS): chữ *"modifies"* bị gán thành danh từ (`NOUN`) với quan hệ `compound` ghép trực tiếp vào chữ *"grades"*.
- Toàn bộ mệnh đề bị gom thành Noun Phrase. Không có thẻ `VERB` nào, dẫn đến thuật toán `relation_candidate` không tìm được Subject.

**Thuật toán Fallback áp dụng tại `nlacp/extraction/relation_candidate.py`:**
- **Bước 1 (Dọn dẹp rác):** Quét các Actions mà spaCy dự đoán. Nếu action là một `NOUN` và cấu trúc text của nó không nằm trong danh sách hành động chuẩn mực của `crud_map` -> Xoá kết quả giả mạo này (`raw_actions.clear()`).
- **Bước 2 (Kích hoạt Fallback Map):** Nếu không tìm thấy Action hợp lệ, tra cứu mọi từ trong câu (bao gồm cả các từ đang bị gán là `NOUN`/`PROPN` hoặc `VERB` nhưng bị loại vì `dep_ == compound`) so với từ điển `fallback_verbs` (e.g., `{'modifies': 'modify', 'updates': 'update', 'creates': 'create', 'checks': 'check', ...}`).
- **Bước 3 (Gán lại Logic thành phần):**
  - **Action:** Gán từ vựng tìm được làm hành động gốc (ví dụ: `modify`, `check`).
  - **Subject:** Tìm kiếm lùi từ vị trí action (bên trái) để lấy danh từ đầu tiên gặp được làm chủ thể (ví dụ: `assistant`, `student`).
  - **Object (Trích xuất Noun Root chính xác):** Nếu từ action là một `compound`, tra cứu đệ quy lên `token.head` để vượt qua toàn bộ chuỗi các compound (ví dụ: `checks (compound) -> application (compound) -> status (ROOT)`). Từ đó chọn Head trên cùng (`status`) làm gốc của Object để hàm `_get_full_noun` có thể gom trọn vẹn Noun Phrase (`application status`) mà không làm suy hao từ ngữ. Nếu không, hướng về danh từ đầu tiên bên tay phải.

## 2. Lỗi Environment bị trộn lẫn vào Subject/Object Attributes
**Trường hợp lỗi điển hình:**
> *"An instructor updates a gradebook during the semester."*

**Lý do lỗi (Root Cause):**
- Hàm `_get_object_tokens` trong bộ quét Environment khi duyệt xuống cây dependency của "gradebook" đã duyệt lố sâu vào nhánh con `prep` -> `pobj` -> "semester".
- Hệ quả là từ "the semester" vừa là môi trường, vừa bị ghi danh là "object attributues".
- Lỗi thứ hai: thuật toán kiểm tra chồng chéo (overlap) trước đây đã kiểm tra giao thoa trên toàn bộ từ vựng. Ví dụ: *"An admissions officer... in the admissions office."* -> cụm từ *"admissions office"* có chung từ *"admissions"* với subject *"admissions officer"* nên bộ quét lầm tưởng nó là Subject Attribute và thẳng tay vứt bỏ Environment quý giá.

**Thuật toán Filter & Ngăn chặn chồng chéo (`auto_extraction.py` & `env_extractor.py`):**
1. **Duyệt nông (Shallow Parsing):** Tại `_get_object_tokens()`, nếu đang duyệt cây con mà đụng một giới từ thuộc Môi trường (`TEMPORAL_PREPS` / `SPATIAL_PREPS`), thuật toán lập tức **`break / continue`** để không ăn vào cụm từ chỉ không gian / thời gian.
2. **Khớp nối Head Noun (Pobj Check):** Ở khối điều kiện Reject của Env Extractor, thay vì kiểm tra bất kì từ nào (any words overlap), thuật toán bây giờ chỉ loại trừ Environment nếu **danh từ chính tả làm ngữ cảnh gốc (`pobj`)** thực sự xuất hiện trong Subject. Điều này cứu sống *"admissions office"* vì `office` không nằm trong *"admissions officer"*.
3. **Loại trừ chéo (Post-Extraction Filter):**
   - Đảo ngược thứ tự chạy: **Thực thi `extract_env_attributes` trước tiên!**
   - Tạo danh sách `Blocked Phrases` chứa tất cả các phần text của các môi trường tìm được.
   - Khi Relation Extractor và Attribute Extractor chạy, mọi cụm từ có độ giao thoa với `Blocked Phrases` đều tự động bị **loại trừ**.
   - Cắt gọt (Strip) các từ môi trường bị dư thừa và dính liền vào Subject hay Object sau cùng trước khi serialize ra `policy_dataset.json`.

---
**Quy tắc bảo trì thuật toán vĩnh viễn:**  
Không sửa hoặc loại bỏ những dòng có comment `FALLBACK` hoặc `NGĂN CHẶN` trong `relation_candidate.py` và `env_extractor.py`, trừ khi mô hình NLP cốt lõi được huấn luyện lại chuyên hóa hoàn toàn (retrained model) trên miền dữ liệu an điện toán đám mây.

## 3. Nguyên tắc Token Isolation — Cách ly thành phần

**Trường hợp lỗi điển hình:**
> *"A teaching assistant reviews submissions at night."*

**Lý do lỗi (Root Cause):**
- SpaCy gộp toàn bộ câu thành 1 Noun Phrase với `submissions` là ROOT. Các từ `teaching`, `assistant`, `reviews` đều bị gán là compound/amod của `submissions`.
- Fallback nhận diện đúng `reviews` là action → gán `submissions` là Object root.
- Hàm `_get_full_noun("submissions")` quét các compound children → thấy `teaching`, `assistant`, `reviews` → trả về *"teaching assistant reviews submissions"* làm Object! ❌
- Và subject chỉ lấy được *"assistant"* thay vì *"teaching assistant"* vì tree bị gom sai.

**Thuật toán Token Isolation áp dụng tại `nlacp/extraction/relation_candidate.py`:**

**3.1 — Tham số `exclude_indices` của `_get_full_noun`:**
- Hàm `_get_full_noun(token, exclude_indices=None)` nhận thêm tham số `exclude_indices` là tập hợp các `token.i` đã bị claim.
- Khi quét compound children, bỏ qua mọi token có `child.i in exclude_indices`.
- Kết quả: `_get_full_noun("submissions", {i_teaching, i_assistant, i_reviews})` → chỉ trả về `"submissions"`. ✅

**3.2 — `claimed_indices` kết hợp subject + action:**
```python
claimed_indices = {t.i for t in subject_tokens + action_tokens}
objects = [_get_full_noun(t, exclude_indices=claimed_indices) for t in obj_tokens]
```
*Đây là điểm thi hành chính của nguyên tắc: "token đã là subject/action thì không được vào object".*

**3.3 — Span-based Subject trong Fallback:**
- Khi fallback tìm action verb mà parse chính không có nsubj, hệ thống scan ngược từ action để gom **span liền kề** gồm NOUN/PROPN + modifier VERB/ADJ (amod/compound).
- Span text được build trực tiếp: `' '.join(t.text for t in span_toks)` → *"teaching assistant"*.
- String này được lưu vào `fallback_subject_str` và override `_get_full_noun` (vì cây bị hỏng không thể dùng compound children).
- Logic ưu tiên: nếu `fallback_subject_str` tồn tại VÀ không có `nsubj` dependency thực trong subject_tokens → dùng `fallback_subject_str`; ngược lại dùng `_get_full_noun` bình thường.

---
**Quy tắc bảo trì thuật toán vĩnh viễn:**  
Không sửa hoặc loại bỏ những dòng có comment `FALLBACK`, `Token Isolation`, hoặc `NGĂN CHẶN` trong `relation_candidate.py` và `env_extractor.py`, trừ khi mô hình NLP cốt lõi được huấn luyện lại chuyên hóa hoàn toàn (retrained model) trên miền dữ liệu an điện toán đám mây.
