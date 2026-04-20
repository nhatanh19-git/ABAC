import spacy
import json
import os

# ===================================================================
# relation_candidate.py
# Module 1: Attribute Extraction (Alohaly et al. 2019)
#
#   Pattern 1: nsubj + amod      → "senior nurse"
#   Pattern 2: nsubj + compound  → "lab technician"
#   Pattern 3: nsubj + prep      → "nurse at hospital"
#   Pattern 4: dobj + amod       → "approved records"
#   Pattern 5: pobj + amod       → "approved procedures"
# ===================================================================

from nlacp.utils.nlp_utils import get_spacy_model
nlp = get_spacy_model()

SUBJECT_DEPS = {"nsubj", "nsubjpass", "csubj"}
OBJECT_DEPS  = {"dobj", "pobj", "attr"}
ATTR_DEPS    = {"amod", "compound", "acl", "prep", "nummod"}

STOPWORDS = {"a", "an", "the", "his", "her", "its", "their",
             "list", "full", "all", "this", "that",
             "in", "at", "of", "on", "by", "to", "for", "with",
             "from", "up", "into", "as", "about", "over", "under"}

ENV_PREPS = {"during", "between", "after", "before", "within",
             "throughout", "until", "from", "via", "through"}

CONDITIONAL_TRIGGERS = {"when", "if", "unless", "once", "whether", "provided", "assuming", "case"}

def _is_in_conditional_clause(token):
    """Kiểm tra token có thuộc mệnh đề điều kiện (conditional advcl) không."""
    curr = token
    while curr:
        if curr.dep_ == "advcl":
            # check if it has a mark/advmod child as trigger
            for c in curr.children:
                if c.text.lower() in CONDITIONAL_TRIGGERS:
                    return True
                if c.text.lower() == "in":
                    for gc in c.children:
                        if gc.text.lower() == "case":
                            return True
        if curr.head == curr:
            break
        curr = curr.head
    return False

def _get_full_noun(token, exclude_indices=None):
    """
    Lấy danh từ đầy đủ (bao gồm các noun compound modifiers và tính từ đặc thù).
    Ví dụ: 'lab' (compound) + 'procedures' -> 'lab procedures'
    
    exclude_indices: set of token.i values to skip (tokens already claimed as subject/action).
    Nguyên tắc Token Isolation: token đã claim cho subject/action KHÔNG được lọt vào object phrase.
    """
    if not token:
        return None
    if exclude_indices is None:
        exclude_indices = set()
    tokens = [token]
    for child in token.children:
        # Bỏ qua token đã được claim cho subject hoặc action
        if child.i in exclude_indices:
            continue
        # Bổ sung danh từ ghép
        if child.dep_ == "compound" and child.pos_ in ("NOUN", "PROPN"):
            tokens.append(child)
        # Bổ sung dấu gạch nối (patient-record)
        elif child.dep_ == "punct" and child.text == "-":
            tokens.append(child)
        # Sửa lỗi spaCy phân tách các tính từ đặc thù thành amod
        elif child.dep_ == "amod" and child.text.lower() in ("patient", "medical", "financial", "lab", "health"):
            tokens.append(child)
            
    tokens.sort(key=lambda x: x.i)
    text = " ".join([t.text for t in tokens])
    text = text.replace(" - ", "-").replace(" -", "-").replace("- ", "-")
    return text.strip()


def _get_conjuncts(token):
    """Lấy danh sách các noun conjuncts (and/or) của một token."""
    conjs = []
    for child in token.children:
        if child.dep_ == "conj" and child.pos_ in ("NOUN", "PROPN"):
            conjs.append(child)
            conjs.extend(_get_conjuncts(child))
    return conjs


def parse_sentence(sentence):
    """Tokenize + POS tag + dependency parse."""
    doc = nlp(sentence)
    tokens = []
    for token in doc:
        tokens.append({
            "text":     token.text,
            "lemma":    token.lemma_,
            "pos":      token.pos_,
            "dep":      token.dep_,
            "head":     token.head.text,
            "ent_type": token.ent_type_
        })
    return tokens


def extract_relations(sentence, tokens, _doc=None):
    """
    Trích xuất subject, action, object và attributes từ
    dependency tree theo Top-5 patterns của bài báo.

    Mỗi attribute có:
        name     — modifier text
        value    — element nó bổ nghĩa
        category — "subject" hoặc "object"
        dep      — dependency relation dùng để tìm ra nó
    """
    doc = _doc if _doc is not None else nlp(sentence)

    subject_tokens = []
    raw_actions = []
    action_tokens = []
    obj_dobj_tokens = []
    obj_pobj_tokens = []
    attributes = []

    crud_map = {
        "read": "Read", "view": "Read", "access": "Read", "see": "Read", "audit": "Read", "get": "Read",
        "write": "Write",
        "create": "Create", "make": "Create", "add": "Create", "insert": "Create", "upload": "Create",
        "update": "Update", "modify": "Update", "change": "Update", "edit": "Update", "approve": "Update", "request": "Update",
        "delete": "Delete", "remove": "Delete", "destroy": "Delete", "drop": "Delete"
    }

    def _get_action_conjuncts(tok):
        conjs = []
        for c in tok.children:
            if c.dep_ == "conj":
                conjs.append(c)
                conjs.extend(_get_action_conjuncts(c))
        return conjs

    # ── Tìm subject, action(s), object ──
    for token in doc:
        if _is_in_conditional_clause(token):
            continue
            
        if token.dep_ in SUBJECT_DEPS:
            subject_tokens.append(token)
            subject_tokens.extend(_get_conjuncts(token))

        # Bắt root text cho action, và các liên từ nối với nó (conj)
        # Deep crawl conjuncts to catch "view, edit, and delete"
        if token.dep_ == "ROOT" and token.pos_ in ("VERB", "NOUN"):
            raw_actions.append(token.lemma_)
            action_tokens.append(token)
            for conj in _get_action_conjuncts(token):
                if conj.pos_ == "VERB":
                    raw_actions.append(conj.lemma_)
                    action_tokens.append(conj)
                else:
                    if conj.lemma_.lower() in crud_map:
                        raw_actions.append(conj.lemma_)
                        action_tokens.append(conj)
                    elif conj.pos_ in ("NOUN", "PROPN"):
                        obj_dobj_tokens.append(conj)
                    for child in conj.children:
                        if child.lemma_.lower() in crud_map:
                            raw_actions.append(child.lemma_)
                            action_tokens.append(child)

        elif token.pos_ == "VERB" and token.dep_ not in ("aux", "amod", "compound", "acl", "relcl"):
            if token.lemma_ not in raw_actions:
               raw_actions.append(token.lemma_)
               action_tokens.append(token)

        if token.dep_ == "dobj":
            obj_dobj_tokens.append(token)
            obj_dobj_tokens.extend(_get_conjuncts(token))
        elif token.dep_ in ("pobj", "attr"):
            # Chỉ nhận pobj nếu head KHÔNG phải prep của environment
            if token.head.dep_ == "prep" and token.head.text.lower() in ENV_PREPS:
                continue
            obj_pobj_tokens.append(token)
            obj_pobj_tokens.extend(_get_conjuncts(token))

    # ── FALLBACK: Sửa lỗi spaCy gom cả câu thành 1 Noun Phrase ──
    # Chữa cháy khi spaCy nhầm động từ (modifies, updates, creates) thành danh từ (compound)
    # Nếu Action tìm được là một NOUN rác (vd 'grades') và hoàn toàn không khớp crud_map nào -> Xoá đi để chạy fallback
    valid_action_found = False
    for at in action_tokens:
        if at.pos_ == "VERB" or at.lemma_.lower() in crud_map:
            valid_action_found = True
            break
            
    if not valid_action_found:
        raw_actions.clear()
        action_tokens.clear()
        
    if not action_tokens:
        fallback_verbs = {'modifies': 'modify', 'updates': 'update', 'changes': 'change',
                          'creates': 'create', 'deletes': 'delete', 'reads': 'read',
                          'views': 'view', 'accesses': 'access', 'audits': 'audit',
                          'adds': 'add', 'removes': 'remove', 'destroys': 'destroy', 'edits': 'edit',
                          'approves': 'approve', 'requests': 'request', 'checks': 'check', 'reviews': 'review'}
        fallback_subject_str = None  # Sử dụng string trực tiếp thiếu phân cây đúng
        for token in doc:
            if token.text.lower() in fallback_verbs and token.pos_ in ('NOUN', 'PROPN', 'ADJ', 'VERB'):
                raw_actions.append(fallback_verbs[token.text.lower()])
                action_tokens.append(token)
                
                # Subject: chỉ quét nếu parse chính chưa tìm được subject
                if not subject_tokens:
                    # Quét lùi: thu thập span liền kề gồm NOUN/PROPN và modifier VERB/ADJ (amod)
                    span_toks = []
                    for left_tok in reversed(doc[:token.i]):
                        if left_tok.pos_ in ('NOUN', 'PROPN'):
                            span_toks.insert(0, left_tok)
                        elif left_tok.pos_ in ('ADJ', 'VERB') and left_tok.dep_ in ('amod', 'compound'):
                            span_toks.insert(0, left_tok)
                        elif left_tok.pos_ == 'DET':
                            continue  # bỏ determiner nhưng không dừng
                        else:
                            break
                    if span_toks:
                        # Lưu anchor token vào subject_tokens (dùng cho claimed_indices)
                        anchor = span_toks[-1]  # noun gần action nhất
                        subject_tokens.append(anchor)
                        # Lưu full span text trực tiếp — không qua _get_full_noun
                        fallback_subject_str = ' '.join(t.text for t in span_toks)

                # Object là Noun Root/Head nếu chỉ về phía sau, hoặc Noun đầu tiên bên phải
                if token.head.pos_ in ('NOUN', 'PROPN') and token.head.i > token.i:
                    head_tok = token.head
                    while head_tok.dep_ in ('compound', 'nmod', 'amod') and head_tok.head.pos_ in ('NOUN', 'PROPN'):
                        head_tok = head_tok.head
                    obj_dobj_tokens.append(head_tok)
                else:
                    for right_tok in doc[token.i+1:]:
                        if right_tok.pos_ in ('NOUN', 'PROPN'):
                            obj_dobj_tokens.append(right_tok)
                            break
                break
    else:
        fallback_subject_str = None

    LIGHT_NOUNS = {"list", "set", "group", "collection", "series", "range", "array", "type", "kind", "class"}
    final_dobjs = []
    for dt in obj_dobj_tokens:
        if dt.text.lower() in LIGHT_NOUNS:
            replaced = False
            for child in dt.children:
                if child.dep_ == "prep" and child.text.lower() == "of":
                    for pobj in child.children:
                        if pobj.dep_ == "pobj":
                            final_dobjs.append(pobj)
                            final_dobjs.extend(_get_conjuncts(pobj))
                            replaced = True
            if not replaced:
                final_dobjs.append(dt)
        else:
            final_dobjs.append(dt)
            
    obj_dobj_tokens = final_dobjs

    obj_tokens = obj_dobj_tokens if obj_dobj_tokens else obj_pobj_tokens
    
    def _unique_tokens(toks):
        seen = set()
        return [t for t in toks if not (t in seen or seen.add(t))]

    subject_tokens = _unique_tokens(subject_tokens)
    obj_tokens = _unique_tokens(obj_tokens)

    # Build subjects: uu tien fallback_subject_str neu parse chinh bi hong
    if fallback_subject_str and not any(
        t.dep_ in ('nsubj', 'nsubjpass') for t in subject_tokens
    ):
        subjects = [fallback_subject_str]
    else:
        subjects = [_get_full_noun(t) for t in subject_tokens if t]
    
    # Token Isolation: loại bỏ index của subject + action tokens khỏi object phrase
    # Tránh _get_full_noun(submissions) kéo theo 'teaching assistant reviews' vào object
    claimed_indices = {t.i for t in subject_tokens + action_tokens}
    objects  = [_get_full_noun(t, exclude_indices=claimed_indices) for t in obj_tokens if t]

    # Map raw actions to CRUD
    crud_map = {
        "read": "Read", "view": "Read", "access": "Read", "see": "Read", "audit": "Read", "get": "Read",
        "write": "Write",
        "create": "Create", "make": "Create", "add": "Create", "insert": "Create", "upload": "Create",
        "update": "Update", "modify": "Update", "change": "Update", "edit": "Update", "approve": "Update", "request": "Update",
        "delete": "Delete", "remove": "Delete", "destroy": "Delete", "drop": "Delete"
    }

    actions = []
    for act in raw_actions:
        mapped = crud_map.get(act.lower(), act)
        if mapped not in actions:
            actions.append(mapped)

    # ── Attributes: quét MỌI token có child thuộc ATTR_DEPS ──
    # (Đúng chuẩn Alohaly 2019 Module 1: trích xuất TẤT CẢ pairs,
    #  bao gồm cả env pairs. Category sẽ được gán ở Step 2.)
    
    used_tokens = set(subject_tokens + obj_tokens + action_tokens)
    
    for token in doc:
        if _is_in_conditional_clause(token):
            continue

        # Chỉ xét danh từ và động từ (head noun của pair)
        if token.pos_ not in ("NOUN", "PROPN", "VERB", "ADJ"):
            continue

        for child in token.children:
            if child in used_tokens:
                continue
                
            if child.dep_ in ATTR_DEPS:
                # LOẠI BỎ: Noun Compounds ('lab' procedures) không làm thuộc tính mà được gộp vào object identity
                if child.dep_ == "compound" and child.pos_ in ("NOUN", "PROPN"):
                    continue
                if child.dep_ == "punct" and child.text == "-":
                    continue
                if child.dep_ == "amod" and child.text.lower() in ("patient", "medical", "financial", "lab", "health"):
                    continue
                
                name = child.text.lower()
                if name in STOPWORDS:
                    continue
                
                full_val = _get_full_noun(token)
                attributes.append({
                    "name":     child.text,
                    "value":    full_val,
                    "category": "unclassified",
                    "dep":      child.dep_
                })

    # Loại bỏ trùng lặp (name + value)
    seen   = set()
    unique = []
    for attr in attributes:
        key = (attr["name"].lower(), attr["value"].lower())
        if key not in seen:
            seen.add(key)
            unique.append(attr)

    return {
        "sentence":   sentence,
        "subject":    subjects,
        "actions":    actions,
        "object":     objects,
        "attributes": unique
    }


def _guess_category(element, relation):
    """Đoán xem element thuộc về subject hay object."""
    subjects = relation.get("subject", [])
    if isinstance(subjects, str): subjects = [subjects]
    objects = relation.get("object", [])
    if isinstance(objects, str): objects = [objects]
    
    elem = element.lower()
    for s in subjects:
        if elem and elem in s.lower():
            return "subject"
    for o in objects:
        if elem and elem in o.lower():
            return "object"
    return "unknown"


def generate_candidates(sentence):
    """
    Sinh tất cả candidate pairs (element, modifier) — đúng + sai.
    Positive: các cặp dep thực sự từ parse tree (từ extract_relations).
    Negative: các cặp không có dep relation.
    Output định dạng dictionary cho pipeline/CNN.
    """
    doc = nlp(sentence)
    tokens = [ { "text": t.text, "lemma": t.lemma_, "pos": t.pos_, "dep": t.dep_, "head": t.head.text, "ent_type": t.ent_type_ } for t in doc ]
    relation = extract_relations(sentence, tokens, _doc=doc)
    
    positives = set()
    for attr in relation["attributes"]:
        positives.add((attr["value"].lower(), attr["name"].lower()))
        
    nouns = [t.text for t in doc if t.pos_ in ("NOUN", "PROPN") and not t.is_stop]
    mods  = [t.text for t in doc if t.pos_ in ("ADJ", "NOUN", "VERB") and not t.is_stop] # VERB (participles)
    
    candidates = []
    seen_pairs = set()
    for n in nouns:
        for m in mods:
            if n.lower() == m.lower() or m in STOPWORDS:
                continue
            pair_key = (n.lower(), m.lower())
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            
            is_pos = pair_key in positives
            candidates.append({
                "element":  n,
                "modifier": m,
                "valid":    is_pos,
                "category": _guess_category(n, relation)
            })
            
    return {
        "sentence":   sentence,
        "subject":    relation["subject"],
        "actions":    relation["actions"],
        "object":     relation["object"],
        "candidates": candidates,
        # Giữ lại raw attributes để fallback pipeline cũ
        "attributes": relation["attributes"]
    }


if __name__ == "__main__":
    tests = [
        "An on-call senior nurse may change the list of approved lab procedures.",
        "A junior lab technician can request follow-up lab procedures.",
        "Managers in the finance department can approve expense reports.",
        "Students enrolled in the course can access lecture materials.",
        "A registered patient may view his full health record.",
    ]
    for s in tests:
        tokens = parse_sentence(s)
        result = extract_relations(s, tokens)
        print(f"INPUT:   {s}")
        print(f"Subject: {result['subject']} | Actions: {result['actions']} | Object: {result['object']}")
        for attr in result["attributes"]:
            print(f"  [{attr['category']}] {attr['name']!r} → {attr['value']!r}  (dep:{attr['dep']})")
        print()