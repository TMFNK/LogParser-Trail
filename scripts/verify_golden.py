# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""Fail if scored sample metrics drift from expected/sample_60.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEYS = ("GA", "PA", "FGA", "FTA")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--expected",
        default=str(ROOT / "expected" / "sample_60.json"),
    )
    ap.add_argument(
        "--actual",
        default=str(ROOT / "results" / "raw" / "sample_scores.json"),
    )
    ap.add_argument("--atol", type=float, default=1e-6)
    args = ap.parse_args()

    expected = json.loads(Path(args.expected).read_text())
    actual_path = Path(args.actual)
    if not actual_path.exists():
        raise SystemExit(f"missing scores {actual_path}")
    actual = json.loads(actual_path.read_text())

    failed = []
    for key in KEYS:
        exp = float(expected[key])
        got = float(actual[key])
        if abs(exp - got) > args.atol:
            failed.append(f"{key}: expected {exp}, got {got}")
    if "n_templates" in expected:
        exp_n = int(expected["n_templates"])
        got_n = int(actual["n_templates"])
        if exp_n != got_n:
            failed.append(f"n_templates: expected {exp_n}, got {got_n}")
    if failed:
        raise SystemExit("golden mismatch:\n  " + "\n  ".join(failed))
    print(f"ok: {actual_path} matches {args.expected}")


if __name__ == "__main__":
    main()
