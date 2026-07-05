"""BERT-based toxicity classifier – fast, accurate, runs on CPU.
Uses shared BERT model instance from bert_model_manager to avoid duplicate loading.
Supports both binary and multi-label model outputs.
"""
import logging
from app.bert_model_manager import get_bert_pipeline

logger = logging.getLogger(__name__)

class BertToxicityClassifier:
    def __init__(self, model_name: str = "unitary/toxic-bert", threshold: float = 0.5):
        self.model_name = model_name
        self.threshold = threshold
        self._pipeline = None

    def load(self):
        """Load or get the shared BERT pipeline."""
        if self._pipeline is None:
            logger.info(f"Getting shared BERT model: {self.model_name}")
            self._pipeline = get_bert_pipeline(self.model_name)
            logger.info(f"BERT toxicity model ready. Threshold={self.threshold}")

    def predict(self, text: str):
        """Classify text for toxicity.

        Args:
            text: Input text to classify

        Returns:
            Dict with:
                - toxic_score: float (0.0 to 1.0)
                - flagged: bool
                - reason: str
                - label_details: dict of per-label scores
            Returns None if model not loaded or error occurs
        """
        if self._pipeline is None:
            return None
        if not text or not text.strip():
            return {"toxic_score": 0.0, "flagged": False, "reason": "empty", "label_details": {}}
        # Skip BERT for very short texts (likely not toxic)
        if len(text.strip()) < 10:
            return {"toxic_score": 0.0, "flagged": False, "reason": "too_short", "label_details": {}}
        try:
            # Pipeline returns list of dicts per input (top_k=None gives all classes)
            results = self._pipeline(text, truncation=True, max_length=512)[0]

            # Extract per-label scores (supports both binary and multi-label models)
            label_details = {}
            toxic_score = 0.0
            for r in results:
                label = r["label"].lower()
                score = r["score"]
                label_details[label] = round(score, 4)
                if label in ("toxic", "toxic", "hate"):  # Covers binary BERT and RoBERTa
                    toxic_score = max(toxic_score, score)

            flagged = toxic_score >= self.threshold
            logger.debug(
                f"BERT: text='{text[:50]}...' "
                f"toxic_score={toxic_score:.3f} flagged={flagged} "
                f"labels={list(label_details.keys())}"
            )
            return {
                "toxic_score": round(toxic_score, 4),
                "flagged": flagged,
                "reason": f"BERT classifier: {'toxic' if flagged else 'not toxic'} (confidence {toxic_score:.2f})",
                "label_details": label_details,
            }
        except Exception as e:
            logger.error(f"BERT classifier error: {e}")
            return None
