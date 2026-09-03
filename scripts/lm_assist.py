# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""LM assist (Phase 2 stub). Not wired — exits 2 with a pointer.

The assist will read an immutable parse audit plus its paired structured
CSV, then write proposals and decisions to a separate append-only review
JSONL. It will never modify deterministic outputs. See docs/PHASE2-LM.md.
Never runs in v0.1.
"""

from __future__ import annotations

import sys


def main() -> None:
    print("LM assist is Phase 2 and not wired. See docs/PHASE2-LM.md.")
    print(
        "Parse audit and CSV inputs stay immutable; model review will use "
        "a separate local-only JSONL."
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
