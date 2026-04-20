#!/usr/bin/env python
"""
scripts/compute_fscore.py — Tính F-score cho toàn bộ ABAC pipeline

So sánh:
  policy_dataset.json      — RAW machine output (từ auto_extraction.py)
  policy_dataset_gold.json — Gold Standard (từ interactive_verification.py)

Tính P, R, F1 cho từng trường:
  - Subject
  - Actions
  - Object
  - Environment

Usage:
    python scripts/compute_fscore.py
    python scripts/compute_fscore.py --verbose        # In chi tiết từng câu sai
    python scripts/compute_fscore.py --field subject  # Chỉ tính 1 trường
    python scripts/compute_fscore.py \\
        --machine outputs/policies/policy_dataset.json \\
        --gold    outputs/policies/policy_dataset_gold.json
"""
import json
import os
import sys
import argparse

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from nlacp.paths import POLICY_DATASET_PATH, POLICY_DATASET_GOLD_PATH


# =====================================================================
#  Load
# =====================================================================

def load_json_policies(path: str, label: str) -> dict:
    """Load file JSON policies, trả về dict id → policy."""
    if not os.path.exists(path):
        print(f"[ERROR] Không tìm thấy file {label}: {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    policies = data.get("policies", [])
    return {p["id"]: p for p in policies}


# =====================================================================
#  Normalise helpers
# =====================================================================

def _norm_str(s) -> str:
    """Chuẩn hoá 1 chuỗi: lower, strip, bỏ khoảng trắng thừa."""
    if s is None:
        return ""
    if isinstance(s, list):
        return " ".join(s).lower().strip()
    return str(s).lower().strip()


def _to_set(value) -> set:
    """Chuyển 1 giá trị (str, list, None) thành set các token chuẩn hoá."""
    if value is None:
        return set()
    if isinstance(value, list):
        return {_norm_str(v) for v in value if v}
    val = _norm_str(value)
    return {val} if val else set()


def _env_key(env: dict) -> str:
    """
    Tạo khoá so sánh cho một environment entry.
    Dùng (env_type, 2 từ đầu của full_value) để khớp linh hoạt (partial match).
    """
    fv   = _norm_str(env.get("full_value", env.get("phrase", "")))
    etype = env.get("env_type", "")
    words = fv.split()[:3]          # 3 từ đầu (partial match)
    return f"{etype}::{' '.join(words)}"


# =====================================================================
#  Tính TP / FP / FN cho từng trường
# =====================================================================

def _compute_tp_fp_fn_sets(gold_set: set, pred_set: set):
    tp = len(gold_set & pred_set)
    fp = len(pred_set - gold_set)
    fn = len(gold_set - pred_set)
    return tp, fp, fn


def prf(tp: int, fp: int, fn: int):
    P  = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    R  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    F1 = 2 * P * R / (P + R) if (P + R) > 0 else 0.0
    return P, R, F1


# =====================================================================
#  Đánh giá từng câu
# =====================================================================

def evaluate_pair(gold: dict, pred: dict) -> dict:
    """
    So sánh 1 cặp (gold, pred) cho 4 trường.
    Trả về dict với TP/FP/FN cho mỗi trường.
    """
    result = {}

    # ── Subject ────────────────────────────────────────────────────
    g_sub = _to_set(gold.get("subject"))
    p_sub = _to_set(pred.get("subject"))
    result["subject"] = _compute_tp_fp_fn_sets(g_sub, p_sub)

    # ── Actions ────────────────────────────────────────────────────
    g_act = {_norm_str(a) for a in gold.get("actions", []) if a}
    p_act = {_norm_str(a) for a in pred.get("actions", []) if a}
    result["actions"] = _compute_tp_fp_fn_sets(g_act, p_act)

    # ── Object ─────────────────────────────────────────────────────
    g_obj = _to_set(gold.get("object"))
    p_obj = _to_set(pred.get("object"))
    result["object"] = _compute_tp_fp_fn_sets(g_obj, p_obj)

    # ── Environment ────────────────────────────────────────────────
    g_env = {_env_key(e) for e in gold.get("environment", [])}
    p_env = {_env_key(e) for e in pred.get("environment", [])}
    result["environment"] = _compute_tp_fp_fn_sets(g_env, p_env)

    return result


# =====================================================================
#  Verbose helpers
# =====================================================================

def _print_errors(sentence: str, field: str, gold_set: set, pred_set: set):
    fp_items = pred_set - gold_set
    fn_items = gold_set - pred_set
    if fp_items or fn_items:
        print(f"\n    [{field.upper()}] câu: \"{sentence[:75]}\"")
        for k in sorted(fp_items):
            print(f"      FP (máy sai): {k}")
        for k in sorted(fn_items):
            print(f"      FN (máy bỏ sót): {k}")


# =====================================================================
#  Main evaluate
# =====================================================================

FIELDS = ["subject", "actions", "object", "environment"]


def evaluate(machine_map: dict, gold_map: dict,
             field_filter: str = None, verbose: bool = False) -> dict:
    """
    So sánh machine vs gold, trả về dict kết quả theo từng field.
    """
    fields = [field_filter] if field_filter else FIELDS

    # Accumulate TP/FP/FN
    totals = {f: [0, 0, 0] for f in fields}   # [tp, fp, fn]

    common_ids = sorted(set(gold_map.keys()) & set(machine_map.keys()))
    only_gold  = set(gold_map.keys()) - set(machine_map.keys())
    only_pred  = set(machine_map.keys()) - set(gold_map.keys())

    if only_gold:
        print(f"[WARN] {len(only_gold)} id(s) có trong gold nhưng không có trong machine output — tính là FN.")
    if only_pred:
        print(f"[WARN] {len(only_pred)} id(s) có trong machine nhưng không có trong gold — bị bỏ qua.")

    for pid in common_ids:
        gold = gold_map[pid]
        pred = machine_map[pid]
        pair = evaluate_pair(gold, pred)

        for f in fields:
            tp, fp, fn = pair[f]
            totals[f][0] += tp
            totals[f][1] += fp
            totals[f][2] += fn

        if verbose:
            sentence = gold.get("sentence", "")
            # Subject verbose
            if "subject" in fields:
                g = _to_set(gold.get("subject"))
                p = _to_set(pred.get("subject"))
                _print_errors(sentence, "subject", g, p)
            # Actions verbose
            if "actions" in fields:
                g = {_norm_str(a) for a in gold.get("actions", []) if a}
                p = {_norm_str(a) for a in pred.get("actions", []) if a}
                _print_errors(sentence, "actions", g, p)
            # Object verbose
            if "object" in fields:
                g = _to_set(gold.get("object"))
                p = _to_set(pred.get("object"))
                _print_errors(sentence, "object", g, p)
            # Environment verbose
            if "environment" in fields:
                g = {_env_key(e) for e in gold.get("environment", [])}
                p = {_env_key(e) for e in pred.get("environment", [])}
                _print_errors(sentence, "environment", g, p)

    # Handle ids only in gold (count as FN for each field)
    for pid in only_gold:
        gold = gold_map[pid]
        for f in fields:
            if f == "subject":
                fn_count = len(_to_set(gold.get("subject")))
            elif f == "actions":
                fn_count = len({_norm_str(a) for a in gold.get("actions", []) if a})
            elif f == "object":
                fn_count = len(_to_set(gold.get("object")))
            else:  # environment
                fn_count = len(gold.get("environment", []))
            totals[f][2] += fn_count

    # Compute P/R/F1
    results = {}
    for f in fields:
        tp, fp, fn = totals[f]
        P, R, F1 = prf(tp, fp, fn)
        results[f] = {"P": P, "R": R, "F1": F1, "TP": tp, "FP": fp, "FN": fn}

    return results, len(common_ids)


# =====================================================================
#  Print results
# =====================================================================

def print_results(results: dict, n_sentences: int):
    print(f"\n{'='*62}")
    print(f"  F-SCORE RESULTS  ({n_sentences} câu được so sánh)")
    print(f"{'='*62}")
    print(f"  {'Field':<14}  {'P':>7}  {'R':>7}  {'F1':>7}   TP    FP    FN")
    print(f"  {'-'*56}")

    all_tp = all_fp = all_fn = 0
    for f, r in results.items():
        print(f"  {f.capitalize():<14}  {r['P']:>7.4f}  {r['R']:>7.4f}  {r['F1']:>7.4f}"
              f"   {r['TP']:>3}   {r['FP']:>3}   {r['FN']:>3}")
        all_tp += r["TP"]
        all_fp += r["FP"]
        all_fn += r["FN"]

    # Micro-average overall
    P, R, F1 = prf(all_tp, all_fp, all_fn)
    print(f"  {'-'*56}")
    print(f"  {'OVERALL (micro)':<14}  {P:>7.4f}  {R:>7.4f}  {F1:>7.4f}"
          f"   {all_tp:>3}   {all_fp:>3}   {all_fn:>3}")
    print(f"{'='*62}\n")


# =====================================================================
#  Entry point
# =====================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Tính F-score: so sánh policy_dataset.json vs policy_dataset_gold.json"
    )
    parser.add_argument("--machine", default=POLICY_DATASET_PATH,
                        help="Path tới file machine output (mặc định: policy_dataset.json)")
    parser.add_argument("--gold",    default=POLICY_DATASET_GOLD_PATH,
                        help="Path tới Gold Standard (mặc định: policy_dataset_gold.json)")
    parser.add_argument("--field",   default=None,
                        choices=FIELDS,
                        help="Chỉ tính F-score cho 1 trường (subject/actions/object/environment)")
    parser.add_argument("--verbose", action="store_true",
                        help="In chi tiết các câu bị FP/FN")
    args = parser.parse_args()

    print(f"\n[INFO] Machine output : {args.machine}")
    print(f"[INFO] Gold Standard  : {args.gold}")
    if args.field:
        print(f"[INFO] Chỉ đánh giá   : {args.field}")

    machine_map = load_json_policies(args.machine, "machine output")
    gold_map    = load_json_policies(args.gold,    "Gold Standard")

    print(f"[INFO] Machine: {len(machine_map)} policies  |  Gold: {len(gold_map)} policies")

    results, n = evaluate(machine_map, gold_map,
                          field_filter=args.field,
                          verbose=args.verbose)
    print_results(results, n)


if __name__ == "__main__":
    main()
