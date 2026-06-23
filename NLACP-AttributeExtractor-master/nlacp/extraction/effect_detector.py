"""
Effect Detector for ABAC Policy v2.0

This module detects policy effect (permit/deny) and modality (can/cannot/must/only_if/only_allowed)
from natural language policy sentences.
"""

import spacy
from typing import Tuple, Optional
from nlacp.validation.schema_validator import PolicyEffect, PolicyModality

nlp = None  # Lazy load on first use

def _get_nlp():
    global nlp
    if nlp is None:
        import spacy
        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            nlp = spacy.blank("en")
    return nlp

# Policy effect indicators
DENY_INDICATORS = {
    "cannot", "can not", "can't",
    "who are not", "who are no",
    "not allowed", "not permitted",
    "prohibited", "forbidden",
}

PERMIT_INDICATORS = {
    "can", "may", "could",
    "must", "shall", "should",
    "are allowed", "are permitted",
}

# Policy modality indicators
MODALITY_MAPPING = {
    # Deny
    "cannot": PolicyModality.CANNOT,
    "can not": PolicyModality.CANNOT,
    "can't": PolicyModality.CANNOT,
    "who are not": PolicyModality.CANNOT,
    "not allowed": PolicyModality.CANNOT,
    "not permitted": PolicyModality.CANNOT,
    
    # Must/Obligation
    "must": PolicyModality.MUST,
    "shall": PolicyModality.MUST,
    "should": PolicyModality.MUST,
    "required to": PolicyModality.MUST,
    "must have": PolicyModality.MUST,
    "must be": PolicyModality.MUST,
    
    # Only if / Conditional
    "can only": PolicyModality.ONLY_IF,
    "can only be": PolicyModality.ONLY_IF,
    "only if": PolicyModality.ONLY_IF,
    
    # Only allowed / Restricted
    "are only allowed": PolicyModality.ONLY_ALLOWED,
    "only allowed": PolicyModality.ONLY_ALLOWED,
    
    # Default: can/permit
    "can": PolicyModality.CAN,
    "may": PolicyModality.CAN,
    "could": PolicyModality.CAN,
}


def _find_modal_verb(doc) -> Optional[str]:
    """
    Find modal verb or modality phrase in sentence.
    
    Returns the first matched modal verb token/phrase.
    """
    sentence_lower = doc.text.lower()
    
    # Check for multi-word modalities first (longer patterns)
    multi_word_modalities = [
        "can only",
        "can not",
        "are only allowed",
        "not allowed",
        "not permitted",
        "who are not",
        "who are no",
        "must have",
        "must be",
        "can only be",
        "required to",
        "only if",
        "only allowed",
    ]
    
    for modality in multi_word_modalities:
        if modality in sentence_lower:
            return modality
    
    # Check single-word modalities
    single_word_modalities = [
        "cannot", "can't", "must", "shall", "should",
        "can", "may", "could",
    ]
    
    for modality in single_word_modalities:
        if modality in sentence_lower:
            return modality
    
    return None


def _is_negation_context(sentence: str, modal: str) -> bool:
    """
    Check if modal verb is in a negation context.
    
    Examples:
    - "cannot" is inherently negated
    - "can" followed by "not" within 5 words → negated
    """
    sentence_lower = sentence.lower()
    
    if modal in ("cannot", "can't", "can not"):
        return True
    
    modal_pos = sentence_lower.find(modal)
    if modal_pos == -1:
        return False
    
    # Check window after modal
    window_end = min(len(sentence), modal_pos + len(modal) + 20)
    window = sentence_lower[modal_pos:window_end]
    
    if "not" in window or "no" in window:
        return True
    
    return False


def detect_effect(sentence: str, doc=None) -> PolicyEffect:
    """
    Detect policy effect (permit/deny) from sentence.
    
    Args:
        sentence: Natural language policy sentence
        doc: spaCy Doc object (optional)
    
    Returns:
        PolicyEffect (permit or deny)
    """
    if doc is None:
        doc = _get_nlp()(sentence)
    
    sentence_lower = sentence.lower()
    
    # Check deny indicators first (higher priority)
    for indicator in DENY_INDICATORS:
        if indicator in sentence_lower:
            return PolicyEffect.DENY
    
    # Check permit indicators
    for indicator in PERMIT_INDICATORS:
        if indicator in sentence_lower:
            return PolicyEffect.PERMIT
    
    # Default to permit if no strong indicator found
    return PolicyEffect.PERMIT


def detect_modality(sentence: str, doc=None) -> PolicyModality:
    """
    Detect policy modality (can/cannot/must/only_if/only_allowed).
    
    Args:
        sentence: Natural language policy sentence
        doc: spaCy Doc object (optional)
    
    Returns:
        PolicyModality
    """
    if doc is None:
        doc = _get_nlp()(sentence)
    
    modal_verb = _find_modal_verb(doc)
    
    if modal_verb:
        modal_lower = modal_verb.lower()
        if modal_lower in MODALITY_MAPPING:
            return MODALITY_MAPPING[modal_lower]
    
    # Fallback: infer from effect
    effect = detect_effect(sentence, doc)
    if effect == PolicyEffect.DENY:
        return PolicyModality.CANNOT
    else:
        return PolicyModality.CAN


def detect_effect_and_modality(sentence: str, doc=None) -> Tuple[PolicyEffect, PolicyModality]:
    """
    Detect both effect and modality from sentence.
    
    Args:
        sentence: Natural language policy sentence
        doc: spaCy Doc object (optional)
    
    Returns:
        Tuple of (effect, modality)
    """
    if doc is None:
        doc = _get_nlp()(sentence)
    
    effect = detect_effect(sentence, doc)
    modality = detect_modality(sentence, doc)
    
    # Validate consistency
    if effect == PolicyEffect.DENY and modality == PolicyModality.CAN:
        # Inconsistent: force modality to CANNOT
        modality = PolicyModality.CANNOT
    elif effect == PolicyEffect.PERMIT and modality == PolicyModality.CANNOT:
        # Inconsistent: force effect to DENY
        effect = PolicyEffect.DENY
    
    return effect, modality


def detect_priority(sentence: str) -> Optional[int]:
    """
    Attempt to detect policy priority from sentence.
    
    Priority indicators: numbers, keywords like "high", "critical", etc.
    Currently returns None (could be extended).
    """
    # Placeholder for future priority detection logic
    return None
