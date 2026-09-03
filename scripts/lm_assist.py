# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""Review deterministic parse candidates with a local OpenAI-compatible model."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trailparse import audit as audit_mod  # noqa: E402
from trailparse import io as io_mod  # noqa: E402
from trailparse.assist import (  # noqa: E402
    append_review,
    apply_decisions,
    review_candidate,
    select_candidates,
)
from trailparse.lm import (  # noqa: E402
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    LocalModelClient,
)

RAW_RESULTS = (ROOT / "results" / "raw").resolve()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_paths(
    csv_path: Path,
    audit_path: Path,
    review_path: Path,
    out_csv: Path | None,
) -> None:
    inputs = {csv_path.resolve(), audit_path.resolve()}
    if len(inputs) != 2:
        raise ValueError("CSV and audit inputs must be different files")
    if review_path.resolve() in inputs:
        raise ValueError("review output cannot overwrite an input")
    if not review_path.name.endswith(".lm-review.jsonl"):
        raise ValueError("review output must end with .lm-review.jsonl")
    if not review_path.resolve().is_relative_to(RAW_RESULTS):
        raise ValueError("review output must be under results/raw/")
    if out_csv is not None:
        if out_csv.resolve() in inputs or out_csv.resolve() == review_path.resolve():
            raise ValueError("assisted CSV cannot overwrite an input or review log")
        if not out_csv.name.endswith("_lm.csv"):
            raise ValueError("assisted CSV must end with _lm.csv")
        if not out_csv.resolve().is_relative_to(RAW_RESULTS):
            raise ValueError("assisted CSV must be under results/raw/")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="immutable structured CSV")
    ap.add_argument("--audit", required=True, help="immutable parse audit JSONL")
    ap.add_argument(
        "--review",
        default="results/raw/trail.lm-review.jsonl",
        help="append-only review JSONL under results/raw/",
    )
    ap.add_argument(
        "--out-csv",
        default="",
        help="optional assisted CSV under results/raw/, ending in _lm.csv",
    )
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="list candidates without calling a model or writing outputs",
    )
    args = ap.parse_args()

    csv_path = Path(args.csv)
    audit_path = Path(args.audit)
    review_path = Path(args.review)
    out_csv = Path(args.out_csv) if args.out_csv else None
    try:
        validate_paths(csv_path, audit_path, review_path, out_csv)
    except ValueError as exc:
        ap.error(str(exc))

    before = {csv_path: sha256(csv_path), audit_path: sha256(audit_path)}
    records = audit_mod.read_jsonl(audit_path)
    rows = io_mod.read_structured(csv_path)
    candidates = select_candidates(records, rows)
    print(f"selected {len(candidates)} candidates")
    if args.dry_run:
        for candidate in candidates:
            print(
                f"{candidate.kind}: {','.join(candidate.cluster_ids)} "
                f"audit lines={list(candidate.cited_audit_lines)}"
            )
        return

    try:
        client = LocalModelClient(args.base_url, args.model, args.timeout)
    except ValueError as exc:
        ap.error(str(exc))
    reviews = []
    for candidate in candidates:
        review = review_candidate(
            candidate,
            client,
            audit_sha256=before[audit_path],
            csv_sha256=before[csv_path],
        )
        append_review(review_path, review)
        reviews.append(review)
        print(
            f"{candidate.kind} {','.join(candidate.cluster_ids)}: "
            f"{review['decision']} ({review['reason']})"
        )
        if review["response"].get("error"):
            raise SystemExit(
                f"local model request failed; rejection recorded in {review_path}"
            )

    if out_csv is not None:
        io_mod.write_structured(apply_decisions(rows, reviews), out_csv)
        print(f"wrote assisted CSV to {out_csv}")

    after = {csv_path: sha256(csv_path), audit_path: sha256(audit_path)}
    if after != before:
        raise RuntimeError("immutable input changed during LM review")


if __name__ == "__main__":
    main()
