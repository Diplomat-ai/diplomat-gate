"""docs/ai-act-evidence.md must stay an honest, checkable technical page.

The page maps requirements to artifacts of this repository. Three ways it
can rot are guarded here: citing code that does not exist, over-promising
compliance, and dropping the legal-review banner or a "does not cover"
cell.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
DOC = REPO / "docs" / "ai-act-evidence.md"

# Phrases that turn a technical evidence page into a compliance claim.
FORBIDDEN = [
    r"is compliant",
    r"are compliant",
    r"ensures? compliance",
    r"ai act compliant",
    r"guarantees?",
    r"fully compliant",
    r"garantit",
    r"assure la conformit",
    r"est conforme",
    r"rend conforme",
]


@pytest.fixture(scope="module")
def text() -> str:
    return DOC.read_text(encoding="utf-8")


def _table_rows(text: str) -> list[list[str]]:
    """Requirement rows of the table (header and separator excluded)."""
    lines = [ln for ln in text.splitlines() if ln.startswith("| ")]
    rows = [[c.strip() for c in ln.strip().strip("|").split(" | ")] for ln in lines]
    return [r for r in rows[2:] if r]


def test_status_draft_and_legal_banner(text):
    assert "status: draft" in text
    assert "pending legal review" in text
    assert "not legal advice" in text


def test_table_has_at_least_three_requirement_rows(text):
    assert len(_table_rows(text)) >= 3


def test_every_row_has_four_cells_and_a_limit(text):
    for row in _table_rows(text):
        assert len(row) == 4, row
        assert row[3], f"empty 'does not cover' cell: {row[0]}"
        assert len(row[3]) > 40, f"'does not cover' cell too thin: {row[0]}"


def test_no_compliance_claims(text):
    for pattern in FORBIDDEN:
        assert not re.search(pattern, text, re.IGNORECASE), pattern


def test_every_cited_path_exists(text):
    paths = set()
    for row in _table_rows(text):
        paths.update(re.findall(r"`([\w./-]+\.(?:py|md))`", row[2]))
    assert paths, "the table cites no file path"
    for rel in sorted(paths):
        assert (REPO / rel).is_file(), f"cited path does not exist: {rel}"


def test_every_cited_symbol_exists_in_source(text):
    source = "\n".join(p.read_text(encoding="utf-8") for p in (REPO / "src").rglob("*.py"))
    symbols = set()
    for row in _table_rows(text):
        for token in re.findall(r"`([A-Za-z_]+)`", " ".join(row[:3])):
            if re.fullmatch(r"[A-Z][a-z]+(?:[A-Z][a-z]+)+|[A-Z]+_[A-Z_]+", token):
                symbols.add(token)
    assert {"AuditLog", "NeedsReview", "ReviewQueue", "SENSITIVE_FIELDS"} <= symbols
    for name in sorted(symbols):
        assert name in source, f"cited symbol not found in src/: {name}"
