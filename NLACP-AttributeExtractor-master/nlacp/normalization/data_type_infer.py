import spacy

# ===================================================================
# data_type_infer.py
# Module 5: Attribute Data Type Inference (theo Alohaly et al. 2019)
#
# Dùng spaCy Named Entity Recognition (NER) để suy luận data type
# của attribute value.
#
# Mapping NE type → data type (theo bài báo):
#   ORG, PERSON, GPE, NORP, FAC, PRODUCT, EVENT, WORK_OF_ART → string
#   DATE, TIME                                                 → datetime
#   CARDINAL, ORDINAL, QUANTITY, MONEY, PERCENT               → integer/float
#   Không xác định được                                       → string (default)
# ===================================================================

from nlacp.utils.nlp_utils import get_spacy_model
nlp = get_spacy_model(fallback_to_none=True)


NE_TO_DATATYPE = {
    "PERSON":       "string",
    "ORG":          "string",
    "GPE":          "string",      # country, city
    "NORP":         "string",      # nationality, religion
    "FAC":          "string",      # facility
    "PRODUCT":      "string",
    "EVENT":        "string",
    "WORK_OF_ART":  "string",
    "LAW":          "string",
    "LANGUAGE":     "string",
    "DATE":         "datetime",
    "TIME":         "datetime",
    "CARDINAL":     "integer",
    "ORDINAL":      "integer",
    "QUANTITY":     "float",
    "MONEY":        "float",
    "PERCENT":      "float",
}


def infer_data_type(value_text, category=None, sub_category=None):
    """
    Suy luận data type của một attribute value dựa trên NER.
    Trả về: "string" | "integer" | "float" | "datetime" | "boolean"
    FIX 5: Nhận thêm category và sub_category để infer chính xác hơn.
    """
    if nlp is None:
        return "string"
    if not value_text:
        return "string"

    if category == "environment":
        if sub_category == "temporal":
            return "datetime"   # "during business hours" → datetime, không cần NER
        if sub_category in ("spatial", "network", "device", "physical", "location"):
            return "string"     # location là string trong ABAC

    # Kiểm tra các giá trị boolean phổ biến
    boolean_values = {"true", "false", "yes", "no", "active", "inactive",
                      "enabled", "disabled", "approved", "denied"}
    if value_text.lower() in boolean_values:
        return "boolean"

    # Phân tích NER
    doc = nlp(value_text)
    if doc.ents:
        ent = doc.ents[0]
        return NE_TO_DATATYPE.get(ent.label_, "string")

    # Kiểm tra số đơn giản
    try:
        int(value_text)
        return "integer"
    except ValueError:
        pass

    try:
        float(value_text)
        return "float"
    except ValueError:
        pass

    return "string"


def annotate_attributes_with_type(attributes):
    """
    Thêm trường data_type cho mỗi attribute trong danh sách.
    Mỗi attribute là dict có ít nhất key 'value'.
    FIX 5: Truyền category và sub_category để infer chính xác hơn.
    """
    for attr in attributes:
        attr["data_type"] = infer_data_type(
            attr.get("value", ""),
            attr.get("category", ""),
            attr.get("sub_category", "")
        )
    return attributes


if __name__ == "__main__":
    test_values = [
        "senior", "junior", "on-call", "registered",
        "2024-01-01", "100", "Mayo Clinic", "approved",
        "finance", "doctor", "nurse"
    ]
    for v in test_values:
        dtype = infer_data_type(v)
        print(f"  {v:20s} → {dtype}")
