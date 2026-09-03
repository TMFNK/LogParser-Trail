# Trail miner design (v0.1)

One pass, no models, no training. Each line joins the best matching
cluster or starts a new one. The point of v0.1 is not top scores. It is
a deterministic core whose every decision can be inspected, so the
Phase 2 model assists grouping instead of replacing it.

## Algorithm

1. Strip the syslog header (`Mon DD HH:MM:SS host proc[pid]:`,
   one regex in `trailparse/io.py`). Only the message part is mined.
   Lines that do not match the shape pass through unchanged.
2. Split the message on whitespace. Configured token regexes use
   `fullmatch`; matching tokens are replaced with `<*>`.
3. Candidates are clusters whose token counts differ by at most
   `length_slack` (1) and whose first `anchor_tokens` (2) match exactly.
   Anything else cannot merge.
4. Among candidates, take the highest token similarity. Exact tokens and
   template `<*>` positions count as matches; the denominator is the
   longer token count. Join at `st >= 0.5`, else open a new cluster
   `T<n>`.
5. On join, positions that differ or exist on only one side become `<*>`
   for good. Templates only ever generalize, never split.

Settings live in `configs/miner.yaml` and are pinned.

## Why anchors

Similarity alone merges lines that differ in exactly one outcome word.
`Failed password …` and `Accepted password …` agree on every token but
one, so a pure threshold puts them in the same template. The anchor
rule (first two tokens must match) keeps outcomes apart without any
per-dataset tuning. It is a heuristic, not a principle, and the audit
log shows everywhere it fires.

## Audit schema (v1)

`results/audit.jsonl`, one record per line:

```json
{"line": 12, "cluster": "T3", "decision": "matched",
 "similarity": 0.875, "template": "Failed password for <*> ..."}
```

`decision` is `new_cluster` (similarity 0.0) or `matched`. Phase 2
reads this file to find low-confidence joins and propose fixes. The
format is versioned: readers must ignore unknown fields, writers must
not rename existing ones.

The parse audit is an immutable receipt. Model proposals and human or
threshold decisions belong in a separate append-only `*.lm-review.jsonl`
that cites parse-audit line numbers and a digest of the source audit.
Example text comes from the paired structured CSV, joined by `LineId`.
An assisted parse, if produced, is a separate CSV; it never replaces the
deterministic parser output.

## Local-model review

The optional assist joins audit `line` to structured CSV `LineId`. It selects
matched decisions below `0.7` similarity and pairs of final cluster templates
whose token-level Levenshtein edit distance is one. A candidate is sent only
when three distinct cited example lines are available.

Prompt version `trail-lm-v1` asks for exactly `SAME` or `TWO`. For a
low-confidence join, `TWO` accepts splitting the cited target line. For a
near-duplicate pair, `SAME` accepts merging the clusters. Any absent,
conflicting, or otherwise unparseable answer is rejected. Accepted changes
are materialized only in a separate `*_lm.csv`.

The append-only review schema is `lm-review-v1`. Every record stores source
SHA-256 digests, cited audit lines, examples, templates, request payload,
prompt version, model identity, raw and parsed response, decision, change,
and reason. Model traffic uses direct HTTP to literal `127.0.0.1`; proxies,
redirects, hostnames, TLS endpoints, and concurrent requests are disallowed.

## Known limits

- Header split is syntactic only. Timestamps, pids, and hostnames are
  dropped, not parsed. No per-field semantics yet.
- Token masks are a small, pinned list of whole-token regexes, not a
  general field parser.
- Order-dependent. A different line order can give different clusters.
  The sample is committed, so runs are reproducible anyway.
- Long lines with many variable tokens fall below the similarity
  threshold and can still fragment. On SecOps-2k, sudo COMMAND lines can
  split by username or by token-count differences greater than one. The
  fragmentation inventory remains visible in the audit log.
- The committed 60-line sample is the self-contained regression fixture.
  SecOps-2k scoring runs only when the Tier B checkout sits next to this
  repo (see `./reproduce.sh`).
- A low-confidence accepted split isolates the cited line; it does not infer
  whether later members should follow it. The review artifact remains
  inspectable and the deterministic output remains unchanged.
