"""
Policy Formatter for ABAC Policy v2.0

This module formats and structures extracted policy components into
the final JSON output according to schema v2.0.
"""

from typing import Optional, List, Dict, Any
from nlacp.validation.schema_validator import (
    Policy, Subject, Action, Resource, Environment, Condition,
    PolicyEffect, PolicyModality
)


class PolicyFormatter:
    """Formatter for ABAC policies."""
    
    @staticmethod
    def format_abac_policy(
        effect: PolicyEffect,
        subjects: List[Subject],
        actions: List[Action],
        resource: Resource,
        environments: Optional[List[Environment]] = None,
        context: Optional[List[Condition]] = None,
    ) -> str:
        """
        Create one-line ABAC policy summary.
        
        Format: "<EFFECT> subject[<attrs>] ACTION[<ops>] RESOURCE[<label>,<attrs>] ENV[<systems>] IF <conditions>"
        
        Args:
            effect: Policy effect (permit/deny)
            subjects: List of subjects
            actions: List of actions
            resource: Resource/object
            environments: Optional environmental constraints
            conditions: Optional policy conditions
        
        Returns:
            One-line ABAC policy string
        """
        effect_str = effect.value.upper()
        
        # Format subjects
        subject_attrs = []
        for subj in subjects:
            if subj.role:
                subject_attrs.append(subj.role)
            if subj.qualifiers and subj.qualifiers.type:
                subject_attrs.append(subj.qualifiers.type)
        subject_str = f"subject[{','.join(subject_attrs)}]" if subject_attrs else "subject"
        
        # Format actions
        action_ops = []
        for act in actions:
            op_val = act.operation if isinstance(act.operation, str) else act.operation.value
            action_ops.append(op_val)
        action_str = f"ACTION[{','.join(action_ops)}]"
        
        # Format resource
        resource_attrs = []
        if resource:
            if resource.label:
                resource_attrs.append(resource.label)
            if resource.attributes and resource.attributes.status:
                resource_attrs.append(resource.attributes.status)
        resource_str = f"RESOURCE[{','.join(resource_attrs)}]" if resource_attrs else "RESOURCE"
        
        # Format environments
        env_systems = []
        if environments:
            for env in environments:
                if env.systems:
                    for sys in env.systems:
                        if sys.label:
                            env_systems.append(sys.label)
        env_str = f"ENV[{','.join(env_systems)}]" if env_systems else ""
        
        # Format context/conditions
        cond_str = ""
        if context:
            cond_exprs = [c.formal_expression for c in context if c.formal_expression]
            if cond_exprs:
                cond_str = f" IF {' AND '.join(cond_exprs)}"
        
        # Assemble final policy
        policy_parts = [effect_str, subject_str, action_str, resource_str]
        if env_str:
            policy_parts.append(env_str)
        
        abac_policy = " ".join(policy_parts) + cond_str
        
        return abac_policy
    
    @staticmethod
    def build_relation_pairs(
        subjects: List[Subject],
        resource: Resource,
        actions: List[Action],
    ) -> List[Dict]:
        """
        Build relation pairs from policy components.
        
        Args:
            subjects: List of subjects
            resource: Resource
            actions: List of actions
        
        Returns:
            List of relation pair dictionaries
        """
        relation_pairs = []
        
        # Subject relations
        for subj in subjects:
            if subj.qualifiers:
                if subj.qualifiers.type:
                    relation_pairs.append({
                        "entity": "subject",
                        "rel_type": "attribute",
                        "attribute": "type",
                        "value": subj.qualifiers.type
                    })
                if subj.qualifiers.rank:
                    relation_pairs.append({
                        "entity": "subject",
                        "rel_type": "attribute",
                        "attribute": "rank",
                        "value": subj.qualifiers.rank
                    })
                if subj.qualifiers.office:
                    office_val = subj.qualifiers.office
                    if isinstance(office_val, list):
                        office_val = ", ".join(office_val)
                    relation_pairs.append({
                        "entity": "subject",
                        "rel_type": "membership",
                        "attribute": "office",
                        "value": office_val
                    })
                if subj.qualifiers.department:
                    relation_pairs.append({
                        "entity": "subject",
                        "rel_type": "scope",
                        "attribute": "department",
                        "value": subj.qualifiers.department
                    })
        
        # Resource relations
        if resource:
            if resource.qualifier:
                relation_pairs.append({
                    "entity": "resource",
                    "rel_type": "possession",
                    "attribute": "qualifier",
                    "value": resource.qualifier
                })
            
            if resource.scope and resource.scope.level:
                relation_pairs.append({
                    "entity": "resource",
                    "rel_type": "scope",
                    "attribute": "level",
                    "value": resource.scope.level
                })
            
            if resource.attributes:
                if resource.attributes.sensitivity:
                    relation_pairs.append({
                        "entity": "resource",
                        "rel_type": "attribute",
                        "attribute": "sensitivity",
                    "value": resource.attributes.sensitivity
                })
                if resource.attributes.status:
                    relation_pairs.append({
                        "entity": "resource",
                        "rel_type": "status",
                        "attribute": "status",
                        "value": resource.attributes.status
                    })
                relation_pairs.append({
                    "entity": "action",
                    "rel_type": "attribute",
                    "attribute": "negated",
                    "value": "true"
                })
        
        return relation_pairs


def format_policy_to_json(
    policy_id: int,
    sentence: str,
    effect: PolicyEffect,
    modality: PolicyModality,
    subjects: List[Subject],
    actions: List[Action],
    resource: Resource,
    environments: Optional[List[Environment]] = None,
    context: Optional[List[Condition]] = None,
    subjects_logical_op: Optional[str] = None,
    actions_logical_op: Optional[str] = None,
    conditions_logical_op: Optional[str] = None,
    priority: Optional[int] = None,
) -> Policy:
    """
    Format all components into final Policy object.
    
    Args:
        policy_id: Policy identifier
        sentence: Original sentence
        effect: Policy effect
        modality: Policy modality
        subjects: List of subjects
        actions: List of actions
        resource: Resource
        environments: Optional environments
        conditions: Optional conditions
        subjects_logical_op: Optional AND/OR between subjects
        actions_logical_op: Optional AND/OR between actions
        conditions_logical_op: Optional AND/OR between conditions
        priority: Optional priority
    
    Returns:
        Policy object ready for JSON serialization
    """
    formatter = PolicyFormatter()
    
    # Build ABAC policy summary
    abac_policy = formatter.format_abac_policy(
        effect, subjects, actions, resource, environments, context
    )
    
    # Build relation pairs
    relation_pairs = formatter.build_relation_pairs(subjects, resource, actions)
    
    # Create policy object
    policy = Policy(
        id=policy_id,
        sentence=sentence,
        authorization_decision=effect,
        policy_modality=modality,
        priority=priority,
        subjects=subjects,
        subjects_logical_op=subjects_logical_op,
        actions=actions,
        actions_logical_op=actions_logical_op,
        resource=resource,
        environments=environments or [],
        context=context or [],
        conditions_logical_op=conditions_logical_op,
        relation_pairs=relation_pairs or None,
        abac_policy=abac_policy
    )
    
    return policy


def batch_format_policies(
    sentences: List[str],
    extracted_components: List[Dict[str, Any]],
) -> List[Policy]:
    """
    Format multiple sentences into policies.
    
    Args:
        sentences: List of original sentences
        extracted_components: List of component dictionaries (one per sentence)
            Each should contain: effect, modality, subjects, actions, resource,
            environments, conditions, etc.
    
    Returns:
        List of Policy objects
    """
    policies = []
    
    for policy_id, (sentence, components) in enumerate(zip(sentences, extracted_components), 1):
        policy = format_policy_to_json(
            policy_id=policy_id,
            sentence=sentence,
            **components
        )
        policies.append(policy)
    
    return policies
