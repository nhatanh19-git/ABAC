"""
Subject Extractor for ABAC Policy v2.0

This module extracts and normalizes subject entities from policy sentences.
Subjects can be: user, role, group, system, agreement, schedule.
"""

import spacy
from typing import List, Dict, Optional, Tuple
from nlacp.validation.schema_validator import Subject, SubjectQualifier, EntityType

nlp = None  # Lazy load

def _get_nlp():
    global nlp
    if nlp is None:
        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            nlp = spacy.blank("en")
    return nlp

# Subject dependency patterns
SUBJECT_DEPS = {"nsubj", "nsubjpass", "csubj"}

# Subject role keywords
SUBJECT_ROLE_KEYWORDS = {
    "student": "student",
    "lecturer": "lecturer",
    "instructor": "instructor",
    "professor": "professor",
    "academic_coordinator": "academic_coordinator",
    "coordinator": "academic_coordinator",
    "department_chair": "department_chair",
    "chair": "department_chair",
    "head": "head",
    "office_user": "office_user",
    "user": "user",
    "applicant": "applicant",
    "visiting_lecturer": "visiting_lecturer",
    "teacher": "lecturer",
}

# Subject type qualifiers
SUBJECT_TYPE_QUALIFIERS = {
    "civilian": "civilian",
    "visiting": "visiting",
    "retired": "retired",
    "official": "official",
}

# Subject rank qualifiers
SUBJECT_RANK_QUALIFIERS = {
    "senior": "senior",
    "head": "head",
    "chair": "chair",
    "coordinator": "coordinator",
}

# Subject status qualifiers
SUBJECT_STATUS_QUALIFIERS = {
    "retired": "retired",
    "active": "active",
    "not_yet_retired": "not_yet_retired",
}

# Office/Department qualifiers
OFFICE_QUALIFIERS = {
    "academic_affairs": "academic_affairs",
    "examination": "examination",
    "finance": "finance",
    "educational_testing": "educational_testing",
    "board_of_directors": "board_of_directors",
}

# Negation indicators
NEGATION_TRIGGERS = {"not", "who are not", "who are no", "no longer"}


def _get_conjuncts(token) -> List:
    """Get conjuncts (and/or) of a token."""
    conjs = []
    for child in token.children:
        if child.dep_ == "conj" and child.pos_ in ("NOUN", "PROPN"):
            conjs.append(child)
            conjs.extend(_get_conjuncts(child))
    return conjs


def _get_full_noun(token) -> Optional[str]:
    """Get full noun phrase including compound modifiers."""
    if not token:
        return None
    tokens = [token]
    for child in token.children:
        if child.dep_ == "compound" and child.pos_ in ("NOUN", "PROPN"):
            tokens.append(child)
        elif child.dep_ == "amod":
            tokens.append(child)
    tokens.sort(key=lambda x: x.i)
    text = " ".join([t.text for t in tokens])
    return text.strip()


def _extract_subject_tokens(doc) -> List:
    """Extract subject tokens from dependency tree."""
    subject_tokens = []
    # Prefer subjects of the main clause (whose head is the root verb)
    root = None
    for t in doc:
        if t.dep_ == "ROOT":
            root = t
            break

    for token in doc:
        # Only consider subjects that attach to the main/root verb
        if token.dep_ in SUBJECT_DEPS and root is not None and token.head == root:
            subject_tokens.append(token)
            subject_tokens.extend(_get_conjuncts(token))
    return subject_tokens


def _detect_negation(sentence: str, subject_phrase: str) -> bool:
    """Detect if subject is negated (e.g., 'who are NOT')."""
    # Look for negation patterns around subject
    sentence_lower = sentence.lower()
    subject_lower = subject_phrase.lower()
    subject_pos = sentence_lower.find(subject_lower)
    
    if subject_pos == -1:
        return False
    
    # Check window around subject
    window_start = max(0, subject_pos - 50)
    window_end = min(len(sentence_lower), subject_pos + len(subject_lower) + 50)
    window = sentence_lower[window_start:window_end]
    
    for trigger in NEGATION_TRIGGERS:
        if trigger in window:
            return True
    return False


def _identify_role(subject_phrase: str) -> Tuple[Optional[str], Dict]:
    """
    Identify subject role and qualifiers from phrase.
    
    Returns:
        Tuple of (role, qualifiers_dict)
    """
    phrase_lower = subject_phrase.lower()
    
    # Check for multi-word patterns first
    patterns = [
        ("academic coordinator", "academic_coordinator"),
        ("department chair", "department_chair"),
        ("department's chair", "department_chair"),
        ("visiting lecturer", "visiting_lecturer"),
        ("office user", "office_user"),
        ("civilian student", "student"),
        ("civilian students", "student"),
        ("applicant", "applicant"),
        ("applicants", "applicant"),
    ]
    
    qualifiers = {}
    role = None
    
    for pattern, role_name in patterns:
        if pattern in phrase_lower:
            role = role_name
            # Extract qualifiers from pattern
            if "civilian" in pattern:
                qualifiers["type"] = "civilian"
            elif "visiting" in pattern:
                qualifiers["type"] = "visiting"
            break
    
    # If no pattern matched, try single words
    if not role:
        for keyword, role_name in SUBJECT_ROLE_KEYWORDS.items():
            if keyword in phrase_lower:
                role = role_name
                break
    
    # Extract type qualifiers
    for type_q in SUBJECT_TYPE_QUALIFIERS:
        if type_q in phrase_lower:
            qualifiers["type"] = type_q
    
    # Extract rank qualifiers
    for rank_q in SUBJECT_RANK_QUALIFIERS:
        if rank_q in phrase_lower:
            qualifiers["rank"] = rank_q
    
    # Extract status qualifiers
    for status_q in SUBJECT_STATUS_QUALIFIERS:
        if status_q in phrase_lower:
            qualifiers["status"] = status_q
    
    # Extract office qualifiers
    for office_q in OFFICE_QUALIFIERS:
        if office_q in phrase_lower:
            if "office" not in qualifiers:
                qualifiers["office"] = []
            qualifiers["office"].append(office_q)
    
    # Check for "own department" scope
    if "own" in phrase_lower and ("department" in phrase_lower or "department's" in phrase_lower):
        qualifiers["department"] = "own"
    elif "any" in phrase_lower and "department" in phrase_lower:
        qualifiers["department"] = "any"
    
    if not role:
        role = "user"  # default role
    
    # Flatten office list if needed
    if "office" in qualifiers and len(qualifiers["office"]) == 1:
        qualifiers["office"] = qualifiers["office"][0]
    
    return role, qualifiers


def _determine_entity_type(role: str, qualifiers: Dict) -> EntityType:
    """Determine entity type based on role and qualifiers."""
    if role == "visiting_lecturer_agreement":
        return EntityType.AGREEMENT
    elif "schedule" in role.lower():
        return EntityType.SCHEDULE
    # Most subjects are users
    return EntityType.USER


def extract_subjects(sentence: str, doc=None) -> List[Subject]:
    """
    Extract all subjects from a policy sentence.
    
    Args:
        sentence: Natural language policy sentence
        doc: spaCy Doc object (optional, will parse if not provided)
    
    Returns:
        List of Subject objects
    """
    if doc is None:
        doc = _get_nlp()(sentence)
    
    subject_tokens = _extract_subject_tokens(doc)
    
    if not subject_tokens:
        return []
    
    subjects = []
    for token in subject_tokens:
        # Get full noun phrase
        subject_phrase = _get_full_noun(token)
        if not subject_phrase:
            subject_phrase = token.text
        
        # Identify role and qualifiers
        role, qualifiers_dict = _identify_role(subject_phrase)
        
        # Detect negation
        negated = _detect_negation(sentence, subject_phrase)
        if negated:
            qualifiers_dict["negated"] = negated
        
        # Build qualifier object
        qualifiers = SubjectQualifier(**qualifiers_dict) if qualifiers_dict else None
        
        # Determine entity type
        entity_type = _determine_entity_type(role, qualifiers_dict)
        
        # Build namespace
        namespace = f"subject.{entity_type.value}.{role}"
        if qualifiers:
            if qualifiers.type:
                namespace += f".{qualifiers.type}"
        
        # Extract ref tokens (tokens that reference this subject)
        ref_tokens = [t.text for t in [token] + _get_conjuncts(token)]
        
        subject = Subject(
            entity_type=entity_type,
            ref_tokens=ref_tokens,
            role=role,
            qualifiers=qualifiers,
            namespace=namespace
        )
        
        subjects.append(subject)
    
    return subjects


def extract_subjects_with_logical_op(sentence: str, doc=None) -> Tuple[List[Subject], Optional[str]]:
    """
    Extract subjects with logical operator (AND/OR) if multiple.
    
    Returns:
        Tuple of (subjects_list, logical_operator)
    """
    subjects = extract_subjects(sentence, doc)
    
    if len(subjects) <= 1:
        return subjects, None
    
    # Detect logical operator
    sentence_lower = sentence.lower()
    logical_op = None
    
    if " and " in sentence_lower:
        logical_op = "AND"
    elif " or " in sentence_lower:
        logical_op = "OR"
    
    return subjects, logical_op
