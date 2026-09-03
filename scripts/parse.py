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

PUBLIC_SAMPLE_INPUT = (ROOT / "examples" / "sample.log").resolve()
PUBLIC_SAMPLE_OUTPUTS = {
    (ROOT / "results" / "parsed_sample.csv").resolve(),
    (ROOT / "results" / "audit.jsonl").resolve(),
}


def validate_output_paths(
    input_path: Path,
    out_csv: Path,
    out_audit: Path,
    *,
    allow_public_output: bool = False,
) -> None:
    source = input_path.resolve()
    csv_path = out_csv.resolve()
    audit_path = out_audit.resolve()
    if csv_path == audit_path:
        raise ValueError("CSV and audit output paths must be different")
    if source in {csv_path, audit_path}:
        raise ValueError("an output path cannot overwrite the input log")
    if (
        not allow_public_output
        and source != PUBLIC_SAMPLE_INPUT
        and {csv_path, audit_path} & PUBLIC_SAMPLE_OUTPUTS
    ):
        raise ValueError(
            "refusing to write a real log to a committed public example; "
            "use results/raw/ or pass --allow-public-output"
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="log file to parse")
    ap.add_argument("--out-csv", required=True, help="structured CSV output")
    ap.add_argument("--out-audit", required=True, help="audit JSONL output")
    ap.add_argument(
        "--allow-public-output",
        action="store_true",
        help="allow a non-sample log to replace committed public examples",
    )
    args = ap.parse_args()
    input_path = Path(args.input)
    out_csv = Path(args.out_csv)
    out_audit = Path(args.out_audit)
    try:
        validate_output_paths(
            input_path,
            out_csv,
            out_audit,
            allow_public_output=args.allow_public_output,
        )
    except ValueError as exc:
        ap.error(str(exc))

    cfg = yaml.safe_load((ROOT / "configs" / "miner.yaml").read_text())
    miner = Miner(
        st=float(cfg["st"]),
        anchor_tokens=int(cfg["anchor_tokens"]),
        length_slack=int(cfg.get("length_slack", 0)),
        regex=list(cfg.get("regex") or []),
    )

    fed: list[tuple[int, str, Cluster]] = []
    for i, raw in enumerate(io_mod.read_log(input_path), start=1):
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
    io_mod.write_structured(rows, out_csv)
    audit_mod.write_jsonl(miner.decisions, out_audit)
    summary = audit_mod.summarize(miner.decisions)
    print(
        f"parsed {summary['n_lines']} lines -> "
        f"{len(miner.clusters)} templates, audit in {args.out_audit}"
    )


if __name__ == "__main__":
    main()
