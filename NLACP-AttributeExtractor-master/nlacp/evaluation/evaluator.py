"""
evaluator.py — Đo P, R, F1 cho Env-Att Extractor
Chạy: python -m nlacp.evaluation.evaluator --data data/annotated/corpus.json
"""
import json
import os
import sys
import argparse

from nlacp.extraction.env_extractor import extract_env_attributes

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_annotated(data_path):
    with open(data_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _make_key(attr, loose=True):
    """Key để so sánh gold vs predicted."""
    cat = attr.get("category", "")
    val = attr.get("value", "").lower().strip()
    if loose:
        # Chỉ xét category + 2 từ đầu của value (partial match)
        val_words = val.split()[:2]
        return (cat, " ".join(val_words))
    return (cat, val)


def evaluate_single(gold_attrs, pred_attrs, partial=True):
    """Tính TP, FP, FN cho 1 câu."""
    gold_set = set(_make_key(a, partial) for a in gold_attrs)
    pred_set = set(_make_key(a, partial) for a in pred_attrs)

    tp = len(gold_set & pred_set)
    fp = len(pred_set - gold_set)
    fn = len(gold_set - pred_set)
    return tp, fp, fn


def compute_prf(tp, fp, fn):
    P  = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    R  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    F1 = 2 * P * R / (P + R) if (P + R) > 0 else 0.0
    return P, R, F1


def evaluate(data, category_filter=None, verbose=False):
    """
    Evaluate trên toàn bộ dataset.
    category_filter: "temporal" | "spatial" | None (cả hai)
    """
    total_tp = total_fp = total_fn = 0

    for item in data:
        sentence   = item.get("sentence", "")
        gold_attrs = item.get("env_attributes", [])

        # Lọc theo category nếu cần
        if category_filter:
            gold_attrs = [a for a in gold_attrs
                          if a.get("category") == category_filter]

        pred_attrs = extract_env_attributes(sentence)
        if category_filter:
            pred_attrs = [a for a in pred_attrs
                          if a.get("category") == category_filter]

        tp, fp, fn = evaluate_single(gold_attrs, pred_attrs)
        total_tp += tp
        total_fp += fp
        total_fn += fn

        if verbose and (fp > 0 or fn > 0):
            print(f"\n  [ERR] {sentence[:80]}...")
            gold_set = set(_make_key(a) for a in gold_attrs)
            pred_set = set(_make_key(a) for a in pred_attrs)
            for k in pred_set - gold_set:
                print(f"    FP: {k}")
            for k in gold_set - pred_set:
                print(f"    FN: {k}")

    P, R, F1 = compute_prf(total_tp, total_fp, total_fn)
    return P, R, F1, total_tp, total_fp, total_fn


def evaluate_by_dataset(data_dir, verbose=False):
    """Chạy evaluate trên tất cả file JSON trong thư mục."""
    results = {}
    files = [f for f in os.listdir(data_dir) if f.endswith(".json")]

    for fname in sorted(files):
        path   = os.path.join(data_dir, fname)
        data   = load_annotated(path)
        name   = fname.replace("_annotated.json", "").replace(".json", "")

        print(f"\n{'='*50}")
        print(f"  Dataset: {name} ({len(data)} sentences)")
        print(f"{'='*50}")

        for cat in [None, "temporal", "spatial"]:
            label = cat.capitalize() if cat else "Overall"
            P, R, F1, tp, fp, fn = evaluate(
                data, category_filter=cat, verbose=(verbose and cat is None)
            )
            print(f"  {label:10s}: P={P:.4f}  R={R:.4f}  F1={F1:.4f}"
                  f"  (TP={tp}, FP={fp}, FN={fn})")
            if cat is None:
                results[name] = {"P": round(P, 4), "R": round(R, 4), "F1": round(F1, 4)}

    return results


def evaluate_one_sentence(sentence, verbose=True):
    """Quick test một câu."""
    pred = extract_env_attributes(sentence)
    print(f"\nInput:  {sentence}")
    print(f"Predicted ({len(pred)}):")
    for a in pred:
        print(f"  [{a['category']:8s}/{a['subcategory']:12s}] "
              f"\"{a['value']}\"  ({a['method']})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data",    default=None,  help="Path to annotated JSON or directory")
    parser.add_argument("--sent",    default=None,  help="Single sentence to test")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.sent:
        evaluate_one_sentence(args.sent, verbose=args.verbose)

    elif args.data:
        path = args.data
        if os.path.isdir(path):
            evaluate_by_dataset(path, verbose=args.verbose)
        elif os.path.isfile(path):
            data = load_annotated(path)
            print(f"\nEvaluating: {path} ({len(data)} sentences)")
            for cat in [None, "temporal", "spatial"]:
                label = cat.capitalize() if cat else "Overall"
                P, R, F1, tp, fp, fn = evaluate(data, cat, verbose=args.verbose)
                print(f"  {label:10s}: P={P:.4f}  R={R:.4f}  F1={F1:.4f}")
    else:
        # Demo tự test
        print("\n--- Quick test ---")
        demo = [
            "A doctor can view records during business hours.",
            "Nurses from the hospital network can update charts.",
            "Administrators using trusted workstations can modify settings.",
            "Staff can access data between 8am and 5pm on weekdays.",
            "A patient may view his health record.",  # no env-att
        ]
        for s in demo:
            evaluate_one_sentence(s)
