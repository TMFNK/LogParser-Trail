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

## One-command run

```bash
./reproduce.sh
```

Needs Python 3.12+ and [uv](https://docs.astral.sh/uv/). It builds the
60-line sample, parses it, writes the audit trail, scores against
ground truth, and writes `results/baseline.md`. Under a minute. If the
Tier B checkout (`../LogParser-Dataset`) is present, it also scores
SecOps-2k and appends that row.

## Layout

```text
LogParser-Trail/
├── README.md CITATION.cff LICENSE NOTICE
├── configs/miner.yaml      # pinned: st 0.5, 2 anchor tokens
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
│   └── lm_assist.py        # local review CLI; deterministic inputs stay immutable
├── expected/sample_60.json # CI golden for the 60-line sample
├── docs/DESIGN.md          # algorithm, audit schema, known limits
├── docs/PHASE2-LM.md       # local-model review contract
├── results/                # committed sample run (parsed CSV, audit, table)
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
command aborts above 100 candidates unless `--max-candidates` is explicit,
and refuses to replace an existing `*_lm.csv` unless `--force` is passed.
`scripts/lm_assist.py` remains as a source-checkout compatibility wrapper.

## Scores

`seclog/metrics.py` in Tier B and `harness/metrics.py` in Tier A use
the same formulas. Independent Apache-2.0 code in all three repos, no
GPL eval copy anywhere.

## Manual steps

```bash
uv sync --extra dev
uv run python scripts/make_sample.py
uv run python scripts/parse.py --input examples/sample.log \
  --out-csv results/parsed_sample.csv --out-audit results/audit.jsonl
uv run python scripts/score.py --truth examples/sample_structured.csv \
  --parsed results/parsed_sample.csv \
  --out-json results/raw/sample_scores.json
uv run python scripts/verify_golden.py
uv run pytest -q
```

For private logs, choose ignored outputs:

```bash
uv run python scripts/parse.py --input /path/to/private.log \
  --out-csv results/raw/private.csv \
  --out-audit results/raw/private.audit.jsonl
```

## License

Apache-2.0, copyright 2026 MbitAI. See LICENSE and NOTICE.

Need this applied to your own log pipelines? https://www.mbitai.com
