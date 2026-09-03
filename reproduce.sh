#!/usr/bin/env bash
# Reproduce Trail v0.1: sample, parse, audit, score, test.
set -euo pipefail
cd "$(dirname "$0")"

uv sync --extra dev
uv run python scripts/make_sample.py
uv run python scripts/parse.py --input examples/sample.log \
  --out-csv results/parsed_sample.csv --out-audit results/audit.jsonl
uv run python scripts/score.py \
  --truth examples/sample_structured.csv --parsed results/parsed_sample.csv \
  --label "sample (60 lines, 8 templates)" --out-md results/baseline.md \
  --out-json results/raw/sample_scores.json
uv run python scripts/verify_golden.py
uv run pytest -q

# Optional Tier B cross-check: score SecOps-2k when checked out alongside.
if [ -f ../LogParser-Dataset/dataset/SecOps_2k.log ]; then
  echo "--- SecOps-2k cross-check (../LogParser-Dataset found) ---"
  uv run python scripts/parse.py --input ../LogParser-Dataset/dataset/SecOps_2k.log \
    --out-csv results/raw/secops_parsed.csv --out-audit results/raw/secops_audit.jsonl
  echo "tight:"; uv run python scripts/score.py \
    --truth ../LogParser-Dataset/dataset/SecOps_2k.log_structured.csv \
    --parsed results/raw/secops_parsed.csv \
    --label "SecOps-2k tight (25)" --append-md results/baseline.md \
    --out-json results/raw/trail_secops_tight.json
  uv run python scripts/verify_secops.py
  echo "loose:"; uv run python scripts/score.py \
    --truth ../LogParser-Dataset/dataset/SecOps_2k.log_structured_loose.csv \
    --parsed results/raw/secops_parsed.csv \
    --label "SecOps-2k loose (10)" --append-md results/baseline.md
else
  echo "(skip SecOps-2k: ../LogParser-Dataset not found)"
fi
echo "reproduce OK"
