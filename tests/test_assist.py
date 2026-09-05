# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""Candidate selection, review records, and assisted CSV changes."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trailparse.assist import (  # noqa: E402
    DEFAULT_MAX_CANDIDATES,
    LOW_SIMILARITY,
    MAX_AUTO_AFFECTED,
    MAX_EXAMPLES,
    Candidate,
    append_review,
    apply_decisions,
    build_prompt,
    decide,
    parse_same_or_two,
    review_candidate,
    select_candidates,
    token_edit_distance,
)
from trailparse.audit import read_jsonl  # noqa: E402
from trailparse.io import read_structured  # noqa: E402


class FakeClient:
    def __init__(self, text="SAME"):
        self.text = text
        self.model = "requested-model"
        self.prompts = []

    def complete(self, prompt):
        self.prompts.append(prompt)
        return {
            "text": self.text,
            "model": "test-model",
            "raw": {"choices": [{"message": {"content": self.text}}]},
        }


class FailingClient(FakeClient):
    def complete(self, prompt):
        raise ConnectionRefusedError("server unavailable")


def row(line_id, event_id, template, content):
    return {
        "LineId": str(line_id),
        "Content": content,
        "EventId": event_id,
        "EventTemplate": template,
        "ParameterList": "[]",
    }


def test_review_thresholds_are_pinned():
    # Chosen once, not tuned per run. A deliberate change here must also
    # refresh results/lm_scores.json and the README LM table.
    assert LOW_SIMILARITY == 0.7
    assert MAX_EXAMPLES == 3
    assert MAX_AUTO_AFFECTED == 10
    assert DEFAULT_MAX_CANDIDATES == 100


def test_token_edit_distance_handles_replace_insert_and_delete():
    assert token_edit_distance(["a", "b"], ["a", "c"]) == 1
    assert token_edit_distance(["a", "b"], ["a", "x", "b"]) == 1
    assert token_edit_distance(["a", "x", "b"], ["a", "b"]) == 1
    assert token_edit_distance(["a", "b"], ["x", "y"]) == 2


def test_committed_sample_candidates_have_three_audit_cited_examples():
    records = read_jsonl(ROOT / "results" / "audit.jsonl")
    rows = read_structured(ROOT / "results" / "parsed_sample.csv")

    candidates = select_candidates(records, rows)

    assert [(c.kind, c.cluster_ids) for c in candidates] == [
        ("low_confidence", ("T1",)),
        ("low_confidence", ("T2",)),
        ("low_confidence", ("T3",)),
        ("near_duplicate", ("T1", "T2")),
    ]
    content_by_line = {int(r["LineId"]): r["Content"] for r in rows}
    for candidate in candidates:
        assert len(candidate.examples) == 3
        assert candidate.examples == tuple(
            content_by_line[line_id] for line_id in candidate.cited_audit_lines
        )


def test_candidates_carry_affected_line_counts():
    contents = {1: "event a", 2: "event b", 3: "event c"}
    records = []
    rows = []
    for i in range(1, 13):
        content = contents.get(i, "event a")
        decision = "matched" if i == 2 else "new_cluster"
        records.append(
            {
                "line": i,
                "cluster": "T1",
                "decision": decision,
                "similarity": 0.5 if i == 2 else 0.0,
                "template": "event <*>",
            }
        )
        rows.append(row(i, "T1", "event <*>", content))

    (candidate,) = select_candidates(records, rows)

    assert candidate.kind == "low_confidence"
    assert candidate.target_line == 2
    assert candidate.affected_lines == 12


def test_candidates_without_three_examples_are_not_sent():
    records = [
        {
            "line": 1,
            "cluster": "T1",
            "decision": "new_cluster",
            "similarity": 0.0,
            "template": "event a",
        },
        {
            "line": 2,
            "cluster": "T1",
            "decision": "matched",
            "similarity": 0.5,
            "template": "event <*>",
        },
    ]
    rows = [
        row(1, "T1", "event <*>", "event a"),
        row(2, "T1", "event <*>", "event b"),
    ]

    assert select_candidates(records, rows) == []


def test_candidate_selection_rejects_mismatched_artifacts():
    records = [
        {
            "line": 1,
            "cluster": "T1",
            "decision": "new_cluster",
            "similarity": 0.0,
            "template": "event one",
        }
    ]

    with pytest.raises(ValueError, match="cluster mismatch"):
        select_candidates(records, [row(1, "T2", "event one", "event one")])
    with pytest.raises(ValueError, match="LineId mismatch"):
        select_candidates(
            records,
            [
                row(1, "T1", "event one", "event one"),
                row(2, "T1", "event one", "event one"),
            ],
        )
    with pytest.raises(ValueError, match="final templates"):
        select_candidates(records, [row(1, "T1", "event <*>", "event one")])


def test_candidate_limit_stops_dense_near_duplicate_set():
    records = []
    rows = []
    for i, word in enumerate(["a", "b", "c", "d"], start=1):
        cid = f"T{i}"
        template = f"event {word}"
        records.append(
            {
                "line": i,
                "cluster": cid,
                "decision": "new_cluster",
                "similarity": 0.0,
                "template": template,
            }
        )
        rows.append(row(i, cid, template, template))

    with pytest.raises(ValueError, match="candidate limit exceeded"):
        select_candidates(records, rows, max_candidates=3)


def test_prompt_and_response_contract():
    candidate = Candidate(
        kind="near_duplicate",
        cluster_ids=("T1", "T2"),
        cited_audit_lines=(1, 2, 3),
        examples=("event a", "event b", "event c"),
        templates=("event <*>", "events <*>"),
        similarity=None,
        target_line=None,
    )

    prompt = build_prompt(candidate)

    assert "Reply with one word: SAME or TWO." in prompt
    assert "1. event a" in prompt
    # v2 prompt carries definitions, rules, and counterexamples for the SLM.
    assert "SAME means one event type" in prompt
    assert "TWO means different event types" in prompt
    assert "Accepted vs Failed" in prompt
    assert "Example SAME:" in prompt
    assert "Example TWO:" in prompt
    assert parse_same_or_two("<think>reasoning</think>SAME") == "SAME"
    assert parse_same_or_two("<think>SAME") is None
    assert parse_same_or_two("SAME or TWO") is None
    assert decide(candidate, "SAME") == ("accept", "merge", "model said SAME")

    low = Candidate(
        kind="low_confidence",
        cluster_ids=("T1",),
        cited_audit_lines=(2, 1, 3),
        examples=("target", "peer one", "peer two"),
        templates=("event <*>",),
        similarity=0.5,
        target_line=2,
    )
    assert "Is example 1" in build_prompt(low)

    unequal = Candidate(
        kind="near_duplicate",
        cluster_ids=("T1", "T2"),
        cited_audit_lines=(1, 2, 3),
        examples=("event a", "event b", "event x b"),
        templates=("event <*>", "event <*> <*>"),
        similarity=None,
        target_line=None,
    )
    assert decide(unequal, "SAME") == (
        "reject",
        "none",
        "unequal-length merge is not materialized",
    )


def test_review_contains_request_response_identity_citations_and_digests():
    candidate = Candidate(
        kind="low_confidence",
        cluster_ids=("T1",),
        cited_audit_lines=(2, 1, 3),
        examples=("event b", "event a", "event c"),
        templates=("event <*>",),
        similarity=0.5,
        target_line=2,
    )

    review = review_candidate(
        candidate,
        FakeClient("TWO"),
        audit_sha256="audit-digest",
        csv_sha256="csv-digest",
    )

    assert review["schema"] == "lm-review-v1"
    assert review["cited_audit_lines"] == [2, 1, 3]
    assert review["model"] == "test-model"
    assert review["prompt_version"] == "trail-lm-v2"
    assert review["response"]["parsed"] == "TWO"
    assert review["decision"] == "accept"
    assert review["change"] == "split"
    assert review["audit_sha256"] == "audit-digest"
    assert review["csv_sha256"] == "csv-digest"


def test_failed_request_is_an_audited_rejection():
    candidate = Candidate(
        kind="near_duplicate",
        cluster_ids=("T1", "T2"),
        cited_audit_lines=(1, 2, 3),
        examples=("event a", "event b", "event c"),
        templates=("event <*>", "events <*>"),
        similarity=None,
        target_line=None,
    )

    review = review_candidate(
        candidate,
        FailingClient(),
        audit_sha256="audit-digest",
        csv_sha256="csv-digest",
    )

    assert review["decision"] == "reject"
    assert review["change"] == "none"
    assert review["reason"] == "model request failed"
    assert review["response"]["error"].startswith("ConnectionRefusedError:")


def test_append_review_is_append_only(tmp_path):
    output = tmp_path / "review.jsonl"

    append_review(output, {"decision": "accept"})
    append_review(output, {"decision": "reject"})

    decisions = [
        json.loads(line)["decision"] for line in output.read_text().splitlines()
    ]
    assert decisions == ["accept", "reject"]


def test_apply_decisions_returns_separate_rows_for_merge_and_split():
    source = [
        row(1, "T1", "event <*>", "event a"),
        row(2, "T1", "event <*>", "event b"),
        row(3, "T2", "events <*>", "events c"),
    ]
    reviews = [
        {
            "decision": "accept",
            "change": "split",
            "target_line": 2,
            "cluster_ids": ["T1"],
        },
        {
            "decision": "accept",
            "change": "merge",
            "target_line": None,
            "cluster_ids": ["T1", "T2"],
        },
    ]

    assisted = apply_decisions(source, reviews)

    assert source[1]["EventId"] == "T1"
    assert assisted[1]["EventId"] == "T3"
    assert assisted[1]["EventTemplate"] == "event b"
    assert assisted[2]["EventId"] == "T1"
    assert assisted[0]["EventTemplate"] == "<*> <*>"
    assert assisted[2]["ParameterList"] == "['events', 'c']"


def test_apply_decisions_merge_keeps_key_aware_params():
    source = [
        row(1, "T1", "event user=root", "event user=root"),
        row(2, "T2", "event user=admin", "event user=admin"),
    ]

    assisted = apply_decisions(
        source, [{"change": "merge", "cluster_ids": ["T1", "T2"]}]
    )

    assert {item["EventId"] for item in assisted} == {"T1"}
    assert assisted[0]["EventTemplate"] == "event user=<*>"
    assert assisted[0]["ParameterList"] == "['root']"
    assert assisted[1]["ParameterList"] == "['admin']"


def test_apply_decisions_handles_overlapping_merges():
    source = [
        row(1, "T1", "event one", "event one"),
        row(2, "T2", "event two", "event two"),
        row(3, "T3", "event three", "event three"),
    ]
    reviews = [
        {"change": "merge", "cluster_ids": ["T1", "T2"]},
        {"change": "merge", "cluster_ids": ["T2", "T3"]},
    ]

    assisted = apply_decisions(source, reviews)

    assert {item["EventId"] for item in assisted} == {"T1"}
    assert {item["EventTemplate"] for item in assisted} == {"event <*>"}


def test_apply_decisions_rejects_conflicted_merge_component():
    source = [
        row(1, "T1", "event one", "event one"),
        row(2, "T2", "event two", "event two"),
        row(3, "T3", "event three", "event three"),
    ]
    reviews = [
        {"change": "merge", "cluster_ids": ["T1", "T2"]},
        {"change": "merge", "cluster_ids": ["T2", "T3"]},
        {
            "kind": "near_duplicate",
            "change": "none",
            "cluster_ids": ["T1", "T3"],
            "response": {"parsed": "TWO"},
        },
    ]

    with pytest.raises(ValueError, match="conflicting SAME/TWO"):
        apply_decisions(source, reviews)


def test_apply_decisions_rejects_unequal_length_merge():
    source = [
        row(1, "T1", "event one", "event one"),
        row(2, "T2", "event one extra", "event one extra"),
    ]

    with pytest.raises(ValueError, match="unequal-length"):
        apply_decisions(source, [{"change": "merge", "cluster_ids": ["T1", "T2"]}])


def test_big_split_is_held_for_human_review():
    candidate = Candidate(
        kind="low_confidence",
        cluster_ids=("T3",),
        cited_audit_lines=(18, 3, 21),
        examples=("target", "peer one", "peer two"),
        templates=("event <*>",),
        similarity=0.5,
        target_line=18,
        affected_lines=410,
    )
    assert decide(candidate, "TWO") == (
        "needs-human",
        "none",
        "split of 410 lines in T3 held for human review",
    )


def test_big_merge_is_held_for_human_review():
    candidate = Candidate(
        kind="near_duplicate",
        cluster_ids=("T7", "T11"),
        cited_audit_lines=(7, 15, 10),
        examples=("event a", "event b", "event c"),
        templates=("event <*>", "event <*>"),
        similarity=None,
        target_line=None,
        affected_lines=160,
    )
    assert decide(candidate, "SAME") == (
        "needs-human",
        "none",
        "merge of 160 lines in T7,T11 held for human review",
    )


def test_small_accepts_still_apply():
    split = Candidate(
        kind="low_confidence",
        cluster_ids=("T1",),
        cited_audit_lines=(2, 1, 3),
        examples=("target", "peer one", "peer two"),
        templates=("event <*>",),
        similarity=0.5,
        target_line=2,
        affected_lines=3,
    )
    assert decide(split, "TWO") == ("accept", "split", "model said TWO")
    merge = Candidate(
        kind="near_duplicate",
        cluster_ids=("T1", "T2"),
        cited_audit_lines=(1, 2, 3),
        examples=("event a", "event b", "event c"),
        templates=("event <*>", "event <*>"),
        similarity=None,
        target_line=None,
        affected_lines=6,
    )
    assert decide(merge, "SAME") == ("accept", "merge", "model said SAME")


def test_needs_human_records_are_not_materialized():
    source = [
        row(1, "T1", "event <*>", "event a"),
        row(2, "T1", "event <*>", "event b"),
        row(3, "T2", "event <*>", "event c"),
    ]
    reviews = [
        {
            "decision": "needs-human",
            "change": "none",
            "target_line": 2,
            "cluster_ids": ["T1"],
        },
        {
            "decision": "needs-human",
            "change": "none",
            "target_line": None,
            "cluster_ids": ["T1", "T2"],
        },
    ]

    assisted = apply_decisions(source, reviews)

    assert [item["EventId"] for item in assisted] == ["T1", "T1", "T2"]
    assert [item["EventTemplate"] for item in assisted] == [
        "event <*>",
        "event <*>",
        "event <*>",
    ]


def test_apply_decisions_accepts_empty_parse():
    assert apply_decisions([], []) == []
