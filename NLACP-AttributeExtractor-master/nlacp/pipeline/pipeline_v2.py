"""
ABAC Policy v2.0 Pipeline

Complete end-to-end pipeline for extracting structured ABAC policies from
natural language Access Control Policy sentences.

Usage:
    from nlacp.pipeline.pipeline_v2 import parse_acp_sentence, parse_acp_batch
    
    policy = parse_acp_sentence("Civilian students can view their own scores...")
    print(policy.model_dump_json())
"""

import logging
from typing import List, Optional, Dict, Any, Tuple
import spacy

from nlacp.preprocessing import preprocess_sentence
from nlacp.extraction.effect_detector import detect_effect_and_modality
from nlacp.extraction.subject_extractor import extract_subjects_with_logical_op
from nlacp.extraction.action_extractor import extract_actions_with_logical_op
from nlacp.extraction.resource_extractor import extract_resource
from nlacp.extraction.env_extractor import extract_env_attributes
from nlacp.extraction.condition_extractor import extract_conditions_with_logical_op
from nlacp.normalization.policy_formatter import format_policy_to_json
from nlacp.validation.schema_validator import (
    PolicyValidator, PolicyDataset, Policy,
    PolicyEffect, PolicyModality,
    Environment, EnvironmentSystem, TimeRange, EnvironmentType
)
import re

logger = logging.getLogger(__name__)

nlp = None  # Lazy load

def _get_nlp():
    global nlp
    if nlp is None:
        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            nlp = spacy.blank("en")
    return nlp


class AcpParser:
    """Parser for Access Control Policy sentences."""
    
    def __init__(self, strict_validation: bool = False):
        """
        Initialize parser.
        
        Args:
            strict_validation: If True, raise exception on validation errors
        """
        self.nlp = _get_nlp()
        self.validator = PolicyValidator(strict_mode=strict_validation)
        self.strict_validation = strict_validation
    
    def parse_sentence(self, sentence: str, policy_id: int = 1,
                      preprocess: bool = True) -> Tuple[Optional[Policy], List[str]]:
        """
        Parse single ACP sentence into Policy object.
        
        Args:
            sentence: Natural language policy sentence
            policy_id: Policy ID
            preprocess: Whether to preprocess text first
        
        Returns:
            Tuple of (Policy object, list of warnings)
        """
        warnings = []
        
        try:
            # Step 1: Preprocess
            if preprocess:
                sentence, lang = preprocess_sentence(sentence, expand_abbr=True)
                if lang != "en":
                    warnings.append(f"Non-English text detected: {lang}")
            
            # Parse with spaCy
            doc = self.nlp(sentence)
            
            # Step 2: Detect effect and modality
            effect, modality = detect_effect_and_modality(sentence, doc)
            
            # Step 3: Extract subjects
            subjects, subjects_logical_op = extract_subjects_with_logical_op(sentence, doc)
            if not subjects:
                warnings.append("No subjects detected")
                if self.strict_validation:
                    return None, warnings
            
            # Step 4: Extract actions
            actions, actions_logical_op = extract_actions_with_logical_op(sentence, doc)
            if not actions:
                warnings.append("No actions detected")
                if self.strict_validation:
                    return None, warnings
            
            # Step 5: Extract resource
            resource = extract_resource(sentence, doc)
            if not resource:
                warnings.append("No resource detected")
                if self.strict_validation:
                    return None, warnings
            
            # Step 6: Extract environments
            env_attrs = extract_env_attributes(sentence)
            # Convert env_attrs to Environment objects
            environments = []
            if env_attrs:
                # Map rule-based env_attr dicts into Pydantic Environment models
                def _to_hhmm(x):
                    if not x or not isinstance(x, dict):
                        return None
                    # Case: {'value': 7, 'unit': 'am'}
                    if 'value' in x and 'unit' in x:
                        try:
                            h = int(x['value'])
                        except Exception:
                            return None
                        unit = str(x['unit']).lower()
                        if unit == 'pm' and h != 12:
                            h = (h % 12) + 12
                        if unit == 'am' and h == 12:
                            h = 0
                        return f"{h:02d}:00"
                    # Case: {'text': '7am'} or plain string
                    txt = x.get('text') if isinstance(x, dict) else None
                    if txt and isinstance(txt, str):
                        m = re.match(r"^(\d{1,2})\s*(am|pm)$", txt.strip(), re.I)
                        if m:
                            h = int(m.group(1))
                            unit = m.group(2).lower()
                            if unit == 'pm' and h != 12:
                                h = (h % 12) + 12
                            if unit == 'am' and h == 12:
                                h = 0
                            return f"{h:02d}:00"
                    return None

                for i, env_attr in enumerate(env_attrs, start=1):
                    try:
                        et = env_attr.get('env_type', '')
                        if et == 'temporal':
                            env_type = EnvironmentType.TEMPORAL
                        elif et == 'spatial_network':
                            env_type = EnvironmentType.NETWORK
                        elif et == 'spatial_device':
                            env_type = EnvironmentType.SYSTEM
                        else:
                            env_type = EnvironmentType.LOCATION

                        trigger_word = env_attr.get('trigger')
                        trigger_phrase = env_attr.get('phrase') or env_attr.get('full_value')

                        systems = None
                        if env_type == EnvironmentType.SYSTEM:
                            sys_label = env_attr.get('env_name') or env_attr.get('phrase')
                            if sys_label:
                                systems = [EnvironmentSystem(label=sys_label, namespace=env_attr.get('namespace'))]

                        time_range = None
                        ev = env_attr.get('env_value')
                        if env_type == EnvironmentType.TEMPORAL and isinstance(ev, dict):
                            # Try to convert common parsed forms into HH:MM
                            if ev.get('operator') == 'between' and isinstance(ev.get('from'), dict):
                                f_hh = _to_hhmm(ev.get('from'))
                                t_hh = _to_hhmm(ev.get('to'))
                                if f_hh or t_hh:
                                    time_range = TimeRange(from_time=f_hh, to_time=t_hh)
                            else:
                                # single-bound temporal (at/within/from)
                                v = ev.get('value')
                                if isinstance(v, dict):
                                    f_hh = _to_hhmm(v)
                                    if f_hh:
                                        time_range = TimeRange(from_time=f_hh)

                        env = Environment(
                            id=f"env_{i}",
                            env_type=env_type,
                            trigger_phrase=trigger_phrase,
                            trigger_word=trigger_word,
                            systems=systems,
                            time_range=time_range
                        )
                        environments.append(env)
                    except Exception:
                        # Skip any env entries that fail conversion
                        continue
            
            # Step 7: Extract conditions
            conditions, conditions_logical_op = extract_conditions_with_logical_op(sentence, doc)
            
            # Step 8: Format into Policy object
            policy = format_policy_to_json(
                policy_id=policy_id,
                sentence=sentence,
                effect=effect,
                modality=modality,
                subjects=subjects,
                actions=actions,
                resource=resource,
                environments=environments,
                context=conditions,
                subjects_logical_op=subjects_logical_op,
                actions_logical_op=actions_logical_op,
                conditions_logical_op=conditions_logical_op,
            )
            
            # Step 9: Validate
            is_valid, validation_errors, _ = self.validator.validate_policy(
                policy.dict(exclude_none=True)
            )
            if not is_valid:
                warnings.extend(validation_errors)
                if self.strict_validation:
                    return None, warnings
            
            return policy, warnings
        
        except Exception as e:
            error_msg = f"Error parsing sentence: {str(e)}"
            warnings.append(error_msg)
            logger.error(error_msg, exc_info=True)
            return None, warnings
    
    def parse_batch(self, sentences: List[str], 
                   preprocess: bool = True) -> Tuple[List[Policy], Dict[int, List[str]]]:
        """
        Parse batch of sentences.
        
        Args:
            sentences: List of policy sentences
            preprocess: Whether to preprocess text
        
        Returns:
            Tuple of (policies_list, warnings_dict)
        """
        policies = []
        warnings_dict = {}
        
        for idx, sentence in enumerate(sentences, 1):
            policy, warnings = self.parse_sentence(
                sentence, 
                policy_id=idx,
                preprocess=preprocess
            )
            
            if policy:
                policies.append(policy)
            
            if warnings:
                warnings_dict[idx] = warnings
        
        return policies, warnings_dict
    
    def parse_batch_to_dataset(self, domain: str, sentences: List[str],
                              preprocess: bool = True) -> PolicyDataset:
        """
        Parse batch of sentences into complete dataset.
        
        Args:
            domain: Domain name (e.g., 'university', 'healthcare')
            sentences: List of policy sentences
            preprocess: Whether to preprocess text
        
        Returns:
            PolicyDataset object
        """
        policies, _ = self.parse_batch(sentences, preprocess=preprocess)
        
        dataset = PolicyDataset(
            version="2.0",
            domain=domain,
            policies=policies
        )
        
        return dataset


# Module-level convenience functions

_parser = None


def get_parser(strict_validation: bool = False) -> AcpParser:
    """Get or create parser instance."""
    global _parser
    if _parser is None or _parser.strict_validation != strict_validation:
        _parser = AcpParser(strict_validation=strict_validation)
    return _parser


def parse_acp_sentence(sentence: str, policy_id: int = 1,
                       preprocess: bool = True) -> Optional[Policy]:
    """
    Parse single ACP sentence.
    
    Returns:
        Policy object or None if parsing failed
    """
    parser = get_parser()
    policy, warnings = parser.parse_sentence(sentence, policy_id=policy_id, preprocess=preprocess)
    
    if warnings:
        logger.warning(f"Parsing warnings: {warnings}")
    
    return policy


def parse_acp_batch(domain: str, sentences: List[str],
                   preprocess: bool = True) -> PolicyDataset:
    """
    Parse batch of ACP sentences into dataset.
    
    Returns:
        PolicyDataset object
    """
    parser = get_parser()
    return parser.parse_batch_to_dataset(domain, sentences, preprocess=preprocess)


def parse_acp_json_batch(domain: str, sentences: List[str],
                        preprocess: bool = True) -> str:
    """
    Parse batch of ACP sentences and return JSON string.
    
    Returns:
        JSON string representation of PolicyDataset
    """
    dataset = parse_acp_batch(domain, sentences, preprocess=preprocess)
    return dataset.json(exclude_none=True, indent=2)
