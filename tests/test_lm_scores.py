# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""No-harm gate: the committed LM summary must not regress vs deterministic.

Offline: reads only the committed results/lm_scores.json, no model server.
This guards the committed data; the code mechanism behind it
(MAX_AUTO_AFFECTED hold, needs-human not materialized) is guarded by
tests/test_assist.py.
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
    # 16 candidates from the dry-run; changing thresholds reshapes the
    # set, so update README + lm_scores.json together (see pin test).
    assert scores["candidates"] == 16
    assert isinstance(scores["model"], str) and scores["model"].strip()
    for section in ("deterministic", "v1", "v2"):
        for split in ("tight", "loose"):
            assert scores[section][split]["n_templates"] == 26
            assert isinstance(scores[section][split]["n_templates"], int)
            for key in KEYS:
                value = scores[section][split][key]
                assert isinstance(value, float)
                assert 0.0 <= value <= 1.0


def test_v2_matches_deterministic_for_identical_csv():
    # v2 summary claims 0 auto-applies: the assisted CSV is byte-identical
    # to the deterministic parse, so scores must be equal, not just >=.
    # If a future assist legitimately improves scores, update the summary
    # and relax this to the no-harm gate below.
    scores = load()
    det = scores["deterministic"]
    assisted = scores["v2"]
    for split in ("tight", "loose"):
        for key in KEYS:
            assert assisted[split][key] == det[split][key], (
                f"v2 {split} {key} differs from deterministic "
                f"but summary claims identical CSV: "
                f"{assisted[split][key]} != {det[split][key]}"
            )


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
