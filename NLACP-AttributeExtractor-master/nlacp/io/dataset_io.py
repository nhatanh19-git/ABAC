"""
nlacp/io/dataset_io.py — Centralized dataset I/O for ABAC Pipeline v2.0

Supports both v1 (legacy) and v2.0 (Pydantic-based) policy dataset formats.
All pipeline scripts should use this module instead of direct json.load/dump.

Format v1 (legacy):
    {
        "policies": [
            {"id", "sentence", "subject", "actions", "object", "relation_pairs", "environment", ...}
        ]
    }

Format v2.0:
    {
        "version": "2.0",
        "domain": "...",
        "policies": [
            {"id", "sentence", "authorization_decision", "policy_modality",
             "subjects", "actions", "resource", "environments", "context", ...}
        ]
    }
"""

import json
import os
import logging
from typing import Optional, List, Dict, Any, Tuple
from copy import deepcopy

from nlacp.paths import POLICY_DATASET_PATH, POLICY_DATASET_GOLD_PATH

logger = logging.getLogger(__name__)

CURRENT_VERSION = "2.0"


# ============================================================================
#  Version Detection
# ============================================================================

def detect_version(data: dict) -> str:
    """
    Detect dataset format version.

    Returns:
        "2.0" if data has 'version' field == "2.0"
        "1.0" otherwise (legacy format)
    """
    return data.get("version", "1.0")


def is_v2(data: dict) -> bool:
    """Return True if dataset is v2.0 format."""
    return detect_version(data) == "2.0"


# ============================================================================
#  Raw Load / Save
# ============================================================================

def load_raw(path: str = None) -> dict:
    """
    Load dataset file as raw dict (any version).

    Returns:
        dict with 'policies' key, or empty dict if file doesn't exist.
    """
    target = path or POLICY_DATASET_PATH
    if not os.path.exists(target):
        return {}
    try:
        with open(target, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to load dataset from {target}: {e}")
        return {}


def save_raw(data: dict, path: str = None) -> None:
    """Save raw dict to dataset file."""
    target = path or POLICY_DATASET_PATH
    os.makedirs(os.path.dirname(target), exist_ok=True)
    # Ensure compatibility: rename 'resource' -> 'object' for saved output
    out = deepcopy(data)
    for p in out.get("policies", []):
        if "resource" in p and "object" not in p:
            p["object"] = p.pop("resource")

    with open(target, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=4, ensure_ascii=False)


# ============================================================================
#  V2 Typed Load / Save
# ============================================================================

def save_dataset_v2(dataset, path: str = None) -> None:
    """
    Save a PolicyDataset (Pydantic v2 object) to JSON file.

    Args:
        dataset: PolicyDataset Pydantic model instance
        path: Optional output path (default: POLICY_DATASET_PATH)
    """
    target = path or POLICY_DATASET_PATH
    os.makedirs(os.path.dirname(target), exist_ok=True)
    # Dump to dict so we can rename keys for display/output
    data = dataset.model_dump()
    for p in data.get("policies", []):
        if "resource" in p and "object" not in p:
            p["object"] = p.pop("resource")

    with open(target, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    logger.info(f"Saved v2.0 dataset ({len(dataset.policies)} policies) → {target}")


def load_dataset_v2(path: str = None):
    """
    Load and validate dataset from file as PolicyDataset.

    Returns:
        PolicyDataset instance or None if file doesn't exist / invalid format.
    """
    from nlacp.validation.schema_validator import PolicyDataset, PolicyValidator

    target = path or POLICY_DATASET_PATH
    data = load_raw(target)
    if not data:
        return None

    if not is_v2(data):
        logger.warning(f"Dataset at {target} is not v2.0 format (version={detect_version(data)}). "
                       "Use load_raw() for v1 data.")
        return None

    validator = PolicyValidator(strict_mode=False)
    is_valid, errors, dataset = validator.validate_dataset(data)
    if not is_valid:
        logger.error(f"Dataset validation failed: {errors}")
    return dataset


# ============================================================================
#  Unified policy list accessor
# ============================================================================

def get_policies_list(path: str = None) -> List[dict]:
    """
    Return policies list from dataset file regardless of version.

    Returns:
        List of policy dicts (raw, not validated).
    """
    data = load_raw(path)
    return data.get("policies", [])


def get_processed_sentences(path: str = None) -> set:
    """Return set of lowercase sentence strings already in the dataset."""
    policies = get_policies_list(path)
    return {p.get("sentence", "").lower().strip() for p in policies}


def get_max_id(path: str = None) -> int:
    """Return the maximum policy ID in the dataset (0 if empty)."""
    policies = get_policies_list(path)
    if not policies:
        return 0
    return max((p.get("id", 0) for p in policies), default=0)


# ============================================================================
#  Gold Standard I/O
# ============================================================================

def load_gold_raw(path: str = None) -> dict:
    """Load gold standard dataset (raw dict)."""
    return load_raw(path or POLICY_DATASET_GOLD_PATH)


def save_gold_raw(data: dict, path: str = None) -> None:
    """Save gold standard dataset (raw dict)."""
    save_raw(data, path or POLICY_DATASET_GOLD_PATH)


def save_gold_v2(dataset, path: str = None) -> None:
    """Save gold standard dataset as v2.0."""
    save_dataset_v2(dataset, path or POLICY_DATASET_GOLD_PATH)


# ============================================================================
#  V2 → display helpers  (for interactive_verification.py)
# ============================================================================

def v2_policy_to_display(policy: dict) -> dict:
    """
    Extract display-friendly flat fields from a v2 policy dict.

    Returns dict with keys: subject_str, actions_str, object_str, env_list, conditions_list
    """
    # Subject names
    subjects = policy.get("subjects", [])
    subject_roles = [s.get("role") or s.get("entity_type", "?") for s in subjects]
    subject_str = ", ".join(subject_roles) if subject_roles else "(none)"

    # Actions verbs
    actions = policy.get("actions", [])
    action_verbs = [a.get("verb", a.get("operation", "?")) for a in actions]
    actions_str = ", ".join(action_verbs) if action_verbs else "(none)"

    # Resource/Object label (prefer `object` field in saved output)
    resource = policy.get("object") or policy.get("resource") or {}
    object_str = resource.get("label") or resource.get("entity_type") or "(none)"

    # Environments
    env_list = policy.get("environments", [])

    # Context/conditions
    conditions_list = policy.get("context", [])

    return {
        "subject_str": subject_str,
        "actions_str": actions_str,
        "object_str": object_str,
        "env_list": env_list,
        "conditions_list": conditions_list,
    }


# ============================================================================
#  V2 attr helpers  (for att_extractor.py)
# ============================================================================

def extract_sa_attrs_from_v2(policy: dict) -> List[dict]:
    """
    Extract Subject Attributes (SA) from a v2 policy's subjects[].qualifiers.

    Returns list of attr dicts with keys: name, value, category="subject"
    """
    attrs = []
    for subj in policy.get("subjects", []):
        role = subj.get("role", "")
        qualifiers = subj.get("qualifiers") or {}

        for attr_name in ("type", "rank", "status", "office", "department"):
            val = qualifiers.get(attr_name)
            if val and isinstance(val, str):
                attrs.append({
                    "name": attr_name,
                    "value": role or val,
                    "attr_value": val,
                    "category": "subject",
                    "subject_role": role,
                })
            elif val and isinstance(val, list):
                for v in val:
                    attrs.append({
                        "name": attr_name,
                        "value": role or v,
                        "attr_value": v,
                        "category": "subject",
                        "subject_role": role,
                    })
    return attrs


def extract_oa_attrs_from_v2(policy: dict) -> List[dict]:
    """
    Extract Object/Resource Attributes (OA) from a v2 policy's resource.

    Returns list of attr dicts with keys: name, value, category="object"
    """
    attrs = []
    resource = policy.get("resource") or {}
    if not resource:
        return attrs

    entity_type = resource.get("entity_type", "data")
    label = resource.get("label", "")

    # qualifier (own, every, all...)
    qualifier = resource.get("qualifier")
    if qualifier:
        attrs.append({
            "name": "qualifier",
            "value": label or entity_type,
            "attr_value": qualifier,
            "category": "object",
            "resource_type": entity_type,
        })

    # scope.level
    scope = resource.get("scope") or {}
    scope_level = scope.get("level")
    if scope_level:
        attrs.append({
            "name": "scope",
            "value": label or entity_type,
            "attr_value": scope_level,
            "category": "object",
            "resource_type": entity_type,
        })

    # subject_filter
    subj_filter = resource.get("subject_filter")
    if subj_filter:
        attrs.append({
            "name": "subject_filter",
            "value": label or entity_type,
            "attr_value": subj_filter,
            "category": "object",
            "resource_type": entity_type,
        })

    # attributes.sensitivity / attributes.status
    res_attrs = resource.get("attributes") or {}
    for attr_name in ("sensitivity", "status"):
        val = res_attrs.get(attr_name)
        if val:
            attrs.append({
                "name": attr_name,
                "value": label or entity_type,
                "attr_value": val,
                "category": "object",
                "resource_type": entity_type,
            })

    return attrs


def build_env_namespace_v2(env: dict) -> str:
    """
    Build environment namespace string from a v2 Environment dict.

    v2 EnvironmentType: system | temporal | location | network

    Returns e.g.: "environment.time.business_hours", "environment.location.hospital"
    """
    env_type = env.get("env_type", "")
    systems = env.get("systems") or []
    time_range = env.get("time_range") or {}
    trigger_phrase = env.get("trigger_phrase", "")

    # Map env_type → top-level namespace
    type_ns_map = {
        "temporal": "environment.time",
        "location": "environment.location",
        "network":  "environment.network",
        "system":   "environment.system",
    }
    top = type_ns_map.get(env_type, "environment.other")

    # Use first system label if available
    if systems:
        label = systems[0].get("label", "").lower().replace(" ", "_")
        return f"{top}.{label}" if label else top

    # Temporal: use time range
    if env_type == "temporal" and time_range:
        from_t = time_range.get("from_time") or time_range.get("from", "")
        to_t   = time_range.get("to_time")   or time_range.get("to", "")
        if from_t and to_t:
            return f"{top}.range:{from_t}-{to_t}"

    # Fallback: use trigger phrase
    if trigger_phrase:
        slug = trigger_phrase.lower().replace(" ", "_")
        return f"{top}.{slug}"

    return top
