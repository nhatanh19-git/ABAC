"""
Preprocessing module for ABAC Policy v2.0

This module handles text preprocessing: normalization, language detection, coreference resolution.
"""

import re
import spacy
from typing import Optional, List, Tuple

try:
    from langdetect import detect, LangDetectException
except ImportError:
    # Fallback if langdetect not available
    def detect(text):
        return "en"

nlp = None  # Lazy load

def _get_nlp():
    global nlp
    if nlp is None:
        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            nlp = spacy.blank("en")
    return nlp
    class LangDetectException(Exception):
        pass

# Common abbreviations in policy text
ABBREVIATION_MAPPING = {
    "ais": "academic information system",
    "lms": "learning management system",
    "vlms": "visiting lecturer management system",
    "crs": "course registration system",
    "vl": "visiting lecturer",
    "hh": "hour",
    "hh:mm": "time",
}

# Text normalization rules
NORMALIZATION_RULES = [
    (r'\s+', ' '),  # Multiple spaces → single space
    (r'\n', ' '),  # Newlines → space
    (r'\t', ' '),  # Tabs → space
    (r'["""]', '"'),  # Smart quotes → regular quotes
    (r'["\']{2,}', '"'),  # Multiple quotes → single
]


class Preprocessor:
    """Text preprocessor for policy sentences."""
    
    def __init__(self, language: str = "en"):
        """
        Initialize preprocessor.
        
        Args:
            language: Language code (default: 'en' for English)
        """
        self.language = language
        self.nlp = _get_nlp()
    
    def normalize_text(self, text: str) -> str:
        """
        Normalize text: remove extra whitespace, standardize quotes, etc.
        
        Args:
            text: Input text
        
        Returns:
            Normalized text
        """
        result = text
        
        for pattern, replacement in NORMALIZATION_RULES:
            result = re.sub(pattern, replacement, result)
        
        return result.strip()
    
    def expand_abbreviations(self, text: str) -> str:
        """
        Expand common abbreviations used in policy text.
        
        Args:
            text: Input text
        
        Returns:
            Text with abbreviations expanded
        """
        result = text
        
        for abbr, expansion in ABBREVIATION_MAPPING.items():
            # Match whole words with word boundaries
            pattern = r'\b' + re.escape(abbr) + r'\b'
            result = re.sub(pattern, expansion, result, flags=re.IGNORECASE)
        
        return result
    
    def detect_language(self, text: str) -> str:
        """
        Detect language of text.
        
        Args:
            text: Input text
        
        Returns:
            Language code (e.g., 'en', 'vi')
        """
        try:
            lang = detect(text)
            return lang
        except LangDetectException:
            return "en"  # default to English
    
    def tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into sentences.
        
        Args:
            text: Input text
        
        Returns:
            List of sentences
        """
        # Simple sentence splitting on periods/newlines
        # For full tokenization, use spaCy externally
        sentences = text.replace('\n', '.').split('.')
        sentences = [s.strip() for s in sentences if s.strip()]
        return sentences
    
    def resolve_coreference(self, text: str) -> str:
        """
        Attempt basic coreference resolution (pronouns → entities).
        
        For now, a simple heuristic-based approach. In production, use neuralcoref or similar.
        
        Args:
            text: Input text
        
        Returns:
            Text with pronoun references resolved
        """
        # This is a placeholder. Full coreference resolution requires more sophisticated NLP.
        # For now, we just return the text as-is, flagging it for manual review if needed.
        
        pronouns = ["he", "she", "it", "they", "them", "his", "her", "their"]
        text_lower = text.lower()
        
        has_pronoun = any(f" {p} " in f" {text_lower} " for p in pronouns)
        
        if has_pronoun:
            # Log a note about potential coreference issues
            # In a full system, trigger coreference resolution here
            pass
        
        return text
    
    def preprocess(self, text: str, expand_abbr: bool = True, 
                  resolve_coref: bool = False) -> Tuple[str, str]:
        """
        Full preprocessing pipeline.
        
        Args:
            text: Input text
            expand_abbr: Whether to expand abbreviations
            resolve_coref: Whether to attempt coreference resolution
        
        Returns:
            Tuple of (processed_text, language)
        """
        # Normalize
        text = self.normalize_text(text)
        
        # Detect language
        lang = self.detect_language(text)
        self.language = lang
        
        # Expand abbreviations if requested
        if expand_abbr:
            text = self.expand_abbreviations(text)
        
        # Resolve coreference if requested
        if resolve_coref:
            text = self.resolve_coreference(text)
        
        return text, lang


# Singleton instance
_preprocessor = None


def get_preprocessor(language: str = "en") -> Preprocessor:
    """Get or create preprocessor instance."""
    global _preprocessor
    if _preprocessor is None:
        _preprocessor = Preprocessor(language=language)
    return _preprocessor


def preprocess_sentence(sentence: str, expand_abbr: bool = True) -> Tuple[str, str]:
    """
    Convenience function to preprocess a single sentence.
    
    Returns:
        Tuple of (processed_sentence, language)
    """
    preprocessor = get_preprocessor()
    return preprocessor.preprocess(sentence, expand_abbr=expand_abbr, resolve_coref=False)
