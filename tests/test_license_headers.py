# SPDX-License-Identifier: BUSL-1.1
"""Every module under src/ carries the SPDX BUSL-1.1 header, and third-party portions are noted."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"
SPDX = "# SPDX-License-Identifier: BUSL-1.1"


def _sources() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def test_src_is_not_empty():
    assert _sources()


def test_every_src_module_starts_with_spdx_header():
    missing = [
        p.relative_to(REPO).as_posix()
        for p in _sources()
        if p.read_text(encoding="utf-8").splitlines()[:1] != [SPDX]
    ]
    assert missing == []


def test_audit_module_keeps_spdx_and_notes_apache_portions():
    lines = (SRC / "diplomat_gate" / "audit.py").read_text(encoding="utf-8").splitlines()
    assert lines[0] == SPDX
    assert "Portions Copyright Mohak Gupta, licensed under Apache-2.0" in lines[1]


def test_notice_lists_external_contributions():
    notice = (REPO / "NOTICE").read_text(encoding="utf-8")
    for needle in ("Mohak Gupta", "2d42eb1", "Yarizakura", "1d4743a", "licenses/Apache-2.0.txt"):
        assert needle in notice
    assert (REPO / "licenses" / "Apache-2.0.txt").is_file()
