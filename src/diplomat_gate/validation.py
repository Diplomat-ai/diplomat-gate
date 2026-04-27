"""Validate gate.yaml configuration files.

Pure, side-effect-free inspection of a configuration file. Does not
instantiate a Gate. Does not perform any I/O beyond reading the YAML file.

Used by:
    - The `diplomat-gate validate` CLI command.
    - The (future) `Diplomat-ai/gate-check-action` GitHub Action.
    - The (future) pre-commit hook.

Output format is stable across versions (see ``ValidationReport.format_version``).
"""

from __future__ import annotations

import dataclasses
import difflib
from dataclasses import dataclass
from typing import Any, get_args, get_origin, get_type_hints

from .policies.loader import iter_registered_policies

# ── Public constants ───────────────────────────────────────────────────────────

#: Schema version of the JSON output. Bump on breaking changes.
FORMAT_VERSION = "1"

#: Severity values accepted on policy entries.
ALLOWED_SEVERITIES = ("critical", "high", "medium", "low")

#: on_fail values accepted on policy entries.
ALLOWED_ON_FAIL = ("STOP", "REVIEW")

#: Common fields that exist on every policy (declared by ``Policy`` base class).
_COMMON_POLICY_FIELDS = frozenset({"id", "name", "domain", "severity", "on_fail", "enabled"})

#: Fields allowed in the top-level ``audit:`` section.
_ALLOWED_AUDIT_FIELDS = frozenset({"enabled", "path"})

#: Fields allowed in the top-level ``review_queue:`` section.
_ALLOWED_REVIEW_QUEUE_FIELDS = frozenset({"enabled", "path", "ttl_seconds"})

#: Top-level keys that are silently accepted (not policy domain lists).
_KNOWN_TOP_LEVEL_KEYS = frozenset(
    {"payment", "email", "policies", "audit", "review_queue", "version"}
)

#: Policies for which leaving the critical field at its default is suspicious.
_CRITICAL_FIELDS_BY_POLICY: dict[str, str] = {
    "payment.amount_limit": "max_amount",
    "payment.daily_limit": "max_daily",
    "payment.recipient_blocklist": "blocked",
    "email.domain_blocklist": "blocked",
}

#: Base Policy dataclass field names — excluded from "specific fields" lookup.
_BASE_POLICY_FIELD_NAMES = frozenset(
    {"policy_id", "name", "domain", "severity", "on_fail", "enabled", "config"}
)


# ── Public types ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Issue:
    """A single validation finding (error or warning)."""

    path: str  # e.g. "payment[0].max_amount" or "audit.path"
    code: str  # e.g. "unknown_policy", "type_mismatch"
    message: str  # human-readable, English, no trailing period
    severity: str  # "error" | "warning"


@dataclass(frozen=True)
class ValidationReport:
    """Outcome of a validate_config() call."""

    ok: bool  # True iff len(errors) == 0
    errors: tuple[Issue, ...]  # sorted by (path, code)
    warnings: tuple[Issue, ...]  # sorted by (path, code)
    policies_loaded: tuple[str, ...]  # sorted alphabetically
    config_path: str
    format_version: str = FORMAT_VERSION


# ── Internal helpers ───────────────────────────────────────────────────────────


def _suggest(name: str, candidates: list[str]) -> str | None:
    matches = difflib.get_close_matches(name, candidates, n=1, cutoff=0.6)
    return matches[0] if matches else None


def _type_name(t: type) -> str:
    """Return a human-readable name for a type annotation."""
    origin = get_origin(t)
    if origin is None:
        return getattr(t, "__name__", repr(t))
    args = get_args(t)
    if origin is list:
        inner = _type_name(args[0]) if args else "?"
        return f"list[{inner}]"
    if origin is dict:
        k = _type_name(args[0]) if args else "?"
        v = _type_name(args[1]) if len(args) > 1 else "?"
        return f"dict[{k}, {v}]"
    return repr(t)


def _check_type(value: Any, expected: type) -> bool:
    """Return True if ``value`` is compatible with ``expected``."""
    origin = get_origin(expected)
    if origin is None:
        # bool is a subclass of int in Python — reject it explicitly for int/float.
        if expected is int:
            return isinstance(value, int) and not isinstance(value, bool)
        if expected is float:
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if expected is bool:
            return isinstance(value, bool)
        # typing.Any — accept anything.
        try:
            from typing import Any as _Any  # noqa: PLC0415

            if expected is _Any:
                return True
        except ImportError:
            pass
        try:
            return isinstance(value, expected)
        except TypeError:
            return True  # exotic type — degrade gracefully
    if origin is list:
        if not isinstance(value, list):
            return False
        args = get_args(expected)
        if not args:
            return True
        (inner,) = args
        return all(_check_type(item, inner) for item in value)
    if origin is dict:
        if not isinstance(value, dict):
            return False
        args = get_args(expected)
        if not args or len(args) < 2:
            return True
        k_type, v_type = args
        return all(_check_type(k, k_type) and _check_type(v, v_type) for k, v in value.items())
    # Fallback for unknown generic origins — accept.
    return True


def _get_specific_fields(cls: type) -> dict[str, type]:
    """Return {yaml_field_name: expected_type} for fields specific to this policy class."""
    try:
        hints = get_type_hints(cls)
    except Exception:  # noqa: BLE001
        return {}
    return {name: typ for name, typ in hints.items() if name not in _BASE_POLICY_FIELD_NAMES}


def _get_known_yaml_fields(cls: type) -> frozenset[str]:
    """Return the full set of valid YAML keys for a policy class."""
    specific = _get_specific_fields(cls)
    return _COMMON_POLICY_FIELDS | frozenset(specific.keys())


def _get_field_default(cls: type, field_name: str) -> Any:
    """Return the default value of a dataclass field, or ``dataclasses.MISSING``."""
    try:
        for f in dataclasses.fields(cls):  # type: ignore[arg-type]
            if f.name == field_name:
                if f.default is not dataclasses.MISSING:
                    return f.default
                if f.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
                    return f.default_factory()
                return dataclasses.MISSING
    except Exception:  # noqa: BLE001
        pass
    return dataclasses.MISSING


# ── Section validators ─────────────────────────────────────────────────────────


def _validate_audit_section(
    audit: Any,
    errors: list[Issue],
    warnings: list[Issue],
) -> None:
    if audit is None:
        return
    if not isinstance(audit, dict):
        errors.append(
            Issue(
                path="audit",
                code="bad_top_level_type",
                message=f"'audit' must be a mapping, got {type(audit).__name__}",
                severity="error",
            )
        )
        return
    for key in audit:
        if key not in _ALLOWED_AUDIT_FIELDS:
            suggestion = _suggest(key, list(_ALLOWED_AUDIT_FIELDS))
            msg = f"Unknown field 'audit.{key}'"
            if suggestion:
                msg += f". Did you mean '{suggestion}'?"
            warnings.append(
                Issue(
                    path=f"audit.{key}", code="unknown_audit_field", message=msg, severity="warning"
                )
            )
    if "enabled" in audit and not isinstance(audit["enabled"], bool):
        errors.append(
            Issue(
                path="audit.enabled",
                code="audit_bad_type",
                message=f"'audit.enabled' must be a bool, got {type(audit['enabled']).__name__}",
                severity="error",
            )
        )
    if "path" in audit and not isinstance(audit["path"], str):
        errors.append(
            Issue(
                path="audit.path",
                code="audit_bad_type",
                message=f"'audit.path' must be a string, got {type(audit['path']).__name__}",
                severity="error",
            )
        )


def _validate_review_queue_section(
    rq: Any,
    errors: list[Issue],
    warnings: list[Issue],
) -> None:
    if rq is None:
        return
    if not isinstance(rq, dict):
        errors.append(
            Issue(
                path="review_queue",
                code="bad_top_level_type",
                message=f"'review_queue' must be a mapping, got {type(rq).__name__}",
                severity="error",
            )
        )
        return
    for key in rq:
        if key not in _ALLOWED_REVIEW_QUEUE_FIELDS:
            suggestion = _suggest(key, list(_ALLOWED_REVIEW_QUEUE_FIELDS))
            msg = f"Unknown field 'review_queue.{key}'"
            if suggestion:
                msg += f". Did you mean '{suggestion}'?"
            warnings.append(
                Issue(
                    path=f"review_queue.{key}",
                    code="unknown_review_queue_field",
                    message=msg,
                    severity="warning",
                )
            )
    if "enabled" in rq and not isinstance(rq["enabled"], bool):
        errors.append(
            Issue(
                path="review_queue.enabled",
                code="review_queue_bad_type",
                message=f"'review_queue.enabled' must be a bool, got {type(rq['enabled']).__name__}",
                severity="error",
            )
        )
    if "path" in rq and not isinstance(rq["path"], str):
        errors.append(
            Issue(
                path="review_queue.path",
                code="review_queue_bad_type",
                message=f"'review_queue.path' must be a string, got {type(rq['path']).__name__}",
                severity="error",
            )
        )


def _validate_policy_entry(
    entry: Any,
    section_prefix: str,
    idx: int,
    registry: dict[str, type],
    errors: list[Issue],
    warnings: list[Issue],
    policies_loaded: list[str],
) -> None:
    base_path = f"{section_prefix}[{idx}]"

    if not isinstance(entry, dict):
        errors.append(
            Issue(
                path=base_path,
                code="bad_top_level_type",
                message=f"Policy entry must be a mapping, got {type(entry).__name__}",
                severity="error",
            )
        )
        return

    raw_id = entry.get("id")
    if raw_id is None or not isinstance(raw_id, str):
        errors.append(
            Issue(
                path=base_path,
                code="missing_id",
                message=(
                    "Policy entry missing required 'id' field"
                    if raw_id is None
                    else f"'id' must be a string, got {type(raw_id).__name__}"
                ),
                severity="error",
            )
        )
        return  # Cannot proceed without a valid id.

    policy_id = raw_id
    id_path = f"{section_prefix}[{idx}].id"

    if policy_id not in registry:
        suggestion = _suggest(policy_id, list(registry.keys()))
        msg = f"Unknown policy id '{policy_id}'"
        if suggestion:
            msg += f". Did you mean '{suggestion}'?"
        errors.append(Issue(path=id_path, code="unknown_policy", message=msg, severity="error"))
        return  # Cannot validate fields without knowing the class.

    cls = registry[policy_id]
    has_error = False

    # Common field checks.
    if "severity" in entry:
        sev = entry["severity"]
        if not isinstance(sev, str):
            errors.append(
                Issue(
                    path=f"{base_path}.severity",
                    code="bad_severity",
                    message=f"'severity' must be a string, got {type(sev).__name__}",
                    severity="error",
                )
            )
            has_error = True
        elif sev not in ALLOWED_SEVERITIES:
            errors.append(
                Issue(
                    path=f"{base_path}.severity",
                    code="bad_severity",
                    message=f"Invalid severity '{sev}'. Allowed: {', '.join(ALLOWED_SEVERITIES)}",
                    severity="error",
                )
            )
            has_error = True

    if "on_fail" in entry:
        of = entry["on_fail"]
        if not isinstance(of, str):
            errors.append(
                Issue(
                    path=f"{base_path}.on_fail",
                    code="bad_on_fail",
                    message=f"'on_fail' must be a string, got {type(of).__name__}",
                    severity="error",
                )
            )
            has_error = True
        elif of not in ALLOWED_ON_FAIL:
            errors.append(
                Issue(
                    path=f"{base_path}.on_fail",
                    code="bad_on_fail",
                    message=f"Invalid on_fail '{of}'. Allowed: {', '.join(ALLOWED_ON_FAIL)}",
                    severity="error",
                )
            )
            has_error = True

    if "enabled" in entry:
        en = entry["enabled"]
        if not isinstance(en, bool):
            errors.append(
                Issue(
                    path=f"{base_path}.enabled",
                    code="bad_enabled",
                    message=f"'enabled' must be a bool, got {type(en).__name__}",
                    severity="error",
                )
            )
            has_error = True

    specific_fields = _get_specific_fields(cls)
    known_yaml_fields = _COMMON_POLICY_FIELDS | frozenset(specific_fields.keys())

    # Unknown field warnings.
    for key in entry:
        if key not in known_yaml_fields:
            suggestion = _suggest(key, list(known_yaml_fields))
            msg = f"Unknown field '{key}'"
            if suggestion:
                msg += f". Did you mean '{suggestion}'?"
            warnings.append(
                Issue(
                    path=f"{base_path}.{key}",
                    code="unknown_field",
                    message=msg,
                    severity="warning",
                )
            )

    # Type-check specific fields.
    for field_name, expected_type in specific_fields.items():
        if field_name in entry:
            value = entry[field_name]
            try:
                if not _check_type(value, expected_type):
                    errors.append(
                        Issue(
                            path=f"{base_path}.{field_name}",
                            code="type_mismatch",
                            message=(
                                f"Field '{field_name}' expected {_type_name(expected_type)}, "
                                f"got {type(value).__name__} ({value!r})"
                            ),
                            severity="error",
                        )
                    )
                    has_error = True
            except Exception:  # noqa: BLE001
                pass  # Degrade gracefully on exotic type annotations.

    if not has_error:
        policies_loaded.append(policy_id)


def _validate_policies(
    config: dict[str, Any],
    errors: list[Issue],
    warnings: list[Issue],
    policies_loaded: list[str],
) -> None:
    registry = iter_registered_policies()

    # Form 2: top-level "policies" key.
    if "policies" in config:
        entries = config["policies"]
        if not isinstance(entries, list):
            errors.append(
                Issue(
                    path="policies",
                    code="bad_top_level_type",
                    message=f"'policies' must be a list, got {type(entries).__name__}",
                    severity="error",
                )
            )
            return
        for i, entry in enumerate(entries):
            _validate_policy_entry(
                entry, "policies", i, registry, errors, warnings, policies_loaded
            )
        return

    # Form 1: per-domain keys.
    for domain in ("payment", "email"):
        if domain not in config:
            continue
        entries = config[domain]
        if not isinstance(entries, list):
            errors.append(
                Issue(
                    path=domain,
                    code="bad_top_level_type",
                    message=f"'{domain}' must be a list, got {type(entries).__name__}",
                    severity="error",
                )
            )
            continue
        if len(entries) == 0:
            warnings.append(
                Issue(
                    path=domain,
                    code="empty_domain",
                    message=f"Domain '{domain}' is empty. This is allowed but may be unintentional",
                    severity="warning",
                )
            )
            continue
        for i, entry in enumerate(entries):
            _validate_policy_entry(entry, domain, i, registry, errors, warnings, policies_loaded)


def _emit_post_warnings(
    config: dict[str, Any],
    policies_loaded: list[str],
    warnings: list[Issue],
) -> None:
    if not policies_loaded:
        warnings.append(
            Issue(
                path="(root)",
                code="no_policies",
                message=(
                    "No policies loaded. Add at least one policy under "
                    "'payment:', 'email:', or 'policies:'"
                ),
                severity="warning",
            )
        )

    # Default critical field warnings.
    entries_with_prefix: list[tuple[str, int, dict[str, Any]]] = []
    if "policies" in config and isinstance(config["policies"], list):
        for i, e in enumerate(config["policies"]):
            if isinstance(e, dict):
                entries_with_prefix.append(("policies", i, e))
    else:
        for domain in ("payment", "email"):
            if domain in config and isinstance(config[domain], list):
                for i, e in enumerate(config[domain]):
                    if isinstance(e, dict):
                        entries_with_prefix.append((domain, i, e))

    registry = iter_registered_policies()
    for section, idx, entry in entries_with_prefix:
        policy_id = entry.get("id")
        if not isinstance(policy_id, str) or policy_id not in _CRITICAL_FIELDS_BY_POLICY:
            continue
        critical_field = _CRITICAL_FIELDS_BY_POLICY[policy_id]
        if critical_field not in entry:
            cls = registry.get(policy_id)
            default_val = _get_field_default(cls, critical_field) if cls else dataclasses.MISSING
            default_str = f" {default_val}" if default_val is not dataclasses.MISSING else ""
            warnings.append(
                Issue(
                    path=f"{section}[{idx}]",
                    code="default_critical_field",
                    message=(
                        f"Critical field '{critical_field}' not set; "
                        f"using default{default_str}. "
                        f"Set it explicitly to silence this warning"
                    ),
                    severity="warning",
                )
            )


# ── Public API ─────────────────────────────────────────────────────────────────


def validate_config(path: str) -> ValidationReport:
    """Validate the ``gate.yaml`` file at ``path``.

    Raises:
        FileNotFoundError: if the file does not exist.
        OSError: on other I/O errors.
        ValueError: if the YAML cannot be parsed.
        ImportError: if PyYAML is not installed (with a helpful message).
    """
    try:
        import yaml  # noqa: PLC0415
    except ImportError as err:
        raise ImportError(
            "PyYAML required to validate YAML files. Install: pip install diplomat-gate[yaml]"
        ) from err

    with open(path) as f:
        try:
            config = yaml.safe_load(f)
        except yaml.YAMLError as err:
            raise ValueError(f"YAML parse error: {err}") from err

    if config is None:
        config = {}

    if not isinstance(config, dict):
        return ValidationReport(
            ok=False,
            errors=(
                Issue(
                    path="(root)",
                    code="bad_top_level_type",
                    message=f"Top-level must be a mapping, got {type(config).__name__}",
                    severity="error",
                ),
            ),
            warnings=(),
            policies_loaded=(),
            config_path=path,
        )

    errors: list[Issue] = []
    warnings: list[Issue] = []
    policies_loaded: list[str] = []

    _validate_audit_section(config.get("audit"), errors, warnings)
    _validate_review_queue_section(config.get("review_queue"), errors, warnings)
    _validate_policies(config, errors, warnings, policies_loaded)
    _emit_post_warnings(config, policies_loaded, warnings)

    errors_sorted = tuple(sorted(errors, key=lambda i: (i.path, i.code)))
    warnings_sorted = tuple(sorted(warnings, key=lambda i: (i.path, i.code)))
    return ValidationReport(
        ok=len(errors_sorted) == 0,
        errors=errors_sorted,
        warnings=warnings_sorted,
        policies_loaded=tuple(sorted(policies_loaded)),
        config_path=path,
    )


def report_to_dict(report: ValidationReport) -> dict[str, Any]:
    """Render a ValidationReport as a JSON-serialisable dict.

    Key order is stable: ok, format_version, config_path, policies_loaded,
    errors, warnings.
    """

    def issue_dict(i: Issue) -> dict[str, str]:
        return {"path": i.path, "code": i.code, "message": i.message, "severity": i.severity}

    return {
        "ok": report.ok,
        "format_version": report.format_version,
        "config_path": report.config_path,
        "policies_loaded": list(report.policies_loaded),
        "errors": [issue_dict(i) for i in report.errors],
        "warnings": [issue_dict(i) for i in report.warnings],
    }


def format_report_text(report: ValidationReport, *, use_color: bool) -> str:
    """Render a ValidationReport as human-readable text for stdout."""
    if use_color:
        green = "\x1b[32m"
        yellow = "\x1b[33m"
        red = "\x1b[31m"
        reset = "\x1b[0m"
    else:
        green = yellow = red = reset = ""

    n_pol = len(report.policies_loaded)
    n_err = len(report.errors)
    n_warn = len(report.warnings)

    if not report.ok:
        header = f"{red}INVALID{reset}: {n_pol} policies loaded, {n_err} errors, {n_warn} warnings"
    elif n_warn > 0:
        header = (
            f"{yellow}OK with warnings{reset}: {n_pol} policies loaded, 0 errors, {n_warn} warnings"
        )
    else:
        header = f"{green}OK{reset}: {n_pol} policies loaded, 0 errors, 0 warnings"

    lines = [header]
    for issue in report.errors:
        sev_col = f"{red}error{reset}  "
        lines.append(f"  {sev_col}  {issue.path:<40}  {issue.code:<24}  {issue.message}")
    for issue in report.warnings:
        sev_col = f"{yellow}warning{reset}"
        lines.append(f"  {sev_col}  {issue.path:<40}  {issue.code:<24}  {issue.message}")
    return "\n".join(lines)
