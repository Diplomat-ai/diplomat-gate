# SPDX-License-Identifier: BUSL-1.1
"""Every module under src/ carries the SPDX BUSL-1.1 header, and third-party portions are noted."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"
SPDX = "# SPDX-License-Identifier: BUSL-1.1"
SPDX_MIXED = "# SPDX-License-Identifier: BUSL-1.1 AND Apache-2.0"
PORTIONS = "Portions Copyright Mohak Gupta, licensed under Apache-2.0"
MIXED = ("src/diplomat_gate/audit.py", "src/diplomat_gate/cli.py")


def _sources() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def test_src_is_not_empty():
    assert _sources()


def test_every_src_module_starts_with_spdx_header():
    missing = [
        p.relative_to(REPO).as_posix()
        for p in _sources()
        if p.relative_to(REPO).as_posix() not in MIXED
        and p.read_text(encoding="utf-8").splitlines()[:1] != [SPDX]
    ]
    assert missing == []


def test_mixed_modules_carry_both_licences_and_the_portions_note():
    for rel in MIXED:
        lines = (REPO / rel).read_text(encoding="utf-8").splitlines()
        assert lines[0] == SPDX_MIXED, rel
        assert PORTIONS in lines[1], rel


def test_mixed_test_file_and_doc_carry_the_note():
    test_lines = (REPO / "tests" / "test_audit.py").read_text(encoding="utf-8").splitlines()
    assert test_lines[0] == SPDX_MIXED
    assert PORTIONS in test_lines[1]
    doc_lines = (REPO / "docs" / "audit-trail.md").read_text(encoding="utf-8").splitlines()
    assert "SPDX-License-Identifier: BUSL-1.1 AND Apache-2.0" in doc_lines[0]
    assert PORTIONS in doc_lines[1]


def test_notice_lists_external_contributions():
    notice = (REPO / "NOTICE").read_text(encoding="utf-8")
    for needle in (
        "Mohak Gupta",
        "2d42eb1",
        "PR #26",
        "@lukiod",
        "Yarizakura",
        "CrepuscularIRIS",
        "1d4743a",
        "licenses/Apache-2.0.txt",
        "BUSL-1.1 AND Apache-2.0",
    ):
        assert needle in notice
    assert (REPO / "licenses" / "Apache-2.0.txt").is_file()
