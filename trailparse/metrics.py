# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""GA, PA, FGA, FTA from Jiang et al., ISSTA'24 (LogHub-2.0), section 4.2.

Independent implementation of the published formulas, shared with
TMFNK/LogParser-Harness and TMFNK/LogParser-Dataset. Does not copy
Loghub-2.0 benchmark/evaluation (GPL-3, TA-Eval-Rep).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Mapping, Sequence


def _f1(precision: float, recall: float) -> float:
    if precision + recall == 0.0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def _group_indices(labels: Sequence[object]) -> dict[object, frozenset[int]]:
    groups: dict[object, list[int]] = defaultdict(list)
    for i, lab in enumerate(labels):
        groups[lab].append(i)
    return {lab: frozenset(idxs) for lab, idxs in groups.items()}


def _normalize_template(template: object) -> tuple[str, ...]:
    text = "" if template is None else str(template)
    return tuple(text.split())


def grouping_accuracy(gt_ids: Sequence[object], parsed_ids: Sequence[object]) -> float:
    """Share of messages whose parsed group equals the ground-truth group."""
    if len(gt_ids) != len(parsed_ids):
        raise ValueError("gt_ids and parsed_ids must have the same length")
    n = len(gt_ids)
    if n == 0:
        return 0.0
    gt_groups = _group_indices(gt_ids)
    parsed_groups = _group_indices(parsed_ids)
    correct = sum(
        1 for g, p in zip(gt_ids, parsed_ids) if gt_groups[g] == parsed_groups[p]
    )
    return correct / n


def parsing_accuracy(
    gt_templates: Sequence[object], parsed_templates: Sequence[object]
) -> float:
    """Share of messages whose template tokens match the ground truth exactly."""
    if len(gt_templates) != len(parsed_templates):
        raise ValueError("template sequences must have the same length")
    n = len(gt_templates)
    if n == 0:
        return 0.0
    correct = sum(
        1
        for gt, parsed in zip(gt_templates, parsed_templates)
        if _normalize_template(gt) == _normalize_template(parsed)
    )
    return correct / n


def fga(gt_ids: Sequence[object], parsed_ids: Sequence[object]) -> float:
    """F1 of grouping accuracy (template-level)."""
    if len(gt_ids) != len(parsed_ids):
        raise ValueError("gt_ids and parsed_ids must have the same length")
    gt_groups = _group_indices(gt_ids)
    parsed_groups = _group_indices(parsed_ids)
    n_g, n_p = len(gt_groups), len(parsed_groups)
    if n_g == 0 or n_p == 0:
        return 0.0
    parsed_sets = set(parsed_groups.values())
    n_c = sum(1 for s in gt_groups.values() if s in parsed_sets)
    return _f1(n_c / n_p, n_c / n_g)


def _correctly_identified_template_count(
    gt_templates: Sequence[object], parsed_templates: Sequence[object]
) -> int:
    """N̂c: parsed templates whose messages share one ground-truth template."""
    groundtruth_by_parsed: dict[tuple[str, ...], set[tuple[str, ...]]] = defaultdict(
        set
    )
    for gt, parsed in zip(gt_templates, parsed_templates):
        groundtruth_by_parsed[_normalize_template(parsed)].add(
            _normalize_template(gt)
        )
    return sum(
        groundtruth == {parsed}
        for parsed, groundtruth in groundtruth_by_parsed.items()
    )


def fta(
    gt_ids: Sequence[object],
    parsed_ids: Sequence[object],
    gt_templates: Sequence[object],
    parsed_templates: Sequence[object],
) -> float:
    """F1 of template accuracy (strictest LogHub-2.0 score).

    A parsed template is correctly identified iff all of its messages
    share one ground-truth template and its tokens match that template
    (Jiang et al., ISSTA'24 §4.2.2). PTA = N̂c / N_p, RTA = N̂c / N_g.
    """
    if not (
        len(gt_ids) == len(parsed_ids) == len(gt_templates) == len(parsed_templates)
    ):
        raise ValueError("all sequences must have the same length")
    n_g = len({_normalize_template(template) for template in gt_templates})
    n_p = len({_normalize_template(template) for template in parsed_templates})
    if n_g == 0 or n_p == 0:
        return 0.0
    n_hat = _correctly_identified_template_count(gt_templates, parsed_templates)
    return _f1(n_hat / n_p, n_hat / n_g)


def score_all(
    gt_ids: Sequence[object],
    parsed_ids: Sequence[object],
    gt_templates: Sequence[object],
    parsed_templates: Sequence[object],
) -> dict[str, float]:
    return {
        "GA": grouping_accuracy(gt_ids, parsed_ids),
        "PA": parsing_accuracy(gt_templates, parsed_templates),
        "FGA": fga(gt_ids, parsed_ids),
        "FTA": fta(gt_ids, parsed_ids, gt_templates, parsed_templates),
    }


def score_frames(
    gt: Mapping[str, Sequence[object]], parsed: Mapping[str, Sequence[object]]
) -> dict[str, float]:
    """Score aligned EventId / EventTemplate columns."""
    return score_all(
        list(gt["EventId"]),
        list(parsed["EventId"]),
        list(gt["EventTemplate"]),
        list(parsed["EventTemplate"]),
    )
