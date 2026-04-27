"""Unit tests for diplomat_gate.validation (no subprocess)."""

from __future__ import annotations

from pathlib import Path

import pytest

from diplomat_gate.validation import (
    Issue,
    ValidationReport,
    format_report_text,
    report_to_dict,
    validate_config,
)

FIXTURES = Path(__file__).parent / "fixtures" / "validation"


# ── Happy paths ────────────────────────────────────────────────────────────────


def test_valid_minimal_returns_ok():
    report = validate_config(str(FIXTURES / "valid_minimal.yaml"))
    assert report.ok is True
    assert report.errors == ()
    assert "payment.amount_limit" in report.policies_loaded


def test_valid_minimal_no_warnings():
    # valid_minimal has max_amount set explicitly — no default_critical_field warning.
    report = validate_config(str(FIXTURES / "valid_minimal.yaml"))
    assert report.warnings == ()


def test_valid_full_matches_example():
    report = validate_config(str(FIXTURES / "valid_full.yaml"))
    assert report.ok is True
    assert report.errors == ()
    assert len(report.policies_loaded) >= 8


def test_policies_key_form_supported():
    report = validate_config(str(FIXTURES / "policies_key_form.yaml"))
    assert report.ok is True
    assert "payment.amount_limit" in report.policies_loaded
    assert "email.domain_blocklist" in report.policies_loaded


def test_format_version_is_stable():
    report = validate_config(str(FIXTURES / "valid_minimal.yaml"))
    assert report.format_version == "1"


# ── Errors ─────────────────────────────────────────────────────────────────────


def test_unknown_policy_id_errors():
    report = validate_config(str(FIXTURES / "error_unknown_policy.yaml"))
    assert report.ok is False
    assert any(e.code == "unknown_policy" for e in report.errors)
    issue = next(e for e in report.errors if e.code == "unknown_policy")
    assert issue.path.endswith(".id")
    # difflib should suggest 'payment.amount_limit' for the typo 'payment.amout_limit'
    assert "amount_limit" in issue.message.lower() or "did you mean" in issue.message.lower()


def test_missing_id_errors():
    report = validate_config(str(FIXTURES / "error_missing_id.yaml"))
    assert report.ok is False
    assert any(e.code == "missing_id" for e in report.errors)


def test_bad_severity_errors():
    report = validate_config(str(FIXTURES / "error_bad_severity.yaml"))
    assert report.ok is False
    assert any(e.code == "bad_severity" for e in report.errors)


def test_bad_on_fail_errors():
    report = validate_config(str(FIXTURES / "error_bad_on_fail.yaml"))
    assert report.ok is False
    assert any(e.code == "bad_on_fail" for e in report.errors)


def test_type_mismatch_errors():
    report = validate_config(str(FIXTURES / "error_type_mismatch.yaml"))
    assert report.ok is False
    assert any(e.code == "type_mismatch" for e in report.errors)
    issue = next(e for e in report.errors if e.code == "type_mismatch")
    assert "max_amount" in issue.path


def test_audit_bad_type_errors():
    report = validate_config(str(FIXTURES / "error_audit_bad_type.yaml"))
    assert report.ok is False
    assert any(e.code == "audit_bad_type" for e in report.errors)
    # Both enabled (str) and path (int) should be reported.
    audit_errors = [e for e in report.errors if e.code == "audit_bad_type"]
    assert len(audit_errors) == 2


# ── Warnings ───────────────────────────────────────────────────────────────────


def test_unknown_field_warns():
    report = validate_config(str(FIXTURES / "warn_unknown_field.yaml"))
    assert report.ok is True
    assert any(w.code == "unknown_field" for w in report.warnings)
    w = next(w for w in report.warnings if w.code == "unknown_field")
    # difflib should suggest 'max_amount' for the typo 'max_amout'
    assert "max_amount" in w.message


def test_default_critical_field_warns():
    report = validate_config(str(FIXTURES / "warn_default_critical_field.yaml"))
    assert report.ok is True
    assert any(w.code == "default_critical_field" for w in report.warnings)
    w = next(w for w in report.warnings if w.code == "default_critical_field")
    assert "max_amount" in w.message
    assert "10000" in w.message


def test_empty_domain_warns():
    report = validate_config(str(FIXTURES / "warn_empty_domain.yaml"))
    assert any(w.code == "empty_domain" for w in report.warnings)
    w = next(w for w in report.warnings if w.code == "empty_domain")
    assert w.path == "payment"


def test_no_policies_warns():
    report = validate_config(str(FIXTURES / "warn_no_policies.yaml"))
    assert any(w.code == "no_policies" for w in report.warnings)


# ── Robustness ─────────────────────────────────────────────────────────────────


def test_yaml_parse_error_raises_value_error(tmp_path):
    bad = tmp_path / "broken.yaml"
    bad.write_text("payment:\n  - id: payment.amount_limit\n    max_amount: [1, 2, 3\n")
    with pytest.raises(ValueError, match="YAML parse error"):
        validate_config(str(bad))


def test_missing_file_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        validate_config("/nonexistent/path/gate.yaml")


def test_top_level_not_mapping_returns_error(tmp_path):
    bad = tmp_path / "list_at_root.yaml"
    bad.write_text("- foo\n- bar\n")
    report = validate_config(str(bad))
    assert report.ok is False
    assert any(e.code == "bad_top_level_type" for e in report.errors)


def test_empty_file_no_policies_warning(tmp_path):
    empty = tmp_path / "empty.yaml"
    empty.write_text("")
    report = validate_config(str(empty))
    assert report.ok is True
    assert any(w.code == "no_policies" for w in report.warnings)


# ── Diffability ────────────────────────────────────────────────────────────────


def test_errors_are_sorted_stably():
    report = validate_config(str(FIXTURES / "error_audit_bad_type.yaml"))
    pairs = [(e.path, e.code) for e in report.errors]
    assert pairs == sorted(pairs)


def test_report_to_dict_key_order_is_stable():
    report = validate_config(str(FIXTURES / "valid_minimal.yaml"))
    d = report_to_dict(report)
    assert list(d.keys()) == [
        "ok",
        "format_version",
        "config_path",
        "policies_loaded",
        "errors",
        "warnings",
    ]


def test_report_to_dict_policies_loaded_is_sorted():
    report = validate_config(str(FIXTURES / "valid_full.yaml"))
    d = report_to_dict(report)
    assert d["policies_loaded"] == sorted(d["policies_loaded"])


def test_report_is_json_serialisable():
    import json

    report = validate_config(str(FIXTURES / "valid_full.yaml"))
    d = report_to_dict(report)
    payload = json.dumps(d)  # must not raise
    reparsed = json.loads(payload)
    assert reparsed["ok"] is True
    assert reparsed["format_version"] == "1"


# ── Format text ────────────────────────────────────────────────────────────────


def test_format_report_text_no_color():
    report = validate_config(str(FIXTURES / "valid_minimal.yaml"))
    text = format_report_text(report, use_color=False)
    assert "OK" in text
    assert "\x1b[" not in text  # no ANSI escape codes


def test_format_report_text_with_color():
    report = validate_config(str(FIXTURES / "valid_minimal.yaml"))
    text = format_report_text(report, use_color=True)
    assert "\x1b[" in text


def test_format_report_text_invalid_contains_error_lines():
    report = validate_config(str(FIXTURES / "error_unknown_policy.yaml"))
    text = format_report_text(report, use_color=False)
    assert "INVALID" in text
    assert "unknown_policy" in text


def test_format_report_text_warnings():
    report = validate_config(str(FIXTURES / "warn_unknown_field.yaml"))
    text = format_report_text(report, use_color=False)
    assert "OK with warnings" in text
    assert "unknown_field" in text


# ── Type checking edge cases ───────────────────────────────────────────────────


def test_bool_is_not_accepted_for_int_field(tmp_path):
    bad = tmp_path / "bool_for_int.yaml"
    bad.write_text("email:\n  - id: email.business_hours\n    start: true\n    end: 18\n")
    report = validate_config(str(bad))
    assert report.ok is False
    assert any(e.code == "type_mismatch" and "start" in e.path for e in report.errors)


def test_int_is_accepted_for_float_field(tmp_path):
    ok = tmp_path / "int_for_float.yaml"
    ok.write_text("payment:\n  - id: payment.amount_limit\n    max_amount: 10000\n")
    report = validate_config(str(ok))
    assert report.ok is True


def test_list_of_strings_passes_type_check(tmp_path):
    f = tmp_path / "list_str.yaml"
    f.write_text(
        'email:\n  - id: email.domain_blocklist\n    blocked: ["*.evil.com", "*.bad.net"]\n'
    )
    report = validate_config(str(f))
    assert report.ok is True


def test_list_of_wrong_type_fails(tmp_path):
    f = tmp_path / "list_wrong.yaml"
    f.write_text(
        "email:\n"
        "  - id: email.business_hours\n"
        "    days: [monday, tuesday]\n"  # list[str] but expects list[int]
    )
    report = validate_config(str(f))
    assert report.ok is False
    assert any(e.code == "type_mismatch" for e in report.errors)


# ── Policies loaded tracking ───────────────────────────────────────────────────


def test_failed_policy_not_in_policies_loaded():
    report = validate_config(str(FIXTURES / "error_bad_severity.yaml"))
    assert "payment.amount_limit" not in report.policies_loaded


def test_unknown_policy_not_in_policies_loaded():
    report = validate_config(str(FIXTURES / "error_unknown_policy.yaml"))
    assert report.policies_loaded == ()


# ── Review queue section ───────────────────────────────────────────────────────


def test_review_queue_bad_enabled_errors(tmp_path):
    f = tmp_path / "rq.yaml"
    f.write_text(
        "review_queue:\n"
        "  enabled: maybe\n"
        "  path: ./review.db\n"
        "payment:\n"
        "  - id: payment.amount_limit\n"
        "    max_amount: 1000\n"
    )
    report = validate_config(str(f))
    assert report.ok is False
    assert any(e.code == "review_queue_bad_type" and "enabled" in e.path for e in report.errors)


def test_review_queue_bad_path_errors(tmp_path):
    f = tmp_path / "rq_path.yaml"
    f.write_text(
        "review_queue:\n"
        "  enabled: true\n"
        "  path: 99\n"
        "payment:\n"
        "  - id: payment.amount_limit\n"
        "    max_amount: 1000\n"
    )
    report = validate_config(str(f))
    assert report.ok is False
    assert any(e.code == "review_queue_bad_type" and "path" in e.path for e in report.errors)


def test_review_queue_unknown_field_warns(tmp_path):
    f = tmp_path / "rq_warn.yaml"
    f.write_text(
        "review_queue:\n"
        "  enabled: true\n"
        "  ttl_secs: 3600\n"  # typo for ttl_seconds
        "payment:\n"
        "  - id: payment.amount_limit\n"
        "    max_amount: 1000\n"
    )
    report = validate_config(str(f))
    assert report.ok is True
    assert any(w.code == "unknown_review_queue_field" for w in report.warnings)


def test_review_queue_not_mapping_errors(tmp_path):
    f = tmp_path / "rq_bad.yaml"
    f.write_text(
        "review_queue: notamapping\npayment:\n  - id: payment.amount_limit\n    max_amount: 1000\n"
    )
    report = validate_config(str(f))
    assert report.ok is False
    assert any(e.code == "bad_top_level_type" and e.path == "review_queue" for e in report.errors)


# ── Audit section extra branches ───────────────────────────────────────────────


def test_audit_not_mapping_errors(tmp_path):
    f = tmp_path / "audit_bad.yaml"
    f.write_text(
        "audit: notamapping\npayment:\n  - id: payment.amount_limit\n    max_amount: 1000\n"
    )
    report = validate_config(str(f))
    assert report.ok is False
    assert any(e.code == "bad_top_level_type" and e.path == "audit" for e in report.errors)


def test_audit_unknown_field_with_suggestion(tmp_path):
    f = tmp_path / "audit_typo.yaml"
    f.write_text(
        "audit:\n"
        "  enabeld: true\n"  # typo for enabled
        "  path: ./audit.db\n"
        "payment:\n"
        "  - id: payment.amount_limit\n"
        "    max_amount: 1000\n"
    )
    report = validate_config(str(f))
    assert report.ok is True
    assert any(w.code == "unknown_audit_field" for w in report.warnings)


# ── Policies section extra branches ────────────────────────────────────────────


def test_policies_key_not_list_errors(tmp_path):
    f = tmp_path / "policies_bad.yaml"
    f.write_text("policies: notalist\n")
    report = validate_config(str(f))
    assert report.ok is False
    assert any(e.code == "bad_top_level_type" and e.path == "policies" for e in report.errors)


def test_domain_not_list_errors(tmp_path):
    f = tmp_path / "domain_bad.yaml"
    f.write_text("payment: notalist\n")
    report = validate_config(str(f))
    assert report.ok is False
    assert any(e.code == "bad_top_level_type" and e.path == "payment" for e in report.errors)


def test_policy_entry_not_dict_errors(tmp_path):
    f = tmp_path / "entry_bad.yaml"
    f.write_text("payment:\n  - just_a_string\n")
    report = validate_config(str(f))
    assert report.ok is False
    assert any(e.code == "bad_top_level_type" for e in report.errors)


def test_on_fail_not_string_errors(tmp_path):
    f = tmp_path / "on_fail_bad.yaml"
    f.write_text("payment:\n  - id: payment.amount_limit\n    max_amount: 1000\n    on_fail: 42\n")
    report = validate_config(str(f))
    assert report.ok is False
    assert any(e.code == "bad_on_fail" for e in report.errors)


def test_enabled_not_bool_errors(tmp_path):
    f = tmp_path / "enabled_bad.yaml"
    f.write_text(
        "payment:\n"
        "  - id: payment.amount_limit\n"
        "    max_amount: 1000\n"
        "    enabled: yes\n"  # PyYAML parses "yes" as bool True, use string
    )
    # PyYAML parses unquoted 'yes' as True (bool), so use a string explicitly
    f.write_text(
        "payment:\n  - id: payment.amount_limit\n    max_amount: 1000\n    enabled: 'maybe'\n"
    )
    report = validate_config(str(f))
    assert report.ok is False
    assert any(e.code == "bad_enabled" for e in report.errors)


def test_default_critical_field_policies_key_form(tmp_path):
    """default_critical_field warning fires for the 'policies:' key form too."""
    f = tmp_path / "crit.yaml"
    f.write_text(
        "policies:\n  - id: payment.amount_limit\n    severity: critical\n    on_fail: STOP\n"
    )
    report = validate_config(str(f))
    assert report.ok is True
    assert any(w.code == "default_critical_field" for w in report.warnings)
    w = next(w for w in report.warnings if w.code == "default_critical_field")
    assert w.path == "policies[0]"


def test_id_not_string_errors(tmp_path):
    f = tmp_path / "id_num.yaml"
    f.write_text("payment:\n  - id: 42\n    max_amount: 1000\n")
    report = validate_config(str(f))
    assert report.ok is False
    assert any(e.code == "missing_id" for e in report.errors)


def test_dict_type_field_accepted(tmp_path):
    """A field typed as dict[str, Any] accepts a dict value."""
    # Use Policy.config field — but config is excluded from specific fields.
    # Instead, test via an int field passed as dict to trigger type_mismatch.
    f = tmp_path / "dict_type.yaml"
    f.write_text(
        "payment:\n  - id: payment.velocity\n    max_txn: {nested: value}\n"  # dict instead of int
    )
    report = validate_config(str(f))
    assert report.ok is False
    assert any(e.code == "type_mismatch" and "max_txn" in e.path for e in report.errors)


# ── format_report_text colour/no-colour ────────────────────────────────────────


def test_format_report_text_color_invalid():
    report = ValidationReport(
        ok=False,
        errors=(Issue(path="payment[0].id", code="missing_id", message="No id", severity="error"),),
        warnings=(),
        policies_loaded=(),
        config_path="test.yaml",
    )
    text = format_report_text(report, use_color=True)
    assert "\x1b[31m" in text
    assert "INVALID" in text
    assert "missing_id" in text


def test_format_report_text_color_ok_with_warnings():
    report = ValidationReport(
        ok=True,
        errors=(),
        warnings=(
            Issue(
                path="payment[0].max_amout",
                code="unknown_field",
                message="typo",
                severity="warning",
            ),
        ),
        policies_loaded=("payment.amount_limit",),
        config_path="test.yaml",
    )
    text = format_report_text(report, use_color=True)
    assert "\x1b[33m" in text
    assert "OK with warnings" in text


def test_format_report_text_no_color_ok():
    report = ValidationReport(
        ok=True,
        errors=(),
        warnings=(),
        policies_loaded=("payment.amount_limit",),
        config_path="test.yaml",
    )
    text = format_report_text(report, use_color=False)
    assert "\x1b[" not in text
    assert "OK:" in text


# ── report_to_dict ─────────────────────────────────────────────────────────────


def test_report_to_dict_includes_all_keys():
    report = validate_config(str(FIXTURES / "valid_minimal.yaml"))
    d = report_to_dict(report)
    assert list(d.keys()) == [
        "ok",
        "format_version",
        "config_path",
        "policies_loaded",
        "errors",
        "warnings",
    ]


# ── top-level non-mapping ──────────────────────────────────────────────────────


def test_top_level_non_mapping_errors(tmp_path):
    f = tmp_path / "bad_root.yaml"
    f.write_text("- item1\n- item2\n")
    report = validate_config(str(f))
    assert report.ok is False
    assert any(e.code == "bad_top_level_type" and e.path == "(root)" for e in report.errors)


def test_empty_yaml_gives_no_policies_warning(tmp_path):
    f = tmp_path / "empty.yaml"
    f.write_text("")
    report = validate_config(str(f))
    assert report.ok is True
    assert any(w.code == "no_policies" for w in report.warnings)


# ── _type_name for dict fields ─────────────────────────────────────────────────


def test_type_name_for_list_dict_fields():
    """Ensure type annotations on list[str] fields produce readable names in error messages."""
    from typing import get_type_hints

    from diplomat_gate.policies.emails import DomainBlocklistPolicy
    from diplomat_gate.validation import _type_name  # noqa: PLC0415

    hints = get_type_hints(DomainBlocklistPolicy)
    assert "blocked" in hints
    name = _type_name(hints["blocked"])
    assert "list" in name


# ── _type_name and _check_type internals ──────────────────────────────────────


def test_type_name_dict_generic():
    from diplomat_gate.validation import _type_name  # noqa: PLC0415

    assert _type_name(dict[str, int]) == "dict[str, int]"


def test_type_name_unknown_generic():
    from diplomat_gate.validation import _type_name  # noqa: PLC0415

    # Optional[int] has a union origin that is neither list nor dict
    result = _type_name(int | None)  # noqa: UP007
    assert isinstance(result, str)


def test_check_type_typing_any():
    from typing import Any

    from diplomat_gate.validation import _check_type  # noqa: PLC0415

    assert _check_type("anything", Any) is True
    assert _check_type(42, Any) is True


def test_check_type_list_with_wrong_item():
    from diplomat_gate.validation import _check_type  # noqa: PLC0415

    assert _check_type(["a", "b"], list[str]) is True
    assert _check_type(["a", 1], list[str]) is False


def test_check_type_dict_generic():
    from diplomat_gate.validation import _check_type  # noqa: PLC0415

    assert _check_type({"a": 1}, dict[str, int]) is True
    assert _check_type({"a": "x"}, dict[str, int]) is False


def test_check_type_list_no_args():
    """list without type args always accepts."""
    from diplomat_gate.validation import _check_type  # noqa: PLC0415

    assert _check_type([1, "mixed"], list) is True  # type: ignore[type-arg]


def test_check_type_bool_rejected_for_int_and_float():
    from diplomat_gate.validation import _check_type  # noqa: PLC0415

    assert _check_type(True, int) is False
    assert _check_type(True, float) is False
    assert _check_type(True, bool) is True
