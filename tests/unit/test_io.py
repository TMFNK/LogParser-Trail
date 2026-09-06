# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 MbitAI — see NOTICE for attribution.
"""Output files publish only after a complete write."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trailparse.io import atomic_text_writer  # noqa: E402


def test_atomic_writer_preserves_existing_file_on_failure(tmp_path):
    output = tmp_path / "output.txt"
    output.write_text("old\n")

    with pytest.raises(RuntimeError):
        with atomic_text_writer(output) as f:
            f.write("new\n")
            raise RuntimeError("interrupted")

    assert output.read_text() == "old\n"
    assert list(tmp_path.iterdir()) == [output]
