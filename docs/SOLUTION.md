# Trail as a business solution (MbitAI)

Who this is for, what it buys you, and how it is delivered. The technical
detail lives in [`trail-techreport.pdf`](../trail-techreport.pdf),
`DESIGN.md`, and `PHASE2-LM.md`.

## The problem in one paragraph

Every SOC, NOC, and platform team pays for log analytics, yet the parsing
layer underneath is usually uninspectable: when the miner merges two event
types, every detector, dashboard, and incident report built on top inherits
the error silently — and nobody can show which lines produced which
template. Cloud-model parsers fix accuracy at the price of shipping
authentication logs, firewall denials, and usernames to a third party.
Trail exists so you do not have to choose between accuracy and control.

## What Trail delivers

- **Structured events from raw logs.** LogHub-shaped CSV out
  (`LineId, Content, EventId, EventTemplate, ParameterList`) that drops
  straight into existing SIEM / lakehouse / notebook workflows.
- **A receipt for every decision.** One audit record per line — cluster,
  decision, similarity, resulting template. Any template traces back to the
  exact lines and merges that built it. That is the artifact auditors,
  incident reviewers, and customer security questionnaires ask for.
- **Deterministic, pinned, reproducible.** One command (`./reproduce.sh`)
  rebuilds the sample, re-parses, re-scores, and checks the golden fixture
  in under a minute. A parse delivered to a customer re-runs bit-identically
  months later.
- **Offline and data-sovereign.** Parsing needs no network. The optional
  model review runs against a loopback-local 2B quant on commodity hardware
  (measured: Apple M2, 8 GB RAM, CPU) — no cloud account, no per-token bill,
  no data-protection addendum, nothing parsed leaves the machine.
- **Honest scoring.** GA/PA/FGA/FTA per the LogHub-2.0 definitions, with a
  pinned Drain baseline as the gate: Trail clears SecOps-2k tight at
  FGA/FTA 0.8627 against Drain's 0.2947/0.2526.

## Who buys it

| Buyer | Pain | Trail answer |
| --- | --- | --- |
| SecOps / SOC lead | Noisy templates, missed groupings, unauditable detections | 26 templates vs Drain's 70 on the same 2k lines; every grouping cited in the audit log |
| Platform / SRE | Log pipeline changes nobody can diff or roll back safely | Pinned config + golden fixture + CI gate; parse diffs are reviewable |
| Compliance / CISO | Log data in scope for GDPR / sectoral rules; cloud LLMs need DPAs | Fully offline core; loopback-only local review; secrets-handling documented in README |
| MSP / consultancy | Customer-specific log formats, per-engagement tuning cost | One pinned config, small mask list, sample-driven onboarding per customer |

## Engagement shapes (MbitAI)

1. **Assessment (fixed scope).** Your sample logs in, parsed CSV + audit
   trail + scorecard out, under NDA, on your hardware or ours. Go/no-go on
   numbers, not slides.
2. **Pilot (your pipeline).** Trail parses a live feed next to your current
   miner; grouping quality and template-count deltas are measured on your
   data with the same GA/PA/FGA/FTA scorecard.
3. **Production + handover.** Pinned config for your formats, CI golden
   fixtures from your logs, runbooks for re-parse and review, team training
   on the audit trail. Optional local-model review sized to your hardware.

Contact: [https://www.mbitai.com](https://www.mbitai.com)

## Costs to budget (measured, not estimated)

| Item | Observed |
| --- | --- |
| Deterministic parse + score + tests | Under a minute, no GPU, no network |
| Local model load (2B Q6_K, CPU) | ~40 s one-off, ~3.7 GB resident |
| Review throughput | ~29 s per candidate; candidate sets number in the dozens |
| License | Apache-2.0; weights used are Apache-2.0 (keeps your tree license-clean) |

No per-seat, per-GB, or per-token metering exists in the deterministic core.
Model review cost is your local compute only.

## Limits, stated plainly

- Header split is syntactic; timestamps/pids/hostnames are dropped, not parsed.
- Masks are a small pinned whole-token list, not a general field parser.
- Order-dependent clustering; reproducibility comes from committed fixtures.
- Long, highly-variable lines can still fragment (visible in the audit log).
- An accepted split isolates the cited line; it does not re-infer later members.

These are documented in `DESIGN.md` because enterprise buyers should find
limits before the pilot does — and because each one is observable in the
audit trail rather than hidden in model weights.
