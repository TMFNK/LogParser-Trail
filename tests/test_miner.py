# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""Miner core: determinism, anchor rule, merge behavior."""

import random
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


def test_shuffled_order_keeps_audit_well_formed():
    # The miner is order-dependent by design: templates only generalize, so
    # arrival order shapes clusters. Whatever the order, the audit must stay
    # a complete receipt: one decision per line, every cluster non-empty.
    repeated = LINES * 3
    shuffled = repeated[:]
    random.Random(7).shuffle(shuffled)

    first, second = run(shuffled), run(shuffled)

    assert [d.cluster for d in first.decisions] == [
        d.cluster for d in second.decisions
    ]
    assert sorted(d.line_id for d in first.decisions) == list(
        range(1, len(shuffled) + 1)
    )
    assert first.decisions and all(c.count > 0 for c in first.clusters)
    assert sum(c.count for c in first.clusters) == len(shuffled)


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


def test_repeated_short_messages_share_a_cluster():
    miner = run(["heartbeat", "heartbeat"])
    assert len(miner.clusters) == 1
    assert miner.clusters[0].count == 2


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


def test_token_masks_preserve_parameter_values():
    miner = Miner(regex=[r"SRC=\S+"])
    cluster = miner.feed(1, "event start SRC=203.0.113.7")
    assert miner.params_for("event start SRC=203.0.113.7", cluster) == [
        "SRC=203.0.113.7"
    ]


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


def test_mask_mapping_keeps_field_name():
    miner = Miner(regex=[{"pattern": r"pid=\d+", "replace": "pid=<*>"}])
    cluster = miner.feed(1, "USER_AUTH pid=1234 res=ok")
    assert cluster.template == ["USER_AUTH", "pid=<*>", "res=ok"]


def test_string_mask_still_means_bare_wildcard():
    miner = Miner(regex=[r"pid=\d+"])
    cluster = miner.feed(1, "USER_AUTH pid=1234 res=ok")
    assert cluster.template == ["USER_AUTH", "<*>", "res=ok"]


def test_merge_preserves_shared_key_prefix():
    assert merge(["user=root"], ["user=admin"]) == ["user=<*>"]
    assert merge(["IN=eth0"], ["IN=lo"]) == ["IN=<*>"]
    # differing keys fall back to bare wildcard, as do bare tokens
    assert merge(["user=root"], ["group=wheel"]) == ["<*>"]
    assert merge(["root"], ["admin"]) == ["<*>"]
    # already-generalized positions are stable
    assert merge(["user=<*>"], ["user=bob"]) == ["user=<*>"]
    assert merge(["<*>"], ["anything"]) == ["<*>"]


def test_key_aware_template_positions_still_match():
    assert similarity(["user=bob"], ["user=<*>"]) == 1.0
    assert similarity(["a", "user=bob"], ["a", "user=<*>"]) == 1.0


def test_params_for_splits_compound_wildcards():
    miner = Miner(
        regex=[{"pattern": r"^\S+\(uid=\d+\)$", "replace": "<*>(uid=<*>)"}]
    )
    raw = "session opened for user root by admin(uid=1000)"
    cluster = miner.feed(1, raw)
    assert cluster.template[-1] == "<*>(uid=<*>)"
    assert miner.params_for(raw, cluster) == ["admin", "1000"]


def test_params_for_bare_wildcard_yields_whole_token():
    miner = Miner(regex=[r"SRC=\S+"])
    cluster = miner.feed(1, "event start SRC=203.0.113.7")
    assert miner.params_for("event start SRC=203.0.113.7", cluster) == [
        "SRC=203.0.113.7"
    ]


def test_identity_keys_split_same_shape_lines():
    lines = [
        "[UFW BLOCK] IN=eth0 OUT= SRC=1.1.1.1 DST=2.2.2.2 PROTO=TCP SPT=1 DPT=2",
        "[UFW BLOCK] IN=eth0 OUT= SRC=1.1.1.1 DST=2.2.2.2 PROTO=UDP SPT=1 DPT=2",
    ]
    plain = Miner(st=0.5, anchor_tokens=2)
    for i, line in enumerate(lines, start=1):
        plain.feed(i, line)
    assert len(plain.clusters) == 1

    strict = Miner(st=0.5, anchor_tokens=2, identity_keys=["PROTO"])
    for i, line in enumerate(lines, start=1):
        strict.feed(i, line)
    assert len(strict.clusters) == 2
    protos = sorted(c.template[6] for c in strict.clusters)
    assert protos == ["PROTO=TCP", "PROTO=UDP"]


def test_identity_keys_ignore_generalized_positions():
    miner = Miner(st=0.5, anchor_tokens=2, identity_keys=["PROTO"])
    base = "[UFW BLOCK] IN={inn} OUT= SRC=1.1.1.1 DST=2.2.2.2 PROTO=TCP SPT={s} DPT={d}"
    miner.feed(1, base.format(inn="eth0", s=1, d=2))
    miner.feed(2, base.format(inn="eth1", s=3, d=4))
    assert len(miner.clusters) == 1


def test_positional_mask_fires_only_at_its_index():
    miner = Miner(
        regex=[
            {
                "pattern": r"^[a-z][a-z0-9_.-]*$",
                "replace": "<*>",
                "position": 0,
                "next": ":",
            }
        ]
    )
    first = miner.feed(1, "root : user NOT authorized")
    second = miner.feed(2, "bob : user NOT authorized")
    assert first.template[0] == "<*>"
    assert first.cid == second.cid
    # same shape later in the line is left alone
    third = miner.feed(3, "root : run root command")
    assert third.template[3] == "root"


def test_positional_mask_requires_its_follower():
    miner = Miner(
        regex=[
            {
                "pattern": r"^[a-z][a-z0-9_.-]*$",
                "replace": "<*>",
                "position": 0,
                "next": ":",
            }
        ]
    )
    # "reverse mapping ..." and "mod_jk child ..." stay literal
    for raw in ("reverse mapping check", "mod_jk child init"):
        cluster = miner.feed(1, raw)
        assert cluster.template[0] != "<*>", raw
