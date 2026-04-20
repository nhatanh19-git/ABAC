import json
import os

# ===================================================================
# dataset_builder.py  (nlacp/io/)
# Quản lý đọc/ghi dataset JSON
# ===================================================================

# nlacp/io/ → nlacp/ → project root
from nlacp.paths import POLICY_DATASET_PATH as DATASET_PATH

# Stop determiners that should never be stored as modifier
_STOP_DETS = {"a", "an", "the", "this", "that", "these", "those"}


def ensure_dataset():
    os.makedirs(os.path.dirname(DATASET_PATH), exist_ok=True)
    if not os.path.exists(DATASET_PATH):
        data = {"policies": []}
        with open(DATASET_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)


def load_dataset():
    ensure_dataset()
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_dataset(data):
    with open(DATASET_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def _format_environment(env_attrs):
    """Chuyển từ env_extractor format sang format mới có preposition/head/modifier."""
    result = []
    for ea in env_attrs:
        if "full_value" in ea:
            result.append(ea)
            continue
            
        value = ea.get("value", "")
        parts = value.split()
        prep  = ea.get("trigger", parts[0] if parts else "")
        # Lọc bỏ preposition gốc + stop determiners
        content = [p for p in parts
                   if p.lower() not in _STOP_DETS
                   and p.lower() != prep.lower()]
        head     = content[-1] if content else (parts[-1] if parts else value)
        modifier = content[0]  if len(content) > 1 else None
        result.append({
            "type":        ea.get("sub_category", ea.get("subcategory", "")),
            "preposition": prep,
            "head":        head,
            "modifier":    modifier,
            "full_value":  value,
            "normalized":  ea.get("short_name", ""),
            "namespace":   ea.get("namespace", ""),
            "data_type":   ea.get("data_type", "string")
        })
    return result


def add_policy(relation_data):
    """
    Thêm một policy vào dataset.
    relation_data chứa: sentence, subject, actions, object, attributes, environment
    Mỗi attribute/environment có fields tương ứng.
    """
    dataset = load_dataset()

    # Tránh trùng câu
    for policy in dataset["policies"]:
        if policy["sentence"] == relation_data["sentence"]:
            return

    new_id = len(dataset["policies"]) + 1

    actions_list = relation_data.get("actions", [])

    policy = {
        "id":          new_id,
        "sentence":    relation_data["sentence"],
        "subject":     relation_data.get("subject"),
        "actions":     actions_list,
        "object":      relation_data.get("object"),
        "attributes":  relation_data.get("attributes", []),
        "environment": _format_environment(relation_data.get("environment", []))
    }

    dataset["policies"].append(policy)
    save_dataset(dataset)
    print(f"[OK] Policy #{new_id} added to dataset.")