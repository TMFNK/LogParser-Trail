# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""Score CSVs by LineId rather than incidental row order."""

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.score import score_pair  # noqa: E402
from trailparse.io import COLUMNS  # noqa: E402


def write_rows(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def row(line_id: int, event_id: str, template: str) -> dict:
    return {
        "LineId": str(line_id),
        "Content": "",
        "EventId": event_id,
        "EventTemplate": template,
        "ParameterList": "[]",
    }


def test_score_pair_aligns_rows_by_line_id(tmp_path):
    truth = tmp_path / "truth.csv"
    parsed = tmp_path / "parsed.csv"
    write_rows(
        truth,
        [row(1, "G1", "event <*>"), row(2, "G1", "event <*>"), row(3, "G2", "done")],
    )
    write_rows(
        parsed,
        [row(3, "T2", "done"), row(1, "T1", "event <*>"), row(2, "T1", "event <*>")],
    )

    scores, n_templates = score_pair(str(truth), str(parsed))

    assert scores == {"GA": 1.0, "PA": 1.0, "FGA": 1.0, "FTA": 1.0}
    assert n_templates == 2


def test_score_pair_rejects_duplicate_or_missing_line_ids(tmp_path):
    truth = tmp_path / "truth.csv"
    parsed = tmp_path / "parsed.csv"
    write_rows(truth, [row(1, "G1", "event"), row(2, "G2", "done")])
    write_rows(parsed, [row(1, "T1", "event"), row(1, "T2", "done")])

    with pytest.raises(ValueError, match="duplicate LineId"):
        score_pair(str(truth), str(parsed))
