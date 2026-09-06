# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""SecOps tight scores remain above the locked Drain gate."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.verify_secops import failures  # noqa: E402


def test_secops_gate_accepts_current_scores():
    assert failures({"FGA": 0.4872, "FTA": 0.3077}) == []


def test_secops_gate_rejects_regression():
    assert failures({"FGA": 0.4872, "FTA": 0.2}) == [
        "FTA: required >= 0.2526, got 0.2"
    ]
