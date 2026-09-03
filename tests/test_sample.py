# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""Committed sample: presence, size, truth shape, miner sanity."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trailparse import io as io_mod  # noqa: E402
from trailparse.miner import Miner  # noqa: E402

LOG = ROOT / "examples" / "sample.log"
TRUTH = ROOT / "examples" / "sample_structured.csv"


def test_sample_files_sized():
    assert LOG.exists(), "run ./reproduce.sh (make_sample) first"
    assert TRUTH.exists(), "run ./reproduce.sh (make_sample) first"
    assert len(LOG.read_text().splitlines()) == 60
    rows = io_mod.read_structured(TRUTH)
    assert len(rows) == 60
    assert {r["EventId"] for r in rows} == {f"G{i}" for i in range(1, 9)}


def test_sensible_cluster_count():
    miner = Miner(st=0.5, anchor_tokens=2)
    for i, raw in enumerate(io_mod.read_log(LOG), start=1):
        miner.feed(i, io_mod.split_header(raw))
    assert len(miner.clusters) == 8, len(miner.clusters)


def test_truth_params_match_templates():
    import ast

    for r in io_mod.read_structured(TRUTH):
        params = ast.literal_eval(r["ParameterList"])
        assert len(params) == r["EventTemplate"].count("<*>"), r["LineId"]
