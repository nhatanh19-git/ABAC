"""
Action Extractor for ABAC Policy v2.0

This module extracts and normalizes actions/operations from policy sentences.
Maps natural language verbs to standard ABAC operations (CRUD+).
"""

import spacy
from typing import List, Tuple, Optional, Dict
from nlacp.validation.schema_validator import Action, Operation

nlp = None  # Lazy load

def _get_nlp():
    global nlp
    if nlp is None:
        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            nlp = spacy.blank("en")
    return nlp

# Verb to operation mapping
VERB_TO_OPERATION = {
    # Read operations
    "read": Operation.READ,
    "view": Operation.READ,
    "access": Operation.READ,
    "see": Operation.READ,
    "audit": Operation.READ,
    "get": Operation.READ,
    "check": Operation.CHECK,
    "review": Operation.READ,
    "examine": Operation.READ,
    
    # Create operations
    "create": Operation.CREATE,
    "make": Operation.CREATE,
    "add": Operation.CREATE,
    "insert": Operation.CREATE,
    "upload": Operation.UPLOAD,
    "new": Operation.CREATE,
    "register": Operation.REGISTER,
    "issue": Operation.ISSUE,
    
    # Update operations
    "update": Operation.UPDATE,
    "modify": Operation.UPDATE,
    "change": Operation.UPDATE,
    "edit": Operation.UPDATE,
    "approve": Operation.APPROVE,
    "request": Operation.UPDATE,
    "assign": Operation.ASSIGN,
    "number": Operation.NUMBER,
    "export": Operation.EXPORT,
    
    # Delete operations
    "delete": Operation.DELETE,
    "remove": Operation.DELETE,
    "destroy": Operation.DELETE,
    "drop": Operation.DELETE,
    
    # Other operations
    "download": Operation.DOWNLOAD,
    "comment": Operation.COMMENT,
    "deny": Operation.DENY,
    "assess": Operation.ASSESS,
    "take": Operation.TAKE,
    "execute": Operation.EXECUTE,
    "require": Operation.REQUIRE,
    "transfer": Operation.TRANSFER,
    "cancel": Operation.CANCEL,
}

# Action dependency patterns
ACTION_DEPS = {"ROOT", "xcomp", "advcl"}

# Negation indicators
NEGATION_WORDS = {"not", "cannot", "no", "never", "neither"}


def _extract_action_tokens(doc) -> List:
    """Extract action tokens from dependency tree."""
    action_tokens = []
    
    for token in doc:
        # Main verb (ROOT)
        if token.dep_ == "ROOT" and token.pos_ in ("VERB", "NOUN", "AUX"):
            if token.pos_ == "VERB" or (token.pos_ in ("NOUN", "AUX") and token.lemma_.lower() in VERB_TO_OPERATION):
                action_tokens.append(token)
        
        # Modal verbs (aux) - usually can/cannot/must
        elif token.pos_ == "AUX" and token.text.lower() in ("can", "cannot", "could", "could not", "might"):
            continue  # skip modal verb as action, it's a modality indicator
        
        # Other verbs
        elif token.pos_ == "VERB" and token.dep_ not in ("aux", "amod", "compound", "acl", "relcl"):
            if token not in action_tokens:
                action_tokens.append(token)
    
    # Extract conjuncts (and/or verbs)
    conjuncts = []
    for token in action_tokens:
        for child in token.children:
            if child.dep_ == "conj" and child.pos_ in ("VERB", "NOUN"):
                conjuncts.append(child)
    
    action_tokens.extend(conjuncts)
    return action_tokens


def _get_negation_before(token, window_size=5) -> bool:
    """Check if negation words appear within window_size tokens before this token."""
    start_idx = max(0, token.i - window_size)
    for i in range(start_idx, token.i):
        if token.doc[i].text.lower() in NEGATION_WORDS:
            return True
    return False


def _map_verb_to_operation(verb: str) -> Optional[Operation]:
    """Map natural language verb to ABAC operation."""
    verb_lower = verb.lower()
    
    # Direct mapping
    if verb_lower in VERB_TO_OPERATION:
        return VERB_TO_OPERATION[verb_lower]
    
    # Lemmatized mapping (try without -ing, -ed, etc.)
    # This is handled by spaCy lemmatization in extract_actions
    return None


def extract_actions(sentence: str, doc=None) -> List[Action]:
    """
    Extract all actions from a policy sentence.
    
    Args:
        sentence: Natural language policy sentence
        doc: spaCy Doc object (optional, will parse if not provided)
    
    Returns:
        List of Action objects
    """
    if doc is None:
        doc = _get_nlp()(sentence)
    
    action_tokens = _extract_action_tokens(doc)
    
    if not action_tokens:
        # Fallback: look for action-like words anywhere
        for token in doc:
            if token.lemma_.lower() in VERB_TO_OPERATION:
                action_tokens.append(token)
    
    actions = []
    for token in action_tokens:
        verb = token.lemma_.lower() if token.lemma_ else token.text.lower()
        operation = _map_verb_to_operation(verb)
        
        if operation is None:
            # Try direct text mapping
            operation = _map_verb_to_operation(token.text.lower())
        
        # Skip if no operation mapping found
        if operation is None:
            continue
        
        # Check for negation before this action
        negated = _get_negation_before(token)
        
        action = Action(
            verb=verb,
            operation=operation,
            negated=negated
        )
        
        actions.append(action)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_actions = []
    for action in actions:
        # Handle both enum and string representations (Pydantic may convert to string)
        op_val = action.operation if isinstance(action.operation, str) else action.operation.value
        key = (action.verb, op_val, action.negated)
        if key not in seen:
            seen.add(key)
            unique_actions.append(action)
    
    return unique_actions


def extract_actions_with_logical_op(sentence: str, doc=None) -> Tuple[List[Action], Optional[str]]:
    """
    Extract actions with logical operator (AND/OR) if multiple.
    
    Returns:
        Tuple of (actions_list, logical_operator)
    """
    actions = extract_actions(sentence, doc)
    
    if len(actions) <= 1:
        return actions, None
    
    # Detect logical operator from sentence
    sentence_lower = sentence.lower()
    logical_op = None
    
    if " and " in sentence_lower:
        logical_op = "AND"
    elif " or " in sentence_lower:
        logical_op = "OR"
    
    return actions, logical_op


def suggest_operation_from_context(sentence: str, doc=None) -> Optional[Operation]:
    """
    If action extraction failed, try to infer operation from context/keywords.
    
    Useful for cases like: "An official visiting lecturer agreement must have a contract number"
    where implicit operations might be CREATE/UPDATE.
    """
    if doc is None:
        doc = nlp(sentence)
    
    sentence_lower = sentence.lower()
    
    # Context-based inference
    if "must have" in sentence_lower:
        return Operation.CREATE
    elif "can only" in sentence_lower or "can only be" in sentence_lower:
        return Operation.READ
    
    return None
