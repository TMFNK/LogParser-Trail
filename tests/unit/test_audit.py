# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""Audit trail: one record per line, faithful summary."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trailparse import audit as audit_mod  # noqa: E402
from trailparse.miner import Miner  # noqa: E402


def test_record_per_line():
    miner = Miner()
    lines = ["a b c", "a b d", "x y z w"]
    for i, raw in enumerate(lines, start=1):
        miner.feed(i, raw)
    assert len(miner.decisions) == 3
    assert miner.decisions[0].decision == "new_cluster"
    assert miner.decisions[0].similarity == 0.0
    assert miner.decisions[1].decision == "matched"
    assert miner.decisions[1].similarity > 0.5


def test_jsonl_roundtrip(tmp_path):
    miner = Miner()
    miner.feed(1, "a b c")
    miner.feed(2, "a b d")
    out = tmp_path / "audit.jsonl"
    audit_mod.write_jsonl(miner.decisions, out)
    records = [json.loads(line) for line in out.read_text().splitlines()]
    assert len(records) == 2
    assert set(records[0]) == {"line", "cluster", "decision", "similarity", "template"}


def test_summary_counts():
    miner = Miner()
    lines = ["a b c d", "a b c d", "a b y z", "x y q"]
    for i, raw in enumerate(lines, start=1):
        miner.feed(i, raw)
    summary = audit_mod.summarize(miner.decisions)
    assert summary == {
        "n_lines": 4,
        "n_new_clusters": 2,
        "n_matched": 2,
        "min_match_similarity": 0.5,
    }
