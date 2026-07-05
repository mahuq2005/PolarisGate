"""SHAP-based explainability for toxicity classification.
Uses shared BERT model instance from bert_model_manager to avoid duplicate loading.
"""
import logging
import numpy as np
import shap
from app.bert_model_manager import get_bert_pipeline

logger = logging.getLogger(__name__)

class ShapExplainer:
    def __init__(self, model_name: str = "unitary/toxic-bert"):
        # Use the shared BERT pipeline (top_k=None so SHAP can see both classes)
        self.pipe = get_bert_pipeline(model_name)
        self.explainer = shap.Explainer(self.pipe)
        logger.info("SHAP explainer loaded (using shared BERT model)")

    def explain(self, text: str, top_n: int = 5) -> list[dict]:
        """Return list of {word, score} for the most influential tokens."""
        shap_values = self.explainer([text])
        if not shap_values:
            return []
        # shap_values is a list of Explanation objects
        expl = shap_values[0]
        tokens = expl.data
        # scores shape: (num_tokens, num_classes) – take the toxic class (index 1)
        if expl.values.ndim == 2:
            scores = expl.values[:, 1]   # toxic class
        else:
            scores = expl.values
        results = []
        for tok, score in zip(tokens, scores):
            if tok.strip():
                results.append({"word": tok.strip(), "score": float(score)})
        results.sort(key=lambda x: abs(x["score"]), reverse=True)
        return results[:top_n]
