"""
nlacp/utils/nlp_utils.py — Centralized factory for loading spaCy models.
"""
import spacy

_nlp_model = None
_model_loaded = False

def get_spacy_model(fallback_to_none=False):
    """
    Tải model spaCy, ưu tiên 'en_core_web_md'. 
    Singleton pattern để tránh load lại nhiều lần tốn memory.
    """
    global _nlp_model, _model_loaded
    if _model_loaded:
        return _nlp_model

    _model_loaded = True

    try:
        _nlp_model = spacy.load("en_core_web_md")
    except OSError:
        try:
            _nlp_model = spacy.load("en_core_web_sm")
        except OSError:
            if fallback_to_none:
                _nlp_model = None
            else:
                raise OSError(
                    "[ERROR] Khong tim thay spaCy model.\n"
                    "Cai bang lenh: python -m spacy download en_core_web_md"
                )
    return _nlp_model
