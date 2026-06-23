NLACP-AttributeExtractor — HƯỚNG DẪN NGƯỜI DÙNG (CHI TIẾT)

Mục đích: tài liệu này hướng dẫn chi tiết cách cài đặt, vận hành, giải thích các thành phần chính trong chương trình và minh họa các lệnh chạy phổ biến.

1. Yêu cầu hệ thống
- Python >= 3.8 (khuyến nghị 3.8..3.11)
- RAM: tối thiểu 2GB, nếu dùng mô hình spaCy lớn hơn (md/lg) nên có nhiều RAM hơn.
- Kết nối Internet để tải mô hình spaCy lần đầu.

2. Chuẩn bị môi trường (Step-by-step)
2.1 Tạo virtual environment (Windows PowerShell):

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

(Trên CMD: `venv\Scripts\activate` — trên macOS/Linux: `source venv/bin/activate`)

2.2 Cài dependencies cơ bản:

```bash
# Nếu có file requirements.txt
pip install -r requirements.txt
# Nếu không, cài tay
pip install spacy scikit-learn numpy pytest pydantic
```

2.3 Tải mô hình spaCy (bắt buộc cho parsing):

```bash
python -m spacy download en_core_web_sm
# Nếu muốn dùng vector similarity (semantic clustering):
python -m spacy download en_core_web_md
```

2.4 Kiểm tra cài đặt nhanh:

```bash
python -c "import spacy; print(spacy.__version__)"
python -c "import pydantic; print('pydantic ok')"
```

3. Cấu trúc dự án và giải thích thành phần
(Đường dẫn tham chiếu là từ thư mục gốc của repo.)

- `nlacp/` — gói mã nguồn chính gồm nhiều module:
  - `nlacp/extraction/` — các extractor NLP:
    - `subject_extractor.py` — nhận diện chủ thể (subject), trả về danh sách Subject models hoặc tokens.
    - `action_extractor.py` — trích xuất verb/action và ánh xạ về `Operation` chuẩn.
    - `resource_extractor.py` — tìm đối tượng/resource của câu.
    - `env_extractor.py` — trình nhận diện môi trường (Environment). Đây là module quan trọng, gồm các bước: trigger phrase detection, semantic filtering, env-type classification và giá trị chuẩn hoá (ví dụ HH:MM).
    - `condition_extractor.py` — trích xuất điều kiện bổ trợ (conditions).
    - `relation_candidate.py` — (còn trong repo) phân tích candidate SA/OA pairs cho pipeline v1 (ngược dòng), một số hàm vẫn được reuse.

  - `nlacp/preprocessing/` — tiền xử lý câu: expand abbreviations, detect language, basic cleaning.
  - `nlacp/normalization/` — chuẩn hóa namespace, gợi short names, gán data types.
  - `nlacp/mining/` — clustering logic (DBSCAN / fallback) và cấu trúc namespace hierarchy builder.
  - `nlacp/io/` — đọc/ghi datasets, builder helper (`dataset_builder.py`).
  - `nlacp/pipeline/pipeline_v2.py` — Parser chính v2: chứa class `AcpParser` và helper module-level functions như `parse_acp_sentence`, `parse_acp_batch`, `parse_acp_json_batch`.
  - `nlacp/validation/schema_validator.py` — định nghĩa schema Pydantic (Policy, Subject, Action, Environment, PolicyDataset) và validator tiện ích.

- `scripts/` — entrypoints và công cụ:
  - `auto_extraction.py` — wrapper để chạy Parser v2 trên file hoặc câu đơn, viết output vào `outputs/policies/policy_dataset.json`.
  - `run_module2.py` — chạy module2: gom cụm environment và tổng hợp bundles (đọc file outputs/policies/policy_dataset.json và sinh outputs/clusters/*).
  - `interactive_verification.py` — CLI để người dùng verify/điều chỉnh các bản trích xuất (tạo Gold dataset).
  - `compute_fscore.py` — so sánh RAW vs GOLD và tính Precision/Recall/F1.

- `outputs/` — thư mục đầu ra (được tạo khi chạy):
  - `outputs/policies/policy_dataset.json` — RAW extraction
  - `outputs/policies/policy_dataset_gold.json` — Gold (sau verify)
  - `outputs/clusters/policy_bundles.json`, `env_context_clusters.json`, `aggregate_policy_bundles.json` — kết quả Module 2

- `test_isolation.py` — script demo nhanh, đã chỉnh để gọi `parse_acp_sentence` từ `pipeline_v2`.

4. Giải thích chi tiết `pipeline_v2` (parser)
- `AcpParser` (class):
  - Khởi tạo lazy-load spaCy (`en_core_web_sm`) và `PolicyValidator`.
  - `parse_sentence(sentence, policy_id, preprocess)`:
    - tiền xử lý (expand abbreviations, detect language), spaCy parsing
    - detect_effect_and_modality
    - extract_subjects_with_logical_op
    - extract_actions_with_logical_op
    - extract_resource
    - extract_env_attributes → chuyển sang `Environment` Pydantic model (chuyển đổi thời gian sang HH:MM nếu có)
    - extract_conditions_with_logical_op
    - format_policy_to_json → trả về `Policy` Pydantic
    - validate bằng `PolicyValidator`
  - `parse_batch`, `parse_batch_to_dataset` hỗ trợ xử lý danh sách câu và trả `PolicyDataset`.

- API module-level:
  - `parse_acp_sentence(sentence)` — thuận tiện cho gọi nhanh từ scripts.
  - `parse_acp_batch(domain, sentences)` — trả về `PolicyDataset`.

5. Hướng dẫn sử dụng chi tiết (Use Cases)

5.1. Chạy một câu đơn bằng Python REPL

```python
from nlacp.pipeline.pipeline_v2 import parse_acp_sentence
policy = parse_acp_sentence('A doctor can view patient records during night shift.', policy_id=1)
if policy:
    print(policy.json(indent=2, exclude_none=True))
```

5.2. Chạy extraction từ file (mỗi dòng 1 câu):

```bash
python scripts/auto_extraction.py input_policies.txt
# Kết quả: outputs/policies/policy_dataset.json
```

`auto_extraction.py` options: (xem header script) hỗ trợ `--sentence`, `--auto`, `--out` v.v.

5.3. Chạy Module 2 (gom cụm env + tổng hợp bundles)

```bash
# Tự động suy tham số
python scripts/run_module2.py --method auto

# Hoặc dùng DBSCAN với tham số cụ thể
python scripts/run_module2.py --method dbscan --eps 0.25 --min-samples 3
```

Kết quả nằm ở `outputs/clusters/`.

5.4. Tạo Gold Standard (CLI verify)

```bash
python scripts/interactive_verification.py
# Sử dụng flags: --resume để tiếp tục
```

5.5. Tính F-Score

```bash
python scripts/compute_fscore.py --verbose
```

6. Định dạng đầu ra & ví dụ mẫu
- `Policy` (Pydantic) JSON có các trường: `id`, `sentence`, `authorization_decision`, `policy_modality`, `subjects` (list), `actions` (list), `resource`, `environments` (list), `context` (conditions).

Ví dụ rút gọn:

```json
{
  "id": 1,
  "sentence": "A doctor can view patient records during night shift.",
  "authorization_decision": "permit",
  "policy_modality": "can",
  "subjects": [{"entity_type":"user","role":"doctor"}],
  "actions": [{"verb":"view","operation":"READ"}],
  "resource": {"entity_type":"record","label":"patient records"},
  "environments": [{"id":"env_1","env_type":"temporal","trigger_phrase":"during night shift","time_range":{"from":"20:00","to":"06:00"}}]
}
```

7. Troubleshooting (vấn đề phổ biến)
- Lỗi: `OSError: [E050] Can't find model 'en_core_web_sm'` → Chưa cài spaCy model. Chạy: `python -m spacy download en_core_web_sm` trong venv.
- Lỗi Pydantic validation: xem `nlacp/validation/schema_validator.py` để hiểu schema mong đợi; kiểm tra dữ liệu đầu vào trước khi pass cho formatter.
- Vấn đề encoding trên Windows PowerShell: đặt ` $env:PYTHONIOENCODING="utf8" ` trước khi chạy script có in ký tự UTF-8.

8. Phát triển & mở rộng
- Thêm extractor mới: implement trong `nlacp/extraction/`, tuân theo interface trả về tokens/objects tương tự các extractor hiện tại, cập nhật `pipeline_v2` để gọi.
- Thay đổi strategy clustering: chỉnh hoặc thêm module trong `nlacp/mining/` và thêm option `--method` cho `run_module2.py`.

9. Kiểm thử local
- Chạy unit tests: `pytest -q` (nếu có test cases)
- Chạy `python test_isolation.py` để xem output parser nhanh.

10. Lưu ý vận hành
- Luôn chạy trong virtualenv mà bạn đã cài spaCy models.
- Khi deploy lên server CI, tiền xử lý tải model spaCy có thể tốn thời gian — cân nhắc pre-download và cache model.

---

Nếu bạn muốn, tôi có thể:
- commit các thay đổi vào git (tôi sẽ thực hiện commit và push nếu bạn cho phép),
- chạy một ví dụ end-to-end trên máy này và gửi output mẫu,
- hoặc tạo thêm phần FAQ / Troubleshooting chi tiết hơn.

Hãy cho biết bạn muốn bước tiếp theo nào: `commit` / `run-sample` / `add-FAQ`.
