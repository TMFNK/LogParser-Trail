# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""LM assist (Phase 2 stub). Not wired — exits 2 with a pointer.

The plan: read results/audit.jsonl, find clusters the deterministic
miner split or merged with low confidence, and ask a local small model
for merge/split proposals. See docs/PHASE2-LM.md. Never runs in v0.1.
"""

from __future__ import annotations

import sys


def main() -> None:
    print("LM assist is Phase 2 and not wired. See docs/PHASE2-LM.md.")
    print(
        "No log line leaves the machine in any phase: the endpoint, "
        "when it exists, will be a local OpenAI-compatible server."
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
