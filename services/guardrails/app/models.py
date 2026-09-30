"""Lazy model loading (Gap 17 extraction).

Extracted from ``worker.py``: the BERT / RoBERTa / SHAP loaders live here so the
worker no longer mixes HTTP + ML + policy + cache + model lifecycle.
"""

from __future__ import annotations

import logging

from app.classifiers.bert_toxic import BertToxicityClassifier
from app.classifiers.roberta_toxic import RobertaToxicityClassifier
from app.shap_explainer import ShapExplainer

logger = logging.getLogger("guardrails")


class ModelLoader:
    """Lazily loads and caches ML models; supports forced reload."""

    def __init__(self, enable_bert: bool = False, enable_roberta: bool = False):
        self._enable_bert = enable_bert
        self._enable_roberta = enable_roberta
        self._bert = None
        self._roberta = None
        self._shap = None

    def get_bert(self):
        """Lazy-load BERT classifier on first use."""
        if self._bert is None and self._enable_bert:
            try:
                self._bert = BertToxicityClassifier(threshold=0.5)
                self._bert.load()
                logger.info("BERT classifier loaded lazily")
            except Exception as e:
                logger.warning(f"BERT load failed, disabling: {e}")
                self._bert = None
        return self._bert

    def get_roberta(self):
        """Lazy-load RoBERTa classifier on first use."""
        if self._roberta is None and self._enable_roberta:
            try:
                self._roberta = RobertaToxicityClassifier(threshold=0.5)
                self._roberta.load()
                logger.info("RoBERTa classifier loaded lazily")
            except Exception as e:
                logger.warning(f"RoBERTa load failed, disabling: {e}")
                self._roberta = None
        return self._roberta

    def get_shap(self):
        """Lazy-load SHAP explainer on first use."""
        if self._shap is None and self._enable_bert:
            try:
                self._shap = ShapExplainer()
                logger.info("SHAP explainer loaded lazily")
            except Exception as e:
                logger.warning(f"SHAP explainer load failed, disabling: {e}")
                self._shap = None
        return self._shap

    def reload_bert(self):
        self._bert = None
        return self.get_bert()

    def reload_roberta(self):
        self._roberta = None
        return self.get_roberta()
