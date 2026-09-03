# LogParser-Trail

Trail is a deterministic-first log template miner. Each parsed line gets
a template and a receipt: one audit record per decision, so any
template traces back to the exact lines and merges that built it.

v0.1 is the deterministic core only. Planned model assist:
`docs/PHASE2-LM.md` (stub in `scripts/lm_assist.py`). No scores on this
page involve a model.

Keywords: log parsing, template mining, audit trail, offline, Drain
alternative.

GitHub topics: `log-parsing` `template-mining` `audit-trail` `offline`
`reproducibility`

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
│   └── io.py               # LogHub-shaped CSV readers/writers
├── examples/               # committed 60-line labeled sample (8 templates)
├── scripts/
│   ├── make_sample.py      # seeded sample generator (seed 7)
│   ├── parse.py            # log -> structured CSV + audit JSONL
│   ├── score.py            # parsed CSV vs truth, four scores
│   ├── verify_golden.py    # sample_60 GA/PA/FGA/FTA + template count
│   └── lm_assist.py        # Phase 2 stub (exits 2, not wired)
├── expected/sample_60.json # CI golden for the 60-line sample
├── docs/DESIGN.md          # algorithm, audit schema, known limits
├── docs/PHASE2-LM.md       # the planned model loop
├── results/                # committed sample run (parsed CSV, audit, table)
└── tests/
```

## Audit trail

`results/audit.jsonl` holds one record per line: line number, cluster,
`matched` or `new_cluster`, similarity, and the template after the
decision. That file is the product as much as the templates are. Phase
2 reads it instead of re-reading the logs.

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

## License

Apache-2.0, copyright 2026 MbitAI. See LICENSE and NOTICE.

Need this applied to your own log pipelines? https://www.mbitai.com
