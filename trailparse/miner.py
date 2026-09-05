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
from typing import NamedTuple

WILDCARD = "<*>"


class Mask(NamedTuple):
    """One whole-token mask: pattern, replacement, optional position/next."""

    pattern: re.Pattern
    replace: str
    position: int | None = None
    nxt: str | None = None


def _compile_masks(regex: list[str | dict[str, object]]) -> list[Mask]:
    """Compile mask entries to Mask triples.

    A plain string entry masks with bare ``<*>`` at any position (the
    historical behavior). A mapping entry names its replacement, e.g.
    ``{"pattern": "pid=\\\\d+", "replace": "pid=<*>"}``, so the template
    keeps the field name, and may restrict the mask to one token index
    with ``position`` (e.g. a leading username at 0) and one literal
    follower with ``next`` (e.g. ``:`` after that username).
    """
    compiled = []
    for entry in regex:
        if isinstance(entry, str):
            compiled.append(Mask(re.compile(entry), WILDCARD))
        else:
            position = entry.get("position")
            nxt = entry.get("next")
            compiled.append(
                Mask(
                    re.compile(str(entry["pattern"])),
                    str(entry.get("replace", WILDCARD)),
                    int(position) if position is not None else None,
                    str(nxt) if nxt is not None else None,
                )
            )
    return compiled


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
        # Any template position holding a wildcard (bare or key-aware,
        # e.g. "user=<*>") matches any token, exactly as bare "<*>" did.
        if WILDCARD in tmpl or tok == tmpl:
            matched += 1
    return matched / n


def generalize_token(tmpl: str, tok: str) -> str:
    """Merge two differing tokens, preserving a shared ``key=`` prefix.

    Tokens that differ only in the value of the same key (``user=root``
    vs ``user=admin``) generalize to ``key=<*>`` instead of bare ``<*>``,
    so the template keeps the field name the ground truth keeps.
    Anything else falls back to bare ``<*>``, as before.
    """
    if tmpl == tok:
        return tmpl
    if WILDCARD in tmpl:
        return tmpl
    if WILDCARD in tok:
        return tok
    tmpl_key, tmpl_sep, _ = tmpl.partition("=")
    tok_key, tok_sep, _ = tok.partition("=")
    if tmpl_sep and tok_sep and tmpl_key == tok_key:
        return f"{tmpl_key}={WILDCARD}"
    return WILDCARD


def merge(template: list[str], tokens: list[str]) -> list[str]:
    n = max(len(template), len(tokens))
    out: list[str] = []
    for i in range(n):
        tmpl = template[i] if i < len(template) else WILDCARD
        tok = tokens[i] if i < len(tokens) else WILDCARD
        out.append(generalize_token(tmpl, tok))
    return out


class Miner:
    def __init__(
        self,
        st: float = 0.5,
        anchor_tokens: int = 2,
        length_slack: int = 0,
        regex: list[str | dict[str, object]] | None = None,
        identity_keys: list[str] | None = None,
    ) -> None:
        self.st = st
        self.anchor_tokens = anchor_tokens
        self.length_slack = length_slack
        self.token_masks = _compile_masks(regex or [])
        # Field names that identify a template: a candidate cluster is
        # rejected when template and line carry the same key with
        # different values (PROTO=TCP vs PROTO=UDP). Everything else
        # may still generalize through key-aware merge.
        self.identity_keys = set(identity_keys or [])
        self.clusters: list[Cluster] = []
        self.decisions: list[Decision] = []

    def _mask(self, tokens: list[str]) -> list[str]:
        if not self.token_masks:
            return tokens
        out = []
        for idx, tok in enumerate(tokens):
            for mask in self.token_masks:
                if mask.position is not None and mask.position != idx:
                    continue
                if mask.nxt is not None and (
                    idx + 1 >= len(tokens) or tokens[idx + 1] != mask.nxt
                ):
                    continue
                if mask.pattern.fullmatch(tok):
                    tok = mask.replace
                    break
            out.append(tok)
        return out

    def _identity_clash(self, template: list[str], tokens: list[str]) -> bool:
        """True when template and line disagree on an identity key."""
        if not self.identity_keys:
            return False
        for tmpl_tok, tok in zip(template, tokens):
            if tmpl_tok == tok:
                continue
            tmpl_key, tmpl_sep, _ = tmpl_tok.partition("=")
            tok_key, tok_sep, _ = tok.partition("=")
            if (
                tmpl_sep
                and tok_sep
                and tmpl_key == tok_key
                and tmpl_key in self.identity_keys
                and WILDCARD not in tmpl_tok
            ):
                return True
        return False

    def _candidates(self, tokens: list[str]) -> list[Cluster]:
        candidates = []
        for cluster in self.clusters:
            if abs(len(cluster.template) - len(tokens)) > self.length_slack:
                continue
            n_anchor = min(self.anchor_tokens, len(tokens), len(cluster.template))
            if cluster.template[:n_anchor] == tokens[:n_anchor]:
                if not self._identity_clash(cluster.template, tokens):
                    candidates.append(cluster)
        return candidates

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
        """Values filling each ``<*>`` of the cluster template, in order.

        A bare ``<*>`` position yields the whole raw token; a compound
        position such as ``<*>(uid=<*>)`` yields each variable part
        (``admin``, ``1000``). This mirrors the ground-truth convention
        where ParameterList holds one entry per ``<*>`` occurrence.
        """
        out: list[str] = []
        for tok, tmpl in zip(raw.split(), cluster.template):
            if WILDCARD not in tmpl:
                continue
            parts = tmpl.split(WILDCARD)
            if parts == ["", ""]:
                out.append(tok)
                continue
            pattern = "(.*?)".join(re.escape(p) for p in parts)
            match = re.fullmatch(pattern, tok)
            if match is None:  # defensive: template should always fit
                out.append(tok)
            else:
                out.extend(match.groups())
        return out
