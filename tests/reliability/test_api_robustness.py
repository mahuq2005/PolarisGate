"""API robustness validation for PolarisGate.

Validates that labeled datasets are well-formed for production use:
no empty strings, text length within bounds, unique IDs, no binary
content, and all JSONL files parse without errors.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_LABELED_ROOT = _PROJECT_ROOT / "tests" / "test_data" / "labeled"


def _discover_jsonl_files(root: Path) -> List[Path]:
    """Recursively find all JSONL files under `root`."""
    return sorted(root.rglob("*.jsonl"))


def _load_all_rows(root: Path) -> List[Dict[str, Any]]:
    """Load every row from every JSONL file under `root`."""
    rows: List[Dict[str, Any]] = []
    for path in _discover_jsonl_files(root):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


# ---------------------------------------------------------------------------
# Module-level fixtures (computed once)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def all_files() -> List[Path]:
    return _discover_jsonl_files(_LABELED_ROOT)


@pytest.fixture(scope="module")
def all_rows() -> List[Dict[str, Any]]:
    return _load_all_rows(_LABELED_ROOT)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAPIRobustness:
    """Validate data quality for API robustness scenarios."""

    def test_no_empty_text(self, all_rows):
        """No example has an empty or whitespace-only text."""
        for row in all_rows:
            text = row.get("text", "")
            assert text.strip(), f"{row.get('id', '?')}: empty text"

    def test_text_length_bounds(self, all_rows):
        """All texts are between 3 and 10000 characters."""
        for row in all_rows:
            text = row.get("text", "")
            assert len(text) >= 3, f"{row.get('id', '?')}: text too short ({len(text)} chars)"
            assert len(text) <= 10000, f"{row.get('id', '?')}: text too long ({len(text)} chars)"

    def test_ids_are_unique(self, all_rows):
        """No duplicate IDs across the entire labeled dataset."""
        ids: Set[str] = set()
        duplicates: List[str] = []
        for row in all_rows:
            rid = row.get("id", "")
            if rid in ids:
                duplicates.append(rid)
            ids.add(rid)
        assert len(duplicates) == 0, f"Duplicate IDs: {duplicates}"

    def test_all_ids_present(self, all_rows):
        """Every row has a non-empty id."""
        for row in all_rows:
            assert row.get("id"), "Row has no id"

    def test_all_files_parse(self, all_files):
        """Every JSONL file parses without errors."""
        for path in all_files:
            try:
                with open(path, encoding="utf-8") as fh:
                    for i, line in enumerate(fh, 1):
                        line = line.strip()
                        if line:
                            json.loads(line)
            except json.JSONDecodeError as e:
                pytest.fail(f"{path.name}:L{i}: {e}")

    def test_no_binary_content(self, all_rows):
        """No null bytes in any text field."""
        for row in all_rows:
            text = row.get("text", "")
            assert "\x00" not in text, f"{row.get('id', '?')}: contains null byte"

    def test_all_texts_are_strings(self, all_rows):
        """Every text field is a string."""
        for row in all_rows:
            assert isinstance(row.get("text"), str), f"{row.get('id', '?')}: text is {type(row.get('text'))}"

    def test_label_keys_consistent(self, all_rows):
        """Every row has a 'label' dict with expected boolean keys."""
        for row in all_rows:
            label = row.get("label", {})
            assert isinstance(label, dict), f"{row.get('id', '?')}: label not dict"
            # At least one boolean key should be present
            bool_keys = [k for k, v in label.items() if isinstance(v, bool)]
            assert len(bool_keys) >= 1, f"{row.get('id', '?')}: no boolean label keys"

    def test_special_characters_in_adversarial(self, all_files):
        """Adversarial JSONL files contain expected special characters."""
        adv_path = _LABELED_ROOT / "toxicity" / "adversarial_100.jsonl"
        if not adv_path.exists():
            pytest.skip("Adversarial file not found")
        content = adv_path.read_text(encoding="utf-8")
        assert "\u200B" in content, "No zero-width space in adversarial file"

    def test_dataset_count_consistency(self, all_files, all_rows):
        """Total rows across all files is consistent (360 as built)."""
        assert len(all_files) == 17, f"Expected 17 JSONL files, got {len(all_files)}"
        assert len(all_rows) == 360, f"Expected 360 total rows, got {len(all_rows)}"

    def test_edge_cases_have_notes(self, all_rows):
        """Edge-case rows (those with 'note' or 'type' field) are well-formed."""
        edge_rows = [r for r in all_rows if "note" in r or "type" in r]
        assert len(edge_rows) >= 30, f"Expected >=30 annotated rows, got {len(edge_rows)}"

    def test_jsonl_no_trailing_empty_lines(self, all_files):
        """No JSONL file ends with a completely empty line (last line is JSON or file ends clean)."""
        for path in all_files:
            content = path.read_text(encoding="utf-8")
            lines = content.split("\n")
            # The last "line" after split might be empty if file ends with \n
            # That's fine — just verify it's not multiple empty trailing lines
            trailing_empty = 0
            for line in reversed(lines):
                if line.strip() == "":
                    trailing_empty += 1
                else:
                    break
            assert trailing_empty <= 1, f"{path.name}: {trailing_empty} trailing empty lines"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])