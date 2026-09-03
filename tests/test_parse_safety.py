# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""Protect committed public examples from accidental real-log output."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.parse import validate_output_paths  # noqa: E402


def test_real_logs_cannot_overwrite_public_examples(tmp_path):
    with pytest.raises(ValueError, match="committed public example"):
        validate_output_paths(
            tmp_path / "private.log",
            ROOT / "results" / "parsed_sample.csv",
            tmp_path / "audit.jsonl",
        )


def test_sample_can_refresh_public_examples():
    validate_output_paths(
        ROOT / "examples" / "sample.log",
        ROOT / "results" / "parsed_sample.csv",
        ROOT / "results" / "audit.jsonl",
    )


def test_outputs_must_be_distinct(tmp_path):
    output = tmp_path / "output"
    with pytest.raises(ValueError, match="must be different"):
        validate_output_paths(tmp_path / "input.log", output, output)
