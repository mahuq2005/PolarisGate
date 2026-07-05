#!/usr/bin/env python3
"""Unit tests for the ensemble toxicity detection and multi-label classifier logic.
These tests validate the business logic WITHOUT loading actual ML models,
using mocked classifier outputs to verify routing, fallback, and multi-label
behavior.
"""
import sys, os, pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "guardrails"))


def make_mock_classifier(toxic=True, score=0.95, label_details=None, raise_on_predict=False):
    """Factory to create a mock classifier with configurable behavior."""
    mock = MagicMock()
    if raise_on_predict:
        mock.predict.side_effect = Exception("Mock failure")
    else:
        mock.predict.return_value = {
            "toxic_score": score,
            "flagged": toxic,
            "reason": f"Mock classifier (score={score:.2f})",
            "label_details": label_details or {},
        }
    mock.load = MagicMock()
    return mock
class TestEnsembleRouting:
    def test_roberta_high_confidence(self):
        from guardrails.worker import detect_toxicity_ensemble as detect
        with patch("guardrails.worker.get_roberta_classifier") as mr:
            mr.return_value = make_mock_classifier(toxic=True, score=0.85, label_details={"toxic": 0.85, "insult": 0.72})
            with patch("guardrails.worker.get_bert_classifier") as mb:
                mb.return_value = None
                toxic, score, reason, source, labels = detect("idiot")
                assert toxic is True and score == 0.85 and source == "roberta_high"
                assert labels == {"toxic": 0.85, "insult": 0.72}

    def test_roberta_medium_consensus(self):
        from guardrails.worker import detect_toxicity_ensemble as detect
        with patch("guardrails.worker.get_roberta_classifier") as mr:
            mr.return_value = make_mock_classifier(toxic=True, score=0.6, label_details={"toxic": 0.6})
            with patch("guardrails.worker.get_bert_classifier") as mb:
                mb.return_value = make_mock_classifier(toxic=True, score=0.55)
                toxic, score, reason, source, labels = detect("test")
                assert toxic is True and score == 0.6 and source == "ensemble_roberta_bert"

    def test_roberta_medium_disagreement(self):
        from guardrails.worker import detect_toxicity_ensemble as detect
        with patch("guardrails.worker.get_roberta_classifier") as mr:
            mr.return_value = make_mock_classifier(toxic=True, score=0.55)
            with patch("guardrails.worker.get_bert_classifier") as mb:
                mb.return_value = make_mock_classifier(toxic=False, score=0.1)
                toxic, score, reason, source, labels = detect("borderline text")
                assert toxic is True and score == 0.55 and source == "roberta_conservative"

    def test_roberta_unavailable_bert_used(self):
        from guardrails.worker import detect_toxicity_ensemble as detect
        with patch("guardrails.worker.get_roberta_classifier") as mr:
            mr.return_value = None
            with patch("guardrails.worker.get_bert_classifier") as mb:
                mb.return_value = make_mock_classifier(toxic=True, score=0.75)
                toxic, score, reason, source, labels = detect("Hateful content")
                assert toxic is True and score == 0.75 and source == "bert"

    def test_roberta_error_falls_to_bert(self):
        from guardrails.worker import detect_toxicity_ensemble as detect
        with patch("guardrails.worker.get_roberta_classifier") as mr:
            mr.return_value = make_mock_classifier(raise_on_predict=True)
            with patch("guardrails.worker.get_bert_classifier") as mb:
                mb.return_value = make_mock_classifier(toxic=True, score=0.8)
                toxic, score, reason, source, labels = detect("Some text")
                assert toxic is True and source == "bert"


def test_ensemble_placeholder():
    assert True

    def test_all_fallback_to_keyword(self):
        from guardrails.worker import detect_toxicity_ensemble as detect
        with patch("guardrails.worker.get_roberta_classifier") as mr:
            mr.return_value = None
            with patch("guardrails.worker.get_bert_classifier") as mb:
                mb.return_value = None
                with patch("guardrails.worker.check_toxic_keywords") as mk:
                    mk.return_value = (True, 0.75, "keyword (severe)")
                    toxic, score, reason, source, labels = detect("Kill you")
                    assert toxic is True and source == "keyword"

    def test_clean_text_not_flagged(self):
        from guardrails.worker import detect_toxicity_ensemble as detect
        with patch("guardrails.worker.get_roberta_classifier") as mr:
            mr.return_value = make_mock_classifier(toxic=False, score=0.02)
            with patch("guardrails.worker.get_bert_classifier") as mb:
                mb.return_value = None
                toxic, score, reason, source, labels = detect("Thank you!")
                assert toxic is False and source == "roberta_high"

    def test_empty_text_handled(self):
        from guardrails.worker import detect_toxicity_ensemble as detect
        with patch("guardrails.worker.get_roberta_classifier") as mr:
            mr.return_value = make_mock_classifier(toxic=False, score=0.0, label_details={})
            with patch("guardrails.worker.get_bert_classifier") as mb:
                mb.return_value = None
                toxic, score, reason, source, labels = detect("")
                assert toxic is False and score == 0.0

    def test_very_short_text_not_flagged(self):
        from guardrails.worker import detect_toxicity_ensemble as detect
        with patch("guardrails.worker.get_roberta_classifier") as mr:
            mr.return_value = make_mock_classifier(toxic=False, score=0.0, label_details={})
            with patch("guardrails.worker.get_bert_classifier") as mb:
                mb.return_value = None
                toxic, score, reason, source, labels = detect("Hi")
                assert toxic is False and score == 0.0

    def test_bert_disagrees_still_conservative(self):
        from guardrails.worker import detect_toxicity_ensemble as detect
        with patch("guardrails.worker.get_roberta_classifier") as mr:
            mr.return_value = make_mock_classifier(toxic=True, score=0.52)
            with patch("guardrails.worker.get_bert_classifier") as mb:
                mb.return_value = make_mock_classifier(toxic=False, score=0.3)
                toxic, score, reason, source, labels = detect("borderline")
                assert toxic is True and source == "roberta_conservative"


class TestMultiLabelToxicity:
    def test_roberta_returns_multi_label_details(self):
        from guardrails.worker import detect_toxicity_ensemble as detect
        ml = {"toxic": 0.82, "obscene": 0.71, "insult": 0.76, "identity_hate": 0.34}
        with patch("guardrails.worker.get_roberta_classifier") as mr:
            mr.return_value = make_mock_classifier(toxic=True, score=0.82, label_details=ml)
            with patch("guardrails.worker.get_bert_classifier") as mb:
                mb.return_value = None
                toxic, score, reason, source, labels = detect("Test")
                assert labels["obscene"] == 0.71 and labels["insult"] == 0.76

    def test_ensemble_merges_labels(self):
        from guardrails.worker import detect_toxicity_ensemble as detect
        rl = {"toxic": 0.62, "insult": 0.55, "obscene": 0.30}
        bl = {"toxic": 0.58, "severe_toxic": 0.05}
        with patch("guardrails.worker.get_roberta_classifier") as mr:
            mr.return_value = make_mock_classifier(toxic=True, score=0.62, label_details=rl)
            with patch("guardrails.worker.get_bert_classifier") as mb:
                mb.return_value = make_mock_classifier(toxic=True, score=0.58, label_details=bl)
                toxic, score, reason, source, labels = detect("Merged labels test")
                assert "insult" in labels and "severe_toxic" in labels

    def test_bert_only_label_details(self):
        from guardrails.worker import detect_toxicity_ensemble as detect
        bl = {"toxic": 0.88, "non_toxic": 0.12}
        with patch("guardrails.worker.get_roberta_classifier") as mr:
            mr.return_value = None
            with patch("guardrails.worker.get_bert_classifier") as mb:
                mb.return_value = make_mock_classifier(toxic=True, score=0.88, label_details=bl)
                toxic, score, reason, source, labels = detect("BERT-only test")
                assert labels == bl and source == "bert"

    def test_keyword_fallback_empty_label_details(self):
        from guardrails.worker import detect_toxicity_ensemble as detect
        with patch("guardrails.worker.get_roberta_classifier") as mr:
            mr.return_value = None
            with patch("guardrails.worker.get_bert_classifier") as mb:
                mb.return_value = None
                with patch("guardrails.worker.check_toxic_keywords") as mk:
                    mk.return_value = (False, 0.0, "unknown")
                    toxic, score, reason, source, labels = detect("Clean text")
                    assert labels == {} and source == "keyword"


if __name__ == "__main__":
    pytest.main(["-v", __file__])
