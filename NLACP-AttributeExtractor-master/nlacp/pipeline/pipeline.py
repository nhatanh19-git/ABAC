from nlacp.extraction.relation_candidate import parse_sentence, extract_relations
from nlacp.extraction.env_extractor import extract_env_attributes
from nlacp.extraction.short_name_suggester import suggest_short_names
from nlacp.normalization.namespace_assigner import assign_namespaces
from nlacp.normalization.category_identifier import identify_categories
from nlacp.io.dataset_builder import add_policy

try:
    from nlacp.normalization.data_type_infer import annotate_attributes_with_type
    HAS_DTYPE = True
except ImportError:
    HAS_DTYPE = False

# ===================================================================
# pipeline.py
# Full ABAC Pipeline (Alohaly et al. 2019 + env_extractor 3-layer)
#
# Pipeline:
#   Module 1: Relation Extraction (subject/action/object)
#   Module 1b: Env Extraction (3-layer algorithm)
#   Module 2: Short Name Suggestion
#   Module 3: Namespace Assignment (env.time.* / env.location.* / ...)
#   Module 4: Category Identification (SA/OA)
#   Module 5: Data Type Inference
#   Module 6: Policy Representation
# ===================================================================

# Prepositions to filter from SA/OA pairs
_ENV_PREPS = {
    "during", "between", "after", "before", "within",
    "throughout", "until", "from", "via", "through",
    "using", "at", "on", "inside", "outside"
}


def _cnn_filter(attributes):
    """
    Placeholder cho CNN filter.
    Trong tương lai, gọi model Predict để lọc attributes.
    Hiện tại pass-through toàn bộ attrs.
    """
    return attributes


def process_sentence(sentence: str, save: bool = False) -> dict:
    """
    Xử lý một câu policy theo pipeline 6 module:
      1. Extract ALL candidate pairs (SA/OA + action/subject/object)
      1b. Extract ENV attributes (3-layer env_extractor)
      2. Loại bỏ env overlap khỏi candidate pairs
      3. Classify pairs còn lại → Subject/Object attributes
      4. Short name → Namespace → Data type
    """
    # [Module 1b] Extract ENV TRƯỚC để lọc SA/OA pairs chính xác hơn
    env_attrs = extract_env_attributes(sentence)

    # Xây dựng env_tokens từ tất cả fields của env (full_value + env_value components)
    env_tokens = set()
    for env in env_attrs:
        # Từ full_value
        for word in env.get("full_value", "").lower().split():
            if word not in {"a", "an", "the"}:
                env_tokens.add(word)
        # Trigger word
        trigger = (env.get("trigger") or "").lower()
        if trigger and not trigger.startswith("ner:"):
            env_tokens.add(trigger)
        # Từ env_value structured dict (time ranges, duration, am/pm)
        ev = env.get("env_value")
        if ev and isinstance(ev, dict):
            # Nested from/to: {"from": {"value":7,"unit":"am"}, "to": {...}}
            for key in ("from", "to"):
                v = ev.get(key)
                if isinstance(v, dict):
                    if v.get("value") is not None:
                        env_tokens.add(str(v["value"]).lower())
                    if v.get("unit"):
                        env_tokens.add(str(v["unit"]).lower())
                    if v.get("modifier"):
                        env_tokens.add(str(v["modifier"]).lower())
                    if v.get("text"):
                        for w in str(v["text"]).lower().split():
                            env_tokens.add(w)
                elif v is not None:
                    for w in str(v).lower().split():
                        env_tokens.add(w)
            # Direct value/unit (duration: {"operator":"within","value":2,"unit":"hours"})
            direct_val = ev.get("value")
            if direct_val is not None and not isinstance(direct_val, dict):
                env_tokens.add(str(direct_val).lower())
            if ev.get("unit"):
                env_tokens.add(str(ev["unit"]).lower())
            if ev.get("modifier"):
                env_tokens.add(str(ev["modifier"]).lower())

    # [Module 1] Extract ALL candidate pairs + S/A/O metadata
    tokens   = parse_sentence(sentence)
    relation = extract_relations(sentence, tokens)

    # [Module 2] CNN filter (hiện pass-through)
    all_pairs = _cnn_filter(relation["attributes"])

    # Loại bỏ pairs mà name thuộc env tokens / prep tokens
    _sub = relation.get("subject") or ""
    _obj = relation.get("object") or ""
    rel_sub = (" ".join(_sub) if isinstance(_sub, list) else str(_sub)).lower()
    rel_obj = (" ".join(_obj) if isinstance(_obj, list) else str(_obj)).lower()
    sa_oa_pairs = []
    for attr in all_pairs:
        name  = (attr.get("name") or "").lower()
        value = (attr.get("value") or "").lower()
        # Bỏ preposition tokens
        if name in _ENV_PREPS:
            continue
        # Bỏ nếu name là env token
        if name in env_tokens:
            continue
        # Bỏ nếu value là env token (nhưng không phải subject/object)
        if value in env_tokens and value not in {rel_sub, rel_obj}:
            continue
        sa_oa_pairs.append(attr)

    # [Module 4] Category Identification
    attrs_mod4 = identify_categories(sa_oa_pairs, sentence, relation.get("object", ""))

    # [Module 2] Suggest short names
    attrs_mod2 = suggest_short_names(attrs_mod4)

    # [Module 3] Assign namespaces (SA/OA)
    attrs_mod3 = assign_namespaces(attrs_mod2, relation.get("subject"), relation.get("object"))

    # [Module 5] Annotate data type
    if HAS_DTYPE:
        final_attrs = annotate_attributes_with_type(attrs_mod3)
    else:
        final_attrs = []
        for a in attrs_mod3:
            a["data_type"] = "string"
            final_attrs.append(a)

    # [Module 6] Tách riêng SA/OA và gắn ENV
    sa_oa = [a for a in final_attrs if a.get("category") in ("subject", "object")]

    # ENV attrs — giữ nguyên format từ 3-layer env_extractor
    # (đã có env_type, subcategory, namespace, data_type, ner_type)
    formatted_env = []
    for env in env_attrs:
        formatted_env.append({
            "env_type":    env.get("env_type", ""),
            "subcategory": env.get("subcategory", ""),
            "trigger":     env.get("trigger", ""),
            "phrase":      env.get("phrase", ""),
            "env_name":    env.get("env_name"),    # tên ngữ nghĩa (hoặc None)
            "env_value":   env.get("env_value"),   # giá trị cụ thể (hoặc None)
            "full_value":  env.get("full_value", ""),
            "ner_type":    env.get("ner_type", ""),
            "normalized":  env.get("normalized", ""),
            "namespace":   env.get("namespace", ""),
            "data_type":   env.get("data_type", ""),
            "method":      env.get("method", "")
        })

    relation["attributes"]  = sa_oa
    relation["environment"] = formatted_env

    if save:
        add_policy(relation)

    return relation


def main():
    print("\n" + "=" * 55)
    print("  ABAC Policy NLP Extraction (3-layer env_extractor)")
    print("=" * 55)
    print("\nType 'exit' to stop\n")
    print("Ví dụ câu đầu vào:")
    print("  An on-call senior nurse may change the list of approved lab procedures.")
    print("  A senior nurse can view records during business hours within the hospital.")
    print("  Administrators using trusted workstations can modify system settings.\n")

    while True:
        try:
            sentence = input("Enter policy sentence: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not sentence:
            continue
        if sentence.lower() == "exit":
            break

        result = process_sentence(sentence)

        print("\n--- Extracted ABAC Policy (6 Modules) ---")
        print(f"  Subject  : {result.get('subject')}")
        print(f"  Actions  : {', '.join(result.get('actions', []))}")
        print(f"  Object   : {result.get('object')}")

        env_list = result.get("environment", [])
        if env_list:
            print(f"  Environment ({len(env_list)}):")
            for e in env_list:
                et  = e.get("env_type", "?")
                sub = e.get("subcategory", "?")
                fv  = e.get("full_value", "?")
                ns  = e.get("namespace", "?")
                ner = e.get("ner_type", "")
                print(f"    [{et}|{sub}] \"{fv}\" → {ns}"
                      + (f"  (NER:{ner})" if ner else ""))
        else:
            print("  Environment: (none detected)")

        sa_oa = result.get("attributes", [])
        if sa_oa:
            print(f"  Attributes ({len(sa_oa)}):")
            for a in sa_oa:
                cat = a.get("category", "?").upper()
                ns  = a.get("namespace", "?")
                sn  = a.get("short_name", "?")
                print(f"    [{cat}] {ns} = \"{sn}\"")
        else:
            print("  Attributes: (none detected)")
        print()


if __name__ == "__main__":
    main()