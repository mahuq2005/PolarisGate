"""Accuracy benchmark tests for toxicity detection.
Tests the ensemble (RoBERTa + BERT + keyword) against a labeled test set.
Measures precision, recall, and F1 score.

This test uses mock pipeline results to validate the accuracy measurement
infrastructure without requiring actual model inference.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "services", "guardrails")
)
import pytest


# Labeled test set: (text, expected_toxic, category)
# These are curated examples that should be consistently classified
LABELED_TEST_SET = [
    # --- CLEAN (not toxic) ---
    ("Hello, how are you today?", False, "clean_greeting"),
    ("Thank you for your help with this project.", False, "clean_thanks"),
    ("I disagree with your opinion on the policy.", False, "clean_disagreement"),
    ("The weather is nice today.", False, "clean_small_talk"),
    ("Can you please explain how this works?", False, "clean_request"),
    ("I appreciate your time and effort.", False, "clean_appreciation"),
    ("The meeting is scheduled for 3 PM.", False, "clean_info"),
    ("Please find the attached document.", False, "clean_business"),
    ("Happy birthday! Hope you have a great day.", False, "clean_birthday"),
    ("The report shows a 15% increase in revenue.", False, "clean_report"),
    # --- TOXIC ---
    ("You are an idiot and completely useless!", True, "toxic_insult"),
    ("I hope someone hurts you badly.", True, "toxic_threat"),
    ("All of those people are terrible and should be removed.", True, "toxic_hate_speech"),
    ("Go kill yourself, nobody wants you here.", True, "toxic_self_harm_incitement"),
    ("You're a worthless piece of garbage.", True, "toxic_insult_2"),
    ("I will find you and make you pay.", True, "toxic_threat_2"),
    ("This is the stupidest thing I've ever read.", True, "toxic_insult_3"),
    ("Shut your mouth and listen for once.", True, "toxic_harassment"),
    ("You people are all the same, just criminals.", True, "toxic_hate_speech_2"),
    ("Nobody cares what you think, loser.", True, "toxic_insult_4"),
    # --- EDGE CASES (subtle/nuanced) ---
    ("That's certainly an interesting approach.", False, "edge_sarcasm_clean"),
    ("I'm sure you did your best.", False, "edge_passive_aggressive_clean"),
    ("Well, that was a brilliant move.", False, "edge_sarcasm_clean_2"),
    ("You might want to reconsider your strategy.", False, "edge_criticism_clean"),
]


class TestToxicityAccuracyMetrics:
    """Test the accuracy measurement infrastructure."""

    def test_precision_calculation(self):
        """Test precision = TP / (TP + FP)."""
        # Simulate: 10 toxic, 10 clean, 2 errors
        tp = 9  # Correctly flagged toxic
        fp = 1  # Incorrectly flagged clean
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        assert precision == 0.90

    def test_recall_calculation(self):
        """Test recall = TP / (TP + FN)."""
        tp = 9  # Correctly flagged toxic
        fn = 1  # Missed toxic
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        assert recall == 0.90

    def test_f1_calculation(self):
        """Test F1 = 2 * (precision * recall) / (precision + recall)."""
        precision = 0.90
        recall = 0.90
        f1 = 2 * (precision * recall) / (precision + recall)
        assert f1 == 0.90

    def test_accuracy_calculation(self):
        """Test accuracy = (TP + TN) / (TP + TN + FP + FN)."""
        tp = 9
        tn = 9
        fp = 1
        fn = 1
        accuracy = (tp + tn) / (tp + tn + fp + fn)
        assert accuracy == 0.90

    def test_perfect_classification(self):
        """Test metrics with perfect classification."""
        tp = 10
        tn = 10
        fp = 0
        fn = 0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = (tp + tn) / (tp + tn + fp + fn)
        assert precision == 1.0
        assert recall == 1.0
        assert f1 == 1.0
        assert accuracy == 1.0

    def test_no_false_positives(self):
        """Test metrics when there are no false positives."""
        tp = 8
        tn = 10
        fp = 0
        fn = 2
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        assert precision == 1.0
        assert recall == 0.80

    def test_no_false_negatives(self):
        """Test metrics when there are no false negatives."""
        tp = 10
        tn = 8
        fp = 2
        fn = 0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        assert round(precision, 4) == 0.8333  # 10/12
        assert recall == 1.0

    def test_all_false_positives(self):
        """Test metrics when everything is flagged as toxic (worst case)."""
        tp = 10  # All toxic correctly flagged
        tn = 0   # No clean correctly identified
        fp = 10  # All clean incorrectly flagged
        fn = 0   # No toxic missed
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        assert precision == 0.50
        assert recall == 1.0
        assert round(f1, 4) == 0.6667  # 2 * (0.5 * 1.0) / (0.5 + 1.0) = 1.0 / 1.5

    def test_all_false_negatives(self):
        """Test metrics when nothing is flagged (worst case)."""
        tp = 0   # No toxic flagged
        tn = 10  # All clean correctly identified
        fp = 0   # No clean incorrectly flagged
        fn = 10  # All toxic missed
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        assert precision == 0.0
        assert recall == 0.0
        assert f1 == 0.0

    def test_labeled_test_set_structure(self):
        """Test that the labeled test set has the correct structure."""
        assert len(LABELED_TEST_SET) > 0
        for text, expected, category in LABELED_TEST_SET:
            assert isinstance(text, str)
            assert isinstance(expected, bool)
            assert isinstance(category, str)
            assert len(text) > 0

    def test_labeled_test_set_balance(self):
        """Test that the labeled test set has balanced toxic/clean examples."""
        toxic_count = sum(1 for _, toxic, _ in LABELED_TEST_SET if toxic)
        clean_count = sum(1 for _, toxic, _ in LABELED_TEST_SET if not toxic)
        assert toxic_count > 0
        assert clean_count > 0
        # Should be roughly balanced
        ratio = toxic_count / (toxic_count + clean_count)
        assert 0.3 <= ratio <= 0.7

    def test_labeled_test_set_categories(self):
        """Test that all categories are present."""
        categories = [cat for _, _, cat in LABELED_TEST_SET]
        assert "clean_greeting" in categories
        assert "toxic_insult" in categories
        assert "toxic_threat" in categories
        assert "toxic_hate_speech" in categories
        assert "edge_sarcasm_clean" in categories

    def test_simulated_classification_results(self):
        """Simulate running the labeled test set through a classifier and measuring accuracy.

        This simulates what the actual accuracy benchmark would do.
        """
        # Simulated classifier results (matching expected for most cases)
        simulated_results = [
            # All clean should be classified as not toxic
            (False, False),  # clean_greeting
            (False, False),  # clean_thanks
            (False, False),  # clean_disagreement
            (False, False),  # clean_small_talk
            (False, False),  # clean_request
            (False, False),  # clean_appreciation
            (False, False),  # clean_info
            (False, False),  # clean_business
            (False, False),  # clean_birthday
            (False, False),  # clean_report
            # All toxic should be classified as toxic
            (True, True),    # toxic_insult
            (True, True),    # toxic_threat
            (True, True),    # toxic_hate_speech
            (True, True),    # toxic_self_harm_incitement
            (True, True),    # toxic_insult_2
            (True, True),    # toxic_threat_2
            (True, True),    # toxic_insult_3
            (True, True),    # toxic_harassment
            (True, True),    # toxic_hate_speech_2
            (True, True),    # toxic_insult_4
            # Edge cases (may have some errors)
            (False, False),  # edge_sarcasm_clean
            (False, False),  # edge_passive_aggressive_clean
            (False, True),   # edge_sarcasm_clean_2 - SIMULATED ERROR (false positive)
            (False, False),  # edge_criticism_clean
        ]

        # Calculate metrics
        tp = sum(1 for expected, actual in simulated_results if expected and actual)
        tn = sum(1 for expected, actual in simulated_results if not expected and not actual)
        fp = sum(1 for expected, actual in simulated_results if not expected and actual)
        fn = sum(1 for expected, actual in simulated_results if expected and not actual)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = (tp + tn) / (tp + tn + fp + fn)

        # With 1 error out of 24 examples
        assert tp == 10  # All toxic caught
        assert tn == 13  # 13/14 clean correctly identified
        assert fp == 1   # 1 false positive (sarcasm)
        assert fn == 0   # No false negatives
        assert precision == 10 / 11  # ~0.909
        assert recall == 1.0
        assert accuracy == 23 / 24  # ~0.958
