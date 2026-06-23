"""
Schema validator for ABAC Policy v2.0 using Pydantic

This module provides validation and serialization for structured ABAC policies
extracted from natural language Access Control Policy (ACP) sentences.
"""

from typing import Optional, List, Union, Any, Dict
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS
# ============================================================================

class PolicyEffect(str, Enum):
    """Policy effect: permit or deny"""
    PERMIT = "permit"
    DENY = "deny"


class PolicyModality(str, Enum):
    """Modal verb/phrase for policy"""
    CAN = "can"
    CANNOT = "cannot"
    MUST = "must"
    ONLY_IF = "only_if"
    ONLY_ALLOWED = "only_allowed"


class LogicalOperator(str, Enum):
    """Logical operator between entities"""
    AND = "AND"
    OR = "OR"


class EntityType(str, Enum):
    """Type of entity in policy"""
    USER = "user"
    ROLE = "role"
    GROUP = "group"
    SYSTEM = "system"
    AGREEMENT = "agreement"
    SCHEDULE = "schedule"


class ResourceEntityType(str, Enum):
    """Type of resource"""
    DATA = "data"
    DOCUMENT = "document"
    RECORD = "record"
    SCHEDULE = "schedule"
    AGREEMENT = "agreement"
    OFFERING = "offering"
    REGISTRATION = "registration"
    ATTRIBUTE = "attribute"


class Operation(str, Enum):
    """Standard ABAC operations"""
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    UPLOAD = "UPLOAD"
    DOWNLOAD = "DOWNLOAD"
    COMMENT = "COMMENT"
    APPROVE = "APPROVE"
    DENY = "DENY"
    ASSIGN = "ASSIGN"
    ASSESS = "ASSESS"
    EXPORT = "EXPORT"
    NUMBER = "NUMBER"
    ISSUE = "ISSUE"
    REGISTER = "REGISTER"
    CANCEL = "CANCEL"
    CHECK = "CHECK"
    TAKE = "TAKE"
    EXECUTE = "EXECUTE"
    REQUIRE = "REQUIRE"
    TRANSFER = "TRANSFER"


class EnvironmentType(str, Enum):
    """Type of environment constraint"""
    SYSTEM = "system"
    TEMPORAL = "temporal"
    LOCATION = "location"
    NETWORK = "network"


class ConditionType(str, Enum):
    """Type of policy condition"""
    RELATIONAL = "relational"
    TEMPORAL = "temporal"
    STATUS = "status"
    THRESHOLD = "threshold"
    APPROVAL = "approval"
    PREREQUISITE = "prerequisite"
    MEMBERSHIP = "membership"
    OVERLAP = "overlap"
    SYSTEM_STATE = "system_state"
    OBLIGATION = "obligation"


class ComparisonOperator(str, Enum):
    """Comparison operators for conditions"""
    EQ = "eq"
    NEQ = "neq"
    IN = "in"
    NOT_IN = "not_in"
    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"
    CONTAINS = "contains"
    OVERLAPS = "overlaps"
    HAS_NOT_PASSED = "has_not_passed"


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class SubjectQualifier(BaseModel):
    """Subject qualifier attributes"""
    type: Optional[str] = Field(None, description="Subject type (civilian, visiting, retired, official)")
    rank: Optional[str] = Field(None, description="Subject rank (senior, head, chair, coordinator)")
    status: Optional[str] = Field(None, description="Subject status (retired, active, not_yet_retired)")
    office: Optional[Union[str, List[str]]] = Field(None, description="Office or department")
    department: Optional[str] = Field(None, description="Department scope (own, any)")
    negated: bool = Field(False, description="True if subject is negated")

    class Config:
        use_enum_values = False


class Subject(BaseModel):
    """Subject entity in policy"""
    entity_type: EntityType = Field(..., description="Type of subject entity")
    ref_tokens: Optional[List[str]] = Field(None, description="Tokens referencing this subject")
    role: Optional[str] = Field(None, description="Normalized role name")
    qualifiers: Optional[SubjectQualifier] = Field(None, description="Subject qualifiers")
    namespace: Optional[str] = Field(None, description="Subject namespace")

    class Config:
        use_enum_values = True


class Action(BaseModel):
    """Action/operation in policy"""
    verb: str = Field(..., description="Original verb from sentence")
    operation: Operation = Field(..., description="Normalized operation type")
    negated: bool = Field(False, description="True if action is negated")

    class Config:
        use_enum_values = True


class ResourceScope(BaseModel):
    """Resource scope definition"""
    level: Optional[str] = Field(None, description="Scope level (self, course, department, all, external, none)")
    ref: Optional[str] = Field(None, description="Scope reference")


class ResourceAttributes(BaseModel):
    """Resource attributes"""
    sensitivity: Optional[str] = Field(None, description="Data sensitivity level")
    status: Optional[str] = Field(None, description="Resource status")


class Resource(BaseModel):
    """Resource/object in policy"""
    entity_type: ResourceEntityType = Field(..., description="Type of resource")
    ref_tokens: Optional[List[str]] = Field(None, description="Tokens referencing this resource")
    label: Optional[str] = Field(None, description="Normalized resource label")
    qualifier: Optional[str] = Field(None, description="Resource qualifier (own, every, all, the, entire)")
    scope: Optional[ResourceScope] = Field(None, description="Resource scope definition")
    subject_filter: Optional[str] = Field(None, description="Type of subject owning resource")
    attributes: Optional[ResourceAttributes] = Field(None, description="Resource attributes")
    namespace: Optional[str] = Field(None, description="Resource namespace")

    class Config:
        use_enum_values = True


class EnvironmentSystem(BaseModel):
    """System in environment"""
    label: str = Field(..., description="System name")
    namespace: Optional[str] = Field(None, description="System namespace")


class TimeRange(BaseModel):
    """Temporal time range"""
    from_time: Optional[str] = Field(None, alias="from", description="Start time (HH:MM)")
    to_time: Optional[str] = Field(None, alias="to", description="End time (HH:MM)")

    class Config:
        allow_population_by_field_name = True

    @field_validator("from_time", "to_time", mode="before")
    @classmethod
    def validate_time_format(cls, v):
        """Validate time format HH:MM"""
        if v is None:
            return v
        if isinstance(v, str):
            parts = v.split(":")
            if len(parts) != 2:
                raise ValueError(f"Invalid time format: {v}. Expected HH:MM")
            try:
                h, m = int(parts[0]), int(parts[1])
                if not (0 <= h <= 23 and 0 <= m <= 59):
                    raise ValueError(f"Invalid time values: {v}")
                return v
            except ValueError:
                raise ValueError(f"Invalid time format: {v}")
        return v


class Environment(BaseModel):
    """Environmental constraint"""
    id: Optional[str] = Field(None, description="Environment identifier")
    env_type: EnvironmentType = Field(..., description="Type of environment")
    trigger_phrase: Optional[str] = Field(None, description="Trigger phrase from sentence")
    trigger_word: Optional[str] = Field(None, description="Trigger preposition")
    systems: Optional[List[EnvironmentSystem]] = Field(None, description="List of systems")
    time_range: Optional[TimeRange] = Field(None, description="Temporal range")

    class Config:
        use_enum_values = True


class Condition(BaseModel):
    """Policy condition"""
    id: str = Field(..., description="Condition identifier")
    type: ConditionType = Field(..., description="Condition type")
    trigger_phrase: Optional[str] = Field(None, description="Trigger phrase from sentence")
    left_operand: Optional[str] = Field(None, description="Left operand")
    operator: Optional[ComparisonOperator] = Field(None, description="Comparison operator")
    right_operand: Optional[str] = Field(None, description="Right operand")
    value: Optional[Union[str, int, float, bool]] = Field(None, description="Literal value")
    value_unit: Optional[str] = Field(None, description="Unit of measurement")
    approver_entity: Optional[List[str]] = Field(None, description="Approver entities")
    approval_state: Optional[str] = Field(None, description="Approval state")
    formal_expression: Optional[str] = Field(None, description="Formal boolean expression")
    negated: bool = Field(False, description="True if condition is negated")

    class Config:
        use_enum_values = True

    @field_validator("formal_expression", mode="before")
    @classmethod
    def formal_expression_required_for_certain_types(cls, v, info):
        """formal_expression should not be empty for most condition types"""
        if "type" in info.data and info.data["type"] in [
            ConditionType.RELATIONAL.value,
            ConditionType.TEMPORAL.value,
            ConditionType.THRESHOLD.value,
            ConditionType.APPROVAL.value
        ]:
            if not v:
                logger.warning(f"Condition type '{info.data['type']}' should have formal_expression")
        return v


class RelationPair(BaseModel):
    """Relationship between policy components"""
    entity: str = Field(..., description="Entity type (subject, resource, action)")
    rel_type: str = Field(..., description="Relation type")
    attribute: str = Field(..., description="Attribute name")
    value: Union[str, int] = Field(..., description="Attribute value")


class Policy(BaseModel):
    """ABAC Policy extracted from sentence"""
    id: int = Field(..., description="Policy identifier")
    sentence: str = Field(..., description="Original ACP sentence")
    authorization_decision: PolicyEffect = Field(..., description="Authorization decision (permit/deny)")
    policy_modality: PolicyModality = Field(..., description="Policy modality")
    priority: Optional[int] = Field(None, description="Policy priority")
    subjects: List[Subject] = Field(..., min_items=1, description="Subject entities")
    subjects_logical_op: Optional[LogicalOperator] = Field(None, description="Logical operator between subjects")
    actions: List[Action] = Field(..., min_items=1, description="Actions")
    actions_logical_op: Optional[LogicalOperator] = Field(None, description="Logical operator between actions")
    resource: Resource = Field(..., description="Resource/object")
    environments: List[Environment] = Field(default_factory=list, description="Environmental constraints")
    context: List[Condition] = Field(default_factory=list, description="Policy context / conditions")
    conditions_logical_op: Optional[LogicalOperator] = Field(None, description="Logical operator between context items")
    relation_pairs: Optional[List[RelationPair]] = Field(None, description="Relation pairs")
    abac_policy: Optional[str] = Field(None, description="One-line ABAC policy summary")

    class Config:
        use_enum_values = True

    @model_validator(mode="after")
    def validate_policy_consistency(self):
        """Validate overall policy consistency"""
        # If multiple subjects, subjects_logical_op should be set
        if len(self.subjects) > 1 and not self.subjects_logical_op:
            logger.warning("Multiple subjects without subjects_logical_op specified")

        # If multiple actions, actions_logical_op should be set
        if len(self.actions) > 1 and not self.actions_logical_op:
            logger.warning("Multiple actions without actions_logical_op specified")

        # If multiple context entries, conditions_logical_op should be set
        if len(self.context) > 1 and not self.conditions_logical_op:
            logger.warning("Multiple context entries without conditions_logical_op specified")

        return self


class PolicyDataset(BaseModel):
    """Dataset of policies"""
    version: str = Field(default="2.0", description="Schema version")
    domain: str = Field(..., description="Domain name")
    policies: List[Policy] = Field(..., min_items=1, description="List of policies")

    class Config:
        use_enum_values = True


# ============================================================================
# VALIDATOR CLASS
# ============================================================================

class PolicyValidator:
    """Main validator for ABAC policies"""

    def __init__(self, strict_mode: bool = False):
        """
        Initialize validator

        Args:
            strict_mode: If True, raise exception on validation errors instead of logging
        """
        self.strict_mode = strict_mode

    def validate_policy(self, policy_dict: Dict[str, Any]) -> tuple[bool, List[str], Optional[Policy]]:
        """
        Validate single policy against schema

        Args:
            policy_dict: Dictionary representing a policy

        Returns:
            Tuple of (is_valid, errors, policy_object)
        """
        try:
            policy = Policy(**policy_dict)
            return True, [], policy
        except Exception as e:
            error_msg = str(e)
            if self.strict_mode:
                raise
            logger.error(f"Policy validation failed: {error_msg}")
            return False, [error_msg], None

    def validate_dataset(self, dataset_dict: Dict[str, Any]) -> tuple[bool, List[str], Optional[PolicyDataset]]:
        """
        Validate entire dataset

        Args:
            dataset_dict: Dictionary representing the policy dataset

        Returns:
            Tuple of (is_valid, errors, dataset_object)
        """
        try:
            dataset = PolicyDataset(**dataset_dict)
            return True, [], dataset
        except Exception as e:
            error_msg = str(e)
            if self.strict_mode:
                raise
            logger.error(f"Dataset validation failed: {error_msg}")
            return False, [error_msg], None

    def validate_json_string(self, json_string: str) -> tuple[bool, List[str], Optional[PolicyDataset]]:
        """
        Validate JSON string

        Args:
            json_string: JSON string to validate

        Returns:
            Tuple of (is_valid, errors, dataset_object)
        """
        try:
            data = json.loads(json_string)
            return self.validate_dataset(data)
        except json.JSONDecodeError as e:
            error_msg = f"JSON parsing error: {str(e)}"
            if self.strict_mode:
                raise
            logger.error(error_msg)
            return False, [error_msg], None

    def validate_json_file(self, file_path: str) -> tuple[bool, List[str], Optional[PolicyDataset]]:
        """
        Validate JSON file

        Args:
            file_path: Path to JSON file

        Returns:
            Tuple of (is_valid, errors, dataset_object)
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return self.validate_dataset(data)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            error_msg = f"File validation error: {str(e)}"
            if self.strict_mode:
                raise
            logger.error(error_msg)
            return False, [error_msg], None


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def validate_policy(policy_dict: Dict[str, Any], strict: bool = False) -> tuple[bool, List[str], Optional[Policy]]:
    """Convenience function to validate single policy"""
    validator = PolicyValidator(strict_mode=strict)
    return validator.validate_policy(policy_dict)


def validate_policy_batch(policies: List[Dict[str, Any]], strict: bool = False) -> tuple[int, int, List[str]]:
    """
    Validate batch of policies

    Args:
        policies: List of policy dictionaries
        strict: If True, stop on first error

    Returns:
        Tuple of (valid_count, invalid_count, error_messages)
    """
    validator = PolicyValidator(strict_mode=strict)
    valid_count = 0
    invalid_count = 0
    errors = []

    for i, policy_dict in enumerate(policies):
        is_valid, policy_errors, _ = validator.validate_policy(policy_dict)
        if is_valid:
            valid_count += 1
        else:
            invalid_count += 1
            errors.append(f"Policy {i}: {', '.join(policy_errors)}")
            if strict:
                break

    return valid_count, invalid_count, errors


def validate_dataset(dataset_dict: Dict[str, Any], strict: bool = False) -> tuple[bool, List[str], Optional[PolicyDataset]]:
    """Convenience function to validate entire dataset"""
    validator = PolicyValidator(strict_mode=strict)
    return validator.validate_dataset(dataset_dict)
