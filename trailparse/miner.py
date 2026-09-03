# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""Trail v0.1: deterministic template miner with per-decision audit.

One pass over the lines. Each line either joins the best matching
cluster or starts a new one. Every decision is recorded in the audit
log, so any template can be traced back to the exact lines and merges
that produced it. See docs/DESIGN.md for the algorithm and its limits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

WILDCARD = "<*>"


@dataclass
class Cluster:
    cid: str
    template: list[str]
    count: int = 0
    members: list[int] = field(default_factory=list)


@dataclass
class Decision:
    line_id: int
    cluster: str
    decision: str  # "new_cluster" or "matched"
    similarity: float
    template_after: str


def similarity(tokens: list[str], template: list[str], slack: int = 0) -> float:
    if not tokens or not template:
        return 0.0
    if abs(len(tokens) - len(template)) > slack:
        return 0.0
    n = max(len(tokens), len(template))
    matched = 0
    for tok, tmpl in zip(tokens, template):
        if tmpl == WILDCARD or tok == tmpl:
            matched += 1
    return matched / n


def merge(template: list[str], tokens: list[str]) -> list[str]:
    n = max(len(template), len(tokens))
    out: list[str] = []
    for i in range(n):
        tmpl = template[i] if i < len(template) else WILDCARD
        tok = tokens[i] if i < len(tokens) else WILDCARD
        out.append(tmpl if tmpl == tok else WILDCARD)
    return out


class Miner:
    def __init__(
        self,
        st: float = 0.5,
        anchor_tokens: int = 2,
        length_slack: int = 0,
        regex: list[str] | None = None,
    ) -> None:
        self.st = st
        self.anchor_tokens = anchor_tokens
        self.length_slack = length_slack
        self.token_masks = [re.compile(p) for p in (regex or [])]
        self.clusters: list[Cluster] = []
        self.decisions: list[Decision] = []

    def _mask(self, tokens: list[str]) -> list[str]:
        if not self.token_masks:
            return tokens
        out = []
        for tok in tokens:
            for cre in self.token_masks:
                if cre.fullmatch(tok):
                    tok = WILDCARD
                    break
            out.append(tok)
        return out

    def _candidates(self, tokens: list[str]) -> list[Cluster]:
        n_anchor = self.anchor_tokens
        if len(tokens) < n_anchor:
            return []
        anchor = tokens[:n_anchor]
        return [
            c
            for c in self.clusters
            if abs(len(c.template) - len(tokens)) <= self.length_slack
            and len(c.template) >= n_anchor
            and c.template[:n_anchor] == anchor
        ]

    def feed(self, line_id: int, raw: str) -> Cluster:
        tokens = self._mask(raw.split())
        best: Cluster | None = None
        best_sim = 0.0
        for c in self._candidates(tokens):
            sim = similarity(tokens, c.template, slack=self.length_slack)
            if sim >= self.st and sim > best_sim:
                best, best_sim = c, sim
        if best is None:
            cluster = Cluster(cid=f"T{len(self.clusters) + 1}", template=tokens)
            self.clusters.append(cluster)
            self.decisions.append(
                Decision(line_id, cluster.cid, "new_cluster", 0.0, " ".join(tokens))
            )
        else:
            best.template = merge(best.template, tokens)
            cluster = best
            self.decisions.append(
                Decision(
                    line_id,
                    cluster.cid,
                    "matched",
                    round(best_sim, 4),
                    " ".join(cluster.template),
                )
            )
        cluster.count += 1
        cluster.members.append(line_id)
        return cluster

    def template_of(self, cluster: Cluster) -> str:
        return " ".join(cluster.template)

    def params_for(self, raw: str, cluster: Cluster) -> list[str]:
        tokens = self._mask(raw.split())
        return [
            tok
            for tok, tmpl in zip(tokens, cluster.template)
            if tmpl == WILDCARD
        ]
