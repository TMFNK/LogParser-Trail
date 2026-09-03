# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""CSV readers and writers in LogHub *_structured.csv shape."""

from __future__ import annotations

import csv
import re
from pathlib import Path

COLUMNS = ["LineId", "Content", "EventId", "EventTemplate", "ParameterList"]

HEADER_RE = re.compile(r"^\w{3}\s+\d+ \d+:\d+:\d+ \S+ \S+: (.*)$")


def split_header(line: str) -> str:
    """Return the message part of a syslog line (after `host proc[pid]:`).

    Falls back to the whole line when the shape does not match, so plain
    message-only files parse unchanged.
    """
    m = HEADER_RE.match(line)
    return m.group(1) if m else line


def read_log(path: Path) -> list[str]:
    return path.read_text().splitlines()


def write_structured(rows: list[dict], path: Path) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def read_structured(path: Path) -> list[dict]:
    with open(path) as f:
        return list(csv.DictReader(f))
