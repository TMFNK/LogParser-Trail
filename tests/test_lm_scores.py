# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""No-harm gate: the committed LM summary must not regress vs deterministic.

Offline: reads only the committed results/lm_scores.json, no model server.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SCORES = ROOT / "results" / "lm_scores.json"
KEYS = ("GA", "PA", "FGA", "FTA")


def load():
    return json.loads(SCORES.read_text())


def test_lm_scores_file_has_expected_shape():
    scores = load()
    assert scores["deterministic"]["tight"]["n_templates"] == 26
    for section in ("deterministic", "v1", "v2"):
        for split in ("tight", "loose"):
            for key in KEYS:
                assert isinstance(scores[section][split][key], float)


def test_v2_does_no_harm_vs_deterministic():
    scores = load()
    det = scores["deterministic"]
    assisted = scores["v2"]
    for split in ("tight", "loose"):
        for key in KEYS:
            assert assisted[split][key] >= det[split][key], (
                f"v2 {split} {key} regressed: "
                f"{assisted[split][key]} < {det[split][key]}"
            )
