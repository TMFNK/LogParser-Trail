# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""The CLI keeps deterministic inputs immutable and writes separate artifacts."""

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trailparse import cli  # noqa: E402
from trailparse.io import read_structured, write_structured  # noqa: E402


class FakeClient:
    def __init__(self, base_url, model, timeout):
        self.model = model

    def complete(self, prompt):
        return {
            "text": "SAME",
            "model": self.model,
            "raw": {
                "model": self.model,
                "choices": [{"message": {"content": "SAME"}}],
            },
        }


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_cli_writes_review_and_assisted_csv_without_mutating_inputs(
    tmp_path, monkeypatch
):
    csv_path = tmp_path / "parsed.csv"
    audit_path = tmp_path / "audit.jsonl"
    raw = tmp_path / "results" / "raw"
    review_path = raw / "parsed.lm-review.jsonl"
    out_csv = raw / "parsed_lm.csv"
    rows = [
        {
            "LineId": str(i),
            "Content": f"event {suffix}",
            "EventId": cluster,
            "EventTemplate": template,
            "ParameterList": "[]",
        }
        for i, suffix, cluster, template in [
            (1, "one", "T1", "event <*>"),
            (2, "two", "T1", "event <*>"),
            (3, "three", "T1", "event <*>"),
            (4, "four", "T2", "events <*>"),
            (5, "five", "T2", "events <*>"),
            (6, "six", "T2", "events <*>"),
        ]
    ]
    records = [
        {
            "line": i,
            "cluster": cluster,
            "decision": decision,
            "similarity": similarity,
            "template": template,
        }
        for i, cluster, decision, similarity, template in [
            (1, "T1", "new_cluster", 0.0, "event one"),
            (2, "T1", "matched", 0.5, "event <*>"),
            (3, "T1", "matched", 1.0, "event <*>"),
            (4, "T2", "new_cluster", 0.0, "events four"),
            (5, "T2", "matched", 1.0, "events <*>"),
            (6, "T2", "matched", 1.0, "events <*>"),
        ]
    ]
    write_structured(rows, csv_path)
    audit_path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
    before = (digest(csv_path), digest(audit_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "LocalModelClient", FakeClient)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "lm_assist.py",
            "--csv",
            str(csv_path),
            "--audit",
            str(audit_path),
            "--review",
            str(review_path),
            "--out-csv",
            str(out_csv),
        ],
    )

    cli.main()

    assert (digest(csv_path), digest(audit_path)) == before
    reviews = [json.loads(line) for line in review_path.read_text().splitlines()]
    assert [review["change"] for review in reviews] == ["none", "merge"]
    assisted = read_structured(out_csv)
    assert {row["EventId"] for row in assisted} == {"T1"}


def test_validate_paths_requires_ignored_output_names(tmp_path):
    raw = tmp_path / "results" / "raw"

    with pytest.raises(ValueError, match="under results/raw"):
        cli.validate_paths(
            tmp_path / "parsed.csv",
            tmp_path / "audit.jsonl",
            tmp_path / "public.lm-review.jsonl",
            None,
            raw,
            force=False,
        )
    with pytest.raises(ValueError, match="end with _lm.csv"):
        cli.validate_paths(
            tmp_path / "parsed.csv",
            tmp_path / "audit.jsonl",
            raw / "private.lm-review.jsonl",
            raw / "private.csv",
            raw,
            force=False,
        )


def test_validate_paths_refuses_existing_assisted_csv_without_force(tmp_path):
    raw = tmp_path / "results" / "raw"
    raw.mkdir(parents=True)
    out_csv = raw / "private_lm.csv"
    out_csv.write_text("existing")

    with pytest.raises(ValueError, match="already exists"):
        cli.validate_paths(
            tmp_path / "parsed.csv",
            tmp_path / "audit.jsonl",
            raw / "private.lm-review.jsonl",
            out_csv,
            raw,
            force=False,
        )
    cli.validate_paths(
        tmp_path / "parsed.csv",
        tmp_path / "audit.jsonl",
        raw / "private.lm-review.jsonl",
        out_csv,
        raw,
        force=True,
    )


def test_missing_input_is_reported_without_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "trail-lm-assist",
            "--csv",
            "missing.csv",
            "--audit",
            "missing.jsonl",
            "--dry-run",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        cli.main()

    assert exc.value.code == 2
    stderr = capsys.readouterr().err
    assert "No such file or directory" in stderr
    assert "Traceback" not in stderr


def test_snapshot_revalidation_detects_input_change(tmp_path):
    csv_path = tmp_path / "parsed.csv"
    audit_path = tmp_path / "audit.jsonl"
    write_structured([], csv_path)
    audit_path.write_text("")
    _, _, digests = cli._read_snapshots(csv_path, audit_path)

    audit_path.write_text("{}\n")

    with pytest.raises(RuntimeError, match="immutable input changed"):
        cli._ensure_unchanged(digests)
