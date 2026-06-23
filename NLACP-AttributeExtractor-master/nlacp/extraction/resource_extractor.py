"""
Resource Extractor for ABAC Policy v2.0

This module extracts and normalizes resource/object entities from policy sentences.
Resources can be: data, document, record, schedule, agreement, offering, registration, attribute.
"""

import spacy
from typing import List, Dict, Optional, Tuple
from nlacp.validation.schema_validator import (
    Resource, ResourceEntityType, ResourceScope, ResourceAttributes
)

nlp = None  # Lazy load

def _get_nlp():
    global nlp
    if nlp is None:
        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            nlp = spacy.blank("en")
    return nlp

# Resource dependency patterns
RESOURCE_DEPS = {"dobj", "pobj", "attr"}

# Resource type mapping (noun phrase to entity_type)
RESOURCE_TYPE_MAPPING = {
    # Data resources
    "score": ResourceEntityType.DATA,
    "scores": ResourceEntityType.DATA,
    "grade": ResourceEntityType.DATA,
    "grades": ResourceEntityType.DATA,
    "transcript": ResourceEntityType.DOCUMENT,
    "transcripts": ResourceEntityType.DOCUMENT,
    
    # Documents
    "roster": ResourceEntityType.DOCUMENT,
    "rosters": ResourceEntityType.DOCUMENT,
    "course roster": ResourceEntityType.DOCUMENT,
    "application": ResourceEntityType.DOCUMENT,
    "applications": ResourceEntityType.DOCUMENT,
    "exam": ResourceEntityType.DOCUMENT,
    "multiple choice exam": ResourceEntityType.DOCUMENT,
    "multiple-choice exam": ResourceEntityType.DOCUMENT,
    "exam details": ResourceEntityType.DOCUMENT,
    "material": ResourceEntityType.DOCUMENT,
    "learning material": ResourceEntityType.DOCUMENT,
    "learning materials": ResourceEntityType.DOCUMENT,
    "agreement": ResourceEntityType.AGREEMENT,
    "visiting lecturer agreement": ResourceEntityType.AGREEMENT,
    "contract": ResourceEntityType.DOCUMENT,
    
    # Schedules
    "class schedule": ResourceEntityType.SCHEDULE,
    "class schedules": ResourceEntityType.SCHEDULE,
    "teaching schedule": ResourceEntityType.SCHEDULE,
    "teaching schedules": ResourceEntityType.SCHEDULE,
    "visiting lecturer class": ResourceEntityType.SCHEDULE,
    "visiting lecturer classes": ResourceEntityType.SCHEDULE,
    "schedule": ResourceEntityType.SCHEDULE,
    "schedules": ResourceEntityType.SCHEDULE,
    "teaching hour": ResourceEntityType.SCHEDULE,
    "teaching hours": ResourceEntityType.SCHEDULE,
    
    # Offerings
    "course offering": ResourceEntityType.OFFERING,
    "course offerings": ResourceEntityType.OFFERING,
    
    # Registrations
    "course registration": ResourceEntityType.REGISTRATION,
    "course registrations": ResourceEntityType.REGISTRATION,
    "registration": ResourceEntityType.REGISTRATION,
    
    # Attributes
    "contract number": ResourceEntityType.ATTRIBUTE,
    "attribute": ResourceEntityType.ATTRIBUTE,
    "field": ResourceEntityType.ATTRIBUTE,
    
    # Records
    "record": ResourceEntityType.RECORD,
    "records": ResourceEntityType.RECORD,
    "student record": ResourceEntityType.RECORD,
    "medical record": ResourceEntityType.RECORD,
}

# Resource label mapping (for normalization)
RESOURCE_LABEL_MAPPING = {
    "score": "score",
    "scores": "score",
    "grade": "grade",
    "grades": "grade",
    "transcript": "transcript",
    "transcripts": "transcript",
    "roster": "roster",
    "rosters": "roster",
    "course roster": "roster",
    "application": "application",
    "applications": "application",
    "exam": "exam",
    "multiple choice exam": "multiple_choice_exam",
    "multiple-choice exam": "multiple_choice_exam",
    "exam details": "exam_details",
    "material": "learning_material",
    "learning material": "learning_material",
    "learning materials": "learning_material",
    "agreement": "agreement",
    "visiting lecturer agreement": "visiting_lecturer_agreement",
    "contract": "contract",
    "contract number": "contract_number",
    "class schedule": "class_schedule",
    "class schedules": "class_schedule",
    "teaching schedule": "teaching_schedule",
    "teaching schedules": "teaching_schedule",
    "visiting lecturer class": "visiting_lecturer_class",
    "visiting lecturer classes": "visiting_lecturer_class",
    "schedule": "schedule",
    "schedules": "schedule",
    "teaching hour": "teaching_hours",
    "teaching hours": "teaching_hours",
    "course offering": "course_offering",
    "course offerings": "course_offering",
    "course registration": "course_registration",
    "course registrations": "course_registration",
    "registration": "registration",
    "record": "record",
    "records": "record",
    "student record": "student_record",
    "medical record": "medical_record",
}

# Scope-related keywords
SCOPE_QUALIFIERS = {
    "own": "own",
    "their": "own",
    "my": "own",
    "every": "every",
    "all": "all",
    "entire": "entire",
    "the": "the",
}

SCOPE_LEVEL_INDICATORS = {
    "that course": "course",
    "for that course": "course",
    "in that course": "course",
    "that department": "department",
    "for that department": "department",
    "in that department": "department",
    "own department": "department",
    "all courses": "all",
    "every course": "all",
    "enrolled courses": "course",
    "per year": "all",
}

# Sensitivity levels
SENSITIVITY_KEYWORDS = {
    "public": "public",
    "internal": "internal",
    "confidential": "confidential",
    "secret": "secret",
}

# Status keywords
STATUS_KEYWORDS = {
    "open": "open",
    "closed": "closed",
    "submitted": "submitted",
    "issued": "issued",
    "numbered": "numbered",
    "official": "official",
    "approved": "approved",
}

# Subject filter indicators
SUBJECT_FILTER_KEYWORDS = {
    "civilian": "civilian_student",
    "civilian student": "civilian_student",
    "civilian students": "civilian_student",
}


def _get_full_noun(token, exclude_indices=None) -> Optional[str]:
    """Get full noun phrase including compound modifiers and adjectives."""
    if not token:
        return None
    if exclude_indices is None:
        exclude_indices = set()
    
    tokens = [token]
    for child in token.children:
        if child.i in exclude_indices:
            continue
        if child.dep_ == "compound" and child.pos_ in ("NOUN", "PROPN"):
            tokens.append(child)
        elif child.dep_ == "amod" and child.text.lower() not in ("that", "which"):
            tokens.append(child)
    
    tokens.sort(key=lambda x: x.i)
    text = " ".join([t.text for t in tokens])
    return text.strip()


def _get_conjuncts(token) -> List:
    """Get conjuncts (and/or) of a token."""
    conjs = []
    for child in token.children:
        if child.dep_ == "conj" and child.pos_ in ("NOUN", "PROPN"):
            conjs.append(child)
            conjs.extend(_get_conjuncts(child))
    return conjs


def _extract_resource_tokens(doc) -> List:
    """Extract resource tokens from dependency tree."""
    resource_tokens = []
    
    for token in doc:
        if token.dep_ == "dobj":
            resource_tokens.append(token)
            resource_tokens.extend(_get_conjuncts(token))
        elif token.dep_ in ("pobj", "attr"):
            resource_tokens.append(token)
            resource_tokens.extend(_get_conjuncts(token))
    
    return resource_tokens


def _identify_resource_type(resource_phrase: str) -> ResourceEntityType:
    """Identify resource entity type from phrase."""
    phrase_lower = resource_phrase.lower()
    
    # Exact matches first
    if phrase_lower in RESOURCE_TYPE_MAPPING:
        return RESOURCE_TYPE_MAPPING[phrase_lower]
    
    # Partial matches
    for key, entity_type in RESOURCE_TYPE_MAPPING.items():
        if key in phrase_lower:
            return entity_type
    
    # Default
    return ResourceEntityType.DOCUMENT


def _extract_resource_label(resource_phrase: str) -> str:
    """Extract normalized resource label."""
    phrase_lower = resource_phrase.lower()
    
    if phrase_lower in RESOURCE_LABEL_MAPPING:
        return RESOURCE_LABEL_MAPPING[phrase_lower]
    
    # Partial match
    for key, label in RESOURCE_LABEL_MAPPING.items():
        if key in phrase_lower:
            return label
    
    # Fallback: convert to snake_case
    return phrase_lower.replace(" ", "_")


def _extract_qualifier(sentence: str, resource_phrase: str) -> Optional[str]:
    """Extract resource qualifier (own, every, all, entire)."""
    sentence_lower = sentence.lower()
    phrase_pos = sentence_lower.find(resource_phrase.lower())
    
    if phrase_pos == -1:
        return None
    
    # Check window before resource
    window_start = max(0, phrase_pos - 50)
    window = sentence_lower[window_start:phrase_pos]
    
    # Check for qualifiers in order of priority
    if "entire" in window:
        return "entire"
    elif "every" in window:
        return "every"
    elif "all" in window:
        return "all"
    elif "their own" in window or "my own" in window or "own" in window:
        return "own"
    elif "the" in window:
        return "the"
    
    return None


def _extract_scope(sentence: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract resource scope (level and ref).
    
    Returns:
        Tuple of (scope_level, scope_ref)
    """
    sentence_lower = sentence.lower()
    
    # Check scope indicators
    for indicator, level in SCOPE_LEVEL_INDICATORS.items():
        if indicator in sentence_lower:
            return level, indicator.replace("for ", "").replace("in ", "")
    
    # Check for "per year" indicator
    if "per year" in sentence_lower:
        return "all", "per_year"
    
    return None, None


def _extract_subject_filter(sentence: str) -> Optional[str]:
    """Extract subject filter (type of subject owning resource)."""
    sentence_lower = sentence.lower()
    
    for keyword, filter_name in SUBJECT_FILTER_KEYWORDS.items():
        if keyword in sentence_lower:
            return filter_name
    
    return None


def _extract_attributes(sentence: str) -> Dict:
    """Extract resource attributes (sensitivity, status)."""
    sentence_lower = sentence.lower()
    attributes = {}
    
    # Check sensitivity
    for keyword, sens_level in SENSITIVITY_KEYWORDS.items():
        if keyword in sentence_lower:
            attributes["sensitivity"] = sens_level
            break
    
    # Check status
    for keyword, status in STATUS_KEYWORDS.items():
        if keyword in sentence_lower:
            attributes["status"] = status
            break
    
    return attributes if attributes else None


def extract_resource(sentence: str, doc=None) -> Optional[Resource]:
    """
    Extract resource from a policy sentence.
    
    Args:
        sentence: Natural language policy sentence
        doc: spaCy Doc object (optional)
    
    Returns:
        Resource object or None if no resource found
    """
    if doc is None:
        doc = _get_nlp()(sentence)
    
    resource_tokens = _extract_resource_tokens(doc)
    
    if not resource_tokens:
        return None
    
    # Take first resource (primary object)
    token = resource_tokens[0]
    resource_phrase = _get_full_noun(token)
    if not resource_phrase:
        resource_phrase = token.text
    
    # Identify type and label
    entity_type = _identify_resource_type(resource_phrase)
    label = _extract_resource_label(resource_phrase)
    
    # Extract qualifier
    qualifier = _extract_qualifier(sentence, resource_phrase)
    
    # Extract scope
    scope_level, scope_ref = _extract_scope(sentence)
    scope = ResourceScope(level=scope_level, ref=scope_ref) if scope_level or scope_ref else None
    
    # Extract subject filter
    subject_filter = _extract_subject_filter(sentence)
    
    # Extract attributes
    attributes_dict = _extract_attributes(sentence)
    attributes = ResourceAttributes(**attributes_dict) if attributes_dict else None
    
    # Build namespace
    namespace = f"resource.{entity_type.value}.{label}"
    
    # Ref tokens
    ref_tokens = [t.text for t in [token] + _get_conjuncts(token)]
    
    resource = Resource(
        entity_type=entity_type,
        ref_tokens=ref_tokens,
        label=label,
        qualifier=qualifier,
        scope=scope,
        subject_filter=subject_filter,
        attributes=attributes,
        namespace=namespace
    )
    
    return resource
