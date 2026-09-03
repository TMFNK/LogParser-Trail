# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""Command-line entry point for local-model review."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

from trailparse import io as io_mod
from trailparse.assist import (
    DEFAULT_MAX_CANDIDATES,
    append_review,
    apply_decisions,
    review_candidate,
    select_candidates,
)
from trailparse.lm import DEFAULT_BASE_URL, DEFAULT_MODEL, LocalModelClient


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_snapshots(
    csv_path: Path, audit_path: Path
) -> tuple[list[dict], list[dict], dict[Path, str]]:
    csv_bytes = csv_path.read_bytes()
    audit_bytes = audit_path.read_bytes()
    rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8"))))
    records = [
        json.loads(line)
        for line in audit_bytes.decode("utf-8").splitlines()
        if line
    ]
    return (
        rows,
        records,
        {csv_path: _digest(csv_bytes), audit_path: _digest(audit_bytes)},
    )


def _ensure_unchanged(expected: dict[Path, str]) -> None:
    for path, digest in expected.items():
        if _digest(path.read_bytes()) != digest:
            raise RuntimeError(f"immutable input changed during review: {path}")


def validate_paths(
    csv_path: Path,
    audit_path: Path,
    review_path: Path,
    out_csv: Path | None,
    raw_results: Path,
    *,
    force: bool,
) -> None:
    inputs = {csv_path.resolve(), audit_path.resolve()}
    if len(inputs) != 2:
        raise ValueError("CSV and audit inputs must be different files")
    if review_path.resolve() in inputs:
        raise ValueError("review output cannot overwrite an input")
    if not review_path.name.endswith(".lm-review.jsonl"):
        raise ValueError("review output must end with .lm-review.jsonl")
    if not review_path.resolve().is_relative_to(raw_results.resolve()):
        raise ValueError("review output must be under results/raw/")
    if out_csv is None:
        return
    if out_csv.resolve() in inputs or out_csv.resolve() == review_path.resolve():
        raise ValueError("assisted CSV cannot overwrite an input or review log")
    if not out_csv.name.endswith("_lm.csv"):
        raise ValueError("assisted CSV must end with _lm.csv")
    if not out_csv.resolve().is_relative_to(raw_results.resolve()):
        raise ValueError("assisted CSV must be under results/raw/")
    if out_csv.exists() and not force:
        raise ValueError(f"assisted CSV already exists: {out_csv} (use --force)")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="immutable structured CSV")
    parser.add_argument("--audit", required=True, help="immutable parse audit JSONL")
    parser.add_argument(
        "--review",
        default="results/raw/trail.lm-review.jsonl",
        help="append-only review JSONL under results/raw/",
    )
    parser.add_argument(
        "--out-csv",
        default="",
        help="optional assisted CSV under results/raw/, ending in _lm.csv",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace an existing assisted CSV; review JSONL still appends",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=DEFAULT_MAX_CANDIDATES,
        help=f"abort above this many candidates (default: {DEFAULT_MAX_CANDIDATES})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list candidates without calling a model or writing outputs",
    )
    return parser


def main() -> None:
    parser = _parser()
    args = parser.parse_args()
    csv_path = Path(args.csv)
    audit_path = Path(args.audit)
    review_path = Path(args.review)
    out_csv = Path(args.out_csv) if args.out_csv else None
    raw_results = (Path.cwd() / "results" / "raw").resolve()
    try:
        validate_paths(
            csv_path,
            audit_path,
            review_path,
            out_csv,
            raw_results,
            force=args.force,
        )
        rows, records, digests = _read_snapshots(csv_path, audit_path)
        candidates = select_candidates(
            records, rows, max_candidates=args.max_candidates
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        parser.error(str(exc))

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
        parser.error(str(exc))
    reviews = []
    for candidate in candidates:
        review = review_candidate(
            candidate,
            client,
            audit_sha256=digests[audit_path],
            csv_sha256=digests[csv_path],
        )
        try:
            _ensure_unchanged(digests)
        except (OSError, RuntimeError) as exc:
            raise SystemExit(str(exc)) from exc
        try:
            append_review(review_path, review)
        except OSError as exc:
            raise SystemExit(f"cannot append review log: {exc}") from exc
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
        try:
            _ensure_unchanged(digests)
            if out_csv.exists() and not args.force:
                raise RuntimeError(
                    f"assisted CSV already exists: {out_csv} (use --force)"
                )
            assisted = apply_decisions(rows, reviews)
        except (OSError, RuntimeError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        try:
            io_mod.write_structured(assisted, out_csv)
        except OSError as exc:
            raise SystemExit(f"cannot write assisted CSV: {exc}") from exc
        print(f"wrote assisted CSV to {out_csv}")
