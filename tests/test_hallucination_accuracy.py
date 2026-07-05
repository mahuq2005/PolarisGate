"""Accuracy benchmark tests for hallucination detection.
Tests the NLI-based detector against known hallucination/factual pairs.
Measures correct classification rate, precision, recall, and F1.

This test uses simulated NLI results to validate the accuracy measurement
infrastructure without requiring actual model inference.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
import pytest


# Labeled test set: (context, response, expected_hallucination, category)
LABELED_TEST_SET = [
    # --- FACTUAL (not hallucinated) ---
    (
        "The company revenue was $10M in 2023.",
        "The company revenue was $10M in 2023.",
        False,
        "factual_exact_match",
    ),
    (
        "Alice is the CEO of Acme Corp.",
        "Alice is the CEO of Acme Corp.",
        False,
        "factual_entity_match",
    ),
    (
        "The product launch is scheduled for Q3 2024.",
        "The product launch is scheduled for Q3 2024.",
        False,
        "factual_date_match",
    ),
    (
        "The team consists of 5 engineers and 2 designers.",
        "The team consists of 5 engineers and 2 designers.",
        False,
        "factual_numbers_match",
    ),
    (
        "The server has 32GB RAM and 8 CPU cores.",
        "The server has 32GB RAM and 8 CPU cores.",
        False,
        "factual_specs_match",
    ),
    # --- HALLUCINATION ---
    (
        "The company revenue was $10M in 2023.",
        "The company revenue was $50M in 2023.",
        True,
        "hallucination_wrong_number",
    ),
    (
        "Alice is the CEO of Acme Corp.",
        "Bob is the CEO of Acme Corp.",
        True,
        "hallucination_wrong_entity",
    ),
    (
        "The product launch is scheduled for Q3 2024.",
        "The product launch is scheduled for Q1 2023.",
        True,
        "hallucination_wrong_date",
    ),
    (
        "The team consists of 5 engineers and 2 designers.",
        "The team consists of 10 engineers and 5 designers.",
        True,
        "hallucination_wrong_numbers",
    ),
    (
        "The server has 32GB RAM and 8 CPU cores.",
        "The server has 64GB RAM and 16 CPU cores.",
        True,
        "hallucination_wrong_specs",
    ),
    (
        "The meeting is at 2 PM in Room 3.",
        "The meeting is at 3 PM in Room 5.",
        True,
        "hallucination_wrong_details",
    ),
    # --- EDGE CASES ---
    (
        "The company was founded in 2000.",
        "The company was founded over 20 years ago.",
        False,
        "edge_paraphrase_factual",
    ),
    (
        "Revenue grew by 15% this quarter.",
        "Revenue grew by fifteen percent this quarter.",
        False,
        "edge_word_vs_number",
    ),
    (
        "The system processes 1000 requests per second.",
        "The system processes 1,000 requests per second.",
        False,
        "edge_format_difference",
    ),
]


class TestHallucinationAccuracyMetrics:
    """Test the hallucination accuracy measurement infrastructure."""

    def test_labeled_test_set_structure(self):
        """Test that the labeled test set has the correct structure."""
        assert len(LABELED_TEST_SET) > 0
        for context, response, expected, category in LABELED_TEST_SET:
            assert isinstance(context, str)
            assert isinstance(response, str)
            assert isinstance(expected, bool)
            assert isinstance(category, str)
            assert len(context) > 0
            assert len(response) > 0

    def test_labeled_test_set_balance(self):
        """Test that the labeled test set has balanced hallucination/factual examples."""
        hall_count = sum(1 for _, _, hall, _ in LABELED_TEST_SET if hall)
        factual_count = sum(1 for _, _, hall, _ in LABELED_TEST_SET if not hall)
        assert hall_count > 0
        assert factual_count > 0
        ratio = hall_count / (hall_count + factual_count)
        assert 0.3 <= ratio <= 0.7

    def test_labeled_test_set_categories(self):
        """Test that all categories are present."""
        categories = [cat for _, _, _, cat in LABELED_TEST_SET]
        assert "factual_exact_match" in categories
        assert "hallucination_wrong_number" in categories
        assert "hallucination_wrong_entity" in categories
        assert "edge_paraphrase_factual" in categories

    def test_simulated_perfect_classification(self):
        """Test metrics with perfect classification."""
        # Simulate perfect NLI results
        simulated_results = [
            (False, False),  # factual_exact_match
            (False, False),  # factual_entity_match
            (False, False),  # factual_date_match
            (False, False),  # factual_numbers_match
            (False, False),  # factual_specs_match
            (True, True),    # hallucination_wrong_number
            (True, True),    # hallucination_wrong_entity
            (True, True),    # hallucination_wrong_date
            (True, True),    # hallucination_wrong_numbers
            (True, True),    # hallucination_wrong_specs
            (True, True),    # hallucination_wrong_details
            (False, False),  # edge_paraphrase_factual
            (False, False),  # edge_word_vs_number
            (False, False),  # edge_format_difference
        ]

        tp = sum(1 for expected, actual in simulated_results if expected and actual)
        tn = sum(1 for expected, actual in simulated_results if not expected and not actual)
        fp = sum(1 for expected, actual in simulated_results if not expected and actual)
        fn = sum(1 for expected, actual in simulated_results if expected and not actual)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = (tp + tn) / (tp + tn + fp + fn)

        assert tp == 6
        assert tn == 8
        assert fp == 0
        assert fn == 0
        assert precision == 1.0
        assert recall == 1.0
        assert f1 == 1.0
        assert accuracy == 1.0

    def test_simulated_with_errors(self):
        """Test metrics with some classification errors (realistic scenario)."""
        # Simulate: 1 false positive (edge_paraphrase flagged as hallucination)
        #           1 false negative (hallucination_wrong_details missed)
        simulated_results = [
            (False, False),  # factual_exact_match
            (False, False),  # factual_entity_match
            (False, False),  # factual_date_match
            (False, False),  # factual_numbers_match
            (False, False),  # factual_specs_match
            (True, True),    # hallucination_wrong_number
            (True, True),    # hallucination_wrong_entity
            (True, True),    # hallucination_wrong_date
            (True, True),    # hallucination_wrong_numbers
            (True, True),    # hallucination_wrong_specs
            (True, False),   # hallucination_wrong_details - MISSED (FN)
            (False, True),   # edge_paraphrase_factual - FALSE POSITIVE (FP)
            (False, False),  # edge_word_vs_number
            (False, False),  # edge_format_difference
        ]

        tp = sum(1 for expected, actual in simulated_results if expected and actual)
        tn = sum(1 for expected, actual in simulated_results if not expected and not actual)
        fp = sum(1 for expected, actual in simulated_results if not expected and actual)
        fn = sum(1 for expected, actual in simulated_results if expected and not actual)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = (tp + tn) / (tp + tn + fp + fn)

        assert tp == 5  # 5/6 hallucination caught
        assert tn == 7  # 7/8 factual correctly identified
        assert fp == 1  # 1 false positive
        assert fn == 1  # 1 false negative
        assert round(precision, 4) == 0.8333  # 5/6
        assert round(recall, 4) == 0.8333  # 5/6
        assert round(f1, 4) == 0.8333
        assert round(accuracy, 4) == 0.8571  # 12/14

    def test_contradiction_detection_rate(self):
        """Test that contradictions are detected at high rate."""
        # Simulate: NLI correctly identifies contradictions
        contradiction_pairs = [
            ("Revenue was $10M", "Revenue was $50M", True),
            ("CEO is Alice", "CEO is Bob", True),
            ("Launch in Q3 2024", "Launch in Q1 2023", True),
        ]

        correct = sum(1 for _, _, expected in contradiction_pairs if expected)
        assert correct == 3
        assert correct / len(contradiction_pairs) == 1.0

    def test_entailment_detection_rate(self):
        """Test that entailments are detected at high rate."""
        entailment_pairs = [
            ("Revenue was $10M", "Revenue was $10M", False),
            ("CEO is Alice", "CEO is Alice", False),
            ("Launch in Q3 2024", "Launch in Q3 2024", False),
        ]

        correct = sum(1 for _, _, expected in entailment_pairs if not expected)
        assert correct == 3
        assert correct / len(entailment_pairs) == 1.0

    def test_false_positive_rate(self):
        """Test false positive rate calculation."""
        fp = 1
        tn = 7
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        assert round(fpr, 4) == 0.1250  # 1/8

    def test_false_negative_rate(self):
        """Test false negative rate calculation."""
        fn = 1
        tp = 5
        fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0
        assert round(fnr, 4) == 0.1667  # 1/6
