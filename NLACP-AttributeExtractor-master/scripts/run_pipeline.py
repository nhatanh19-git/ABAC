#!/usr/bin/env python
"""
scripts/run_pipeline.py — Entry point cho toàn bộ ABAC pipeline.

Pipeline:
  input.txt
    → auto_extraction.py            (Bước 1: SA+OA+ENV candidates → tự động → policy_dataset.json)
    → att_extractor.py              (Bước 2: DBSCAN clustering → attribute keys)

  [Tạo Gold Standard riêng]
    → interactive_verification.py   (Đọc policy_dataset.json → người dùng verify → policy_dataset_gold.json)

Usage:
    python scripts/run_pipeline.py                        # Full pipeline (stdin)
    python scripts/run_pipeline.py input.txt              # Full pipeline từ file
    python scripts/run_pipeline.py --extract              # Chỉ Bước 2 (đã có policy_dataset.json)
    python scripts/run_pipeline.py --extract --no-cluster # Bước 2, bỏ qua clustering
    python scripts/run_pipeline.py --sentence "..."       # Xử lý 1 câu nhanh (quick test)
"""
import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


# =====================================================================
#  Quick single-sentence test (không qua verification)
# =====================================================================

def run_single_sentence(sentence: str):
    """Xử lý 1 câu và in kết quả ngay (debug mode)."""
    from nlacp.pipeline.pipeline import process_sentence
    result = process_sentence(sentence)

    print("\n--- Extracted ABAC Policy ---")
    print(f"  Subject  : {result.get('subject')}")
    print(f"  Actions  : {result.get('actions', [])}")
    print(f"  Object   : {result.get('object')}")

    env_list = result.get("environment", [])
    if env_list:
        print(f"  Environment ({len(env_list)}):")
        for e in env_list:
            ns = e.get("namespace", "?")
            fv = e.get("full_value", e.get("phrase", "?"))
            et = e.get("env_type", "?")
            print(f"    [{et}] \"{fv}\" → {ns}")
    else:
        print("  Environment: (none detected)")

    attrs = result.get("attributes", [])
    if attrs:
        print(f"  Attributes ({len(attrs)}):")
        for a in attrs:
            cat = a.get("category", "?").upper()
            ns  = a.get("namespace", "?")
            sn  = a.get("short_name", "?")
            print(f"    [{cat}] {ns} = \"{sn}\"")
    else:
        print("  Attributes: (none detected)")

    print()
    print(json.dumps(result, indent=2, ensure_ascii=False))


# =====================================================================
#  Bước 1: auto_extraction (fully automatic)
# =====================================================================

def run_verification(input_file: str = None):
    from scripts.auto_extraction import main as extract_auto_main
    extract_auto_main(input_file=input_file)


# =====================================================================
#  Bước 2: att_extractor
# =====================================================================

def run_extraction(run_cluster: bool = True):
    from scripts.att_extractor import main as extract_main
    extract_main(run_cluster=run_cluster)


# =====================================================================
#  Full pipeline
# =====================================================================

def run_full_pipeline(input_file: str = None, run_cluster: bool = True):
    print("\n" + "=" * 60)
    print("  ABAC FULL PIPELINE")
    print("  Bước 1: Auto Extraction → Bước 2: Attribute Clustering")
    print("=" * 60)

    # Bước 1 — hoàn toàn tự động
    print("\n[BƯỚC 1] Auto Extraction (fully automatic)...")
    run_verification(input_file=input_file)

    # Bước 2
    print("\n[BƯỚC 2] Attribute Extraction + Clustering...")
    run_extraction(run_cluster=run_cluster)

    print("\n" + "=" * 60)
    print("  PIPELINE HOÀN TẤT!")
    print("  → Tạo Gold Standard: python scripts/interactive_verification.py")
    print("=" * 60)


# =====================================================================
#  Entry point
# =====================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ABAC Policy Extractor Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  python scripts/run_pipeline.py input.txt          # Full pipeline từ file
  python scripts/run_pipeline.py --auto input.txt   # Chỉ Bước 1 (auto extraction)
  python scripts/run_pipeline.py --extract          # Chỉ Bước 2 (đã có policy_dataset.json)
  python scripts/run_pipeline.py --sentence "..."   # Quick test 1 câu

  # Tạo Gold Standard (riêng):
  python scripts/interactive_verification.py        # Verify policy_dataset.json → gold
        """
    )
    parser.add_argument("input_file", nargs="?", default=None,
                        help="File .txt chứa câu policy (mỗi dòng một câu)")
    parser.add_argument("--auto", action="store_true",
                        help="Chỉ chạy Bước 1 (auto_extraction, không hỏi người dùng)")
    parser.add_argument("--extract", action="store_true",
                        help="Chỉ chạy Bước 2 (att_extractor)")
    parser.add_argument("--no-cluster", action="store_true",
                        help="Bỏ qua DBSCAN clustering trong Bước 2")
    parser.add_argument("--sentence", default=None,
                        help="Quick test: xử lý 1 câu nhanh")
    args = parser.parse_args()

    if args.sentence:
        run_single_sentence(args.sentence)
    elif args.auto:
        run_verification(input_file=args.input_file)
    elif args.extract:
        run_extraction(run_cluster=not args.no_cluster)
    else:
        run_full_pipeline(input_file=args.input_file, run_cluster=not args.no_cluster)