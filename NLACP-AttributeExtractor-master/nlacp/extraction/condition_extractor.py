"""
Condition Extractor for ABAC Policy v2.0

This module extracts and normalizes policy conditions from natural language sentences.
Conditions can be: relational, temporal, status, threshold, approval, prerequisite,
membership, overlap, system_state, obligation.
"""

import re
import spacy
from typing import List, Dict, Optional, Tuple
from datetime import time
from nlacp.validation.schema_validator import (
    Condition, ConditionType, ComparisonOperator
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

# Condition trigger keywords
CONDITION_TRIGGERS = {
    # Relational conditions
    "for courses which they have taken": ConditionType.RELATIONAL,
    "for courses which they are taking": ConditionType.RELATIONAL,
    "for that course": ConditionType.RELATIONAL,
    "for that department": ConditionType.RELATIONAL,
    "for courses in that department": ConditionType.RELATIONAL,
    "for all courses": ConditionType.RELATIONAL,
    "in that course": ConditionType.RELATIONAL,
    
    # Temporal conditions
    "between": ConditionType.TEMPORAL,
    "after": ConditionType.TEMPORAL,
    "before": ConditionType.TEMPORAL,
    "during": ConditionType.TEMPORAL,
    "from": ConditionType.TEMPORAL,
    "within": ConditionType.TEMPORAL,
    
    # Status conditions
    "in an open state": ConditionType.STATUS,
    "in a closed state": ConditionType.STATUS,
    "if it has been numbered": ConditionType.OBLIGATION,
    "if it has been made official": ConditionType.OBLIGATION,
    "if it has been exported": ConditionType.OBLIGATION,
    
    # Threshold conditions
    "exceeds": ConditionType.THRESHOLD,
    "more than": ConditionType.THRESHOLD,
    "reaches": ConditionType.THRESHOLD,
    "up to": ConditionType.THRESHOLD,
    "does not exceed": ConditionType.THRESHOLD,
    "cannot teach more than": ConditionType.THRESHOLD,
    "cannot register for a course": ConditionType.THRESHOLD,
    
    # Approval conditions
    "after the approval of": ConditionType.APPROVAL,
    "with the approval of": ConditionType.APPROVAL,
    "with the director's approval": ConditionType.APPROVAL,
    "after approval of": ConditionType.APPROVAL,
    "only if": ConditionType.APPROVAL,
    "if the board of directors has rejected": ConditionType.APPROVAL,
    
    # Prerequisite conditions
    "have not passed the prerequisites": ConditionType.PREREQUISITE,
    "have not passed prerequisites": ConditionType.PREREQUISITE,
    "passed the prerequisites": ConditionType.PREREQUISITE,
    
    # Membership conditions
    "in the academic affairs office": ConditionType.MEMBERSHIP,
    "in the finance office": ConditionType.MEMBERSHIP,
    "in the examination office": ConditionType.MEMBERSHIP,
    "not in the academic affairs office": ConditionType.MEMBERSHIP,
    
    # Overlap conditions
    "overlapping class schedules": ConditionType.OVERLAP,
    "overlapping schedules": ConditionType.OVERLAP,
    
    # System state conditions
    "if the system has not been activated": ConditionType.SYSTEM_STATE,
    "if the system has been activated": ConditionType.SYSTEM_STATE,
    "system has not been activated": ConditionType.SYSTEM_STATE,
    
    # Obligation conditions
    "must have": ConditionType.OBLIGATION,
    "must be": ConditionType.OBLIGATION,
}

# Comparison operators
OPERATOR_KEYWORDS = {
    "exceeds": ComparisonOperator.GT,
    "greater than": ComparisonOperator.GT,
    "more than": ComparisonOperator.GT,
    ">": ComparisonOperator.GT,
    
    "reaches": ComparisonOperator.GTE,
    "at least": ComparisonOperator.GTE,
    "greater than or equal": ComparisonOperator.GTE,
    ">=": ComparisonOperator.GTE,
    
    "less than": ComparisonOperator.LT,
    "fewer than": ComparisonOperator.LT,
    "<": ComparisonOperator.LT,
    
    "up to": ComparisonOperator.LTE,
    "not exceed": ComparisonOperator.LTE,
    "does not exceed": ComparisonOperator.LTE,
    "<=": ComparisonOperator.LTE,
    
    "equals": ComparisonOperator.EQ,
    "is": ComparisonOperator.EQ,
    "=": ComparisonOperator.EQ,
    
    "not equal": ComparisonOperator.NEQ,
    "is not": ComparisonOperator.NEQ,
    "!=": ComparisonOperator.NEQ,
    
    "in": ComparisonOperator.IN,
    "not in": ComparisonOperator.NOT_IN,
    "contains": ComparisonOperator.CONTAINS,
    "overlaps": ComparisonOperator.OVERLAPS,
    "has not passed": ComparisonOperator.HAS_NOT_PASSED,
}

# Unit keywords
UNIT_KEYWORDS = {
    "hour": "hours",
    "hours": "hours",
    "per year": "hours/year",
    "yearly": "hours/year",
    "credit": "credits",
    "credits": "credits",
    "student": "students",
    "students": "students",
    "vnd": "vnd",
}

# Approver keywords
APPROVER_KEYWORDS = {
    "academic affairs": "academic_affairs_office",
    "academic affairs office": "academic_affairs_office",
    "finance": "finance_office",
    "finance office": "finance_office",
    "director": "director",
    "board of directors": "board_of_directors",
}


def _extract_time_range(phrase: str) -> Optional[Tuple[str, str]]:
    """
    Extract time range from phrase like 'between 7:00 am and 5:25 pm'.
    
    Returns:
        Tuple of (start_time, end_time) in HH:MM format, or None
    """
    # Pattern: "between HH:MM am/pm and HH:MM am/pm"
    pattern = r'between\s+(\d{1,2}):(\d{2})\s*(am|pm)?\s+and\s+(\d{1,2}):(\d{2})\s*(am|pm)?'
    match = re.search(pattern, phrase, re.IGNORECASE)
    
    if not match:
        return None
    
    start_h = int(match.group(1))
    start_m = int(match.group(2))
    start_ap = match.group(3)
    end_h = int(match.group(4))
    end_m = int(match.group(5))
    end_ap = match.group(6)
    
    # Convert to 24-hour format
    if start_ap and start_ap.lower() == "pm" and start_h != 12:
        start_h += 12
    elif start_ap and start_ap.lower() == "am" and start_h == 12:
        start_h = 0
    
    if end_ap and end_ap.lower() == "pm" and end_h != 12:
        end_h += 12
    elif end_ap and end_ap.lower() == "am" and end_h == 12:
        end_h = 0
    
    return (f"{start_h:02d}:{start_m:02d}", f"{end_h:02d}:{end_m:02d}")


def _extract_numeric_value(phrase: str) -> Optional[float]:
    """Extract numeric value from phrase."""
    # Pattern for numbers with optional decimal and suffix
    pattern = r'(\d+(?:\.\d+)?)\s*(?:hours?|credits?|vnd)?'
    match = re.search(pattern, phrase)
    
    if match:
        return float(match.group(1))
    return None


def _extract_value_unit(phrase: str) -> Optional[str]:
    """Extract unit from phrase."""
    phrase_lower = phrase.lower()
    
    for keyword, unit in UNIT_KEYWORDS.items():
        if keyword in phrase_lower:
            return unit
    
    return None


def _extract_approver_entities(phrase: str) -> Optional[List[str]]:
    """Extract approver entity names from phrase."""
    approvers = []
    phrase_lower = phrase.lower()
    
    for keyword, approver in APPROVER_KEYWORDS.items():
        if keyword in phrase_lower:
            approvers.append(approver)
    
    return approvers if approvers else None


def _detect_approval_state(phrase: str) -> Optional[str]:
    """Detect approval state (approved/rejected)."""
    phrase_lower = phrase.lower()
    
    if "rejected" in phrase_lower or "has rejected" in phrase_lower:
        return "rejected"
    elif "approved" in phrase_lower or "approval" in phrase_lower:
        return "approved"
    
    return None


def _build_formal_expression(cond_type: ConditionType, left_op: str, operator: str, 
                            right_op: str = None, value: str = None) -> str:
    """Build formal boolean expression for condition."""
    if operator == ComparisonOperator.EQ.value or operator == "eq":
        return f"{left_op} == {right_op or value}"
    elif operator == ComparisonOperator.NEQ.value or operator == "neq":
        return f"{left_op} != {right_op or value}"
    elif operator == ComparisonOperator.GT.value or operator == "gt":
        return f"{left_op} > {right_op or value}"
    elif operator == ComparisonOperator.GTE.value or operator == "gte":
        return f"{left_op} >= {right_op or value}"
    elif operator == ComparisonOperator.LT.value or operator == "lt":
        return f"{left_op} < {right_op or value}"
    elif operator == ComparisonOperator.LTE.value or operator == "lte":
        return f"{left_op} <= {right_op or value}"
    elif operator == ComparisonOperator.IN.value or operator == "in":
        return f"{left_op} IN ({right_op or value})"
    elif operator == ComparisonOperator.NOT_IN.value or operator == "not_in":
        return f"{left_op} NOT IN ({right_op or value})"
    elif operator == ComparisonOperator.CONTAINS.value or operator == "contains":
        return f"{left_op} CONTAINS ({right_op or value})"
    elif operator == ComparisonOperator.OVERLAPS.value or operator == "overlaps":
        return f"NOT ({left_op} OVERLAPS {right_op or value})"
    elif operator == ComparisonOperator.HAS_NOT_PASSED.value or operator == "has_not_passed":
        return f"{left_op} HAS_NOT_PASSED {right_op or value}"
    
    return ""


def extract_conditions(sentence: str, doc=None) -> List[Condition]:
    """
    Extract all conditions from a policy sentence.
    
    Args:
        sentence: Natural language policy sentence
        doc: spaCy Doc object (optional)
    
    Returns:
        List of Condition objects
    """
    if doc is None:
        doc = _get_nlp()(sentence)
    
    conditions = []
    sentence_lower = sentence.lower()
    cond_id = 1
    
    # Find condition triggers
    for trigger_phrase, cond_type in CONDITION_TRIGGERS.items():
        if trigger_phrase in sentence_lower:
            # Extract context around trigger
            trigger_pos = sentence_lower.find(trigger_phrase)
            context_start = max(0, trigger_pos - 50)
            context_end = min(len(sentence), trigger_pos + len(trigger_phrase) + 50)
            context = sentence[context_start:context_end]
            
            # Handle different condition types
            if cond_type == ConditionType.TEMPORAL:
                time_range = _extract_time_range(context)
                if time_range:
                    formal_expr = f"environment.current_time IN [{time_range[0]}, {time_range[1]}]"
                    condition = Condition(
                        id=f"cond_{cond_id}",
                        type=cond_type,
                        trigger_phrase=trigger_phrase,
                        left_operand="environment.current_time",
                        operator=ComparisonOperator.IN,
                        value=f"[{time_range[0]}, {time_range[1]}]",
                        formal_expression=formal_expr,
                        negated=False
                    )
                    conditions.append(condition)
                    cond_id += 1
            
            elif cond_type == ConditionType.THRESHOLD:
                numeric_value = _extract_numeric_value(context)
                unit = _extract_value_unit(context)
                
                if numeric_value:
                    # Detect operator
                    operator = ComparisonOperator.GT
                    left_op = "subject.teaching_hours"
                    
                    if "does not exceed" in context.lower() or "not exceed" in context.lower():
                        operator = ComparisonOperator.LTE
                    
                    formal_expr = _build_formal_expression(
                        cond_type, left_op, operator.value, value=str(numeric_value)
                    )
                    
                    condition = Condition(
                        id=f"cond_{cond_id}",
                        type=cond_type,
                        trigger_phrase=trigger_phrase,
                        left_operand=left_op,
                        operator=operator,
                        value=numeric_value,
                        value_unit=unit,
                        formal_expression=formal_expr,
                        negated=False
                    )
                    conditions.append(condition)
                    cond_id += 1
            
            elif cond_type == ConditionType.APPROVAL:
                approvers = _extract_approver_entities(context)
                approval_state = _detect_approval_state(context)
                
                formal_expr = f"resource.approver IN ({', '.join(approvers) if approvers else 'unknown'})"
                
                condition = Condition(
                    id=f"cond_{cond_id}",
                    type=cond_type,
                    trigger_phrase=trigger_phrase,
                    left_operand="resource.approval_status",
                    operator=ComparisonOperator.EQ,
                    approver_entity=approvers,
                    approval_state=approval_state,
                    formal_expression=formal_expr,
                    negated=False
                )
                conditions.append(condition)
                cond_id += 1
            
            elif cond_type == ConditionType.OBLIGATION:
                # e.g., "must have contract number" -> resource.contract_number IS NOT NULL
                formal_expr = "resource.contract_number IS NOT NULL"
                
                condition = Condition(
                    id=f"cond_{cond_id}",
                    type=cond_type,
                    trigger_phrase=trigger_phrase,
                    left_operand="resource.contract_number",
                    operator=ComparisonOperator.NEQ,
                    value="NULL",
                    formal_expression=formal_expr,
                    negated=False
                )
                conditions.append(condition)
                cond_id += 1
            
            elif cond_type == ConditionType.RELATIONAL:
                # Context-based relational condition
                formal_expr = "resource.course_id IN subject.enrolled_courses"
                
                condition = Condition(
                    id=f"cond_{cond_id}",
                    type=cond_type,
                    trigger_phrase=trigger_phrase,
                    left_operand="resource.course_id",
                    operator=ComparisonOperator.IN,
                    right_operand="subject.enrolled_courses",
                    formal_expression=formal_expr,
                    negated=False
                )
                conditions.append(condition)
                cond_id += 1
            
            elif cond_type == ConditionType.OVERLAP:
                formal_expr = "NOT (resource.course_A.schedule OVERLAPS resource.course_B.schedule)"
                
                condition = Condition(
                    id=f"cond_{cond_id}",
                    type=cond_type,
                    trigger_phrase=trigger_phrase,
                    left_operand="resource.course_A.schedule",
                    operator=ComparisonOperator.OVERLAPS,
                    right_operand="resource.course_B.schedule",
                    formal_expression=formal_expr,
                    negated=True
                )
                conditions.append(condition)
                cond_id += 1
            
            elif cond_type == ConditionType.PREREQUISITE:
                formal_expr = "subject.completed_courses CONTAINS resource.prerequisite_course_ids"
                
                condition = Condition(
                    id=f"cond_{cond_id}",
                    type=cond_type,
                    trigger_phrase=trigger_phrase,
                    left_operand="subject.completed_courses",
                    operator=ComparisonOperator.CONTAINS,
                    right_operand="resource.prerequisite_course_ids",
                    formal_expression=formal_expr,
                    negated=True  # "have NOT passed"
                )
                conditions.append(condition)
                cond_id += 1
    
    return conditions


def extract_conditions_with_logical_op(sentence: str, doc=None) -> Tuple[List[Condition], Optional[str]]:
    """
    Extract conditions with logical operator (AND/OR) if multiple.
    
    Returns:
        Tuple of (conditions_list, logical_operator)
    """
    conditions = extract_conditions(sentence, doc)
    
    if len(conditions) <= 1:
        return conditions, None
    
    # Detect logical operator
    sentence_lower = sentence.lower()
    logical_op = None
    
    if " and " in sentence_lower:
        logical_op = "AND"
    elif " or " in sentence_lower:
        logical_op = "OR"
    
    return conditions, logical_op
