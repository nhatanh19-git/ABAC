"""
Analyze environment extraction - find sentences being skipped.
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import json
from nlacp.extraction import env_extractor as ee
from nlacp.utils.nlp_utils import get_spacy_model

nlp = get_spacy_model()

with open('outputs/policies/policy_dataset.json', encoding='utf-8') as f:
    data = json.load(f)
policies = data if isinstance(data, list) else data.get('policies', [])

# Tìm câu có preposition nhưng không có environment
print("=== Câu có prep gắn với VERB nhưng KHÔNG có environment ===\n")

for p in policies:
    env = p.get('environment', [])
    if env:
        continue
    s = p['sentence']
    doc = nlp(s)
    
    # Kiểm tra có prep gắn verb không
    for tok in doc:
        if tok.dep_ == 'prep' and ee._is_attached_to_verb(tok):
            # Có prep nhưng không bắt được env
            phrase = ee._extract_noun_phrase(tok)
            env_name = ee._parse_env_name(tok)
            env_value = ee._parse_env_value(tok)
            subject_tokens = ee._get_subject_tokens(doc)
            
            phrase_words = set(phrase.lower().split()) if phrase else set()
            
            # Xác định tại sao bị skip
            reason = "unknown"
            pobj_text = None
            for child in tok.children:
                if child.dep_ in ("pobj", "pcomp"):
                    pobj_text = child.text.lower()
                    break
            
            if pobj_text and pobj_text in subject_tokens:
                reason = "POBJ in subject"
            elif phrase and any(p2 in phrase.lower().split() for p2 in ee.PERSON_NOUNS):
                reason = "PERSON_NOUN"
            elif env_name is None and env_value is None:
                reason = "env_name AND env_value both None"
            elif not phrase:
                reason = "empty phrase"
            elif tok.text.lower() not in ee.SPATIAL_PREPS and tok.text.lower() not in ee.TEMPORAL_PREPS:
                reason = f"prep '{tok.text}' not in SPATIAL/TEMPORAL PREPS"
            elif tok.text.lower() in ee.SPATIAL_PREPS:
                has_hint = ee._has_hint(phrase, ee.SPATIAL_HINTS)
                ner_type = ee._get_ner_type(doc, phrase)
                is_loc = ner_type in ("GPE", "LOC", "FAC", "ORG")
                if not has_hint and not is_loc:
                    reason = f"SPATIAL but no hint & no NER | phrase='{phrase}' | ner='{ner_type}'"
            elif tok.text.lower() in ee.TEMPORAL_PREPS:
                is_temp = ee._has_hint(phrase, ee.TEMPORAL_HINTS) or ee._looks_like_time_value(env_value)
                if not is_temp:
                    reason = f"TEMPORAL but no hint | phrase='{phrase}'"
            
            print(f"[{p['id']}] {s}")
            print(f"  prep='{tok.text}' | phrase='{phrase}' | reason='{reason}'")
            print()
            break  # chỉ lấy prep đầu tiên bị miss
