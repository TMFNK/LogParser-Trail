# Trail architecture

How the pieces fit. Algorithm rationale lives in `DESIGN.md`; the review
contract in `PHASE2-LM.md`; the business reading in `SOLUTION.md`.

## Components

| Module | Role |
| --- | --- |
| `trailparse/miner.py` | Deterministic core: single-pass clustering, anchor/length/identity guards, merge, parameter extraction |
| `trailparse/io.py` | Syslog header split, LogHub-shaped CSV readers/writers, atomic file writes |
| `trailparse/audit.py` | Audit JSONL writer + summary (one record per parsed line) |
| `trailparse/metrics.py` | GA/PA/FGA/FTA per Jiang et al., ISSTA'24 §4.2 (independent Apache-2.0 implementation) |
| `trailparse/assist.py` | Review candidate selection, SAME/TWO prompt build, verdict parsing, decision application |
| `trailparse/lm.py` | Loopback-only OpenAI-compatible client (no proxies, no redirects, serialized calls) |
| `trailparse/cli.py` | Installed `trail-lm-assist` command |
| `configs/miner.yaml` | Pinned miner settings (`st`, `anchor_tokens`, `length_slack`, `regex`, `identity_keys`) |
| `scripts/parse.py` | Log → structured CSV + audit JSONL |
| `scripts/score.py` | Parsed CSV vs ground truth → GA/PA/FGA/FTA (+ markdown/JSON outputs) |
| `scripts/make_sample.py` | Seeded sample generator (seed 7, 60 lines, 8 templates) |
| `scripts/verify_golden.py` | Sample GA/PA/FGA/FTA + template-count gate |
| `scripts/verify_secops.py` | SecOps-2k tight FGA/FTA gate vs pinned Drain baseline |
| `scripts/lm_assist.py` | Source-checkout compatibility wrapper for `trail-lm-assist` |

## Execution flow

1. `make_sample.py` builds the labeled 60-line fixture (`examples/`).
   The generator is the annotator: each line's source template is its
   ground truth.
2. `parse.py` loads `configs/miner.yaml`, feeds each message line through
   `Miner.feed`, then emits rows using each cluster's **final** template
   (templates only generalize as later lines merge in).
3. `audit.py` writes one JSONL record per line alongside the CSV. The two
   files are joined by `LineId`/`line` and cross-validated before any review.
4. `score.py` aligns parsed rows to ground truth by `LineId` and computes
   GA/PA/FGA/FTA; `verify_golden.py` / `verify_secops.py` enforce the gates.
5. Optionally, `trail-lm-assist` selects low-confidence joins and
   near-duplicate pairs from the audit trail, reviews each with the local
   model, appends verdicts to `*.lm-review.jsonl`, and materializes accepts
   into a separate `*_lm.csv`. Deterministic outputs are never mutated;
   digests are re-checked before and after every model call.

## Data flow

```text
raw log ──parse.py──▶ structured CSV ──score.py──▶ GA/PA/FGA/FTA
                │            │                        ▲
                │            ▼                        │
                └───── audit JSONL ──trail-lm-assist──┘
                                     (review JSONL + separate *_lm.csv)
```

## Test layout

- `tests/unit/` — miner core, audit schema, IO, metrics, assist selection
  and decisions, loopback client, scoring, output-safety guards, SecOps gate.
- `tests/integration/` — committed-sample fixture check, committed
  `lm_scores.json` summary check, end-to-end CLI (review + assisted CSV
  without mutating inputs).

`./reproduce.sh` exercises the full chain: sample → parse → audit → score →
golden gate → test suite, plus the SecOps-2k cross-check when the Tier B
checkout sits alongside this repo.
