import json
import os

# ===================================================================
# namespace_hierarchy.py
# Module 3: Hierarchical Namespace Assignment (Alohaly et al. 2019)
#
# Xây dựng cấu trúc phân cấp ABAC từ clusters thuộc tính:
#   1. Group attributes theo element (subject/object group)
#   2. Tính inheritance: isAncestor(ns1, ns2)
#      → ns1 là tổ tiên của ns2 nếu attrs(ns1) ⊆ attrs(ns2)
#   3. Hợp nhất namespaces tương đương (cùng attribute set)
#   4. Tạo đồ thị phân cấp (parents, children, assigned_attributes)
#   5. Lưu vào namespace_hierarchy.json
# ===================================================================

import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from nlacp.paths import (POLICY_DATASET_PATH as DATASET_PATH,
                          ATTRIBUTE_CLUSTERS_PATH as CLUSTERS_PATH,
                          NAMESPACE_HIERARCHY_PATH as OUTPUT_PATH,
                          POLICY_BUNDLES_PATH as BUNDLES_PATH)


# ===================================================================
# 1. Load Data
# ===================================================================

def load_dataset():
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def load_clusters():
    # Prefer explicit attribute clusters file. If missing, try to build
    # a lightweight clusters structure from policy_bundles or from
    # attributes present in the policy dataset (fallback).
    if os.path.exists(CLUSTERS_PATH):
        with open(CLUSTERS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    # Build synthetic clusters from policy bundles if available
    attrs_set = set()
    if os.path.exists(BUNDLES_PATH):
        try:
            with open(BUNDLES_PATH, "r", encoding="utf-8") as f:
                bundles = json.load(f).get("policy_bundles", [])
            # bundles may not contain attribute names; fall back to dataset later
        except Exception:
            bundles = []
    else:
        bundles = []

    # If bundles present, try to extract attribute names and suggested short_names
    attr_to_short = {}    # canonical attr name -> suggested short_name
    attrs_found = set()

    # From dataset attributes (preferred source for short_name suggestions)
    if os.path.exists(DATASET_PATH):
        try:
            with open(DATASET_PATH, "r", encoding="utf-8") as f:
                dataset = json.load(f)
            for policy in dataset.get("policies", []):
                for attr in policy.get("attributes", []):
                    name = (attr.get("name") or attr.get("value") or "").strip()
                    short = (attr.get("short_name") or "").strip()
                    if name:
                        key = name.lower()
                        attrs_found.add(key)
                        if short:
                            attr_to_short[key] = short
        except Exception:
            pass

    # From policy bundles: resource names, relation labels, context relations
    if os.path.exists(BUNDLES_PATH):
        try:
            with open(BUNDLES_PATH, "r", encoding="utf-8") as f:
                bundles = json.load(f).get("policy_bundles", [])
            for b in bundles:
                # resource name
                rc = b.get("resource_cluster", {})
                rname = rc.get("resource") or ""
                if rname:
                    attrs_found.add(str(rname).lower())
                # relations
                ctx = b.get("context_cluster", {})
                for rel in ctx.get("relations", []) or []:
                    # rel may be dict with attribute/value
                    if isinstance(rel, dict):
                        # try keys commonly used
                        for k in ("attribute", "value", "name", "label"):
                            v = rel.get(k)
                            if v:
                                attrs_found.add(str(v).lower())
                    elif isinstance(rel, str):
                        attrs_found.add(rel.lower())
        except Exception:
            pass

    # Helper to compute short name from a list of attribute strings
    def _compute_short_name(attr_list):
        stop = {"a", "an", "the", "of", "in", "at", "on", "by", "to", "for", "own"}
        from collections import Counter
        tokens = []
        for attr in attr_list:
            for t in str(attr).lower().split():
                if t not in stop and len(t) > 2:
                    tokens.append(t)
        if not tokens:
            return (attr_list[0] if attr_list else "attr").replace(" ", "_")
        return Counter(tokens).most_common(1)[0][0]

    # If we have found attrs, group them by suggested short_name or heuristic
    clusters = {"clusters": []}
    if attrs_found:
        grouping = {}
        for a in sorted(attrs_found):
            short = attr_to_short.get(a)
            if not short:
                # heuristic: use token freq
                short = _compute_short_name([a])
            grouping.setdefault(short, []).append(a)

        cid = 0
        for short, members in grouping.items():
            clusters["clusters"].append({
                "cluster_id": cid,
                "short_name": short,
                "attributes": members
            })
            cid += 1
    else:
        # fallback: empty clusters
        clusters = {"clusters": []}

    return clusters


# ===================================================================
# 2. Build Element → Attribute mapping
# ===================================================================

def build_element_attr_map(dataset, clusters):
    """
    Tạo mapping từ element (subject/object text) → set of cluster short_names.
    Dựa trên:
    - policy_dataset.json:  biết element value và attribute name
    - attribute_clusters.json: biết cluster assignment và short name
    """
    # Tạo mapping: attr_name → (cluster_id, short_name)
    attr_to_cluster = {}
    for cluster in clusters.get("clusters", []):
        short_name  = cluster.get("short_name", f"attr_{cluster['cluster_id']}")
        cluster_id  = cluster["cluster_id"]
        for attr in cluster.get("attributes", []):
            attr_name = attr.lower() if isinstance(attr, str) else attr.get("name", "").lower()
            if attr_name:
                attr_to_cluster[attr_name] = {
                    "cluster_id": cluster_id,
                    "short_name": short_name
                }

    # Build element → set of attribute short_names
    element_attrs = {}   # { element_name: { category: "subject"/"object", attrs: set() } }

    for policy in dataset.get("policies", []):
        subjects = policy.get("subject", [])
        if isinstance(subjects, str): subjects = [subjects]
        objects = policy.get("object", [])
        if isinstance(objects, str): objects = [objects]
        
        sub_names = [s.lower().strip() for s in subjects if s.strip()]
        obj_names = [o.lower().strip() for o in objects if o.strip()]

        for attr in policy.get("attributes", []):
            attr_name   = attr.get("name", "").lower()
            category    = attr.get("category", "subject")
            
            elements = sub_names if category == "subject" else obj_names

            for element in elements:
                cluster_info = attr_to_cluster.get(attr_name)
                if not cluster_info:
                    continue

                if element not in element_attrs:
                    element_attrs[element] = {
                        "category": category,
                        "attrs":    set()
                    }
                element_attrs[element]["attrs"].add(cluster_info["short_name"])

    # Convert sets to sorted lists
    for elem in element_attrs:
        element_attrs[elem]["attrs"] = sorted(element_attrs[elem]["attrs"])

    return element_attrs


# ===================================================================
# 3. isAncestor: Tính inheritance
# ===================================================================

def is_ancestor(ns1_attrs, ns2_attrs):
    """
    ns1 là tổ tiên (ancestor) của ns2 nếu attrs(ns1) ⊆ attrs(ns2).
    Nghĩa là ns2 thừa kế tất cả attributes của ns1 + thêm một số attrs riêng.
    """
    set1 = set(ns1_attrs)
    set2 = set(ns2_attrs)
    return set1 < set2  # strict subset


# ===================================================================
# 4. Compute hierarchy
# ===================================================================

def compute_hierarchy(element_attrs):
    """
    Xây dựng cấu trúc phân cấp:
    - parents:   namespaces cha của namespace hiện tại
    - children:  namespaces con
    - assigned:  attributes được gán trực tiếp (không kế thừa từ cha)
    """
    elements = list(element_attrs.keys())
    hierarchy = {}

    for elem in elements:
        hierarchy[elem] = {
            "category":           element_attrs[elem]["category"],
            "attrs":              element_attrs[elem]["attrs"],
            "parents":            [],
            "children":           [],
            "assigned_attributes": []
        }

    # Tính parents/children
    for ns1 in elements:
        for ns2 in elements:
            if ns1 == ns2:
                continue
            attrs1 = element_attrs[ns1]["attrs"]
            attrs2 = element_attrs[ns2]["attrs"]

            if is_ancestor(attrs1, attrs2):
                # ns1 là cha của ns2 — nhưng chỉ thêm parent trực tiếp
                # (parent trực tiếp = không có intermediate ns)
                is_direct = True
                for ns3 in elements:
                    if ns3 in (ns1, ns2):
                        continue
                    attrs3 = element_attrs[ns3]["attrs"]
                    if is_ancestor(attrs1, attrs3) and is_ancestor(attrs3, attrs2):
                        is_direct = False
                        break
                if is_direct:
                    if ns1 not in hierarchy[ns2]["parents"]:
                        hierarchy[ns2]["parents"].append(ns1)
                    if ns2 not in hierarchy[ns1]["children"]:
                        hierarchy[ns1]["children"].append(ns2)

    # Thêm root namespace "subject"/"object" cho các node không có parent
    roots = {"subject": [], "object": []}
    for elem, info in hierarchy.items():
        if not info["parents"]:
            cat = info["category"]
            roots[cat].append(elem)

    # Tính assigned_attributes cho mỗi namespace
    for elem, info in hierarchy.items():
        inherited = set()
        for parent in info["parents"]:
            inherited |= set(hierarchy[parent]["attrs"])
        assigned = [a for a in info["attrs"] if a not in inherited]
        hierarchy[elem]["assigned_attributes"] = assigned

    return hierarchy, roots


# ===================================================================
# 5. Output JSON
# ===================================================================

def build_output(hierarchy, roots):
    namespaces = []
    for name, info in hierarchy.items():
        namespaces.append({
            "namespace":           name,
            "category":            info["category"],
            "all_attributes":      info["attrs"],
            "assigned_attributes": info["assigned_attributes"],
            "parents":             info["parents"],
            "children":            info["children"]
        })

    return {
        "root_subjects": roots.get("subject", []),
        "root_objects":  roots.get("object",  []),
        "namespaces":    namespaces
    }


def save_output(data):
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# ===================================================================
# MAIN
# ===================================================================

def main():
    print("\n" + "="*55)
    print("  Module 3: Hierarchical Namespace Assignment")
    print("  (Alohaly et al. 2019)")
    print("="*55 + "\n")

    # Kiểm tra file tồn tại
    if not os.path.exists(CLUSTERS_PATH):
        print(f"[ERROR] {CLUSTERS_PATH} not found.")
        print("        Run attribute_cluster.py first.")
        return

    dataset = load_dataset()
    clusters = load_clusters()

    element_attrs = build_element_attr_map(dataset, clusters)

    if not element_attrs:
        print("[WARN] No element-attribute mappings found.")
        print("       Make sure policies have attributes with category labels.")
        save_output({"root_subjects": [], "root_objects": [], "namespaces": []})
        return

    print("[INFO] Element → Attributes mapping:")
    for elem, info in element_attrs.items():
        print(f"  {elem:20s} ({info['category']:7s}): {info['attrs']}")

    hierarchy, roots = compute_hierarchy(element_attrs)

    output = build_output(hierarchy, roots)
    save_output(output)

    print(f"\n[INFO] Root subjects: {roots.get('subject', [])}")
    print(f"[INFO] Root objects:  {roots.get('object', [])}")

    print("\n[INFO] Namespace hierarchy:")
    for ns in output["namespaces"]:
        indent = "  " if not ns["parents"] else "    "
        print(f"{indent}[{ns['namespace']}]")
        print(f"{indent}  assigned: {ns['assigned_attributes']}")
        if ns["parents"]:
            print(f"{indent}  parents:  {ns['parents']}")
        if ns["children"]:
            print(f"{indent}  children: {ns['children']}")

    print(f"\n[OK] Namespace hierarchy saved to {OUTPUT_PATH}\n")


if __name__ == "__main__":
    main()
