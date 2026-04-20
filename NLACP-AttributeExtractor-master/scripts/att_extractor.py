#!/usr/bin/env python
"""
scripts/att_extractor.py — Bước 2 mới của pipeline

Đọc policy_dataset.json (đã verified bởi interactive_verification.py),
thực hiện:
  2A. Gán SA/OA attributes từ validated relation_pairs
      (short_name, namespace, data_type)
  2B. Gán ENV namespace theo cấu trúc phân cấp environment.*
  2C. DBSCAN clustering → attribute keys (gom nhóm các attributes tương đồng)
  2D. Namespace hierarchy

Output:
  policy_dataset.json (complete — có đầy đủ attributes + environment)
  outputs/clusters/attribute_clusters.json
  outputs/hierarchy/namespace_hierarchy.json

Usage:
    python scripts/att_extractor.py
    python scripts/att_extractor.py --no-cluster   # Bỏ qua clustering
"""
import json
import os
import sys
import argparse

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from nlacp.extraction.short_name_suggester import suggest_short_names
from nlacp.normalization.namespace_assigner import assign_namespaces
from nlacp.normalization.category_identifier import identify_categories
from nlacp.normalization.data_type_infer import annotate_attributes_with_type
from nlacp.paths import (
    POLICY_DATASET_PATH, ATTRIBUTE_CLUSTERS_PATH, NAMESPACE_HIERARCHY_PATH,
    NS_ENV_TIME, NS_ENV_LOC
)

DATASET_DIR = os.path.dirname(POLICY_DATASET_PATH)
PREDICATE_MAP_PATH = os.path.join(DATASET_DIR, "predicate_property_map.json")
def load_predicate_map():
    try:
        with open(PREDICATE_MAP_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

PREDICATE_MAP = load_predicate_map()

# =====================================================================
#  ENV Namespace — cấu trúc phân cấp theo đặc tả
# =====================================================================

# Mapping env_type → namespace top-level
ENV_NS_MAP = {
    "temporal":         "environment.time",
    "spatial_physical": "environment.location",
    "spatial_network":  "environment.network",
    "spatial_device":   "environment.device",
    "conditional":      "environment.condition",
}

# Mapping subcategory → namespace leaf
ENV_SUB_NS = {
    "working_period": "working_period",  # environment.time.working_period
    "absolute":       "absolute_time",
    "recurring":      "recurring",
    "event":          "event_based",
    "relative":       "relative_time",
    "facility":       "facility",        # environment.location.facility
    "campus":         "campus",
    "geographic":     "geographic",
    "location":       "location",
    "network_zone":   "network_zone",    # environment.network.network_zone
    "access_type":    "access_type",     # environment.network.access_type
    "device_type":    "device_type",     # environment.device.device_type
}


def _build_env_namespace(env_entry: dict) -> str:
    """
    Tạo namespace cho environment entry theo cấu trúc:
      environment.time.working_period:business_hours
      environment.location.facility:hospital
      environment.network.access_type:vpn
      environment.condition.device.connection_status:secure_network (conditional_clause)
    """
    env_type    = env_entry.get("env_type", "")
    subcategory = env_entry.get("subcategory", "")
    normalized  = env_entry.get("normalized", "")

    if env_type == "conditional" and subcategory == "conditional_clause":
        cond = env_entry.get("condition", {})
        entity = cond.get("subject", "").lower().replace(" ", "_") or "unknown_entity"
        predicate = cond.get("predicate", "").lower()
        prop = PREDICATE_MAP.get(predicate, predicate if predicate else "status")
        val = cond.get("object", "").lower().replace(" ", "_") or "true"
        if cond.get("negated"):
            val = f"not_{val}" if val != "true" else "false"
        return f"environment.condition.{entity}.{prop}:{val}"

    top = ENV_NS_MAP.get(env_type, "environment.other")
    sub = ENV_SUB_NS.get(subcategory, subcategory) if subcategory else "unknown"
    val = normalized if normalized else "unknown"
    return f"{top}.{sub}:{val}"


# =====================================================================
#  SA/OA Attribute Processing
# =====================================================================

def process_sa_oa_attributes(policy: dict) -> list:
    """
    Chuyển validated relation_pairs thành SA/OA attributes hoàn chỉnh.
    Steps:
      1. Classify categories (subject / object)
      2. Suggest short names
      3. Assign namespaces
      4. Infer data types
    """
    # Lấy env tokens để loại overlap
    env_tokens = set()
    for env in policy.get("environment", []):
        for word in (env.get("full_value") or "").lower().split():
            if word not in {"a", "an", "the"}:
                env_tokens.add(word)
        trigger = (env.get("trigger") or "").lower()
        if trigger and not trigger.startswith("ner:"):
            env_tokens.add(trigger)

    subjects = policy.get("subject", [])
    if isinstance(subjects, str): subjects = [subjects]
    sub_names = [s.lower() for s in subjects]
    
    objects = policy.get("object", [])
    if isinstance(objects, str): objects = [objects]
    obj_names = [o.lower() for o in objects]

    # Build raw attrs từ relation_pairs
    ENV_PREPS = {"during", "within", "after", "before", "between", "via",
                 "through", "using", "at", "on", "from", "inside", "outside",
                 "throughout", "until"}

    raw_attrs = []
    for pair in policy.get("relation_pairs", []):
        val  = pair[0] if len(pair) > 0 else ""
        name = pair[1] if len(pair) > 1 else ""
        if not val or not name:
            continue
        if name.lower() in ENV_PREPS:
            continue

        # Loại bỏ nếu name hoặc value là env token
        if name.lower() in env_tokens:
            continue
        if val.lower() in env_tokens and val.lower() not in sub_names and val.lower() not in obj_names:
            continue

        # Category sơ bộ
        if val.lower() in sub_names:
            cat = "subject"
        elif val.lower() in obj_names:
            cat = "object"
        else:
            cat = "unclassified"

        raw_attrs.append({
            "name":     name,
            "value":    val,
            "category": cat
        })

    # Module 4: Category identification
    sentence = policy.get("sentence", "")
    attrs = identify_categories(raw_attrs, sentence, objects)

    # Module 2: Short names
    attrs = suggest_short_names(attrs)

    # Module 3: Namespaces
    attrs = assign_namespaces(attrs, subjects, objects)

    # Module 5: Data types
    attrs = annotate_attributes_with_type(attrs)

    return attrs


# =====================================================================
#  ENV Namespace fix-up
# =====================================================================

def process_env_namespace(policy: dict) -> list:
    """
    Từ environment entries trong policy (đã verified),
    đảm bảo namespace đúng chuẩn phân cấp environment.*.
    """
    updated = []
    for env in policy.get("environment", []):
        # Nếu chưa có namespace hoặc namespace format cũ → build lại
        ns = env.get("namespace", "")
        if not ns or not ns.startswith("environment."):
            ns = _build_env_namespace(env)
        env["namespace"] = ns
        updated.append(env)
    return updated


# =====================================================================
#  DBSCAN Clustering
# =====================================================================

def run_clustering(dataset: dict):
    """Chạy attribute clustering (DBSCAN) và lưu kết quả."""
    try:
        from nlacp.mining.attribute_cluster import main as run_cluster_main
        print("\n[INFO] Đang chạy DBSCAN attribute clustering...")
        run_cluster_main()
        print(f"  [OK] Clusters → {ATTRIBUTE_CLUSTERS_PATH}")
    except Exception as e:
        print(f"  [WARN] Clustering thất bại: {e}")


def run_hierarchy():
    """Chạy namespace hierarchy."""
    try:
        from nlacp.mining.namespace_hierarchy import main as run_hier_main
        print("\n[INFO] Đang chạy namespace hierarchy...")
        run_hier_main()
        print(f"  [OK] Hierarchy → {NAMESPACE_HIERARCHY_PATH}")
    except Exception as e:
        print(f"  [WARN] Hierarchy thất bại: {e}")


# =====================================================================
#  REPORT ENV NAMESPACES
# =====================================================================

def print_env_namespace_report(all_policies: list):
    """
    In báo cáo tái sử dụng namespace environment.
    Cùng một 'business hours' có thể xuất hiện trong nhiều policy khác nhau
    → namespace được định nghĩa một lần, tham chiếu lại.
    """
    from collections import defaultdict, Counter
    ns_usage = defaultdict(list)

    for p in all_policies:
        for env in p.get("environment", []):
            ns = env.get("namespace", "")
            if ns:
                ns_usage[ns].append(p.get("id"))

    reused = {ns: ids for ns, ids in ns_usage.items() if len(ids) > 1}

    if reused:
        print("\n  ENV Namespace reuse (xuất hiện trong nhiều policies):")
        for ns, ids in sorted(reused.items(), key=lambda x: -len(x[1])):
            print(f"    {ns}  → policies: {ids}")


# =====================================================================
#  MAIN
# =====================================================================

def main(run_cluster: bool = True):
    print("\n" + "=" * 60)
    print("  ATT EXTRACTOR — Bước 2")
    print("  Attribute Processing + ENV Namespace + DBSCAN Clustering")
    print("=" * 60)

    if not os.path.exists(POLICY_DATASET_PATH):
        print(f"\n[ERROR] {POLICY_DATASET_PATH} không tồn tại.")
        print("        Chạy 'python scripts/interactive_verification.py' trước (Bước 1).")
        return

    with open(POLICY_DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    policies = data.get("policies", [])
    if not policies:
        print("[WARN] policy_dataset.json rỗng.")
        return

    print(f"\n[INFO] Đang xử lý {len(policies)} policy(ies)...\n")

    for policy in policies:
        sentence = policy.get("sentence", "")
        pid      = policy.get("id", "?")
        print(f"  Policy #{pid}: {sentence[:65]}...")

        # B1: Fix-up ENV namespaces
        policy["environment"] = process_env_namespace(policy)
        env_count = len(policy["environment"])
        print(f"    ENV: {env_count} entry(ies)")
        for e in policy["environment"]:
            print(f"      [{e['env_type']:16s}|{e['subcategory']:14s}]"
                  f" \"{e.get('full_value', e.get('phrase','?'))}\"")
            print(f"         → {e['namespace']}")

        # B2: Process SA/OA attributes
        policy["attributes"] = process_sa_oa_attributes(policy)
        attr_count = len(policy["attributes"])
        print(f"    SA/OA: {attr_count} attribute(s)")
        for a in policy["attributes"]:
            cat = a.get("category", "?").upper()
            ns  = a.get("namespace", "?")
            sn  = a.get("short_name", "?")
            print(f"      [{cat}] {ns} = \"{sn}\"")
        print()

    # Ghi lại policy_dataset.json đã enriched
    with open(POLICY_DATASET_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"[OK] Saved complete policies → {POLICY_DATASET_PATH}")

    # In báo cáo namespace reuse
    print_env_namespace_report(policies)

    # Clustering
    if run_cluster:
        run_clustering(data)
        run_hierarchy()

    print("\n" + "=" * 60)
    print("  BƯỚC 2 HOÀN TẤT!")
    print(f"  → policy_dataset.json : {POLICY_DATASET_PATH}")
    if run_cluster:
        print(f"  → attribute_clusters  : {ATTRIBUTE_CLUSTERS_PATH}")
        print(f"  → namespace_hierarchy : {NAMESPACE_HIERARCHY_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ATT Extractor — Bước 2 Pipeline")
    parser.add_argument("--no-cluster", action="store_true",
                        help="Bỏ qua DBSCAN clustering")
    args = parser.parse_args()
    main(run_cluster=not args.no_cluster)
