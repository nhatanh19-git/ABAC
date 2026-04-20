# Module 3: Assigning Attributes to Namespaces Hierarchically
# Sub-tasks:
# (1) Computes inheritance 
# (2) Computes assigned attributes

def assign_namespaces(attributes, subject_names, object_names):
    """
    Takes a list of standard attributes (with short_names) and assigns
    them to hierarchical namespaces (e.g., subject:role:senior_nurse).
    FIX 3: Env attrs processed FIRST to avoid false routing into subject/object.
    Fallback changed from "unknown:" to "context:".
    """
    namespace_attrs = []

    role_keywords     = {"nurse", "technician", "manager", "staff", "student",
                         "officer", "administrator", "librarian", "user", "doctor"}  # added "doctor"
    dept_keywords     = {"department", "hospital", "clinic", "lab", "ward", "office"}
    resource_keywords = {"record", "procedure", "report", "paper", "data",
                         "log", "material", "file", "grade", "submission"}

    for attr_orig in attributes:
        attr = attr_orig.copy()
        short_name = attr.get("short_name", "")
        cat        = attr.get("category", "")
        sub_cat    = attr.get("sub_category", attr.get("subcategory", ""))

        if cat == "environment":
            if sub_cat == "temporal":
                namespace = f"env:time:{short_name}"
            elif sub_cat in ("network",) or any(
                    k in short_name for k in ("network", "vpn", "intranet")):
                namespace = f"env:network:{short_name}"
            elif sub_cat == "device" or any(
                    k in short_name for k in ("device", "workstation", "platform")):
                namespace = f"env:device:{short_name}"
            elif sub_cat in ("spatial", "physical"):
                namespace = f"env:location:{short_name}"
            else:
                namespace = f"env:context:{short_name}"

        # Subject attrs
        elif cat == "subject":
            if any(k in short_name for k in role_keywords):
                namespace = f"subject:role:{short_name}"
            elif any(k in short_name for k in dept_keywords):
                namespace = f"subject:department:{short_name}"
            else:
                namespace = f"subject:group:{short_name}"

        # Object attrs
        elif cat == "object":
            if any(k in short_name for k in resource_keywords):
                namespace = f"object:type:{short_name}"
            else:
                namespace = f"object:prop:{short_name}"

        else:
            namespace = f"context:{short_name}"

        attr["namespace"] = namespace
        namespace_attrs.append(attr)

    return namespace_attrs

if __name__ == "__main__":
    sample_attrs = [
        {"short_name": "senior_nurse", "category": "subject"},
        {"short_name": "finance_department", "category": "subject"},
        {"short_name": "health_record", "category": "object"},
        {"short_name": "business_hour", "category": "temporal"},
        {"short_name": "vact_intranet", "category": "spatial"}
    ]
    
    print("Testing Module 3: Namespace Assignment")
    results = assign_namespaces(sample_attrs, "senior nurse", "health record")
    for r in results:
        print(f"Short Name: '{r['short_name']}' -> Namespace: '{r['namespace']}'")
