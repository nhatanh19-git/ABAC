# NLACP-AttributeExtractor

## Mô tả Dự án
NLACP-AttributeExtractor là một hệ thống pipeline AI chuyên dụng được thiết kế để tự động trích xuất các chính sách "Attribute-Based Access Control" (ABAC - Kiểm soát truy cập dựa trên thuộc tính) từ các câu chính sách bằng ngôn ngữ tự nhiên (NLACPs). Hệ thống chuyển đổi các câu tiếng Anh phi cấu trúc thành định dạng JSON ABAC có cấu trúc mà máy tính có thể đọc được.

Kiến trúc mới được cập nhật sử dụng **Thuật toán Trích xuất Môi trường 3 Tầng (3-Layer Algorithm)** và **Pipeline Tương tác 2 Bước (2-Step Interactive Pipeline)** nhằm đảm bảo độ chính xác cao, đồng thời phân lập chính xác các Thuộc tính Môi trường (Environment) khỏi các Thuộc tính Chủ thể/Đối tượng (Subject/Object).

---

## Tính năng Chính
- **Thuật toán 3 Tầng cho Environment:**
  - *Tầng 1:* Nhận diện Trigger Phrases (Dựa trên Dependency Parsing và Gazetteers).
  - *Tầng 2:* Phân tách ngữ nghĩa (Disambiguation) giữa Thuộc tính Môi trường và Thuộc tính Chủ thể/Đối tượng bằng cách kiểm tra Noun Phrase Containment.
  - *Tầng 3:* Phân loại (Classification) Environment (Không gian Vật lý/Mạng/Thiết bị, Thời gian, Điều kiện) và gán Namespace phân cấp.
- **Kiến trúc Pipeline 2 Bước Mới:**
  - *Bước 1:* Verification đồng thời SA (Subject Attribute), OA (Object Attribute) và ENV.
  - *Bước 2:* Dọn dẹp, chuẩn hóa, phân cụm DBSCAN và xây dựng cấu trúc ABAC cuối cùng.
- **Xác thực Human-in-the-Loop:** Giao diện Command Line tương tác cho phép người dùng xác nhận các ứng viên một cách toàn diện.
- **Cấu trúc ABAC Tự động:** Tự động suy luận Tên viết tắt (Short Name), Không gian tên (Namespace) và Kiểu dữ liệu (Data Type).
- **NLP Fallback Mạnh mẽ:** Cần `en_core_web_md` để sử dụng vector embeddings cho DBSCAN clustering.

---

## Công nghệ Sử dụng
- **Ngôn ngữ:** Python 3.8+
- **Framework NLP:** spaCy (`en_core_web_md` khuyến nghị để có Word Vectors chuẩn trị)
- **Machine Learning:** scikit-learn, numpy (cho thuật toán DBSCAN Clustering)
- **Định dạng Output:** JSON

---

## Cấu trúc Dự án
```text
NLACP-AttributeExtractor/
├── dataset/                        # Datasets (Input Annotations & Runtime JSON Outputs)
│   ├── relation_candidate.json     # Log của các ứng viên quan hệ và môi trường
│   └── policy_dataset.json         # Danh sách policy ABAC cuối cùng
├── nlacp/                          # Core Package (Mã nguồn lõi)
│   ├── extraction/                 # Các Module NLP trích xuất (S-A-O, EnvExtractor 3 Tầng)
│   ├── normalization/              # Module Chuẩn hóa (Namespace & DataType)
│   ├── mining/                     # Module Khai phá (DBSCAN Clustering & Hierarchy)
│   └── pipeline/                   # Pipeline nguyên bản (Single-pass test)
├── scripts/                        # Các Script thực thi chính
│   ├── auto_extraction.py          # Trích xuất tự động (không yêu cầu tương tác)
│   ├── interactive_verification.py # Xác thực ứng viên có sự tham gia của con người (Human-in-the-Loop)
│   ├── att_extractor.py            # Chuẩn hóa Attribute, Gán Namespace & Phân cụm
│   ├── compute_fscore.py           # Tính toán F-score, so sánh với tập dữ liệu Gold
│   └── run_pipeline.py             # Script chạy toàn bộ pipeline/tương tác
├── README.md                       # Tài liệu mô tả dự án
```

---

## Hướng dẫn Cài đặt

1. **Clone repository và di chuyển vào thư mục dự án:**
   ```bash
   git clone <repository-url>
   cd NLACP-AttributeExtractor
   ```

2. **Tạo và kích hoạt môi trường ảo (virtual environment):**
   ```bash
   python -m venv venv
   # Trên Windows:
   venv\Scripts\activate
   # Trên macOS/Linux:
   source venv/bin/activate
   ```

3. **Cài đặt các thư viện lõi & Mô hình ngôn ngữ:**
   ```bash
   pip install spacy scikit-learn numpy pytest
   python -m spacy download en_core_web_md
   ```

---

## Hướng dẫn Sử dụng & Lệnh Chạy

Hệ thống có thể được chạy tự động theo luồng thông qua `run_pipeline.py` hoặc chạy từng bước thủ công.

### 1. Chạy Toàn bộ Pipeline tự động
Lệnh cơ bản để chạy lần lượt **Bước 1** (Verification) và sau đó tự động chuyển sang **Bước 2** (Extraction & Clustering):
```bash
python scripts/run_pipeline.py
```
*(Bạn sẽ được yêu cầu nhập các câu chính sách từ bàn phím. Gõ `done` hoặc `exit` để kết thúc quá trình nhập nhập liệu).*

Nếu bạn đã có một file chứa sẵn các câu policy (mỗi câu một dòng), bạn có thể chạy dưới chế độ Batch Mode:
```bash
python scripts/run_pipeline.py input_policies.txt
```

### 2. Chạy Từng bước Thủ công

**Bước 1: Interactive Verification (Trích xuất & Xác thực Tương tác)**
Trích xuất Subject, Action, Object, SA/OA Candidates và ENV Candidates bằng Thuật toán 3 Tầng. Yêu cầu người dùng xác nhận dữ liệu (y/n/a/s).
```bash
python scripts/interactive_verification.py

```

**Bước 2: Attribute Extraction & Clustering**
Phân tích file `policy_dataset.json` đã được xác nhận (từ Bước 1). Tự động chuẩn hóa Namespace phân cấp (VD: `environment.time.working_period`), Data Types, tạo Short Name và gọi code phân cụm DBSCAN.
```bash
python scripts/att_extractor.py
# Bỏ qua quá trình phân cụm (DBSCAN) nếu hệ thống không yêu cầu:
python scripts/att_extractor.py --no-cluster
```

### 3. Chạy Quick Test / Debug 1 Câu
Sử dụng cờ `--sentence` để phân tích ngay một câu không phụ thuộc UI tương tác xác nhận. Kết quả in thẳng ra màn hình Console, hỗ trợ debug hiệu quả khi cần thay đổi luật extraction:
```bash
python scripts/run_pipeline.py --sentence "A senior nurse can view medical records during business hours within the hospital."
```

### 4. Đánh giá Độ chính xác (Evaluation & F-Score)
Sau khi có phân nhóm và file json đầu ra `outputs/policies/policy_dataset.json`, bạn có thể đo lường độ chính xác thuật toán so với tệp Gold Standard đã xây dựng bằng công cụ đánh giá.
```bash
# Lưu ý trên môi trường Windows PowerShell, thiết lập Encoding thành utf8
$env:PYTHONIOENCODING="utf8"
python scripts/compute_fscore.py

# Đánh giá riêng cho trường Environment và in dữ liệu in sai:
python scripts/compute_fscore.py --field environment --verbose
```

---

## Lưu ý Kỹ thuật Quan trọng
- Các script cũ như `data_processing.py`, `abac_extraction.py`, `filter_env.py`, `candidate_generator.py` và `annotate.py` đã bị **loại bỏ** thay bằng bộ core `run_pipeline.py` / `interactive_verification.py` / `att_extractor.py` để gia tăng performance.
- Mô hình `en_core_web_md` của spaCy là yêu cầu **bắt buộc** để pipeline DBSCAN Clustering hoạt động trơn tru vì nó chứa pre-trained Word2Vec Embeddings.
