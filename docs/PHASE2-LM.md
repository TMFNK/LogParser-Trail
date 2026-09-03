# Phase 2: local-model assist (planned, not built)

The deterministic core stays. The model only proposes template merges
and splits, and every proposal cites the audit records behind it. A
human or a threshold accepts them. Nothing parses without a trail.

## Loop

1. Run the miner. Read `results/audit.jsonl`.
2. Flag low-confidence joins (similarity under 0.7) and near-duplicate
   clusters (templates one token apart) as review candidates.
3. Send each candidate, with 3 example lines, to a local small model
   over an OpenAI-compatible endpoint (`127.0.0.1`, same pattern as
   the Tier A harness server script). Ask one question: same event or
   two? No log leaves the machine.
4. Accepted proposals rewrite the cluster table. Rejected ones are
   logged with the reason. Both end up in the audit file.

## Model

Small and local. Qwen3-class 2–4B quant, CPU-served, one request at a
time. The candidate set is tiny (dozens of clusters, not thousands of
lines), so this runs on the same 8 GB Mac as everything else here.

## Non-goals

No cloud APIs. No fine-tuning in Phase 2. No model output that bypasses
the audit log. If a decision cannot point at audit records, it did not
happen.
