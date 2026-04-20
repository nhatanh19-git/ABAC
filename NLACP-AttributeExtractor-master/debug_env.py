"""Debug: trace exactly what _detect_trigger_phrases does for 'during the semester'"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from nlacp.utils.nlp_utils import get_spacy_model
from nlacp.extraction import env_extractor as ee

nlp = get_spacy_model()

s = "An instructor updates a gradebook during the semester."
print(f"Input: {s}\n")
doc = nlp(s)

# Monkey-patch to add trace
original_detect = ee._detect_trigger_phrases.__wrapped__ if hasattr(ee._detect_trigger_phrases, '__wrapped__') else None

# Manual trace
subject_tokens = ee._get_subject_tokens(doc)
object_tokens  = ee._get_object_tokens(doc)
print(f"subject_tokens: {subject_tokens}")
print(f"object_tokens:  {object_tokens}")
print()

for token in doc:
    tl = token.text.lower()
    if token.dep_ != "prep":
        continue
    if not ee._is_attached_to_verb(token):
        continue

    print(f"--- Trigger: '{token.text}' ---")
    env_name  = ee._parse_env_name(token)
    env_value = ee._parse_env_value(token)
    print(f"  env_name  = {env_name!r}")
    print(f"  env_value = {env_value}")

    if env_name is None and env_value is None:
        print("  SKIPPED: env_name AND env_value both None")
        continue

    phrase = ee._extract_noun_phrase(token)
    print(f"  phrase    = {phrase!r}")

    if not phrase:
        print("  SKIPPED: empty phrase")
        continue

    phrase_words_list = phrase.lower().split()
    phrase_words_set  = set(phrase_words_list)

    if any(p in phrase_words_list for p in ee.PERSON_NOUNS):
        print("  SKIPPED: PERSON_NOUN in phrase")
        continue
    if phrase_words_set & subject_tokens:
        print(f"  SKIPPED: phrase overlaps subject_tokens ({phrase_words_set & subject_tokens})")
        continue

    ner_type = ee._get_ner_type(doc, phrase)
    print(f"  ner_type  = {ner_type!r}")

    # Temporal check
    is_dur = ee._is_duration_value(env_value)
    if tl in ee.TEMPORAL_PREPS or (tl == "from" and is_dur):
        is_temporal = (ee._has_hint(phrase, ee.TEMPORAL_HINTS) or
                       ee._looks_like_time_value(env_value))
        print(f"  is_temporal = {is_temporal}  (hint={ee._has_hint(phrase, ee.TEMPORAL_HINTS)}, looks_time={ee._looks_like_time_value(env_value)})")
        if is_temporal:
            print(f"  → ACCEPTED as temporal: '{token.text} {phrase}'")
        else:
            print(f"  SKIPPED: not temporal")
