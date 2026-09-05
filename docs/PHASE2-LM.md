# Phase 2: local-model assist

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
3. Send each candidate that has 3 distinct example lines to a local small model
   over an OpenAI-compatible endpoint (`127.0.0.1`, same pattern as
   the Tier A harness server script). Prompt version `trail-lm-v2` sends a
   short judge preamble before the question: SAME/TWO definitions (variable-
   only diff vs different action/outcome), SecOps rules (Accepted vs Failed,
   BLOCK vs ALLOW, TCP vs UDP/ICMP are TWO; IP/port/pid/user-only diffs are
   SAME; unsure defaults to SAME), one SAME and one TWO counterexample, and
   the miner similarity for low-confidence joins. Then ask one question:
   same event or two? No log leaves the machine.
4. Append the proposal, cited audit lines, affected-line count, model identity, prompt version,
   raw response, and accept/reject/needs-human reason to `*.lm-review.jsonl`.
5. If accepted decisions are applied, write a new assisted CSV. Do not
   mutate the deterministic CSV or parse audit. Accepts touching more
   than `MAX_AUTO_AFFECTED` lines (10) are recorded as `needs-human`
   and never materialized: splitting one line out of a large pure
   cluster, or merging two big clusters, rewrites too much grouping
   for an unattended model verdict.

The installed `trail-lm-assist` command implements this loop
(`scripts/lm_assist.py` is a compatibility wrapper). It validates matching
line sets, cluster ids, and final templates before review. A reply is accepted
only when it contains one unambiguous `SAME` or `TWO` decision after any Qwen
`<think>` block is removed. For low-confidence joins, example 1 is explicitly
the target line. `TWO` accepts that split; `SAME` accepts an equal-length
near-duplicate merge. Unequal-length merges and conflicted merge components
are not materialized. Other replies are rejected and still recorded. A failed
request is recorded as a rejection before the CLI stops.

The client uses Python's direct `HTTPConnection` to the literal `127.0.0.1`.
It does not read proxy environment variables, does not resolve hostnames, and
does not follow redirects. Calls are serialized with one in-flight request.
The lock is shared across client instances and, on POSIX, processes.
Responses are limited to 1 MiB and the configured timeout is an overall read
deadline.

Each review record uses schema `lm-review-v1` and contains the candidate kind,
cluster ids, cited audit lines, examples, templates, source-file SHA-256
digests, prompt version (`trail-lm-v2`; schema version is independent of
prompt version), exact request, model identity, raw response, parsed
proposal, decision, change, and reason. Review records embed raw log
`Content` as examples and are as sensitive as the parse audit: keep them
under ignored `results/raw/`.

The command aborts above 100 candidates by default; raising
`--max-candidates` is explicit. Existing assisted CSVs are preserved unless
`--force` is passed. Review JSONL always remains append-only.

## Model

Small and local. Qwen3-class 2–4B quant, CPU-served, one request at a
time. The candidate set is tiny (dozens of clusters, not thousands of
lines), so this runs on the same 8 GB Mac as everything else here.

## Non-goals

No cloud APIs. No fine-tuning in Phase 2. No model output that bypasses
the review log. If a decision cannot point at immutable parse-audit records,
it did not happen.
