#!/usr/bin/env python
"""
scripts/interactive_verification.py — Tạo Gold Standard cho tính F-score

Luồng xử lý:
  outputs/policies/policy_dataset.json   (raw machine output từ auto_extraction.py)
    → Duyệt từng câu, hỏi Y/N
    → Nếu Y: cho chỉnh sửa Subject / Actions / Object / Environment
    → Lưu ra outputs/policies/policy_dataset_gold.json   (Gold Standard)

F-score = so sánh policy_dataset.json  vs  policy_dataset_gold.json

Usage:
    python scripts/interactive_verification.py
    python scripts/interactive_verification.py --resume   # Tiếp từ câu chưa xét
"""
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from nlacp.extraction.env_extractor import analyze_manual_env_phrase
from nlacp.paths import POLICY_DATASET_PATH, POLICY_DATASET_GOLD_PATH


# =====================================================================
#  Helpers
# =====================================================================

def _input(prompt: str, default: str = "") -> str:
    """Nhận input từ người dùng, trả về default nếu nhấn Enter trống."""
    try:
        ans = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return ans if ans else default


def _yn(prompt: str, default: str = "n") -> bool:
    """Hỏi Yes/No, trả về True nếu Yes."""
    tag = "[Y/n]" if default == "y" else "[y/N]"
    try:
        ans = input(f"  {prompt} {tag}: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return default == "y"
    if not ans:
        return default == "y"
    return ans.startswith("y")


def _divider(char="─", width=62):
    print(char * width)


# =====================================================================
#  Load / Save
# =====================================================================

def load_machine_output() -> list:
    """Đọc policy_dataset.json (raw output từ auto_extraction)."""
    if not os.path.exists(POLICY_DATASET_PATH):
        print(f"[ERROR] Không tìm thấy file: {POLICY_DATASET_PATH}")
        print("        Hãy chạy trước: python scripts/auto_extraction.py")
        sys.exit(1)
    with open(POLICY_DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("policies", [])


def load_gold_dataset() -> dict:
    """Đọc policy_dataset_gold.json nếu tồn tại (để resume)."""
    if not os.path.exists(POLICY_DATASET_GOLD_PATH):
        return {}
    try:
        with open(POLICY_DATASET_GOLD_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Index theo id để tra nhanh
        return {p["id"]: p for p in data.get("policies", [])}
    except Exception:
        return {}


def save_gold_dataset(gold_policies: list):
    """Ghi policy_dataset_gold.json."""
    os.makedirs(os.path.dirname(POLICY_DATASET_GOLD_PATH), exist_ok=True)
    with open(POLICY_DATASET_GOLD_PATH, "w", encoding="utf-8") as f:
        json.dump({"policies": gold_policies}, f, indent=4, ensure_ascii=False)


# =====================================================================
#  Hiển thị câu policy
# =====================================================================

def _display_policy(policy: dict, idx_display: int, total: int):
    """In thông tin đầy đủ của một policy (raw machine output)."""
    _divider()
    print(f"  Policy [{idx_display}/{total}]  id={policy['id']}")
    print(f"  Câu : {policy['sentence']}")
    _divider("·")
    sub = policy.get("subject")
    print(f"  Subject    : {sub if sub else '(none)'}")
    acts = policy.get("actions", [])
    print(f"  Actions    : {', '.join(acts) if acts else '(none)'}")
    obj = policy.get("object")
    print(f"  Object     : {obj if obj else '(none)'}")
    env_list = policy.get("environment", [])
    if env_list:
        print(f"  Environment ({len(env_list)}):")
        for e in env_list:
            fv  = e.get("full_value", e.get("phrase", "?"))
            et  = e.get("env_type", "?")
            sub_cat = e.get("subcategory", "?")
            ns  = e.get("namespace", "?")
            print(f"    [{et}|{sub_cat}]  \"{fv}\"  →  {ns}")
    else:
        print("  Environment: (none)")
    pairs = policy.get("relation_pairs", [])
    if pairs:
        print(f"  SA/OA pairs ({len(pairs)}):")
        for p in pairs:
            print(f"    '{p[1]}' → '{p[0]}'")
    _divider("·")


# =====================================================================
#  Edit helpers — từng trường
# =====================================================================

def _edit_subject(current) -> object:
    """Cho người dùng chỉnh sửa Subject."""
    cur_str = current if isinstance(current, str) else (", ".join(current) if current else "(none)")
    print(f"\n    Subject hiện tại: {cur_str}")
    new_val = _input(f"    Nhập Subject mới (Enter = giữ nguyên): ", default="")
    if new_val:
        # Nếu nhiều subject cách nhau bằng dấu phẩy thì split
        parts = [v.strip() for v in new_val.split(",") if v.strip()]
        return parts[0] if len(parts) == 1 else parts
    return current


def _edit_actions(current: list) -> list:
    """Cho người dùng chỉnh sửa Actions."""
    print(f"\n    Actions hiện tại: {', '.join(current) if current else '(none)'}")
    print("    Nhập lại Actions, phân cách bằng dấu phẩy (Enter = giữ nguyên):")
    new_val = _input("    > ", default="")
    if new_val:
        return [v.strip() for v in new_val.split(",") if v.strip()]
    return current


def _edit_object(current) -> object:
    """Cho người dùng chỉnh sửa Object."""
    cur_str = current if isinstance(current, str) else (", ".join(current) if current else "(none)")
    print(f"\n    Object hiện tại: {cur_str}")
    new_val = _input("    Nhập Object mới (Enter = giữ nguyên): ", default="")
    if new_val:
        parts = [v.strip() for v in new_val.split(",") if v.strip()]
        return parts[0] if len(parts) == 1 else parts
    return current


def _edit_environment(current: list) -> list:
    """Cho người dùng xét từng ENV entry: giữ / xóa / thêm mới."""
    print(f"\n    Environment hiện tại ({len(current)} entries):")
    if not current:
        print("      (trống)")

    valid_env = []

    # Duyệt từng entry hiện có
    for i, env in enumerate(current):
        fv  = env.get("full_value", env.get("phrase", "?"))
        et  = env.get("env_type", "?")
        sub_cat = env.get("subcategory", "?")
        ns  = env.get("namespace", "?")
        print(f"\n      [{i+1}/{len(current)}] [{et}|{sub_cat}]  \"{fv}\"")
        print(f"              namespace: {ns}")
        keep = _yn("      Giữ lại entry này?", default="y")
        if keep:
            valid_env.append(env)
        else:
            print("      [–] Đã xóa entry này.")

    # Hỏi bổ sung thêm ENV mới
    while True:
        add_more = _yn("\n    Thêm ENV mới bị sót?", default="n")
        if not add_more:
            break
        new_phrase = _input("      Nhập cụm ENV (ví dụ: during business hours): ")
        if not new_phrase:
            continue
        analyzed = analyze_manual_env_phrase(new_phrase)
        valid_env.append(analyzed)
        print(f"      [+] Đã thêm: \"{new_phrase}\"  →  {analyzed['namespace']}")

    return valid_env


# =====================================================================
#  Verify một policy
# =====================================================================

def verify_and_edit_policy(policy: dict) -> dict:
    """
    Người dùng chọn chỉnh sửa gì cho policy này.
    Trả về bản đã chỉnh (gold).
    """
    gold = dict(policy)  # shallow copy để giữ tất cả fields

    print("\n  Chọn thành phần cần chỉnh sửa (có thể chọn nhiều):")
    print("    [1] Subject")
    print("    [2] Actions")
    print("    [3] Object")
    print("    [4] Environment")
    print("    [5] Tất cả (theo thứ tự)")
    print("    [0] Không sửa gì (giữ nguyên kết quả máy)")

    try:
        choice_raw = input("  Lựa chọn (vd: 1 3 4  hoặc  5): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return gold

    if not choice_raw or choice_raw == "0":
        return gold

    choices = set(choice_raw.split())
    if "5" in choices:
        choices = {"1", "2", "3", "4"}

    if "1" in choices:
        gold["subject"] = _edit_subject(gold.get("subject"))
        print(f"    → Subject: {gold['subject']}")

    if "2" in choices:
        gold["actions"] = _edit_actions(gold.get("actions", []))
        print(f"    → Actions: {gold['actions']}")

    if "3" in choices:
        gold["object"] = _edit_object(gold.get("object"))
        print(f"    → Object: {gold['object']}")

    if "4" in choices:
        gold["environment"] = _edit_environment(gold.get("environment", []))
        print(f"    → Environment: {len(gold['environment'])} entries")

    return gold


# =====================================================================
#  MAIN
# =====================================================================

def main(resume: bool = False):
    print("\n" + "=" * 62)
    print("  INTERACTIVE VERIFICATION — Tạo Gold Standard")
    print("  Đọc: policy_dataset.json  →  Lưu: policy_dataset_gold.json")
    print("=" * 62)

    # Load raw machine output
    machine_policies = load_machine_output()
    if not machine_policies:
        print("[WARN] policy_dataset.json trống. Chạy auto_extraction.py trước.")
        return

    # Load gold đã có (nếu resume)
    gold_map = load_gold_dataset() if resume else {}

    print(f"\n[INFO] Tổng {len(machine_policies)} policy trong dataset.")
    if resume and gold_map:
        already_done = len([p for p in machine_policies if p["id"] in gold_map])
        print(f"[INFO] Resume mode: đã xét {already_done} / {len(machine_policies)} câu.")

    print("\nHướng dẫn:")
    print("  N = kết quả máy OK (không cần sửa), chuyển câu tiếp.")
    print("  Y = muốn xem và chỉnh sửa thành phần của câu này.")
    print("  Ctrl+C bất cứ lúc nào để dừng và lưu tiến trình.\n")

    total = len(machine_policies)
    gold_list = []  # kết quả cuối cùng theo thứ tự

    try:
        for display_idx, policy in enumerate(machine_policies, start=1):
            pid = policy["id"]

            # Resume: nếu đã có trong gold thì giữ nguyên, không hỏi lại
            if resume and pid in gold_map:
                gold_list.append(gold_map[pid])
                print(f"  [SKIP] id={pid} — đã xét trước đó, giữ nguyên.")
                continue

            # Hiển thị policy
            _display_policy(policy, display_idx, total)

            # Hỏi Y/N
            want_edit = _yn("Câu này cần chỉnh sửa?", default="n")

            if not want_edit:
                # Giữ nguyên kết quả máy
                gold_list.append(dict(policy))
                print("  [→] Giữ nguyên kết quả máy.")
            else:
                # Vào chế độ chỉnh sửa
                edited = verify_and_edit_policy(policy)
                gold_list.append(edited)
                print("  [✓] Đã cập nhật.")

    except KeyboardInterrupt:
        print("\n\n[!] Dừng sớm — đang lưu tiến trình...")

    # Lưu gold dataset
    if gold_list:
        save_gold_dataset(gold_list)
        print(f"\n{'='*62}")
        print(f"  [OK] Đã lưu {len(gold_list)} policy(ies) vào:")
        print(f"       {POLICY_DATASET_GOLD_PATH}")
        print(f"  (Tổng dataset: {total}  |  Đã xét: {len(gold_list)})")
        print(f"{'='*62}")
        print("\nTính F-score:")
        print("  python -m nlacp.evaluation.evaluator --gold outputs/policies/policy_dataset_gold.json")
    else:
        print("\n[INFO] Không có gì được lưu.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Interactive Verification — Tạo Gold Standard để tính F-score"
    )
    parser.add_argument("--resume", action="store_true",
                        help="Tiếp tục từ lần xét trước (bỏ qua các id đã có trong gold)")
    args = parser.parse_args()
    main(resume=args.resume)
