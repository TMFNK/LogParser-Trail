# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""Parse a log file with the Trail miner: structured CSV plus audit JSONL."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trailparse import Miner  # noqa: E402
from trailparse import audit as audit_mod  # noqa: E402
from trailparse import io as io_mod  # noqa: E402
from trailparse.miner import Cluster  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="log file to parse")
    ap.add_argument("--out-csv", required=True, help="structured CSV output")
    ap.add_argument("--out-audit", required=True, help="audit JSONL output")
    args = ap.parse_args()

    cfg = yaml.safe_load((ROOT / "configs" / "miner.yaml").read_text())
    miner = Miner(
        st=float(cfg["st"]),
        anchor_tokens=int(cfg["anchor_tokens"]),
        length_slack=int(cfg.get("length_slack", 0)),
        regex=list(cfg.get("regex") or []),
    )

    fed: list[tuple[int, str, Cluster]] = []
    for i, raw in enumerate(io_mod.read_log(Path(args.input)), start=1):
        content = io_mod.split_header(raw)
        fed.append((i, content, miner.feed(i, content)))

    # Templates only generalize as later lines merge in, so emit rows
    # after the full pass, using each cluster's final template.
    rows: list[dict] = []
    for i, content, cluster in fed:
        rows.append(
            {
                "LineId": i,
                "Content": content,
                "EventId": cluster.cid,
                "EventTemplate": miner.template_of(cluster),
                "ParameterList": repr(miner.params_for(content, cluster)),
            }
        )
    io_mod.write_structured(rows, Path(args.out_csv))
    audit_mod.write_jsonl(miner.decisions, Path(args.out_audit))
    summary = audit_mod.summarize(miner.decisions)
    print(
        f"parsed {summary['n_lines']} lines -> "
        f"{len(miner.clusters)} templates, audit in {args.out_audit}"
    )


if __name__ == "__main__":
    main()
