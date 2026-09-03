# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""Score a parsed CSV against ground truth with GA/PA/FGA/FTA."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trailparse import io as io_mod  # noqa: E402
from trailparse.metrics import score_frames  # noqa: E402


def index_by_line_id(rows: list[dict], label: str) -> dict[str, dict]:
    indexed = {}
    for row in rows:
        line_id = row["LineId"]
        if line_id in indexed:
            raise ValueError(f"{label} has duplicate LineId {line_id!r}")
        indexed[line_id] = row
    return indexed


def score_pair(truth_path: str, parsed_path: str) -> tuple[dict[str, float], int]:
    gt = io_mod.read_structured(Path(truth_path))
    parsed = io_mod.read_structured(Path(parsed_path))
    gt_by_id = index_by_line_id(gt, "truth")
    parsed_by_id = index_by_line_id(parsed, "parsed")
    if gt_by_id.keys() != parsed_by_id.keys():
        missing = sorted(gt_by_id.keys() - parsed_by_id.keys())
        extra = sorted(parsed_by_id.keys() - gt_by_id.keys())
        raise ValueError(f"LineId mismatch: missing={missing}, extra={extra}")
    parsed = [parsed_by_id[row["LineId"]] for row in gt]
    gt_map = {k: [r[k] for r in gt] for k in ("EventId", "EventTemplate")}
    parsed_map = {k: [r[k] for r in parsed] for k in ("EventId", "EventTemplate")}
    n_templates = len({r["EventId"] for r in parsed})
    return score_frames(gt_map, parsed_map), n_templates


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth", required=True)
    ap.add_argument("--parsed", required=True)
    ap.add_argument("--label", default="")
    ap.add_argument(
        "--out-md",
        default="",
        help="write fresh markdown table with this run as its row",
    )
    ap.add_argument(
        "--append-md", default="", help="append this run as a row to an existing table"
    )
    ap.add_argument(
        "--out-json",
        default="",
        help="write GA/PA/FGA/FTA and n_templates as JSON",
    )
    args = ap.parse_args()
    scores, n_templates = score_pair(args.truth, args.parsed)
    for k in ("GA", "PA", "FGA", "FTA"):
        print(f"{k}={scores[k]:.4f}")
    if args.out_json:
        out = Path(args.out_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {k: scores[k] for k in ("GA", "PA", "FGA", "FTA")}
        payload["n_templates"] = n_templates
        out.write_text(json.dumps(payload, indent=2) + "\n")

    if args.out_md or args.append_md:
        row = (
            f"| {args.label} | {scores['GA']:.4f} | {scores['PA']:.4f} "
            f"| {scores['FGA']:.4f} | {scores['FTA']:.4f} |"
        )
        if args.out_md:
            Path(args.out_md).write_text(
                "# Trail baseline (miner v0.1, no model)\n\n"
                "| Run | GA | PA | FGA | FTA |\n"
                "|---|---|---|---|---|\n"
                f"{row}\n"
            )
        else:
            with open(args.append_md, "a") as f:
                f.write(f"{row}\n")


if __name__ == "__main__":
    main()
