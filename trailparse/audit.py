# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""Audit trail writers. One JSON record per parsed line, plus a summary.

Schema (v1):
  {"line": 12, "cluster": "T3", "decision": "matched",
   "similarity": 0.875, "template": "Failed password for <*> ..."}
  decision is "new_cluster" (similarity 0.0) or "matched".
"""

from __future__ import annotations

import json
from pathlib import Path

from trailparse.io import atomic_text_writer
from trailparse.miner import Decision


def read_jsonl(path: Path) -> list[dict]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line:
            records.append(json.loads(line))
    return records


def write_jsonl(decisions: list[Decision], path: Path) -> None:
    with atomic_text_writer(path) as f:
        for d in decisions:
            f.write(
                json.dumps(
                    {
                        "line": d.line_id,
                        "cluster": d.cluster,
                        "decision": d.decision,
                        "similarity": d.similarity,
                        "template": d.template_after,
                    }
                )
                + "\n"
            )


def summarize(decisions: list[Decision]) -> dict:
    matched = [d for d in decisions if d.decision == "matched"]
    sims = [d.similarity for d in matched]
    return {
        "n_lines": len(decisions),
        "n_new_clusters": sum(1 for d in decisions if d.decision == "new_cluster"),
        "n_matched": len(matched),
        "min_match_similarity": round(min(sims), 4) if sims else None,
    }
