#!/usr/bin/env python
"""
scripts/auto_extraction.py — Bước 1 tự động của pipeline (không cần tương tác người dùng)

Luồng xử lý:
  input.txt (hoặc stdin)
    → relation_candidate.py   — sinh SA + OA candidates
    → env_extractor.py        — sinh ENV candidates (3-layer algorithm)
    → Lưu tự động (không hỏi người)
    → dataset/policy_dataset.json (raw machine output)

Kết quả này là RAW OUTPUT của máy — dùng để tính F-score sau này.
Để tạo Gold Standard, chạy: python scripts/interactive_verification.py

Usage:
    python scripts/auto_extraction.py                # stdin mode
    python scripts/auto_extraction.py input.txt      # batch mode từ file
    python scripts/auto_extraction.py --stdin        # force stdin
"""
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from nlacp.extraction.relation_candidate import extract_relations, parse_sentence
from nlacp.extraction.env_extractor import extract_env_attributes
from nlacp.pipeline.pipeline_v2 import parse_acp_sentence
from nlacp.paths import POLICY_DATASET_PATH, RELATION_CANDIDATE_PATH

DATASET_DIR = os.path.join(PROJECT_ROOT, "dataset")

# Preposition labels — dùng để loại prep tokens khỏi SA/OA candidates
ENV_PREPS = {"during", "within", "after", "before", "between", "via",
             "through", "using", "at", "on", "from", "inside", "outside",
             "throughout", "until"}


# =====================================================================
#  Đọc input
# =====================================================================

def read_sentences_from_file(filepath: str) -> list:
    """Đọc các câu policy từ file .txt (mỗi dòng một câu)."""
    sentences = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                sentences.append(line)
    return sentences


def read_sentences_from_stdin() -> list:
    """Nhập tương tác từ terminal, gõ 'done' hoặc 'exit' để kết thúc."""
    print("\nNhập câu policy (tiếng Anh). Gõ 'done' hoặc 'exit' để kết thúc.")
    print("Ví dụ:")
    print("  An senior nurse may change the list of approved lab procedures during business hours within the hospital.")
    print("  A surgeon can schedule operations between 7am and 3pm")
    print("  A doctor may access patient records if the patient has given consent.")
    print("  Doctors and nurses may view patient records.")
    print("  A doctor may view, edit, and delete patient records.")
    print("  A senior doctor may prescribe controlled substances during night shift from 10pm to 6am.\n")

    sentences = []
    while True:
        try:
            line = input("Enter policy sentence: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        if line.lower() in ("done", "exit", "quit"):
            break
        words = line.split()
        if len(words) < 3:
            print("  [SKIP] Câu quá ngắn (ít nhất 3 từ).")
            continue
        if not any(w.isalpha() for w in words):
            print("  [SKIP] Câu không hợp lệ.")
            continue
        sentences.append(line)
    return sentences


# =====================================================================
#  Extraction (hoàn toàn tự động)
# =====================================================================

def extract_all_candidates(sentence: str) -> dict:
    """
    Chạy cả relation_candidate (SA/OA) + env_extractor (ENV) cho một câu.
    Trả về dict tổng hợp với 3 loại candidates.
    """
    # 1. Trích xuất ENV TRƯỚC để lấy danh sách từ không được dùng cho SA/OA
    env_attrs = extract_env_attributes(sentence)
    env_phrases = []
    for e in env_attrs:
        if e.get("full_value"):
            env_phrases.append(e["full_value"].lower())
        if e.get("phrase"):
            env_phrases.append(e["phrase"].lower())

    # 2. Trích xuất SA/OA
    tokens   = parse_sentence(sentence)
    relation = extract_relations(sentence, tokens)

    # Lọc bỏ prep tokens khỏi SA/OA pairs + Lọc bỏ các từ nằm trong ENV
    sa_oa_pairs = []
    for attr in relation.get("attributes", []):
        name = attr["name"].lower()
        val_lower = attr["value"].lower()

        if name in ENV_PREPS:
            continue
            
        # Kiểm tra nếu term này là một phần của environment phrase -> BLOCKED 
        # (Yêu cầu user: thành phần ENV không được dùng làm thuộc tính cho cái khác)
        is_blocked = False
        for ep in env_phrases:
            if name in ep.split() or val_lower in ep:
                is_blocked = True
                break
        
        if is_blocked:
            continue

        pair = [attr["value"], attr["name"], attr.get("category", "unclassified"), attr.get("dep", "")]
        sa_oa_pairs.append(pair)

    # Loại trùng
    seen = set()
    unique_pairs = []
    for p in sa_oa_pairs:
        key = (p[0].lower(), p[1].lower())
        if key not in seen:
            seen.add(key)
            unique_pairs.append(p)

    # 3. Loại ENV modifiers ra khỏi subject và object strings
    def filter_out_envs(entity_list):
        if not entity_list: return entity_list
        res = []
        for ent in entity_list:
            ent_clean = ent
            for ep in env_phrases:
                # Nếu subject/object chứa hẳn nguyên một đoan ENV, cắt đuôi
                if ep in ent_clean.lower():
                    # Simple heuristic: remove the env part
                    idx = ent_clean.lower().find(ep)
                    ent_clean = ent_clean[:idx].strip()
            if ent_clean:
                res.append(ent_clean)
        return res

    subjects = filter_out_envs(relation.get("subject"))
    objects = filter_out_envs(relation.get("object"))

    return {
        "sentence":    sentence,
        "subject":     subjects,
        "actions":     relation.get("actions", []),
        "object":      objects,
        "sa_oa_pairs": unique_pairs,   # [value, name, category, dep]
        "env_attrs":   env_attrs       # List of env dicts từ env_extractor
    }


def build_policy_record(extracted: dict, idx: int) -> dict:
    """Chuyển kết quả extraction thô thành policy record — không có bước xác nhận."""
    # Giữ toàn bộ SA/OA pairs (chỉ lấy [val, name])
    relation_pairs = [[p[0], p[1]] for p in extracted.get("sa_oa_pairs", [])]

    # Giữ toàn bộ ENV entries (loại bỏ key 'token' nếu có)
    environment = [
        {k: v for k, v in env.items() if k != "token"}
        for env in extracted.get("env_attrs", [])
    ]

    return {
        "id":             idx,
        "sentence":       extracted["sentence"],
        "subject":        extracted["subject"],
        "actions":        extracted["actions"],
        "object":         extracted["object"],
        "relation_pairs": relation_pairs,
        "environments":   environment,
        "authorization_decision": None,
        "policy_modality": None,
        "context": []
    }


# =====================================================================
#  Persistence
# =====================================================================

def load_existing_policies() -> tuple:
    """Đọc policy_dataset.json hiện có, trả về (all_policies, processed_ids, processed_sents)."""
    if not os.path.exists(POLICY_DATASET_PATH):
        return [], set(), set()
    try:
        with open(POLICY_DATASET_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        policies = data.get("policies", [])
        ids      = {p.get("id") for p in policies}
        sents    = {p.get("sentence", "").lower().strip() for p in policies}
        return policies, ids, sents
    except Exception:
        return [], set(), set()


def save_policies(all_policies: list):
    """Ghi policy_dataset.json (raw machine output)."""
    os.makedirs(os.path.dirname(POLICY_DATASET_PATH), exist_ok=True)
    with open(POLICY_DATASET_PATH, "w", encoding="utf-8") as f:
        json.dump({"policies": all_policies}, f, indent=4, ensure_ascii=False)


def save_candidates_log(records: list):
    """Lưu relation_candidate.json (log các candidates đã extract)."""
    os.makedirs(DATASET_DIR, exist_ok=True)
    existing = []
    if os.path.exists(RELATION_CANDIDATE_PATH):
        try:
            with open(RELATION_CANDIDATE_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f).get("relations", [])
        except Exception:
            pass
    all_records = existing + records
    with open(RELATION_CANDIDATE_PATH, "w", encoding="utf-8") as f:
        json.dump({"relations": all_records}, f, indent=4, ensure_ascii=False)


# =====================================================================
#  MAIN
# =====================================================================

def main(input_file: str = None):
    print("\n" + "=" * 60)
    print("  AUTO EXTRACTION — Bước 1 (Fully Automatic)")
    print("  SA/OA + ENV Candidates → policy_dataset.json")
    print("  [RAW machine output — dùng để tính F-score]")
    print("=" * 60)

    # Đọc câu input
    if input_file and os.path.exists(input_file):
        sentences = read_sentences_from_file(input_file)
        print(f"\n[INFO] Đọc {len(sentences)} câu từ {input_file}")
    else:
        if input_file:
            print(f"[WARN] Không tìm thấy file '{input_file}', chuyển sang stdin mode.")
        sentences = read_sentences_from_stdin()

    if not sentences:
        print("[WARN] Không có câu nào để xử lý.")
        return

    # Load dữ liệu cũ
    all_policies, processed_ids, processed_sents = load_existing_policies()

    # Gán ID bắt đầu
    start_id = max(processed_ids, default=0) + 1

    # Extraction — hoàn toàn tự động
    print(f"\n[INFO] Đang extraction {len(sentences)} câu...")
    extracted_all = []
    skipped = 0
    for s in sentences:
        if s.lower().strip() in processed_sents:
            print(f"  [SKIP] Đã có trong dataset: {s[:70]}")
            skipped += 1
            continue
        ext = extract_all_candidates(s)
        extracted_all.append(ext)
        # Preview nhanh
        print(f"  [OK]   {s[:70]}")
        print(f"         Subject: {ext['subject']}  |  Actions: {ext['actions']}  |  Object: {ext['object']}")
        env_count = len(ext['env_attrs'])
        if env_count:
            env_labels = [e.get('full_value', e.get('phrase', '?')) for e in ext['env_attrs']]
            print(f"         ENV ({env_count}): {env_labels}")

    if not extracted_all:
        print("[INFO] Không có câu mới cần xử lý.")
        return

    print(f"\n[INFO] Extraction xong: {len(extracted_all)} câu mới,  {skipped} câu bị skip.")

    # Lưu log candidates
    candidate_log = []
    for e in extracted_all:
        candidate_log.append({
            "sentence":    e["sentence"],
            "subject":     e["subject"],
            "actions":     e["actions"],
            "object":      e["object"],
            "sa_oa_pairs": [[p[0], p[1]] for p in e["sa_oa_pairs"]],
            "env_attrs":   [{k: v for k, v in env.items() if k != "token"} for env in e["env_attrs"]]
        })
    save_candidates_log(candidate_log)

    # Build policy records (không hỏi người dùng)
    new_policies = []
    for i, extracted in enumerate(extracted_all):
        idx = start_id + i
        # Prefer v2 parser output (Pydantic Policy) if possible
        try:
            p = parse_acp_sentence(extracted["sentence"], policy_id=idx)
            if p:
                # p is a Pydantic model (Policy) - dump to plain dict
                try:
                    pdict = p.model_dump()
                except Exception:
                    # fallback for older pydantic versions
                    pdict = p.dict()
                new_policies.append(pdict)
                continue
        except Exception:
            # fall back to legacy record
            pass

        policy = build_policy_record(extracted, idx)
        new_policies.append(policy)

    # Merge + save
    all_policies.extend(new_policies)
    save_policies(all_policies)

    print(f"\n{'='*60}")
    print(f"  [OK] Đã lưu {len(new_policies)} policy(ies) vào:")
    print(f"       {POLICY_DATASET_PATH}")
    print(f"  Tổng policies trong dataset: {len(all_policies)}")
    print(f"{'='*60}")
    print("\nBước tiếp theo:")
    print("  → Tạo Gold Standard : python scripts/interactive_verification.py")
    print("  → Attribute extract  : python scripts/att_extractor.py")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Auto Extraction — SA/OA + ENV (fully automatic, no human input)"
    )
    parser.add_argument("input_file", nargs="?", default=None,
                        help="File .txt chứa câu policy (một câu mỗi dòng)")
    parser.add_argument("--stdin", action="store_true",
                        help="Force stdin mode dù có input_file")
    args = parser.parse_args()

    if args.stdin:
        main(input_file=None)
    else:
        main(input_file=args.input_file)
