# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""Build the 60-line labeled sample: 8 templates, seed 7.

Writes examples/sample.log and examples/sample_structured.csv.
The generator is the annotator here, same as Tier B: the template each
line was drawn from is its ground truth. Rerun to refresh; outputs are
committed.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_LOG = ROOT / "examples" / "sample.log"
OUT_TRUTH = ROOT / "examples" / "sample_structured.csv"

# (truth id, count, pattern, template, param fields)
TEMPLATES = [
    (
        "G1",
        10,
        "Failed password for {u} from {ip} port {p} ssh2",
        "Failed password for <*> from <*> port <*> ssh2",
        ["u", "ip", "p"],
    ),
    (
        "G2",
        4,
        "Accepted password for {u} from {ip} port {p} ssh2",
        "Accepted password for <*> from <*> port <*> ssh2",
        ["u", "ip", "p"],
    ),
    (
        "G3",
        8,
        "Invalid user {u} from {ip} port {p}",
        "Invalid user <*> from <*> port <*>",
        ["u", "ip", "p"],
    ),
    (
        "G4",
        6,
        "Connection closed by authenticating user {u} {ip} port {p} [preauth]",
        "Connection closed by authenticating user <*> <*> port <*> [preauth]",
        ["u", "ip", "p"],
    ),
    (
        "G5",
        6,
        "pam_unix(sshd:auth): authentication failure; rhost={rip}",
        "pam_unix(sshd:auth): authentication failure; rhost=<*>",
        ["rip"],
    ),
    (
        "G6",
        12,
        "[UFW BLOCK] IN=eth0 OUT= SRC={sip} DST=10.0.0.5 PROTO=TCP SPT={sp} DPT=22",
        "[UFW BLOCK] IN=eth0 OUT= SRC=<*> DST=10.0.0.5 PROTO=TCP SPT=<*> DPT=22",
        ["sip", "sp"],
    ),
    (
        "G7",
        7,
        "pam_unix(sudo:session): session opened for user {t} by {bu}(uid={bi})",
        "pam_unix(sudo:session): session opened for user <*> by <*>(uid=<*>)",
        ["t", "bu", "bi"],
    ),
    (
        "G8",
        7,
        "pam_unix(sudo:session): session closed for user {t}",
        "pam_unix(sudo:session): session closed for user <*>",
        ["t"],
    ),
]

USERS = ["root", "admin", "ubuntu", "deploy", "git", "test"]


def main() -> None:
    import sys

    sys.path.insert(0, str(ROOT))
    from trailparse.io import write_structured

    rng = random.Random(7)
    ts = datetime(2026, 6, 14, 0, 0, 1)
    lines: list[str] = []
    rows: list[dict] = []
    lid = 0
    for gid, n, pattern, template, fields in TEMPLATES:
        for _ in range(n):
            u = rng.choice(USERS)
            t = rng.choice(["root", "ubuntu", "deploy"])
            ip = f"203.0.113.{rng.randint(2, 250)}"
            p = str(rng.randint(1024, 65535))
            uid = str(rng.choice([0, 1000, 1001]))
            vals = {
                "u": u,
                "t": t,
                "ip": ip,
                "p": p,
                "id": uid,
                "rip": ip,
                "sip": ip,
                "sp": p,
                "bu": u,
                "bi": uid,
            }
            lid += 1
            ts += timedelta(seconds=rng.randint(1, 9))
            content = pattern.format(**{k: vals[k] for k in fields})
            if gid == "G6":
                proc = "kernel"
            elif gid in ("G7", "G8"):
                proc = "sudo"
            else:
                proc = "sshd"
            pid = rng.randint(10000, 30000)
            lines.append(f"Jun 14 {ts:%H:%M:%S} secops-01 {proc}[{pid}]: {content}")
            rows.append(
                {
                    "LineId": lid,
                    "Content": content,
                    "EventId": gid,
                    "EventTemplate": template,
                    "ParameterList": repr([vals[k] for k in fields]),
                }
            )
    OUT_LOG.write_text("\n".join(lines) + "\n")
    write_structured(rows, OUT_TRUTH)
    print(f"wrote {len(lines)} lines -> {OUT_LOG.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
