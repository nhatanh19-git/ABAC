"""
env_extractor.py — Thuật toán 3 tầng trích xuất Environment Attributes

Tầng 1 — Nhận diện Environment Trigger Phrase
  Phát hiện 4 loại trigger phrase: Temporal / Spatial / Conditional / Network-Device
  Dựa vào dependency relation: advmod / prep / advcl gắn với VERB (không phải nsubj/dobj)

Tầng 2 — Phân biệt Environment vs Subject/Object Attribute
  - Subject attribute: dep trực tiếp tới head noun của subject (amod, nmod, compound)
  - Environment: nằm ngoài NP của subject/object, gắn với verb qua Prepositional Phrase

Tầng 3 — Phân loại loại Environment
  Dùng NER type làm tín hiệu chính:
    TIME/DATE  → temporal
    LOC/FAC/GPE → spatial_physical
  Gazetteers fallback nếu NER không xác định.
  Gán namespace: environment.time.* / environment.location.* / environment.network.*
"""

import re
import spacy

nlp = None  # Lazy load

def _get_nlp():
    global nlp
    if nlp is None:
        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            nlp = spacy.blank("en")
    return nlp

# Regex patterns cho numeric detection
_NUM_PATTERN  = re.compile(r'\d')
_TIME_PATTERN = re.compile(r'\d+(am|pm|:\d+)', re.IGNORECASE)

# ─────────────────────────────────────────────────────────────────────
# GAZETTEERS — Tầng 1 & Tầng 3
# ─────────────────────────────────────────────────────────────────────

# Temporal trigger prepositions (phải gắn với VERB qua dep=prep/advmod)
TEMPORAL_PREPS = {"during", "between", "after", "before", "within",
                  "throughout", "until", "at", "on"}

# Duration units — dùng để nhận diện time constraint có số lượng
DURATION_UNITS = {
    "second", "seconds", "minute", "minutes", "hour", "hours",
    "day", "days", "week", "weeks", "month", "months",
    "year", "years", "decade", "decades",
}

# Duration modifiers (xuất hiện trước duration: "the last 6 months")
DURATION_MODIFIERS = {"last", "past", "next", "previous", "coming", "recent", "first"}

# Temporal hint words (head noun của PP phải chứa ít nhất 1 từ này)
TEMPORAL_HINTS = {
    "hours", "hour", "shift", "night", "morning", "evening", "day", "days",
    "weekday", "weekend", "period", "schedule", "time", "pm", "am",
    "daytime", "nighttime", "business", "working", "deadline",
    "month", "months", "year", "years", "session", "semester", "date", "duration",
    "minute", "minutes", "second", "seconds", "week", "weeks",
    "quarter", "term", "interval",
    # University domain temporal terms
    "meeting", "meetings", "conference", "window", "enrollment", "registration",
    "examination", "exam", "exams", "review", "admission", "orientation",
    "graduation", "commencement", "break", "recess", "holiday", "holidays",
    "lecture", "class", "classes", "office", "consultation",
} | DURATION_UNITS

# Spatial trigger prepositions
SPATIAL_PREPS = {"from", "at", "within", "inside", "outside", "through",
                 "via", "on", "in"}

# Spatial hint words (word-level matching)
SPATIAL_HINTS = {
    "network", "ward", "department", "hospital", "building", "floor",
    "site", "premises", "location", "intranet", "vpn", "system",
    "workstation", "workstations", "device", "devices", "terminal",
    "internal", "external", "remote", "local", "secure", "trusted",
    "encrypted", "campus", "lab", "office", "room", "clinic",
    "headquarters", "facility", "unit", "zone", "area", "section",
    "branch", "icu", "er", "or", "icu", "nicu", "picu",
    "center", "centre", "institute", "outpatient", "inpatient",
    # University domain spatial terms
    "library", "classroom", "auditorium", "gymnasium", "dormitory", "dorm",
    "lounge", "computer", "computers", "laboratory", "laboratories",
    "portal", "managed", "university", "faculty", "college", "hall",
    "cafeteria", "canteen", "studio", "archive", "archives", "server",
    "servers", "kiosk", "kiosks", "station", "stations", "printer", "printers",
    "approved", "authorized", "registered"
}

# Conditional trigger phrases (multi-word)
CONDITIONAL_TRIGGERS = {
    "in case of", "under", "when", "if", "in the event of",
    "in emergency", "during emergency"
}

# Network / Device trigger words (thường dep=advcl/acl, không phải prep)
NETWORK_DEVICE_TRIGGERS = {"using", "via", "through"}
NETWORK_DEVICE_HINTS = {
    "workstation", "device", "terminal", "laptop", "system", "portal",
    "platform", "vpn", "connection", "interface", "channel", "network",
    "intranet", "console", "browser", "app", "client", "trusted",
    "secure", "encrypted", "managed", "approved", "authorized"
}

# Noun words that identify a PERSON → force subject attribute, not env
PERSON_NOUNS = {
    "nurse", "doctor", "staff", "manager", "student", "user",
    "physician", "technician", "administrator", "reviewer", "employee",
    "patient", "provider", "clinician", "researcher", "officer"
}

# Words that signal event sequences (not environment)
# NOTE: 'meeting' and 'conference' removed — they ARE valid temporal environments
# (e.g., "during meetings", "during the conference")
EVENT_SEQUENCE_WORDS = {
    "reviewing", "submitting", "processing", "approval", "completing",
    "receiving", "approving"
}

# Prepositions that commonly attach env PP to the verb
ENV_ATTACHMENT_DEPS = {"prep", "advmod", "advcl", "npadvmod"}

# ─────────────────────────────────────────────────────────────────────
# NAMESPACE mapping — Tầng 3
# ─────────────────────────────────────────────────────────────────────

def _build_namespace(env_type: str, subcategory: str, normalized: str) -> str:
    """
    Tạo namespace theo cấu trúc phân cấp:
      environment.time.working_period
      environment.location.facility
      environment.network.access_type
    """
    top = {
        "temporal":         "environment.time",
        "spatial_physical": "environment.location",
        "spatial_network":  "environment.network",
        "spatial_device":   "environment.device",
        "conditional":      "environment.condition",
    }.get(env_type, "environment.other")

    sub = subcategory if subcategory else normalized.split("_")[0] if normalized else "unknown"
    return f"{top}.{sub}:{normalized}"


# ─────────────────────────────────────────────────────────────────────
# TẦNG 1 — Nhận diện Trigger Phrases
# ─────────────────────────────────────────────────────────────────────

def _is_attached_to_verb(token) -> bool:
    """
    Kiem tra token co gan voi VERB (ROOT hoac bat ky verb) qua
    dep = prep / advmod / advcl / npadvmod hay khong.
    Day la tin hieu chinh phan biet environment vs subject attribute.

    Mở rộng để bao phủ pattern phổ biến của spaCy:
      prep → NOUN(dobj) → VERB       ("during the semester" gắn vào dobj "gradebook")
      prep → NOUN(ROOT) → –          ("on the campus portal" khi ROOT là NOUN)
      prep → NOUN → NOUN(dobj/ROOT)  (chuỗi compound dài hơn)
    """
    head = token.head
    # Truc tiep den verb
    if head.pos_ in ("VERB", "AUX") and token.dep_ in ENV_ATTACHMENT_DEPS:
        return True
    # Gian tiep qua mot level (e.g., prep -> pobj -> prep)
    if head.dep_ in ENV_ATTACHMENT_DEPS and head.head.pos_ in ("VERB", "AUX"):
        return True
    
    # Gian tiếp qua 2 level: token(within/prep) -> hours(pobj) -> during(prep) -> change(VERB)
    # Thường xảy ra khi các cụm ENV đan xen hoặc nối tiếp nhau
    if head.dep_ in ("pobj", "dobj") and head.head.dep_ in ENV_ATTACHMENT_DEPS and head.head.head.pos_ in ("VERB", "AUX"):
        return True

    # Gan voi VERB qua acl/relcl trung gian
    # VD: 'from' (prep, head=accessing) -> accessing (acl, head=verb or subject)
    # Neu head la VERB co dep=acl/relcl -> day la participial clause co the la env
    if head.pos_ == "VERB" and head.dep_ in ("acl", "relcl", "advcl") and token.dep_ == "prep":
        return True

    # ── Mở rộng: prep gắn với NOUN là dobj của VERB ──────────────────────
    # VD: "updates a gradebook DURING the semester"
    #   during(prep) → gradebook(dobj, NOUN) → updates(VERB/ROOT)
    if token.dep_ == "prep" and head.pos_ == "NOUN" and head.dep_ in ("dobj", "nsubj", "attr"):
        if head.head.pos_ in ("VERB", "AUX"):
            return True

    # ── Mở rộng: prep gắn với NOUN là ROOT (spaCy parse sai VERB thành NOUN) ─
    # VD: "checks application status ON the campus portal"
    #   on(prep) → status(ROOT, NOUN) — xử lý bằng cách leo ancestor 3 bước
    if token.dep_ == "prep" and head.dep_ == "ROOT" and head.pos_ == "NOUN":
        return True  # ROOT NOUN → luôn cho phép check env (filter sau ở _disambiguate)

    # ── Mở rộng: prep gắn với NOUN compound (chuỗi compound/dobj/nsubj) ──
    # VD: "modifies course grades IN the lab" — spaCy parse "grades" là ROOT NOUN
    if token.dep_ == "prep" and head.pos_ == "NOUN":
        curr = head.head
        for _ in range(3):
            if curr.pos_ in ("VERB", "AUX"):
                return True
            if curr.dep_ == "ROOT":
                return True   # leo đến ROOT → có thể là env
            if curr == curr.head:
                break
            curr = curr.head

    return False



def _is_network_device_trigger(token) -> bool:
    """
    Kiem tra token co phai la network/device trigger khong,
    ke ca khi dep=acl (e.g., 'using trusted workstations').
    """
    return token.text.lower() in NETWORK_DEVICE_TRIGGERS


CONDITIONAL_TRIGGERS = {"when", "if", "unless", "once", "whether", "provided", "assuming", "case"}

def _is_in_conditional_clause(token):
    """Kiểm tra token có thuộc mệnh đề điều kiện (conditional advcl) không."""
    curr = token
    while curr:
        if curr.dep_ == "advcl":
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

def _is_inside_subject_np(token, subject_tokens: set) -> bool:
    """
    Kiểm tra token có nằm trong NP của subject không.
    Nếu có → đây là subject attribute, không phải environment.
    """
    # token bản thân là subject
    if token.text.lower() in subject_tokens:
        return True
    # token là con của subject token
    for ancestor in token.ancestors:
        if ancestor.text.lower() in subject_tokens:
            # Chỉ tính nếu dep là amod/compound/nmod/det
            if token.dep_ in ("amod", "compound", "nmod", "det", "nummod"):
                return True
    return False


def _get_subject_tokens(doc) -> set:
    """
    Lay tap hop cac token thuoc ve subject NP (bao gom also modifiers cua subject).
    QUAN TRONG: Khong bao gom subtree cua acl/relcl modifiers (participial clauses)
    vi chung co the chua ENV phrases nhu 'using trusted workstations'.
    """
    # ACL deps to explicitly exclude from subject NP
    ACL_DEPS = {"acl", "relcl", "advcl"}

    tokens = set()
    for token in doc:
        if _is_in_conditional_clause(token):
            continue
        if token.dep_ in ("nsubj", "nsubjpass", "csubj"):
            tokens.add(token.text.lower())
            # Chi lay subtree truc tiep cua subject NP, KHONG bao gom acl subtrees
            for child in token.children:
                # Bo qua acl/relcl clauses (chung la ENV context, khong phai subject att)
                if child.dep_ in ACL_DEPS:
                    continue
                # Lay subtree cua cac modifier thong thuong (amod, compound, det, prep)
                tokens.add(child.text.lower())
                for grandchild in child.subtree:
                    # Khong di sau qua acl boundaries
                    if grandchild.dep_ in ACL_DEPS:
                        break
                    tokens.add(grandchild.text.lower())
    return tokens


def _get_object_tokens(doc) -> set:
    """Lấy tập hợp các token thuộc về object NP."""
    tokens = set()
    for token in doc:
        if _is_in_conditional_clause(token):
            continue
        if token.dep_ in ("dobj", "pobj", "attr"):
            # Chỉ lấy direct dobj, bỏ qua pobj của env preps
            if token.dep_ == "pobj" and token.head.text.lower() in TEMPORAL_PREPS | SPATIAL_PREPS:
                continue
            
            tokens.add(token.text.lower())
            for child in token.children:
                # NGĂN CHẶN: Không traverse sâu vào prepositional modifiers nếu nó là ENV trigger
                if child.dep_ == "prep" and child.text.lower() in TEMPORAL_PREPS | SPATIAL_PREPS:
                    continue
                # Thêm con bình thường
                tokens.add(child.text.lower())
                for gc in child.subtree:
                    if gc.dep_ == "prep" and gc.text.lower() in TEMPORAL_PREPS | SPATIAL_PREPS:
                        break  # stop at next prep boundary
                    tokens.add(gc.text.lower())

    return tokens


def _extract_noun_phrase(prep_token) -> str:
    """
    Lấy noun phrase ngay sau giới từ.
    Dừng traversal khi gặp prep boundary tiếp theo để tránh over-reach.
    """
    for child in prep_token.children:
        if child.pos_ in ("NOUN", "PROPN", "ADJ", "NUM"):
            tokens = []
            for t in child.subtree:
                # Dừng khi gặp prep mới (boundary)
                if t.dep_ == "prep" and t != child:
                    break
                if t.is_punct:
                    break
                tokens.append(t.text)
            return " ".join(tokens)
    return ""


def _extract_device_phrase(trigger_token) -> str:
    """
    Lấy phrase cho device/network trigger (using/via/through + NP).
    Xử lý dep=advcl, acl, prep, dobj.
    spaCy thường parse 'using trusted workstations' với:
      using (dep=advcl/acl) → workstations (dep=dobj, pos=NOUN)
                            → trusted (dep=amod, pos=ADJ)
    """
    # Pass 1: Tìm NOUN/PROPN children trực tiếp (bao gồm dobj)
    best_phrase = ""
    for child in trigger_token.children:
        if child.pos_ in ("NOUN", "PROPN"):
            tokens = []
            for t in child.subtree:
                if t.dep_ == "prep" and t != child:
                    break
                if t.is_punct:
                    break
                tokens.append(t.text)
            if tokens:
                phrase = " ".join(tokens)
                if _has_hint(phrase, NETWORK_DEVICE_HINTS):
                    return phrase
                if not best_phrase:
                    best_phrase = phrase

    # Pass 2: ADJ children (vd: 'using secure' — hiếm nhưng xử lý)
    if not best_phrase:
        for child in trigger_token.children:
            if child.pos_ == "ADJ":
                tokens = []
                for t in child.subtree:
                    if t.is_punct:
                        break
                    tokens.append(t.text)
                if tokens:
                    best_phrase = " ".join(tokens)
                    break

    if best_phrase:
        return best_phrase

    # Pass 3 fallback: tìm trong head children (vd: head là main verb)
    head = trigger_token.head
    for child in head.children:
        if child != trigger_token and child.pos_ in ("NOUN", "PROPN"):
            tokens = []
            for t in child.subtree:
                if t.dep_ == "prep" and t != child:
                    break
                if t.is_punct:
                    break
                tokens.append(t.text)
            if tokens:
                return " ".join(tokens)
    return ""


# ─────────────────────────────────────────────────────────────────────
# HELPERS — Unified PP Family (env_name + env_value parsers)
# ─────────────────────────────────────────────────────────────────────

def _has_numeric(token) -> bool:
    """
    Kiểm tra token (và subtree) có chứa giá trị số không.
    Dùng để phân biệt "name phrase" vs "value phrase".
    """
    for t in token.subtree:
        if t.like_num or t.pos_ == "NUM" or _NUM_PATTERN.search(t.text):
            return True
    return False


def _has_numeric_text(text: str) -> bool:
    """Kiểm tra chuỗi text có chứa số không."""
    return bool(_NUM_PATTERN.search(text))


def _parse_env_name(prep_token):
    """
    Parser 1: Lấy noun phrase của pobj, trả về None nếu pobj chứa số.

    Ví dụ:
      "during business hours"           → "business hours"
      "during business hours (9am-5pm)" → "business hours"  (dừng trước dấu "(")
      "between 8am and 5pm"             → None  (pobj chứa số ngoài ngoặc)
      "within the hospital"             → "the hospital"
    """
    for child in prep_token.children:
        if child.dep_ == "pobj" or child.pos_ in ("NOUN", "PROPN", "ADJ"):
            # Duyệt subtree nhưng DỪNG tại "(" (parenthetical boundary)
            # Chỉ kiểm tra numeric cho phần NGOÀI ngoặc đơn
            tokens = []
            has_num_outside_parens = False
            for t in child.subtree:
                if t.text == "(":
                    break  # dừng — phần sau là parenthetical clarification
                if t.dep_ == "prep" and t != child:
                    break
                if t.is_punct:
                    break
                if t.like_num or t.pos_ == "NUM" or _NUM_PATTERN.search(t.text):
                    has_num_outside_parens = True
                tokens.append(t.text)

            # Nếu phần ngoài ngoặc có số → đây là value phrase, không phải name
            if has_num_outside_parens:
                return None
            return " ".join(tokens) if tokens else None
    return None



# ─── Time helpers ──────────────────────────────────────────────────────
_TIME_STR_PAT = re.compile(r'(\d+)\s*(am|pm)', re.IGNORECASE)


def _parse_time_str(text: str):
    """
    Parse time text như "7 am", "3 pm", "10pm", "6am" thành dict có cấu trúc.
    Trả về {"value": N, "unit": "am"/"pm"} hoặc None nếu không phải time.
    """
    if not text:
        return None
    m = _TIME_STR_PAT.search(text.strip())
    if m:
        return {"value": int(m.group(1)), "unit": m.group(2).lower()}
    return None


def _clean_time_entity(text: str) -> str:
    """
    Xóa conjunction/preposition thừa ở cuối entity text (artifact của spaCy NER).
    Ví dụ: "7am and" → "7am", "10pm to" → "10pm"
    """
    return re.sub(
        r'\s+(?:and|or|to|till|until)\s*$', '', text, flags=re.IGNORECASE
    ).strip()


# Regex nhận diện duration: "2 hours", "the last 6 months", "30 minutes"
# Plural phải đứng TRƯỚC singular trong alternation để tránh lấy nhầm "hour" từ "hours"
_DURATION_PAT = re.compile(
    r'(?:the\s+)?(?:(last|next|past|previous|coming|recent|first)\s+)?'
    r'(\d+(?:\.\d+)?)\s+'
    r'(seconds|second|minutes|minute|hours|hour|days|day|weeks|week'
    r'|months|month|years|year|decades|decade)',
    re.IGNORECASE
)


def _parse_duration_str(text: str):
    """
    Parse chuỗi duration thành dict có cấu trúc.
    Ví dụ:
      "2 hours"           → {"value": 2, "unit": "hours"}
      "the last 6 months" → {"value": 6, "unit": "months", "modifier": "last"}
      "30 minutes"        → {"value": 30, "unit": "minutes"}
    Trả về None nếu không phải duration.
    """
    if not text:
        return None
    m = _DURATION_PAT.search(text.strip())
    if not m:
        return None
    result = {
        "value": int(float(m.group(2))),
        "unit":  m.group(3).lower(),
    }
    if m.group(1):
        result["modifier"] = m.group(1).lower()
    return result


def _is_duration_value(env_value) -> bool:
    """Kiểm tra env_value là duration có cấu trúc (có 'unit' thuộc DURATION_UNITS)."""
    if not env_value or not isinstance(env_value, dict):
        return False
    unit = env_value.get("unit")
    return isinstance(unit, str) and unit.lower() in DURATION_UNITS


def _normalize_time_text(text: str) -> str:
    """Chuẩn hóa "7 am" → "7am" để so sánh dedup."""
    return re.sub(r'(\d+)\s+(am|pm)', r'\1\2', text.lower())


def _parse_env_value(prep_token):
    """
    Parser 2: Tìm giá trị cụ thể (số, range) trong PP.
    Chỉ trả về dict nếu pobj subtree chứa ít nhất một token số.

    Kết quả có cấu trúc rõ ràng để downstream dễ đọc:
      - Đơn: {"operator": "at", "value": 7, "unit": "am"}
      - Range: {"operator": "between",
                "from": {"value": 7, "unit": "am"},
                "to":   {"value": 3, "unit": "pm"}}

    Parse trees thực tế từ spaCy:

      "between 7am and 3pm":
        between(prep) → 7(pobj/NUM) ← am(quantmod)
                          am ← and(cc)
                          7 ← pm(conj) ← 3(nummod)

      "from 10pm to 6am":
        from(prep) → pm(pobj) ← 10(nummod)
                  → to(prep)  ← 6(pobj)
                  → am(pobj)           ← unit of to-value

      "at 7am":
        at(prep) → 7(pobj/NUM) ← am(quantmod)
    """
    tl = prep_token.text.lower()

    # Lấy pobj — ưu tiên dep=pobj, fallback pos=NUM/NOUN
    pobj = None
    for child in prep_token.children:
        if child.dep_ == "pobj":
            pobj = child
            break
    if pobj is None:
        for child in prep_token.children:
            if child.pos_ in ("NOUN", "PROPN", "NUM"):
                pobj = child
                break
    if pobj is None:
        return None

    # Chỉ tiếp tục nếu pobj subtree chứa số
    if not _has_numeric(pobj):
        return None

    def _excl_conj_text(token):
        """
        Thu thập text của token.subtree LOẠI TRỪ các token thuộc subtree
        của conj children (để tránh lấy nhầm số/unit của phần "to").
        """
        conj_ids = set()
        for child in token.children:
            if child.dep_ == "conj":
                for t in child.subtree:
                    conj_ids.add(t.i)
        parts = []
        for t in sorted(token.subtree, key=lambda x: x.i):
            if t.i in conj_ids:
                continue        # thuộc conj subtree → bỏ qua
            if t.dep_ == "cc":
                continue        # bỏ "and", "or"
            if t.is_punct:
                break
            parts.append(t.text)
        return " ".join(parts)

    def _simple_text(token):
        """Thu thập toàn bộ subtree text (không loại conj)."""
        parts = []
        for t in sorted(token.subtree, key=lambda x: x.i):
            if t.dep_ == "cc":
                continue
            if t.is_punct:
                break
            parts.append(t.text)
        return " ".join(parts)

    # ── "between X and Y" ──────────────────────────────────────────
    # spaCy: between → pobj=7(NUM), 7 có conj=pm, pm có nummod=3
    if tl == "between":
        from_text = _excl_conj_text(pobj)   # loại trừ subtree của conj
        from_parsed = _parse_time_str(from_text) or {"text": from_text}

        to_parsed = None
        for child in pobj.children:
            if child.dep_ == "conj":
                to_text = _simple_text(child)
                to_parsed = _parse_time_str(to_text) or {"text": to_text}
                break

        if to_parsed:
            return {"operator": "between", "from": from_parsed, "to": to_parsed}
        return {"operator": "between", **from_parsed}

    # ── "from X to Y" ──────────────────────────────────────────────
    # Hai sub-cases:
    #   A) "from 10pm to 6am": to_prep là direct child của prep_token
    #   B) "from 8am to 5pm": parse phức tạp hơn, để NER xử lý
    if tl == "from":
        # Sub-case A: tìm "to" prep là direct child của from
        to_prep = None
        for child in prep_token.children:
            if child.dep_ == "prep" and child.text.lower() in ("to", "till", "until"):
                to_prep = child
                break

        if to_prep:
            # from_val: pobj subtree 
            from_text = _simple_text(pobj)
            from_parsed = _parse_time_str(from_text) or {"text": from_text}

            # to_val: to_prep's pobj + trailing pobjs của from (unit tokens)
            to_pobj = next(
                (c for c in to_prep.children if c.dep_ == "pobj"), None
            )
            trailing_pobjs = sorted(
                [c for c in prep_token.children
                 if c.dep_ == "pobj" and c.i > to_prep.i],
                key=lambda x: x.i
            )

            to_parts = []
            if to_pobj:
                to_parts += [t.text for t in sorted(to_pobj.subtree, key=lambda x: x.i)
                             if not t.is_punct]
            for tp in trailing_pobjs:
                to_parts.append(tp.text)

            to_text = " ".join(to_parts)
            to_parsed = _parse_time_str(to_text) or ({"text": to_text} if to_text else None)

            if to_parsed:
                return {"operator": "between", "from": from_parsed, "to": to_parsed}
            return {"operator": "from", **from_parsed}

        # Sub-case B: "from the last 6 months", "from the past 3 days"
        # pobj đã có numeric (6, 3) → thử parse duration
        pobj_text = _simple_text(pobj)
        dur = _parse_duration_str(pobj_text)
        if dur:
            return {"operator": "from", **dur}

        # Sub-case C: thực sự không rõ → để NER xử lý
        return None

    # ── Single-bound operators ──────────────────────────────────────
    if tl in ("before", "after", "until", "since"):
        val_text = _simple_text(pobj)
        parsed = _parse_time_str(val_text) or _parse_duration_str(val_text)
        if parsed:
            return {"operator": tl, **parsed}
        return {"operator": tl, "value": val_text}

    if tl == "at":
        val_text = _simple_text(pobj)
        parsed = _parse_time_str(val_text) or _parse_duration_str(val_text)
        if parsed:
            return {"operator": "at", **parsed}
        return {"operator": "at", "value": val_text}

    if tl == "within":
        val_text = _simple_text(pobj)
        # Thử parse time (am/pm) trước, rồi duration (hours/minutes/...)
        parsed = _parse_time_str(val_text) or _parse_duration_str(val_text)
        if parsed:
            return {"operator": "within", **parsed}
        return {"operator": "within", "value": val_text}

    return None


def _looks_like_time_value(env_value) -> bool:
    """
    Kiểm tra env_value dict có chứa time-like hoặc duration values.
    Dùng để bypass _has_hint khi env_value đã xác nhận đây là time constraint.
    Hỗ trợ: am/pm, DURATION_UNITS, nested from/to dicts.
    """
    if not env_value:
        return False
    # Structured time: {"value": N, "unit": "am/pm"}
    unit = env_value.get("unit")
    if isinstance(unit, str) and (unit in ("am", "pm") or unit in DURATION_UNITS):
        return True
    # Nested structured: {"from": {"value":..., "unit":...}, ...}
    for key in ("from", "to"):
        nested = env_value.get(key)
        if isinstance(nested, dict):
            u = nested.get("unit")
            if u in ("am", "pm") or u in DURATION_UNITS:
                return True
    for key in ("value", "from", "to"):
        v = env_value.get(key)
        if v and _TIME_PATTERN.search(str(v)):
            return True
    return False


def _has_hint(text: str, hints: set) -> bool:
    """
    Word-level hint matching.
    Short hints (<=3 chars like 'am', 'pm', 'er') → exact word match only.
    Longer hints → exact word OR prefix-substring match.
    This prevents false positives like 'am' matching 'campus'.
    """
    words = set(text.lower().split())
    for h in hints:
        if len(h) <= 3:
            # Short hints: exact word boundary match only
            if h in words:
                return True
        else:
            # Longer hints: check if hint appears as a full word or prefix in any word
            for w in words:
                if w == h or w.startswith(h) or h in w:
                    return True
    return False


def _get_ner_type(doc, phrase_text: str) -> str:
    """Tra NER type của phrase dựa trên entities được spaCy detect."""
    phrase_lower = phrase_text.lower()
    for ent in doc.ents:
        if ent.text.lower() in phrase_lower or phrase_lower in ent.text.lower():
            return ent.label_
    return ""


def _detect_trigger_phrases(doc, subject_tokens: set, object_tokens: set) -> list:
    """
    TẦNG 1: Duyệt qua tất cả tokens, phát hiện trigger phrases.
    Chỉ nhận trigger nếu nó gắn với VERB (không nằm trong NP của subject/object).

    Với mỗi prep token, chạy hai parser song song:
      - _parse_env_name():  lấy noun phrase ngữ nghĩa (None nếu pobj chứa số)
      - _parse_env_value(): lấy giá trị số/range (None nếu không có số)
    Nếu cả hai đều None → bỏ qua.

    Dùng if block RIÊNG (không elif) cho temporal/spatial để một prep như
    'within' được check cả hai hướng.

    Conditional clause giữ nguyên schema riêng (không có env_name/env_value).

    Trả về list of raw candidates:
      { trigger, trigger_type, phrase, env_name, env_value, full_value, ner_type, token }
    """
    candidates = []
    seen_keys = set()

    for token in doc:
        tl = token.text.lower()

        # ── Conditional clauses (WHEN/IF + advcl) — xử lý trước ─────
        if token.dep_ == "advcl" and token.head.pos_ in ("VERB", "AUX"):
            trigger_text = ""
            for c in token.children:
                if c.text.lower() in {"when", "if", "unless", "once",
                                      "whether", "provided", "assuming"}:
                    trigger_text = c.text
                    break
                if c.text.lower() == "in":
                    for gc in c.children:
                        if gc.text.lower() == "case":
                            trigger_text = "in case"
                            break

            if trigger_text:
                c_subject, c_pred, c_object, c_negated = "", token.lemma_, "", False
                sorted_sub = sorted(list(token.subtree), key=lambda x: x.i)
                cl_phrase = " ".join(t.text for t in sorted_sub
                                     if t.text.lower() != trigger_text)

                for c in token.children:
                    if c.dep_ in ("nsubj", "nsubjpass", "csubj"):
                        ns_tokens = [c] + [cc for cc in c.children
                                           if cc.dep_ == "compound"
                                           and cc.pos_ in ("NOUN", "PROPN")]
                        c_subject = " ".join(x.text for x in
                                             sorted(ns_tokens, key=lambda x: x.i))
                    elif c.dep_ == "neg":
                        c_negated = True
                    elif c.dep_ in ("dobj", "pobj", "attr"):
                        obj_toks = []
                        for t in c.subtree:
                            if t.dep_ == "prep" and t != c: break
                            if t.is_punct: break
                            obj_toks.append(t.text)
                        c_object = " ".join(obj_toks)
                    elif c.dep_ == "prep":
                        for pobj in c.children:
                            if pobj.dep_ == "pobj":
                                obj_toks = []
                                for t in pobj.subtree:
                                    if t.dep_ == "prep" and t != pobj: break
                                    if t.is_punct: break
                                    obj_toks.append(t.text)
                                c_object = " ".join(obj_toks)

                key = ("conditional_clause", cl_phrase.lower()[:30])
                if key not in seen_keys:
                    seen_keys.add(key)
                    candidates.append({
                        "trigger":      trigger_text,
                        "trigger_type": "conditional",
                        "subcategory":  "conditional_clause",
                        "phrase":       cl_phrase.strip(),
                        "env_name":     None,
                        "env_value":    None,
                        "full_value":   f"{trigger_text} {cl_phrase}".strip(),
                        "ner_type":     "",
                        "token":        token,
                        "condition": {
                            "subject":   c_subject,
                            "predicate": c_pred,
                            "object":    c_object,
                            "negated":   c_negated
                        }
                    })
            continue  # advcl token đã xử lý xong

        # ── Chỉ xử lý prep tokens gắn với verb ───────────────────────
        if token.dep_ != "prep":
            continue
        if not _is_attached_to_verb(token):
            continue

        # ── Chạy hai parser song song ─────────────────────────────────
        env_name  = _parse_env_name(token)
        env_value = _parse_env_value(token)

        # Nếu cả hai đều None → không phải ENV candidate
        if env_name is None and env_value is None:
            continue

        # Lấy phrase cho backward-compat (classification / hint check / dedup)
        phrase = _extract_noun_phrase(token)
        if not phrase:
            continue

        phrase_words_list = phrase.lower().split()
        phrase_words_set  = set(phrase_words_list)

        if any(p in phrase_words_list for p in PERSON_NOUNS):
            continue
            
        # Chỉ reject nếu pobj chính (head noun) nằm trong subject_tokens
        # Tránh việc "admissions office" bị reject vì subject có từ "admissions"
        pobj_text = None
        for child in token.children:
            if child.dep_ in ("pobj", "pcomp"):
                pobj_text = child.text.lower()
                break
        if pobj_text and pobj_text in subject_tokens:
            continue

        ner_type = _get_ner_type(doc, phrase)

        # ── Temporal check ─────────────────────────────────────────────
        # "from" thường là spatial, nhưng nếu env_value là duration → temporal
        is_duration_temporal = _is_duration_value(env_value)
        if tl in TEMPORAL_PREPS or (tl == "from" and is_duration_temporal):
            is_temporal = (_has_hint(phrase, TEMPORAL_HINTS)
                           or _looks_like_time_value(env_value))
            if is_temporal:
                key = ("temporal", phrase.lower()[:30])
                if key not in seen_keys:
                    seen_keys.add(key)
                    candidates.append({
                        "trigger":      token.text,
                        "trigger_type": "temporal",
                        "phrase":       phrase,
                        "env_name":     env_name,
                        "env_value":    env_value,
                        "full_value":   f"{token.text} {phrase}",
                        "ner_type":     ner_type,
                        "token":        token
                    })
            # Nếu đã xử lý là temporal duration → không cần check spatial nữa
            if is_duration_temporal:
                continue

        # ── Spatial check ──────────────────────────────────────────────
        if tl in SPATIAL_PREPS:
            is_location_ner  = ner_type in ("GPE", "LOC", "FAC", "ORG")
            has_spatial_hint = _has_hint(phrase, SPATIAL_HINTS)
            if has_spatial_hint or is_location_ner:
                key = ("spatial", phrase.lower()[:30])
                if key not in seen_keys:
                    seen_keys.add(key)
                    candidates.append({
                        "trigger":      token.text,
                        "trigger_type": "spatial",
                        "phrase":       phrase,
                        "env_name":     env_name,
                        "env_value":    env_value,
                        "full_value":   f"{token.text} {phrase}",
                        "ner_type":     ner_type,
                        "token":        token
                    })

    # ── NER-based fallback ────────────────────────────────────────────
    def _ner_covered(ent_clean_text):
        """
        Kiểm tra entity text đã được covered bởi rule+dep candidate chưa.
        So sánh sau khi normalize "7 am" ↔ "7am".
        """
        norm = _normalize_time_text(ent_clean_text)
        # Tìm tất cả time tokens dạng "NNam/pm" trong entity
        time_toks = set(re.findall(r'\d+(?:am|pm)', norm))
        for c in candidates:
            if c.get("trigger_type") != "temporal":
                continue
            norm_fv = _normalize_time_text(c.get("full_value", ""))
            if norm and norm in norm_fv:
                return True
            if time_toks and all(tok in norm_fv for tok in time_toks):
                return True
        return False

    for ent in doc.ents:
        if ent.label_ in ("TIME", "DATE"):
            # Xóa conjunction/preposition thừa ở cuối (artifact của spaCy NER)
            ent_clean = _clean_time_entity(ent.text)
            if not ent_clean:
                continue

            if _ner_covered(ent_clean):
                continue    # đã có rule+dep candidate bao phủ

            # Đây là entity mới — tạo env_value có cấu trúc
            ner_env_value = None
            if _has_numeric_text(ent_clean):
                # 1) Thử parse range: "10pm to 6am", "8am to 5pm"
                _rng = re.match(
                    r'([\w\s]+?)\s+(?:to|till|until|and)\s+([\w\s]+)',
                    ent_clean, re.IGNORECASE)
                if _rng:
                    from_parsed = (_parse_time_str(_rng.group(1).strip())
                                   or _parse_duration_str(_rng.group(1).strip()))
                    to_parsed   = (_parse_time_str(_rng.group(2).strip())
                                   or _parse_duration_str(_rng.group(2).strip()))
                    ner_env_value = {
                        "operator": "between",
                        "from": from_parsed or {"text": _rng.group(1).strip()},
                        "to":   to_parsed   or {"text": _rng.group(2).strip()}
                    }
                else:
                    # 2) Thử parse duration: "2 hours", "the last 6 months"
                    dur = _parse_duration_str(ent_clean)
                    if dur:
                        # operator tùy loại entity: TIME → "within", DATE → "from"
                        op = "within" if ent.label_ == "TIME" else "from"
                        ner_env_value = {"operator": op, **dur}
                    else:
                        # 3) Time đơn giản: "7am", "10pm"
                        parsed = _parse_time_str(ent_clean)
                        if parsed:
                            ner_env_value = {"operator": "at", **parsed}
                        else:
                            ner_env_value = {"operator": "at", "value": ent_clean}

            candidates.append({
                "trigger":      "NER:" + ent.label_,
                "trigger_type": "temporal",
                "phrase":       ent_clean,
                "env_name":     None if _has_numeric_text(ent_clean) else ent_clean,
                "env_value":    ner_env_value,
                "full_value":   ent_clean,
                "ner_type":     ent.label_,
                "token":        None
            })
        elif ent.label_ in ("GPE", "LOC", "FAC"):
            already = any(ent.text.lower() in c["full_value"].lower()
                         for c in candidates if c["trigger_type"] == "spatial")
            if not already:
                candidates.append({
                    "trigger":      "NER:" + ent.label_,
                    "trigger_type": "spatial",
                    "phrase":       ent.text,
                    "env_name":     ent.text,
                    "env_value":    None,
                    "full_value":   ent.text,
                    "ner_type":     ent.label_,
                    "token":        None
                })

    return candidates



# ─────────────────────────────────────────────────────────────────────
# TẦNG 2 — Phân biệt Environment vs Subject/Object Attribute
# ─────────────────────────────────────────────────────────────────────

def _disambiguate(candidates: list, subject_tokens: set, object_tokens: set) -> list:
    """
    TẦNG 2: Lọc candidates, loại bỏ những cái thực sự là subject/object attribute.

    Logic chính:
      - Subject attribute: dep trực tiếp tới head noun của subject (amod/nmod/compound)
        VÀ nằm trong NP của subject → loại khỏi env
      - Environment: nằm ngoài NP của subject/object, gắn với verb qua PP
        VÀ có thể tách khỏi câu mà subject/object không thay đổi nghĩa

    Ví dụ phân tích:
      "A nurse at the hospital can view records during business hours."
      - "at the hospital": phrase "hospital" → không nằm trong subject NP
        (subject NP chỉ là "nurse") → ENVIRONMENT (spatial)
      - "during business hours": phrase "business hours" → ENVIRONMENT (temporal)
    """
    confirmed = []

    for cand in candidates:
        phrase_lower = cand["phrase"].lower()
        phrase_words = set(phrase_lower.split())

        # Loại bỏ nếu tất cả từ trong phrase đều nằm trong subject NP
        # (tức là điều này là modifier của subject, không phải env)
        overlap_with_subject = phrase_words & subject_tokens
        if overlap_with_subject and len(overlap_with_subject) >= len(phrase_words):
            continue

        # Loại bỏ nếu tất cả từ trong phrase đều nằm trong object NP
        overlap_with_object = phrase_words & object_tokens
        if overlap_with_object and len(overlap_with_object) >= len(phrase_words):
            continue

        # Loại bỏ event sequences (after reviewing, at meeting, ...)
        if any(e in phrase_lower for e in EVENT_SEQUENCE_WORDS):
            # Ngoại lệ: nếu là temporal NER hợp lệ, vẫn giữ
            if cand["ner_type"] not in ("TIME", "DATE"):
                continue

        # Loại bỏ "from nurses/doctors ..." → subject-att
        if cand["trigger"].lower() == "from" and any(p in phrase_lower for p in PERSON_NOUNS):
            continue

        # Loại bỏ "after reviewing/submitting/..." → action sequence
        action_gerunds = {"reviewing", "submitting", "approving", "processing",
                          "completing", "receiving", "requesting"}
        if cand["trigger"].lower() == "after" and any(w in phrase_lower for w in action_gerunds):
            continue

        confirmed.append(cand)

    return confirmed


# ─────────────────────────────────────────────────────────────────────
# TẦNG 3 — Phân loại loại Environment + Gán Namespace
# ─────────────────────────────────────────────────────────────────────

def _classify_temporal_subcategory(phrase: str) -> str:
    """Phân loại temporal thành absolute / recurring / relative / event."""
    tl = phrase.lower()
    if any(c.isdigit() for c in phrase):
        return "absolute"             # "8am", "5pm", "14:00"
    if any(w in tl for w in ("weekday", "weekend", "monday", "tuesday",
                              "wednesday", "thursday", "friday", "daily")):
        return "recurring"
    if any(w in tl for w in ("emergency", "code", "incident", "situation")):
        return "event"
    if any(w in tl for w in ("business", "working", "office", "shift", "night",
                              "morning", "evening", "daytime")):
        return "working_period"       # ← namespace: environment.time.working_period
    return "relative"


def _classify_spatial_subcategory(phrase: str, ner_type: str) -> tuple:
    """
    Phân loại spatial thành:
      (env_type, subcategory)
    env_type: spatial_physical | spatial_network | spatial_device
    subcategory: facility | campus | network_zone | access_type | device_type
    """
    tl = phrase.lower()

    # Network
    if any(w in tl for w in ("network", "vpn", "intranet", "internet",
                              "internal", "external", "remote")):
        if "vpn" in tl:
            return "spatial_network", "access_type"        # environment.network.access_type
        return "spatial_network", "network_zone"

    # Device
    if any(w in tl for w in ("workstation", "device", "terminal", "laptop",
                              "system", "portal", "platform", "console")):
        return "spatial_device", "device_type"

    # Physical facility (hospital, clinic, lab, ward...)
    if ner_type in ("FAC", "LOC") or any(w in tl for w in (
            "hospital", "clinic", "ward", "department", "lab", "office",
            "room", "building", "floor", "campus", "headquarters", "unit",
            "zone", "area", "section", "branch", "facility")):
        return "spatial_physical", "facility"              # environment.location.facility

    # GPE (city, country)
    if ner_type == "GPE":
        return "spatial_physical", "geographic"

    return "spatial_physical", "location"


def _normalize_phrase(phrase: str) -> str:
    """Tạo normalized key từ phrase (dùng cho namespace)."""
    stop = {"a", "an", "the", "this", "that", "of", "in"}
    parts = [w.lower() for w in phrase.split() if w.lower() not in stop]
    return "_".join(parts) if parts else phrase.lower().replace(" ", "_")


def _classify_and_enrich(candidates: list) -> list:
    """
    TẦNG 3: Gán env_type, subcategory, namespace, data_type cho mỗi candidate.
    NER type là tín hiệu chính; gazetteers là fallback.
    """
    results = []
    for cand in candidates:
        ttype  = cand["trigger_type"]
        phrase = cand["phrase"]
        ner    = cand["ner_type"]

        if ttype == "temporal" or ner in ("TIME", "DATE"):
            subcategory = _classify_temporal_subcategory(phrase)
            env_type    = "temporal"
            data_type   = "time"
        elif ttype == "network_device":
            env_type, subcategory = _classify_spatial_subcategory(phrase, ner)
            data_type = "location"
        elif ttype == "conditional":
            env_type = "conditional"
            subcategory = cand.get("subcategory", "conditional_clause")
            data_type = "boolean"
        else:
            # spatial (và ner_type có thể là GPE/LOC/FAC)
            if ner in ("TIME", "DATE"):
                # Spatial trigger nhưng NER là time → reclassify
                env_type    = "temporal"
                subcategory = _classify_temporal_subcategory(phrase)
                data_type   = "time"
            else:
                env_type, subcategory = _classify_spatial_subcategory(phrase, ner)
                data_type = "location"

        normalized = _normalize_phrase(phrase)
        namespace  = _build_namespace(env_type, subcategory, normalized)

        res_item = {
            "category":    "environment",
            "env_type":    env_type,
            "subcategory": subcategory,
            "trigger":     cand["trigger"],
            "phrase":      phrase,
            "env_name":    cand.get("env_name"),    # tên ngữ nghĩa (hoặc None)
            "env_value":   cand.get("env_value"),   # giá trị cụ thể (hoặc None)
            "full_value":  cand["full_value"],
            "ner_type":    ner,          # ← vector feature cho CNN input layer
            "normalized":  normalized,
            "namespace":   namespace,
            "data_type":   data_type,
            "method":      "ner" if cand["trigger"].startswith("NER:") else "rule+dep"
        }
        if "condition" in cand:
            res_item["condition"] = cand["condition"]

        results.append(res_item)
    return results


# ─────────────────────────────────────────────────────────────────────
# DEDUPLICATION
# ─────────────────────────────────────────────────────────────────────

def _deduplicate(results: list) -> list:
    seen = set()
    out  = []
    for r in results:
        key = (r["env_type"], r["full_value"].lower()[:40])
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def _merge_parenthetical_values(results: list, sentence: str) -> list:
    """
    Post-processing: Xử lý pattern "during business hours (9am to 5pm)".

    Khi có một entry working_period có env_name (ví dụ "business hours")
    và một entry NER temporal chứa time range trong ngoặc đơn (ví dụ "9am to 5pm"),
    hàm sẽ:
      1. Merge env_value của NER entry vào entry working_period
      2. Cập nhật full_value để bao gồm cả dải thời gian
      3. Loại bỏ entry NER trùng lặp (vì nó chỉ là làm rõ giá trị)

    Điều kiện merge:
      - Entry A: subcategory == working_period, env_name không None
      - Entry B: trigger bắt đầu bằng "NER:", env_value không None, có số
      - Entity B nằm trong ngoặc đơn trong câu gốc
    """
    # Tìm tất cả các đoạn nằm trong ngoặc đơn trong câu
    parenthetical_texts = set()
    for m in re.finditer(r'\(([^)]+)\)', sentence):
        parenthetical_texts.add(m.group(1).strip().lower())

    # Phân loại entries
    working_periods = [r for r in results
                       if r.get("subcategory") == "working_period"
                       and r.get("env_name") is not None]

    ner_ranges = [r for r in results
                  if r.get("trigger", "").startswith("NER:")
                  and r.get("env_type") == "temporal"
                  and r.get("env_value") is not None
                  and _has_numeric_text(r.get("phrase", ""))]

    # Không có gì để merge
    if not working_periods or not ner_ranges:
        return results

    merged_ner_ids = set()  # index trong results để remove sau

    for wp in working_periods:
        for ner_r in ner_ranges:
            ner_phrase_lower = ner_r.get("phrase", "").lower().strip()
            ner_full_lower   = ner_r.get("full_value", "").lower().strip()

            # Kiểm tra NER range có nằm trong ngoặc đơn trong câu gốc không
            is_parenthetical = any(
                ner_phrase_lower in pt or ner_full_lower in pt
                for pt in parenthetical_texts
            )
            if not is_parenthetical:
                continue

            # Working period chưa có env_value → merge
            if wp.get("env_value") is None:
                wp["env_value"] = ner_r["env_value"]
                # Cập nhật full_value để rõ ràng hơn
                wp["full_value"] = (
                    f"{wp['full_value']} ({ner_r['phrase']})"
                    if ner_r["phrase"] not in wp["full_value"]
                    else wp["full_value"]
                )
                merged_ner_ids.add(id(ner_r))

    # Loại bỏ các NER entries đã được merge vào working_period
    if merged_ner_ids:
        results = [r for r in results if id(r) not in merged_ner_ids]

    return results


# ─────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────

def extract_env_attributes(sentence: str) -> list:
    """
    Trích xuất environment attributes từ câu NLACP.
    Thuật toán 3 tầng:
      Tầng 1: Nhận diện trigger phrases (dep parse + gazetteers)
      Tầng 2: Phân biệt env vs subject/object attribute (NP containment check)
      Tầng 3: Phân loại loại environment + gán namespace

    Trả về list of dicts:
      { category, env_type, subcategory, trigger, phrase, full_value,
        ner_type, normalized, namespace, data_type, method }
    """
    doc = _get_nlp()(sentence)

    # Tầng 0: Chuẩn bị — xác định subject/object NP tokens
    subject_tokens = _get_subject_tokens(doc)
    object_tokens  = _get_object_tokens(doc)

    # Tầng 1: Phát hiện trigger phrases
    raw_candidates = _detect_trigger_phrases(doc, subject_tokens, object_tokens)

    # Tầng 2: Phân biệt env vs attribute
    confirmed = _disambiguate(raw_candidates, subject_tokens, object_tokens)

    # Tầng 3: Phân loại + namespace
    results = _classify_and_enrich(confirmed)

    # Merge parenthetical time range vào working_period entry
    # VD: "during business hours (9am to 5pm)" → env_name="business hours", env_value={between 9am-5pm}
    results = _merge_parenthetical_values(results, sentence)

    # Deduplication
    results = _deduplicate(results)

    return results


def extract_env_candidates(sentence: str) -> list:
    """
    Sinh ENV candidates theo pattern R(Action, EnvPhrase) cho CNN training.
    Pattern: ROOT verb → prep:during/within/after/at → pobj (EnvPhrase)

    Output tương tự SA/OA candidates trong relation_candidate.py:
      { action, env_phrase, env_type, ner_type, valid, method }
    valid = True vì đây là positive instances từ rule-based detection.
    """
    doc  = _get_nlp()(sentence)
    envs = extract_env_attributes(sentence)

    candidates = []
    # Tìm ROOT verb
    root = None
    for token in doc:
        if token.dep_ == "ROOT":
            root = token
            break

    action_text = root.lemma_ if root else "unknown"

    for env in envs:
        candidates.append({
            "action":     action_text,
            "env_phrase": env["phrase"],
            "env_type":   env["env_type"],
            "subcategory": env["subcategory"],
            "ner_type":   env["ner_type"],   # One-hot feature cho CNN
            "full_value": env["full_value"],
            "namespace":  env["namespace"],
            "valid":      True,              # Positive instance
            "method":     env["method"]
        })

    return candidates


def analyze_manual_env_phrase(phrase: str) -> dict:
    """
    Phân tích tự động một đoạn phrase môi trường người dùng nhập thủ công.
    Tận dụng thuật toán trích xuất qua một câu mẫu (pseudo-sentence).
    """
    s = f"A person works {phrase}."
    attrs = extract_env_attributes(s)
    if attrs:
        best = attrs[0]
        best["full_value"] = phrase
        best["method"] = "manual_auto"
        return best
    
    # Fallback nếu không xác định được
    stop = {"a", "an", "the", "this", "that", "of", "in"}
    parts = [w.lower() for w in phrase.split() if w.lower() not in stop]
    normalized = "_".join(parts) if parts else phrase.lower().replace(" ", "_")
    
    return {
        "category":    "environment",
        "env_type":    "unknown",
        "subcategory": "unknown",
        "trigger":     "manual",
        "phrase":      phrase,
        "full_value":  phrase,
        "ner_type":    "",
        "normalized":  normalized,
        "namespace":   f"environment.other:{normalized}",
        "data_type":   "unknown",
        "method":      "manual_fallback"
    }


# ─────────────────────────────────────────────────────────────────────
# SELF-TEST
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import io
    # Force UTF-8 output on Windows to avoid cp1252 errors
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    tests = [
        # Basic temporal
        "A doctor can view patient records during business hours.",
        # Basic spatial
        "Physicians within the ICU can override standard protocols.",
        # Both temporal + spatial
        "A senior nurse can view medical records during business hours within the hospital.",
        # Device/network
        "Administrators using trusted workstations can modify system settings.",
        "Managers accessing from internal VPN can approve expense reports.",
        # Ambiguity: at the hospital should be ENV (outside subject NP)
        "A nurse at the hospital can view records during business hours.",
        # No env-att
        "A registered patient may view his full health record.",
        # Subject-att only, no env
        "A senior nurse may change approved lab procedures.",
        # Multi-env
        "Staff can access data only between 8am and 5pm on weekdays.",
        # Spatial physical
        "Managers can access records within the campus.",
        # Boundary test
        "Staff may access records at night in the lab.",
        # NEW: structured value only (env_name=None, env_value={between})
        "Staff can access data from 8am to 5pm.",
        # NEW: both name + value in same sentence
        "Staff can access records during business hours from 8am to 5pm.",
    ]

    print("\n" + "=" * 65)
    print("  Env-Att Extractor -- 3-Layer Algorithm Test")
    print("=" * 65)

    for s in tests:
        attrs = extract_env_attributes(s)
        print(f"\nInput:  {s}")
        if attrs:
            for a in attrs:
                print(f"  [{a['env_type']:16s}|{a['subcategory']:14s}] "
                      f"\"{a['full_value']}\"")
                print(f"    -> namespace: {a['namespace']}")
                print(f"       trigger={a['trigger']}, ner={a['ner_type']}, method={a['method']}")
                if a.get('env_name') is not None:
                    print(f"       env_name:  {a['env_name']}")
                if a.get('env_value') is not None:
                    print(f"       env_value: {a['env_value']}")
        else:
            print("  (no environment detected)")
