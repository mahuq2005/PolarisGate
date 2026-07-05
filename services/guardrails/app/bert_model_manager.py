"""Shared BERT/RoBERTa model manager — single instance shared between classifiers and SHAP.

Enterprise-grade: Ensures the model is loaded only once, reducing memory
footprint and startup time. BertToxicityClassifier, RobertaToxicityClassifier,
and ShapExplainer all reference this shared instance.

Supports both binary (toxic/not-toxic) and multi-label (toxic, severe_toxic,
obscene, threat, insult, identity_hate) model outputs.
"""
import logging

logger = logging.getLogger(__name__)

# Module-level singleton — loaded once, shared across all consumers
_model_pipeline = None
_model_name_loaded = None


def get_model_pipeline(model_name: str = "unitary/toxic-bert") -> object:
    """Get or create the shared HuggingFace pipeline singleton.
    
    Args:
        model_name: HuggingFace model identifier (e.g. "unitary/toxic-bert"
                    for binary or "unitary/unbiased-toxic-roberta" for multi-label)
        
    Returns:
        The shared text-classification pipeline
    """
    global _model_pipeline, _model_name_loaded
    
    if _model_pipeline is None or _model_name_loaded != model_name:
        from transformers import pipeline
        logger.info(f"Loading shared model: {model_name}")
        # top_k=None returns all labels (critical for multi-label models like RoBERTa)
        _model_pipeline = pipeline("text-classification", model=model_name, top_k=None)
        _model_name_loaded = model_name
        logger.info(f"Shared model '{model_name}' loaded successfully")
    
    return _model_pipeline


def reload_model_pipeline(model_name: str = "unitary/toxic-bert") -> object:
    """Force reload the pipeline (e.g., after model update).
    
    Args:
        model_name: HuggingFace model identifier
        
    Returns:
        The newly loaded pipeline
    """
    global _model_pipeline, _model_name_loaded
    
    from transformers import pipeline
    logger.info(f"Reloading model: {model_name}")
    _model_pipeline = pipeline("text-classification", model=model_name, top_k=None)
    _model_name_loaded = model_name
    logger.info(f"Model '{model_name}' reloaded successfully")
    return _model_pipeline


def is_model_loaded() -> bool:
    """Check if the model has been loaded."""
    return _model_pipeline is not None


def preload_model_async(model_name: str = "unitary/toxic-bert") -> None:
    """Preload the model in the background to avoid first-request latency.

    This should be called at server startup. The model is loaded in a
    background thread so server startup is not blocked. When the first
    inference request arrives, if the model is still loading, it will
    block until loading completes (which is fine since it's a singleton).

    Args:
        model_name: HuggingFace model identifier to preload
    """
    import threading

    def _load():
        logger.info(f"Background preloading model: {model_name}")
        get_model_pipeline(model_name)
        logger.info(f"Background preload complete: {model_name}")

    thread = threading.Thread(target=_load, daemon=True, name=f"model-preload-{model_name}")
    thread.start()
    logger.info(f"Background preload started for: {model_name}")


# ─── Backward-compatible aliases ────────────────────────────────────────────

def get_bert_pipeline(model_name: str = "unitary/toxic-bert") -> object:
    """Alias for get_model_pipeline — maintained for backward compatibility."""
    return get_model_pipeline(model_name)


def reload_bert_pipeline(model_name: str = "unitary/toxic-bert") -> object:
    """Alias for reload_model_pipeline — maintained for backward compatibility."""
    return reload_model_pipeline(model_name)


def is_bert_loaded() -> bool:
    """Alias for is_model_loaded — maintained for backward compatibility."""
    return is_model_loaded()
