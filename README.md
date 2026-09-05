# LogParser-Trail

Trail is a deterministic-first log template miner. Each parsed line gets
a template and a receipt: one audit record per decision, so any
template traces back to the exact lines and merges that built it.

The deterministic miner remains the parser of record. An optional local-model
assist reviews low-confidence joins and near-duplicate templates without
changing the parse CSV or audit JSONL. No scores on this page involve a model.

Keywords: log parsing, template mining, audit trail, offline, small language
models, Drain alternative.

GitHub topics: `log-parsing` `template-mining` `audit-trail` `offline`
`reproducibility` `small-language-models`

## Project pipeline

- **Tier A — [LogParser-Harness](https://github.com/TMFNK/LogParser-Harness):**
  the reproducible Drain evaluation harness for LogHub-2k and SecOps-2k.
- **Tier B — [LogParser-Dataset](https://github.com/TMFNK/LogParser-Dataset):**
  the synthetic SecOps-2k dataset, grouping rules, and pinned Drain baseline.
- **Tier C — this repository:** the deterministic-first parser, per-decision
  audit trail, SecOps-2k results, and optional local-model review.

## One-command run

```bash
./reproduce.sh
```

Needs Python 3.12+ and [uv](https://docs.astral.sh/uv/). It builds the
60-line sample, parses it, writes the audit trail, scores against
ground truth, checks `expected/sample_60.json`, writes
`results/baseline.md`, then runs the test suite. Under a minute. If the
Tier B checkout (`../LogParser-Dataset`) is present, it also parses
SecOps-2k, appends the tight and loose rows to `results/baseline.md`,
and runs the `scripts/verify_secops.py` gate.

## What is pinned

| Item                                                 | Where                                                      |
| ---------------------------------------------------- | ---------------------------------------------------------- |
| Miner `st`, `anchor_tokens`, `length_slack`, `regex` | `configs/miner.yaml` (`st: 0.5`, 2 anchors, slack 1)       |
| Sample seed and length                               | `scripts/make_sample.py` (seed 7, 60 lines, 8 templates)   |
| Metric formulas                                      | `trailparse/metrics.py` (Jiang et al., ISSTA'24 §4.2)      |
| Expected sample scores                               | `expected/sample_60.json` (GA/PA/FGA/FTA 1.0, 8 templates) |
| SecOps-2k tight gate                                 | `scripts/verify_secops.py` (FGA ≥ 0.2947, FTA ≥ 0.2526)    |
| Python deps                                          | `uv.lock`                                                  |
| CI                                                   | `.github/workflows/reproduce.yml`                          |

Each scored run also writes `results/raw/sample_scores.json` with
GA/PA/FGA/FTA and template count.

## Layout

```text
LogParser-Trail/
├── README.md CITATION.cff LICENSE NOTICE
├── configs/miner.yaml      # pinned: st 0.5, 2 anchor tokens, slack 1
├── trailparse/
│   ├── miner.py            # deterministic core (original code, no Drain copy)
│   ├── audit.py            # JSONL writer + summary
│   ├── metrics.py          # GA/PA/FGA/FTA (LogHub-2.0 formulas, Apache-2.0)
│   ├── io.py               # LogHub-shaped CSV readers/writers
│   ├── assist.py           # candidate selection + review materialization
│   ├── lm.py               # loopback-only OpenAI-compatible client
│   └── cli.py              # installed trail-lm-assist command
├── examples/               # committed 60-line labeled sample (8 templates)
├── scripts/
│   ├── make_sample.py      # seeded sample generator (seed 7)
│   ├── parse.py            # log -> structured CSV + audit JSONL
│   ├── score.py            # parsed CSV vs truth, four scores
│   ├── verify_golden.py    # sample_60 GA/PA/FGA/FTA + template count
│   ├── verify_secops.py    # SecOps-2k tight FGA/FTA gate
│   └── lm_assist.py        # local review CLI; deterministic inputs stay immutable
├── expected/sample_60.json # CI golden for the 60-line sample
├── docs/DESIGN.md          # algorithm, audit schema, known limits
├── docs/PHASE2-LM.md       # local-model review contract
├── results/                # committed sample run (parsed CSV, audit, baseline.md)
│   └── raw/                # ignored scored JSON, SecOps outputs, LM reviews
└── tests/
```

## Audit trail

`results/audit.jsonl` holds one record per line: line number, cluster,
`matched` or `new_cluster`, similarity, and the template after the
decision. That immutable file is the product as much as the templates
are. Phase 2 selects candidates from it, gets example text from the
paired structured CSV, and records model review in a separate ignored
`*.lm-review.jsonl`.

Audit records can contain values from the source log, including secrets in
the first line of a cluster. Keep real-log outputs under `results/raw/` or
another private, ignored directory. The parser refuses to replace the
committed public sample outputs from a different input unless
`--allow-public-output` is explicit.

## Local-model assist

Start an OpenAI-compatible server bound to `127.0.0.1`, then run:

```bash
uv run trail-lm-assist \
  --csv results/parsed_sample.csv \
  --audit results/audit.jsonl \
  --review results/raw/sample.lm-review.jsonl \
  --out-csv results/raw/sample_lm.csv
```

The default endpoint is `http://127.0.0.1:8090/v1` and the default model
alias is `qwen3.8-2b-q6k`; override them with `--base-url` and `--model`.
Only the literal `127.0.0.1` is accepted. The client bypasses environment
proxies, rejects redirects, and sends requests one at a time. Use `--dry-run`
to inspect candidates without contacting a model or writing outputs. The
command aborts above 100 candidates unless `--max-candidates` is explicit.
It refuses to replace an existing `*_lm.csv` unless `--force` is passed.
`scripts/lm_assist.py` remains a source-checkout compatibility wrapper.

## Metrics

Independent Apache-2.0 code (`trailparse/metrics.py`, shared with
TMFNK/LogParser-Harness and TMFNK/LogParser-Dataset). We do not copy Loghub-2.0
`benchmark/evaluation/` (GPL-3). See `docs/DESIGN.md`.

- **GA** — share of messages whose parsed group equals the ground-truth group
- **PA** — share of messages whose template tokens match exactly
- **FGA** — F1 of grouping accuracy at template level (rare and common templates equal)
- **FTA** — F1 of exact template identification (one ground-truth template
  per parsed template, with matching tokens)

## Manual steps

```bash
uv sync --frozen --extra dev
uv run python scripts/make_sample.py
uv run python scripts/parse.py --input examples/sample.log \
  --out-csv results/parsed_sample.csv --out-audit results/audit.jsonl
uv run python scripts/score.py --truth examples/sample_structured.csv \
  --parsed results/parsed_sample.csv \
  --out-json results/raw/sample_scores.json
uv run python scripts/verify_golden.py
uv run ruff check .
uv run pytest -q
```

For private logs, choose ignored outputs:

```bash
uv run python scripts/parse.py --input /path/to/private.log \
  --out-csv results/raw/private.csv \
  --out-audit results/raw/private.audit.jsonl
```

## Results

See `results/baseline.md`. The 60-line sample is the CI golden
(GA/PA/FGA/FTA 1.0, 8 templates). SecOps-2k tight and loose rows are
appended only when the Tier B checkout is present; they also have to
clear the `verify_secops.py` tight gate.

## License

Apache-2.0, copyright 2026 MbitAI. See LICENSE and NOTICE.

Need this applied to your own log pipelines? [MbitAI](https://www.mbitai.com)

## Must-cite

If you publish numbers from Trail, cite this software (see
CITATION.cff) and the LogHub papers that defined its format and metrics:

- Zhihan Jiang et al., "A Large-scale Evaluation for Log Parsing Techniques:
  How Far are We?" ISSTA, 2024. [arXiv:2308.10828](https://arxiv.org/abs/2308.10828)
- Jieming Zhu et al., "LogHub: A Large Collection of System Log Datasets for
  AI-driven Log Analytics." ISSRE, 2023. [arXiv:2008.06448](https://arxiv.org/abs/2008.06448)

## Limitations

- Header split is syntactic only. Timestamps, pids, and hostnames are
  dropped, not parsed. See `docs/DESIGN.md`.
- Token masks are a small, pinned whole-token regex list, not a general
  field parser.
- Order-dependent. A different line order can give different clusters;
  the committed sample keeps runs reproducible.
- Long lines with many variable tokens can fall below the similarity
  threshold and fragment (e.g. sudo COMMAND lines on SecOps-2k). The
  fragmentation stays visible in the audit log.
- The 60-line sample is the self-contained regression fixture. SecOps-2k
  scoring runs only when the Tier B checkout sits next to this repo.
- An accepted low-confidence split isolates the cited line; it does not
  infer whether later members should follow it. Deterministic outputs
  stay unchanged.
