# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""Miner core: determinism, anchor rule, merge behavior."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trailparse.io import split_header  # noqa: E402
from trailparse.miner import Miner, merge, similarity  # noqa: E402

LINES = [
    "Failed password for root from 203.0.113.7 port 51 ssh2",
    "Failed password for admin from 203.0.113.8 port 52 ssh2",
    "Accepted password for root from 203.0.113.7 port 53 ssh2",
    "[UFW BLOCK] IN=eth0 SRC=203.0.113.9 DST=10.0.0.5",
]


def run(lines: list[str]) -> Miner:
    miner = Miner(st=0.5, anchor_tokens=2)
    for i, raw in enumerate(lines, start=1):
        miner.feed(i, raw)
    return miner


def test_split_header():
    full = (
        "Jun 14 00:00:01 secops-01 sshd[100]: "
        "Failed password for root from x port 1 ssh2"
    )
    assert split_header(full) == "Failed password for root from x port 1 ssh2"
    assert split_header("bare message") == "bare message"


def test_deterministic():
    a, b = run(LINES), run(LINES)
    assert [c.template for c in a.clusters] == [c.template for c in b.clusters]
    assert [d.cluster for d in a.decisions] == [d.cluster for d in b.decisions]


def test_outcomes_stay_apart():
    miner = run(LINES)
    texts = [" ".join(c.template) for c in miner.clusters]
    assert sum("Failed password" in t for t in texts) == 1
    assert sum("Accepted password" in t for t in texts) == 1


def test_variable_positions_become_wildcards():
    miner = run(LINES[:2])
    assert len(miner.clusters) == 1
    template = " ".join(miner.clusters[0].template)
    assert "root" not in template and "<*>" in template
    assert template.startswith("Failed password")


def test_wildcard_positions_match_later_lines():
    lines = [
        "event start user=alice action=login id=1 ok",
        "event start user=bob action=login id=2 fail",
        "event start user=carol action=logout id=3 pending",
    ]
    miner = run(lines)
    assert len(miner.clusters) == 1


def test_length_slack_controls_candidate_matching():
    lines = [
        "event start one two",
        "event start one two three",
    ]

    strict = Miner(st=0.5, anchor_tokens=2, length_slack=0)
    relaxed = Miner(st=0.5, anchor_tokens=2, length_slack=1)
    for i, line in enumerate(lines, start=1):
        strict.feed(i, line)
        relaxed.feed(i, line)

    assert len(strict.clusters) == 2
    assert len(relaxed.clusters) == 1
    assert relaxed.clusters[0].template == ["event", "start", "one", "two", "<*>"]


def test_src_mask_enables_first_ufw_merge():
    lines = [
        "[UFW BLOCK] IN=eth0 OUT= SRC=203.0.113.9 DST=10.0.0.5 "
        "SPT=51 DPT=22 PROTO=TCP",
        "[UFW BLOCK] IN=ens3 OUT= SRC=203.0.113.10 DST=10.0.0.6 "
        "SPT=52 DPT=23 PROTO=TCP",
    ]

    without_mask = Miner(st=0.5, anchor_tokens=2)
    with_mask = Miner(st=0.5, anchor_tokens=2, regex=[r"SRC=\S+"])
    for i, line in enumerate(lines, start=1):
        without_mask.feed(i, line)
        with_mask.feed(i, line)

    assert len(without_mask.clusters) == 2
    assert len(with_mask.clusters) == 1


def test_token_masks_require_a_full_match():
    miner = Miner(regex=[r"uid=\d+"])
    cluster = miner.feed(1, "account www-data(uid=1001)")
    assert cluster.template == ["account", "www-data(uid=1001)"]


def test_similarity_edge_cases():
    assert similarity([], []) == 0.0
    assert similarity(["a"], ["a", "b"]) == 0.0
    assert similarity(["a", "b"], ["a", "c"]) == 0.5
    assert similarity(["x", "y"], ["x", "<*>"]) == 1.0
    assert merge(["a", "b"], ["a", "c"]) == ["a", "<*>"]
