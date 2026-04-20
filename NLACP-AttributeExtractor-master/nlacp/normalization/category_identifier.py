# Module 4: Identifying the Category of an Attribute
# The paper suggests classifying parsed attributes into Target Categories
# (Subject, Action, Object, Environment). 
# Our pipeline already handles some categorization via dependency parsing (subject/object)
# and Regex/NER (temporal/spatial). This module ensures any orphaned attribute is caught.

def identify_categories(attributes, sentence, object_names=None):
    """
    Source of truth cho category. Chạy TRƯỚC namespace_assigner.
    FIX 4: Không đọc namespace để tránh circular dependency.
    Chỉ đọc category, sub_category, dep fields từ extraction.
    """
    categorized = []

    for attr_orig in attributes:
        attr = attr_orig.copy()
        cat     = attr.get("category", "")
        sub_cat = attr.get("sub_category", attr.get("subcategory", ""))

        # 1. Env attrs từ env_extractor đã có category rõ ràng
        if cat == "temporal":
            attr["category"]     = "environment"
            attr["sub_category"] = "temporal"

        elif cat == "spatial":
            attr["category"]     = "environment"
            attr["sub_category"] = sub_cat if sub_cat else "spatial"

        # 2. SA/OA attrs từ relation_candidate đã có category
        elif cat in ("subject", "object", "action"):
            pass   # giữ nguyên

        # 3. Env attrs có sub_category nhưng category thiếu
        elif not cat and sub_cat in ("temporal", "spatial", "network", "device",
                                     "physical", "relative", "absolute", "recurring",
                                     "event", "ner_detected", "business_hours",
                                     "ner_gpe", "ner_loc", "ner_fac", "ner_org"):
            attr["category"] = "environment"

        # 4. Fallback: suy luận từ dep field (bao gồm 'unclassified' từ Module 1)
        elif not cat or cat == "unclassified":
            if object_names is None: object_names = []
            if isinstance(object_names, str): object_names = [object_names]
            
            dep = attr.get("dep", "")
            val = attr.get("value", "").lower()
            
            _MIN_LEN = 4
            is_obj = False
            for obj_name in object_names:
                obj_lower = obj_name.lower()
                if (val and len(val) >= _MIN_LEN and len(obj_lower) >= _MIN_LEN
                        and (val in obj_lower or obj_lower in val)):
                    is_obj = True
                    break
                    
            if is_obj:
                attr["category"] = "object"
            else:
                attr["category"] = "subject" if dep else "context"

        categorized.append(attr)

    return categorized

if __name__ == "__main__":
    sample_attrs = [
        {"name": "senior", "value": "nurse", "category": "subject", "dep": "amod"},
        {"name": "", "value": "business_hour", "category": "temporal", "sub_category": "business_hours"},
        {"name": "approved", "value": "approved", "category": ""}
    ]
    
    print("Testing Module 4: Category Identification")
    results = identify_categories(sample_attrs, "A senior nurse views records during business hours.")
    for r in results:
        print(f"Attr: '{r.get('value')}' -> Final Category: '{r['category']}'")
