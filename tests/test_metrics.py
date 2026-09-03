# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""GA/PA/FGA/FTA: empty, match, length mismatch."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trailparse.metrics import (  # noqa: E402
    fga,
    fta,
    grouping_accuracy,
    parsing_accuracy,
)


def test_empty_lists_are_zero():
    assert grouping_accuracy([], []) == 0.0
    assert parsing_accuracy([], []) == 0.0
    assert fga([], []) == 0.0
    assert fta([], [], [], []) == 0.0


def test_equal_labels_ga_is_one():
    ids = ["G1", "G1", "G2"]
    assert grouping_accuracy(ids, ids) == 1.0


def test_length_mismatch_raises():
    with pytest.raises(ValueError):
        grouping_accuracy(["a"], ["a", "b"])
    with pytest.raises(ValueError):
        parsing_accuracy(["t"], ["t", "u"])
    with pytest.raises(ValueError):
        fga(["a"], [])
    with pytest.raises(ValueError):
        fta(["a"], ["a"], ["t"], ["t", "u"])
