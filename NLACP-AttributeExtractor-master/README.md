# NLACP-AttributeExtractor

NLACP-AttributeExtractor là một hệ thống pipeline AI chuyên dụng được thiết kế nhằm tự động hóa quy trình trích xuất thuộc tính (Attribute) và xây dựng chính sách **Kiểm soát truy cập dựa trên thuộc tính (ABAC - Attribute-Based Access Control)** từ các câu mô tả chính sách bằng ngôn ngữ tự nhiên (NLACP). Hệ thống chuyển đổi các câu tiếng Anh phi cấu trúc thành các chính sách cấu trúc ABAC dưới định dạng JSON tiêu chuẩn.

Hệ thống được phát triển với sự kết hợp giữa kỹ thuật xử lý ngôn ngữ tự nhiên (NLP) tiên tiến, thuật toán gom cụm (Clustering) thông minh và quy trình xác thực có sự tham gia của con người (Human-in-the-Loop).

---

## 🚀 Các Tính Năng Chính

*   **Thuật toán trích xuất Môi trường (Environment) 3 Tầng:**
    *   **Tầng 1 (Trigger Phrase Detection):** Nhận diện các cụm từ kích hoạt môi trường dựa trên cấu trúc phân tích cú pháp phụ thuộc (Dependency Parsing) và danh sách Gazetteer.
    *   **Tầng 2 (Semantic Disambiguation):** Phân tách nhập nhằng ngữ nghĩa giữa thuộc tính Môi trường và Chủ thể/Đối tượng bằng kỹ thuật bao hàm cụm danh từ (Noun Phrase Containment).
    *   **Tầng 3 (Environment Classification):** Phân loại thuộc tính môi trường vào các nhóm cụ thể (Không gian vật lý/mạng, Thời gian, Điều kiện hành vi) và gán Namespace phân cấp.
*   **Kiến trúc Pipeline Điều khiển Tự động:** Tích hợp trích xuất tự động và gom cụm thuộc tính chỉ bằng một lệnh duy nhất.
*   **Gom cụm thuộc tính bằng DBSCAN:** Sử dụng thuật toán DBSCAN kết hợp với Word Vectors (`en_core_web_md`) để tự động phân cụm và chuẩn hóa các thuộc tính tương đồng.
*   **Interactive Verification (Human-in-the-Loop):** Giao diện dòng lệnh tương tác trực quan cho phép người dùng duyệt, chỉnh sửa kết quả máy chạy để tạo bộ dữ liệu chuẩn (Gold Standard).
*   **Hệ thống Đánh giá Toàn diện (F-Score):** Đo lường hiệu năng của mô hình thông qua các chỉ số Precision, Recall và F1-Score so với dữ liệu chuẩn.

---

## 🛠️ Công Nghệ Sử Dụng

*   **Ngôn ngữ lập trình:** Python 3.8+
*   **Framework NLP chính:** [spaCy](https://spacy.io/) (yêu cầu mô hình `en_core_web_md` để sử dụng Word Vectors)
*   **Học máy & Xử lý số liệu:** `scikit-learn`, `numpy` (cho thuật toán phân cụm DBSCAN)
*   **Kiểm thử:** `pytest`
*   **Đầu ra dữ liệu:** JSON cấu trúc phân cấp

---

## 📁 Cấu Trúc Dự Án

```text
NLACP-AttributeExtractor/
├── dataset/                        # Dữ liệu bổ trợ cấu hình & quan hệ
│   ├── predicate_property_map.json # Bản đồ ánh xạ thuộc tính quan hệ
│   └── relation_candidate.json     # Log của các ứng viên quan hệ và môi trường
├── outputs/                        # Thư mục đầu ra chạy dự án (Được sinh tự động)
│   ├── policies/
│   │   ├── policy_dataset.json       # Kết quả máy tự động trích xuất (RAW) - Bước 1
│   │   └── policy_dataset_gold.json  # Dữ liệu chuẩn Gold Standard (đã verify) - Bước 3A
│   ├── clusters/
│   │   └── attribute_clusters.json   # Kết quả phân cụm thuộc tính - Bước 2
│   ├── hierarchy/
│   │   └── namespace_hierarchy.json  # Cấu trúc cây Namespace phân cấp - Bước 2
│   └── logs/                         # File ghi chép nhật ký runtime
├── nlacp/                          # Mã nguồn lõi (Core Package)
│   ├── extraction/                 # Module NLP trích xuất (S-A-O, EnvExtractor 3 Tầng, ShortName)
│   ├── normalization/              # Module Chuẩn hóa (Namespace & DataType)
│   ├── mining/                     # Module Khai phá (DBSCAN Clustering & Namespace Hierarchy)
│   ├── evaluation/                 # Module Đánh giá (Tính toán Precision, Recall, F1)
│   ├── io/                         # Module hỗ trợ Đọc/Ghi tập tin
│   ├── utils/                      # Các tiện ích bổ trợ hệ thống
│   └── pipeline/                   # Khung Pipeline xử lý câu đơn/tập lệnh
├── scripts/                        # Các Script thực thi chính
│   ├── auto_extraction.py          # Trích xuất tự động hoàn toàn (Bước 1)
│   ├── att_extractor.py            # Chuẩn hóa thuộc tính & gom cụm DBSCAN (Bước 2)
│   ├── interactive_verification.py # Tạo dữ liệu chuẩn Gold Standard bằng CLI tương tác (Bước 3A)
│   ├── compute_fscore.py           # Đánh giá hiệu năng và tính F-Score (Bước 3B)
│   └── run_pipeline.py             # Script điều khiển chạy toàn bộ pipeline
├── debug_env.py                    # Script debug chi tiết từng bước trích xuất Env của 1 câu
├── diagnose_env.py                 # Script phân tích lý do bỏ sót Environment
├── find_missing_env.py             # Tìm các câu bị lệch Environment giữa RAW và Gold
├── test_isolation.py               # Kiểm thử nhanh độ cô lập của quy trình xử lý
├── Run.txt                         # Hướng dẫn chạy nhanh phác thảo
└── README.md                       # Tài liệu mô tả dự án chi tiết (File này)
```

---

## ⚙️ Hướng Dẫn Cài Đặt

### 1. Khởi tạo môi trường ảo (Virtual Environment)
Khuyến nghị tạo môi trường ảo riêng biệt để tránh xung đột thư viện:

```bash
# Tạo môi trường ảo
python -m venv venv

# Kích hoạt trên Windows (Command Prompt)
venv\Scripts\activate
# Hoặc trên Windows (PowerShell)
.\venv\Scripts\activate

# Kích hoạt trên macOS / Linux
source venv/bin/activate
```

### 2. Cài đặt các thư viện phụ thuộc
Cài đặt các gói thư viện cần thiết và mô hình spaCy bắt buộc:

```bash
pip install spacy scikit-learn numpy pytest
python -m spacy download en_core_web_md
python -m spacy download en_core_web_sm
```

---

## 📖 Hướng Dẫn Sử Dụng & Luồng Pipeline

Hệ thống cung cấp hai luồng hoạt động chính: **Luồng Chạy Pipeline Chính** (Tự động hoàn toàn) và **Luồng Đánh Giá Hiệu Năng** (Dùng Gold Standard).

### A. Luồng Pipeline Chính (Tự động hoàn toàn)

Luồng chạy chính nhận đầu vào là các câu chính sách từ bàn phím hoặc từ file `.txt`, sau đó thực hiện trích xuất thực thể và phân cụm thuộc tính.

```text
[Bàn phím / File .txt]
       │
       ▼
┌────────────────────────────────────────────────────────┐
│ BƯỚC 1: Tự động trích xuất (auto_extraction.py)        │
│ ➔ Tạo file: outputs/policies/policy_dataset.json      │
└───────────────────────┬────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────┐
│ BƯỚC 2: Gom cụm thuộc tính & Namespace (att_extractor.py)│
│ ➔ Tạo: outputs/clusters/attribute_clusters.json       │
│ ➔ Tạo: outputs/hierarchy/namespace_hierarchy.json     │
└────────────────────────────────────────────────────────┘
```

#### Cách 1: Chạy toàn bộ Pipeline bằng 1 lệnh duy nhất
Cách nhanh nhất để chạy cả Bước 1 và Bước 2:
```bash
# Nhập các câu trực tiếp từ bàn phím (nhập 'exit' hoặc 'done' để kết thúc)
python scripts/run_pipeline.py

# Hoặc truyền file chứa danh sách chính sách (mỗi dòng một câu)
python scripts/run_pipeline.py input_policies.txt
```

#### Cách 2: Chạy từng bước độc lập
Nếu bạn muốn chạy riêng biệt hoặc tùy chỉnh tham số:

*   **Bước 1: Trích xuất thô tự động**
    ```bash
    python scripts/auto_extraction.py
    # Hoặc từ file đầu vào
    python scripts/auto_extraction.py input_policies.txt
    ```
    *Đầu ra được lưu tại:* `outputs/policies/policy_dataset.json`.

*   **Bước 2: Chuẩn hóa, gom cụm & sinh Namespace**
    ```bash
    python scripts/att_extractor.py
    ```
    *Nếu muốn chạy Bước 2 bỏ qua phân cụm DBSCAN:*
    ```bash
    python scripts/att_extractor.py --no-cluster
    ```
    *Đầu ra được lưu tại:* `outputs/clusters/attribute_clusters.json` và `outputs/hierarchy/namespace_hierarchy.json`.

---

### B. Luồng Tạo Dữ Liệu Chuẩn & Đánh Giá (F-Score)

Luồng này hỗ trợ tinh chỉnh kết quả trích xuất để làm tập dữ liệu chuẩn (Gold Standard) phục vụ đánh giá thuật toán.

```text
┌──────────────────────────────────────┐
│ outputs/policies/policy_dataset.json  │ (RAW từ Bước 1)
└──────────────────┬───────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────────────────┐
│ BƯỚC 3A: Người dùng xác thực (interactive_verification.py)│
│ ➔ Tạo file: outputs/policies/policy_dataset_gold.json │
└──────────────────┬─────────────────────────────────────┘
                   │
                   ▼ [So sánh RAW vs GOLD]
┌────────────────────────────────────────────────────────┐
│ BƯỚC 3B: Tính toán F-Score (compute_fscore.py)         │
│ ➔ Trả ra các chỉ số: Precision, Recall, F1-Score       │
└────────────────────────────────────────────────────────┘
```

#### Bước 3A: Tạo Gold Standard qua CLI tương tác (Human-in-the-Loop)
Script sẽ duyệt qua từng câu đã chạy từ Bước 1 và hỏi người dùng có muốn chỉnh sửa các trường Subject, Action, Object, Environment hay không.
```bash
python scripts/interactive_verification.py
```
*   **Các phím tắt tương tác nhanh:**
    *   `y` hoặc `yes`: Tiến hành chỉnh sửa các trường của câu hiện tại.
    *   `n` hoặc `no`: Giữ nguyên kết quả trích xuất tự động và chuyển sang câu tiếp theo.
    *   `s` hoặc `skip`: Bỏ qua câu hiện tại (không lưu vào tập Gold).
    *   `q` hoặc `quit`: Lưu tiến trình hiện tại và thoát khỏi chương trình.
*   *Lưu ý:* Nếu bạn đã tắt script giữa chừng, bạn có thể tiếp tục verify từ câu đang dang dở bằng lệnh:
    ```bash
    python scripts/interactive_verification.py --resume
    ```

#### Bước 3B: Đo lường độ chính xác (F-Score)
So sánh file kết quả máy (`policy_dataset.json`) với file chuẩn (`policy_dataset_gold.json`) để đo lường hiệu năng của mô hình:
```bash
# Lệnh cơ bản
python scripts/compute_fscore.py

# Hiển thị chi tiết các câu bị trích xuất lỗi (Sai lệch thực tế so với Gold)
python scripts/compute_fscore.py --verbose

# Đánh giá chuyên sâu cho một trường cụ thể (Ví dụ: environment, subject, object, action)
python scripts/compute_fscore.py --field environment
```
> [!TIP]
> Trên môi trường Windows PowerShell, nếu gặp lỗi hiển thị ký tự UTF-8, hãy cấu hình mã hóa trước khi chạy:
> ```powershell
> $env:PYTHONIOENCODING="utf8"
> python scripts/compute_fscore.py --verbose
> ```

---

### C. Chạy Thử Nghiệm Nhanh (Quick Single-Sentence Test)

Nếu muốn test nhanh thuật toán trích xuất mà không cần đọc từ file hay lưu trữ cơ sở dữ liệu:

```bash
# Chạy quick test thông qua run_pipeline.py
python scripts/run_pipeline.py --sentence "A doctor can read patient records during the night shift."

# Hoặc chạy trực tiếp trên auto_extraction.py
python scripts/auto_extraction.py --sentence "A senior IT administrator can modify access control policies from the secure network."
```

---

## 🛠️ Công Cụ Hỗ Trợ Phân Tích & Gỡ Lỗi (Debugging)

Dự án cung cấp một số công cụ độc lập trong thư mục gốc giúp bạn gỡ lỗi chuyên sâu về thuật toán trích xuất Environment:

1.  **`debug_env.py`**: Chạy thử một câu cụ thể kèm theo vết log từng hàm nội bộ (monkey-patch trace) của `env_extractor.py` để tìm hiểu lý do tại sao trigger phrase được chấp nhận hoặc bị loại bỏ.
    ```bash
    python debug_env.py
    ```
2.  **`diagnose_env.py`**: Quét toàn bộ file kết quả `policy_dataset.json`, tìm ra những câu có chứa giới từ (preposition) chỉ thời gian/không gian nhưng bị thuật toán bỏ sót (skip) kèm theo nguyên nhân cụ thể (ví dụ: do bộ lọc từ PERSON_NOUN, do thiếu NER/hint từ, v.v.).
    ```bash
    python diagnose_env.py
    ```
3.  **`find_missing_env.py`**: So sánh trực tiếp giữa `policy_dataset.json` (RAW) và `policy_dataset_gold.json` (GOLD) để in ra danh sách tất cả các câu bị mất thuộc tính Môi trường (GOLD có trích xuất nhưng RAW của máy không phát hiện được).
    ```bash
    python find_missing_env.py
    ```

---

## 🆕 ABAC Policy v2.0 Parser - Hướng Dẫn Sử Dụng

Phiên bản mới này cung cấp một **Parser ABAC hoàn toàn** sử dụng **spaCy + Pydantic** để phân tích các câu chính sách tiếng Anh thành cấu trúc ABAC có schema chuẩn. Parser tự động trích xuất:
- **Subject** (chủ thể) với vai trò, loại, bậc, phòng ban
- **Action** (hành động) - ánh xạ động từ tự nhiên thành các phép toán CRUD tiêu chuẩn
- **Resource** (tài nguyên) - nhãn, loại dữ liệu, phạm vi
- **Environment** (môi trường) - hệ thống, thời gian, điều kiện
- **Condition** (điều kiện) - quan hệ, thời gian, trạng thái, ngưỡng, phê duyệt, v.v.

### Cài đặt thêm cho v2.0 Parser

```bash
# Cài đặt Pydantic v2
pip install pydantic>=2.13

# Tải mô hình spaCy cho venv (QUAN TRỌNG)
python -m spacy download en_core_web_sm
```

> **⚠️ QUAN TRỌNG:** Mô hình spaCy phải được tải trong **cùng virtual environment** mà bạn chạy parser, không phải system Python.

### Cách 1: Chạy Parser trên một câu đơn

**File Python:**
```python
from nlacp.pipeline.pipeline_v2 import parse_acp_sentence

# Parse một câu policy
sentence = "Civilian students can view their own scores in the academic information system."
policy = parse_acp_sentence(sentence, policy_id=1)

if policy:
    print(f"Authorization decision: {policy.authorization_decision}")
    print(f"Modality: {policy.policy_modality}")
    print(f"Subjects: {len(policy.subjects)}")
    print(f"Actions: {len(policy.actions)}")
    print(f"Resource: {policy.resource.label if policy.resource else 'None'}")
    print(f"ABAC Policy: {policy.abac_policy}")
else:
    print("Failed to parse")
```

**Chạy trên Terminal:**
```bash
python -c "
from nlacp.pipeline.pipeline_v2 import parse_acp_sentence
policy = parse_acp_sentence('Faculty can approve the grades in the system.')
# NLACP-AttributeExtractor (Cập nhật)

NLACP-AttributeExtractor là một pipeline Python để trích xuất cấu trúc chính sách ABAC từ văn bản chính sách tự nhiên, với trọng tâm hiện tại là "gom cụm Môi trường (Environment) và tổng hợp Subject/Action/Resource". Bản cập nhật hiện tại đã triển khai **Module 2** (gom cụm môi trường + tổng hợp bundle), tinh giản pipeline và loại bỏ các script legacy không còn sử dụng.

---

## Điểm nổi bật của phiên bản hiện tại

- Module 2: gom cụm môi trường (env-only clustering) bằng vector-distance (DBSCAN hoặc Agglomerative) và tổng hợp Subjects/Actions/Resources theo mỗi cụm môi trường.
- Chạy theo 2 bước rõ ràng: trích xuất thô (Bước 1) → gom cụm & tổng hợp (Bước 2, `run_module2.py`).
- CLI cho `run_module2.py` hỗ trợ: `--method`, `--eps`, `--min-samples`, `--n-clusters`, `--distance-threshold`.
- Adaptive clustering: tham số `eps` / `min_samples` tự động suy ra dựa trên kích thước và mật độ dữ liệu nếu không được cung cấp.
- Fallback greedy cosine grouping khi sklearn không khả dụng.
- Outputs được lưu trong `outputs/clusters/` với tên file chuẩn mới.

---

## Công nghệ chính

- Python 3.8+
- spaCy (thích `en_core_web_md`, fallback `en_core_web_sm`)
- scikit-learn, numpy
- pytest (cho test unit)

---

## Cấu trúc dự án (tóm tắt, đã chỉnh theo trạng thái hiện tại)

```text
NLACP-AttributeExtractor/
├── dataset/
├── outputs/
│   ├── policies/                 # đầu ra Bước 1
│   │   └── policy_dataset.json
│   ├── clusters/                 # đầu ra Module 2
│   │   ├── policy_bundles.json               # bundles sinh ra từ module xử lý
│   │   ├── env_context_clusters.json         # kết quả gom cụm môi trường (mapping)
│   │   ├── aggregate_policy_bundles.json     # bundles đã được tổng hợp theo cụm môi trường
│   │   └── cluster_report.md                 # báo cáo tóm tắt cụm
│   └── logs/
├── nlacp/                         # mã nguồn lõi (Module 2 nằm ở nlacp/module2.py)
├── scripts/
│   ├── auto_extraction.py          # Bước 1: trích xuất thô -> outputs/policies/policy_dataset.json
│   ├── run_module2.py              # Bước 2: gom cụm env + tổng hợp bundles (entrypoint Module 2)
│   ├── interactive_verification.py # Tạo/điều chỉnh Gold Standard (Bước 3A)
│   └── compute_fscore.py           # Đánh giá với Gold Standard (Bước 3B)
├── debug_env.py
├── diagnose_env.py
├── find_missing_env.py
└── README.md
```

> Lưu ý: các script cũ như `scripts/att_extractor.py`, `scripts/run_pipeline.py`, `scripts/test_parser_v2.py`, `_test_subjects.py` đã bị loại bỏ trong bản cập nhật này.

---

## Cài đặt nhanh

1) Tạo virtualenv và kích hoạt:

```bash
python -m venv venv
# PowerShell
.\venv\Scripts\Activate.ps1
# CMD
venv\Scripts\activate
```

2) Cài phụ thuộc và mô hình spaCy:

```bash
pip install -r requirements.txt || pip install spacy scikit-learn numpy pytest pydantic
python -m spacy download en_core_web_md || python -m spacy download en_core_web_sm
```

---

## Luồng chạy (hiện tại)

1) Bước 1 — Trích xuất thô (tạo `outputs/policies/policy_dataset.json`):

```bash
python scripts/auto_extraction.py [input_file.txt]
```

2) Bước 2 — Gom cụm môi trường và tổng hợp bundles (Module 2):

```bash
# Chạy với tham số tự động
python scripts/run_module2.py --method auto

# Ví dụ điều chỉnh tham số
python scripts/run_module2.py --method dbscan --eps 0.25 --min-samples 3
```

Kết quả lưu tại `outputs/clusters/`:
- `policy_bundles.json` — danh sách bundles trích xuất cho từng policy (nhiều bundle/1 policy)
- `env_context_clusters.json` — danh sách cụm môi trường và mapping từ text→cluster_id
- `aggregate_policy_bundles.json` — bundles đã gom theo cụm môi trường (subject/action/resource aggregated)
- `cluster_report.md` — báo cáo tóm tắt số lượng cụm, singletons, ví dụ mẫu

3) Bước 3A — Tạo Gold Standard (tùy chọn, CLI tương tác):

```bash
python scripts/interactive_verification.py
```

4) Bước 3B — Tính F-Score:

```bash
python scripts/compute_fscore.py
```

---

## Ghi chú vận hành & khuyến cáo

- Module 2 hiện chỉ gom cụm **Environment**; phần `subjects`, `actions`, `resources` được **tổng hợp** theo mỗi cụm (không gom cụm thêm). Điều này giúp tập trung phân tích bối cảnh (context) trước khi quyết định hợp nhất các chính sách ABAC.
- Tham số clustering có thể để `auto` để dùng heuristic nội bộ: median nearest-neighbor distance × multiplier cho `eps` và `min_samples` dựa trên log(N).
- Nếu gặp lỗi liên quan tới cấu trúc dữ liệu (ví dụ: `relation_pairs` là list thay vì dict), script `run_module2.py` có cơ chế chuẩn hoá đầu vào tự động.

---

## Muốn tôi làm gì tiếp?

- Commit thay đổi README vào git (tôi có thể thực hiện), hoặc
- Chạy một lần full pipeline với cluster opts cụ thể và gửi báo cáo mẫu, hoặc
- Mở một `aggregate_policy_bundles.json` mẫu để bạn duyệt.
Chọn: `commit` / `run` / `show-sample`.
Cảm ơn — cho tôi biết bước tiếp theo bạn muốn tôi làm.
