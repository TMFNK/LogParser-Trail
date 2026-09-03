# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""Fail when Trail drops below the locked SecOps tight Drain gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

MINIMUMS = {"FGA": 0.2947, "FTA": 0.2526}


def failures(scores: dict) -> list[str]:
    failed = []
    for key, minimum in MINIMUMS.items():
        actual = float(scores[key])
        if actual < minimum:
            failed.append(f"{key}: required >= {minimum}, got {actual}")
    return failed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--actual",
        default="results/raw/trail_secops_tight.json",
        help="JSON produced by scripts/score.py --out-json",
    )
    args = ap.parse_args()

    path = Path(args.actual)
    if not path.exists():
        raise SystemExit(f"missing SecOps scores {path}")
    failed = failures(json.loads(path.read_text()))
    if failed:
        raise SystemExit("SecOps tight gate failed:\n  " + "\n  ".join(failed))
    print(
        f"ok: SecOps tight FGA >= {MINIMUMS['FGA']} "
        f"and FTA >= {MINIMUMS['FTA']}"
    )


if __name__ == "__main__":
    main()
