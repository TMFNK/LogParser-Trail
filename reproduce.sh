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

# Optional local-model assist: ./reproduce.sh --lm lists candidates without
# a server (--dry-run) and runs the full v2 review + scoring only when a
# local OpenAI-compatible server answers on 127.0.0.1:8090.
# Review JSONL is append-only: rm results/raw/secops-v2.lm-review.jsonl
# for a clean re-run, otherwise this appends 16 duplicate lines.
LM_REQUESTED=0
for arg in ${@+"$@"}; do
  if [ "$arg" = "--lm" ]; then
    LM_REQUESTED=1
    break
  fi
done
if [ "$LM_REQUESTED" = 1 ]; then
  if [ ! -f results/raw/secops_parsed.csv ] || [ ! -f results/raw/secops_audit.jsonl ]; then
    echo "(skip LM assist: results/raw/secops_parsed.csv not found; needs Tier B checkout)"
  else
    echo "--- LM assist candidates (dry-run, no server needed) ---"
    uv run trail-lm-assist \
      --csv results/raw/secops_parsed.csv \
      --audit results/raw/secops_audit.jsonl \
      --review results/raw/secops-v2.lm-review.jsonl --dry-run
    if curl --noproxy '*' -s -m 5 http://127.0.0.1:8090/v1/models > /dev/null 2>&1; then
      echo "--- LM assist review (trail-lm-v2, local server found) ---"
      uv run trail-lm-assist \
        --csv results/raw/secops_parsed.csv \
        --audit results/raw/secops_audit.jsonl \
        --review results/raw/secops-v2.lm-review.jsonl \
        --out-csv results/raw/secops_v2_lm.csv --force
      uv run python scripts/score.py \
        --truth ../LogParser-Dataset/dataset/SecOps_2k.log_structured.csv \
        --parsed results/raw/secops_v2_lm.csv \
        --label "SecOps-2k tight + LM v2" \
        --out-json results/raw/secops_v2_tight.json
      uv run python scripts/score.py \
        --truth ../LogParser-Dataset/dataset/SecOps_2k.log_structured_loose.csv \
        --parsed results/raw/secops_v2_lm.csv \
        --label "SecOps-2k loose + LM v2" \
        --out-json results/raw/secops_v2_loose.json
    else
      echo "(skip LM review: no server on 127.0.0.1:8090; start e.g. llama-server -m Qwen3.8-2B-Q6_K.gguf --host 127.0.0.1 --port 8090)"
    fi
  fi
fi
echo "reproduce OK"
