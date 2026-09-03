# Phase 2: local-model assist (planned, not built)

The deterministic core stays. The model only proposes template merges
and splits, and every proposal cites the audit records behind it. A
human or a threshold accepts them. Nothing parses without a trail.

## Artifact ownership

- The structured CSV and parse audit JSONL are immutable deterministic
  outputs. Model assist never edits or replaces either file.
- Candidate examples come from the structured CSV `Content` column,
  joined to audit records by `LineId` / `line`.
- Model requests, responses, and accept/reject decisions go to a separate
  append-only `*.lm-review.jsonl` under the ignored `results/raw/` directory.
- Any assisted CSV is a new `*_lm.csv` file. The deterministic CSV remains
  the parser of record and its scores stay separate.

## Loop

1. Run the miner. Read its audit JSONL and paired structured CSV.
2. Flag low-confidence joins (similarity under 0.7) and near-duplicate
   clusters whose final templates have token-level edit distance one.
3. Send each candidate, with 3 example lines, to a local small model
   over an OpenAI-compatible endpoint (`127.0.0.1`, same pattern as
   the Tier A harness server script). Ask one question: same event or
   two? No log leaves the machine.
4. Append the proposal, cited audit lines, model identity, prompt version,
   raw response, and accept/reject reason to `*.lm-review.jsonl`.
5. If accepted decisions are applied, write a new assisted CSV. Do not
   mutate the deterministic CSV or parse audit.

## Model

Small and local. Qwen3-class 2–4B quant, CPU-served, one request at a
time. The candidate set is tiny (dozens of clusters, not thousands of
lines), so this runs on the same 8 GB Mac as everything else here.

## Non-goals

No cloud APIs. No fine-tuning in Phase 2. No model output that bypasses
the review log. If a decision cannot point at immutable parse-audit records,
it did not happen.
