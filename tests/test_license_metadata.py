# SPDX-License-Identifier: BUSL-1.1
"""Licence metadata in pyproject.toml, LICENSE and the docs agree on BSL 1.1.

pyproject.toml is read as text: ``tomllib`` is not available on Python 3.10.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _read(name: str) -> str:
    return (REPO / name).read_text(encoding="utf-8")


def test_pyproject_declares_busl():
    match = re.search(r"^license\s*=\s*(.+)$", _read("pyproject.toml"), re.MULTILINE)
    assert match is not None
    assert "BUSL-1.1" in match.group(1)


def test_pyproject_has_no_osi_or_apache_classifier():
    text = _read("pyproject.toml")
    assert "License :: OSI Approved" not in text
    assert "Apache Software License" not in text
    assert "License :: Other/Proprietary License" in text


def test_license_file_is_bsl_with_apache_change_license():
    text = _read("LICENSE")
    assert "Business Source License 1.1" in text
    assert re.search(r"^Change License:\s+Apache License, Version 2\.0$", text, re.MULTILINE)
    assert re.search(r"^Change Date:\s+\d{4}-\d{2}-\d{2}$", text, re.MULTILINE)


def test_licensed_work_matches_package_version():
    version = re.search(r'^version\s*=\s*"([^"]+)"', _read("pyproject.toml"), re.MULTILINE)
    assert version is not None
    assert f"diplomat-gate {version.group(1)}" in _read("LICENSE")


def test_licensing_doc_states_earlier_versions_and_precedence():
    text = _read("LICENSING.md")
    assert "Versions up to and including 0.3.0 were released under Apache-2.0" in text
    assert "LICENSE prevails" in text
    assert "NOTICE" in text


def test_contributing_has_license_grant_clause():
    text = _read("CONTRIBUTING.md")
    assert "perpetual, worldwide, irrevocable, sublicensable" in text
    assert "relicense" in text


def _load_validate_release():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "validate_release", REPO / "scripts" / "validate_release.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_gate_license_steps_pass_on_this_repo():
    module = _load_validate_release()
    assert module._license_check() is True
    assert module._change_date_check() is True


def test_change_date_step_rejects_bad_dates(tmp_path, monkeypatch):
    from datetime import date

    module = _load_validate_release()
    monkeypatch.setattr(module, "REPO", tmp_path)
    today = date(2026, 10, 21)
    cases = {
        "2030-10-21": True,
        "2026-10-21": False,  # not in the future
        "2031-01-01": False,  # more than 4 years away
        "2030-13-01": False,  # not a date
        "soon": False,
    }
    for value, expected in cases.items():
        (tmp_path / "LICENSE").write_text(f"Change Date:          {value}\n", encoding="utf-8")
        assert module._change_date_check(today) is expected, value


def test_license_step_flags_missing_header(tmp_path, monkeypatch):
    module = _load_validate_release()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "LICENSE").write_text("Business Source License 1.1\n", encoding="utf-8")
    monkeypatch.setattr(module, "REPO", tmp_path)
    assert module._license_check() is False
    (tmp_path / "src" / "a.py").write_text(f"{module.SPDX_HEADER}\nx = 1\n", encoding="utf-8")
    assert module._license_check() is True
    (tmp_path / "LICENSE").write_text("MIT\n", encoding="utf-8")
    assert module._license_check() is False


def test_license_step_accepts_mixed_expression_only_on_mixed_files(tmp_path, monkeypatch):
    module = _load_validate_release()
    src = tmp_path / "src" / "diplomat_gate"
    src.mkdir(parents=True)
    (tmp_path / "LICENSE").write_text("Business Source License 1.1\n", encoding="utf-8")
    monkeypatch.setattr(module, "REPO", tmp_path)
    monkeypatch.setattr(module, "MIXED_LICENSE_SRC", ("src/diplomat_gate/audit.py",))
    mixed = f"{module.SPDX_MIXED_HEADER}\n# {module.PORTIONS_NOTE} (see NOTICE)\n"
    (src / "audit.py").write_text(mixed, encoding="utf-8")
    (src / "other.py").write_text(f"{module.SPDX_HEADER}\n", encoding="utf-8")
    assert module._license_check() is True
    # The mixed expression is not accepted on a file that is not listed as mixed.
    (src / "other.py").write_text(mixed, encoding="utf-8")
    assert module._license_check() is False
    # A listed mixed file must carry the mixed expression and the portions note.
    (src / "other.py").write_text(f"{module.SPDX_HEADER}\n", encoding="utf-8")
    (src / "audit.py").write_text(f"{module.SPDX_HEADER}\n", encoding="utf-8")
    assert module._license_check() is False
    (src / "audit.py").write_text(f"{module.SPDX_MIXED_HEADER}\nx = 1\n", encoding="utf-8")
    assert module._license_check() is False
